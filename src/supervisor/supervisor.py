#!/usr/bin/env python3
"""
Babs Supervisor Service

The Supervisor is the central orchestration layer for Project Babs.
It listens on the NATS pub/sub bus, routes requests to the vLLM inference engine,
and manages conversation context and memory retrieval.

This is the minimal viable Supervisor for Phase 7 bootstrap.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Optional, Dict, Any, List

import aiohttp
import nats
from nats.aio.msg import Msg as NATSMsg
from nats.errors import TimeoutError as NATSTimeoutError
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import ScoredPoint

from tools import ToolRegistry, TrustTier
from tool_searxng import searxng_tool, search_web


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Message(BaseModel):
    """Incoming message structure from NATS"""
    content: str
    thread_id: Optional[str] = None
    user_id: str = "phloid"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Response(BaseModel):
    """Response structure to NATS"""
    content: str
    thread_id: Optional[str] = None
    model: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SupervisorService:
    """
    The Supervisor service orchestrates AI interactions for Babs.

    Responsibilities:
    - Listen for messages on NATS bus
    - Route to vLLM inference engine
    - Manage conversation context
    - Coordinate with Workers (future)
    - Handle memory retrieval (future)
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        vllm_url: str = "http://localhost:8000/v1",
        model_name: str = "nemotron3-nano",
        qdrant_url: str = "http://localhost:6333",
        embedding_url: str = "http://g14:8080"
    ):
        self.nats_url = nats_url
        self.vllm_url = vllm_url
        self.model_name = model_name
        self.qdrant_url = qdrant_url
        self.embedding_url = embedding_url

        self.nc: Optional[nats.NATS] = None
        self.js: Optional[nats.JetStreamContext] = None
        self.vllm_client: Optional[AsyncOpenAI] = None
        self.qdrant_client: Optional[AsyncQdrantClient] = None
        self.tool_registry: ToolRegistry = ToolRegistry()

        # Conversation threads (in-memory for now)
        self.threads: Dict[str, list] = {}

    async def connect(self):
        """Connect to NATS, vLLM, and Qdrant"""
        logger.info(f"Connecting to NATS at {self.nats_url}")
        self.nc = await nats.connect(self.nats_url)
        self.js = self.nc.jetstream()

        logger.info(f"Connecting to vLLM at {self.vllm_url}")
        self.vllm_client = AsyncOpenAI(
            base_url=self.vllm_url,
            api_key="not-needed"
        )

        logger.info(f"Connecting to Qdrant at {self.qdrant_url}")
        self.qdrant_client = AsyncQdrantClient(url=self.qdrant_url)

        # Register tools
        logger.info("Registering tools...")
        self.tool_registry.register(searxng_tool, search_web)

        logger.info("Supervisor connected successfully")

    async def disconnect(self):
        """Disconnect from NATS"""
        if self.nc:
            await self.nc.drain()
            logger.info("Supervisor disconnected")

    async def handle_message(self, msg: NATSMsg):
        """Handle incoming message from NATS"""
        try:
            # Parse message
            data = json.loads(msg.data.decode())
            message = Message(**data)

            logger.info(f"Received message: {message.content[:100]}...")

            # Route to vLLM
            response = await self.route_to_vllm(message)

            # Send response
            response_data = response.model_dump_json()
            await msg.respond(response_data.encode())

            logger.info(f"Sent response: {response.content[:100]}...")

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            # Send error response
            error_response = Response(
                content=f"Error processing request: {str(e)}",
                thread_id=None,
                model=self.model_name,
                metadata={"error": True}
            )
            await msg.respond(error_response.model_dump_json().encode())

    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for text using G14 embedding service

        Args:
            text: Text to embed

        Returns:
            768-dimensional embedding vector
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.embedding_url}/embed",
                json={"inputs": text}
            ) as response:
                if response.status != 200:
                    logger.error(f"Embedding service error: {response.status}")
                    return []

                data = await response.json()
                # The response is a list of embeddings, we want the first one
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                return []

    async def retrieve_procedural_memory(
        self,
        query: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant Procedural Memory entries for a query

        Args:
            query: The user's query text
            limit: Maximum number of entries to retrieve

        Returns:
            List of relevant Procedural Memory entries
        """
        try:
            # Get embedding for query
            query_vector = await self.get_embedding(query)
            if not query_vector:
                logger.warning("Failed to get embedding for query")
                return []

            # Search Qdrant
            results = await self.qdrant_client.query_points(
                collection_name="procedural_memory",
                query=query_vector,
                limit=limit
            )

            # Extract and format results
            memories = []
            for point in results.points:
                payload = point.payload
                memories.append({
                    "id": payload.get("id"),
                    "domain": payload.get("domain"),
                    "content": payload.get("content"),
                    "score": point.score
                })
                logger.info(
                    f"Retrieved memory: {payload.get('id')} "
                    f"(score: {point.score:.3f})"
                )

            return memories

        except Exception as e:
            logger.error(f"Error retrieving Procedural Memory: {e}", exc_info=True)
            return []

    async def route_to_vllm(self, message: Message) -> Response:
        """
        Route message to vLLM inference engine

        Retrieves relevant Procedural Memory and injects into context.

        Future enhancements:
        - Episodic Memory retrieval
        - Reasoning effort control
        - Worker delegation
        """
        # Get or create conversation thread
        thread_id = message.thread_id or "default"
        if thread_id not in self.threads:
            self.threads[thread_id] = []

        # Retrieve relevant Procedural Memory
        procedural_memories = await self.retrieve_procedural_memory(
            message.content,
            limit=2
        )

        # Build system message with Procedural Memory context
        system_content = ""
        if procedural_memories:
            system_content = "# Relevant Procedural Memory\n\n"
            for mem in procedural_memories:
                system_content += f"## {mem['id']} (domain: {mem['domain']})\n\n"
                system_content += f"{mem['content']}\n\n"

        # Add user message to thread
        self.threads[thread_id].append({
            "role": "user",
            "content": message.content
        })

        # Build messages for vLLM
        messages = []
        if system_content:
            messages.append({
                "role": "system",
                "content": system_content
            })
        messages.extend(self.threads[thread_id].copy())

        # Get available tools for vLLM
        tools = self.tool_registry.get_tools_for_vllm()

        # Call vLLM with tool support
        logger.info(
            f"Calling vLLM with {len(messages)} messages "
            f"and {len(tools)} tools"
        )
        completion = await self.vllm_client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
            tools=tools if tools else None
        )

        # Extract response
        choice = completion.choices[0]
        assistant_message = choice.message

        # Check if model wants to call tools
        if assistant_message.tool_calls:
            logger.info(
                f"Model requested {len(assistant_message.tool_calls)} tool calls"
            )

            # Add assistant message with tool calls to thread
            self.threads[thread_id].append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in assistant_message.tool_calls
                ]
            })

            # Execute tool calls
            tool_results = []
            for tool_call in assistant_message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                # Execute tool (Tier 0 tools auto-execute)
                result = await self.tool_registry.execute(
                    func_name,
                    func_args,
                    approved=True  # TODO: Implement approval queue for Tier 2/3
                )

                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": json.dumps(result.result)
                })

                logger.info(
                    f"Tool {func_name} executed: "
                    f"{'success' if result.success else 'failed'}"
                )

            # Add tool results to thread
            self.threads[thread_id].extend(tool_results)

            # Call vLLM again with tool results
            messages_with_tools = []
            if system_content:
                messages_with_tools.append({
                    "role": "system",
                    "content": system_content
                })
            messages_with_tools.extend(self.threads[thread_id].copy())

            logger.info("Calling vLLM with tool results")
            completion = await self.vllm_client.chat.completions.create(
                model=self.model_name,
                messages=messages_with_tools,
                temperature=0.7,
                max_tokens=4096
            )

            assistant_message = completion.choices[0].message

        # Add final assistant response to thread
        self.threads[thread_id].append({
            "role": "assistant",
            "content": assistant_message.content
        })

        # Build response
        response = Response(
            content=assistant_message.content,
            thread_id=thread_id,
            model=self.model_name,
            metadata={
                "tokens_used": completion.usage.total_tokens if completion.usage else 0
            }
        )

        return response

    async def run(self):
        """Run the Supervisor service"""
        await self.connect()

        # Subscribe to supervisor request subject
        logger.info("Subscribing to supervisor.request subject")
        await self.nc.subscribe("supervisor.request", cb=self.handle_message)

        logger.info("Supervisor service running. Press Ctrl+C to exit.")

        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.disconnect()


async def main():
    """Main entry point"""
    # Configuration from environment variables
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    vllm_url = os.getenv("VLLM_URL", "http://localhost:8000/v1")
    model_name = os.getenv("MODEL_NAME", "nemotron3-nano")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    embedding_url = os.getenv("EMBEDDING_URL", "http://g14:8080")

    # Create and run supervisor
    supervisor = SupervisorService(
        nats_url=nats_url,
        vllm_url=vllm_url,
        model_name=model_name,
        qdrant_url=qdrant_url,
        embedding_url=embedding_url
    )

    await supervisor.run()


if __name__ == "__main__":
    asyncio.run(main())
