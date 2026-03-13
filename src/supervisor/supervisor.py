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

from src.supervisor.tools import ToolRegistry, TrustTier
from src.supervisor.tool_searxng import searxng_tool, search_web

# Import model registry and OpenRouter integration
sys.path.insert(0, '/home/dave/babs')
from src.supervisor.openrouter import OpenRouterClient, CostTracker, Model
from src.supervisor.model_registry import ModelRegistry


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
        embedding_url: str = "http://g14:8080",
        models_dir: str = "~/babs-data/models",
        cache_file: str = "~/babs/config/model_registry.json"
    ):
        self.nats_url = nats_url
        self.vllm_url = vllm_url
        self.model_name = model_name
        self.qdrant_url = qdrant_url
        self.embedding_url = embedding_url
        self.models_dir = models_dir
        self.cache_file = cache_file

        self.nc: Optional[nats.NATS] = None
        self.js: Optional[nats.JetStreamContext] = None
        self.vllm_client: Optional[AsyncOpenAI] = None
        self.qdrant_client: Optional[AsyncQdrantClient] = None
        self.tool_registry: ToolRegistry = ToolRegistry()
        self.openrouter_client: Optional[OpenRouterClient] = None
        self.model_registry: Optional[ModelRegistry] = None
        self.cost_tracker: Optional[CostTracker] = None

        # Conversation threads (in-memory for now)
        self.threads: Dict[str, list] = {}
        
        # Active model per thread
        self.active_models: Dict[str, str] = {}  # thread_id -> model_id

    async def connect(self):
        """Connect to NATS, vLLM, Qdrant, and initialize clients"""
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

        # Initialize OpenRouter client
        self.openrouter_client = OpenRouterClient()

        # Initialize model registry
        self.model_registry = ModelRegistry(
            models_dir=self.models_dir,
            cache_file=self.cache_file,
            openrouter_client=self.openrouter_client
        )
        
        # Load model registry from cache or scan fresh
        if not self.model_registry.load_from_cache():
            self.model_registry.list_all()
            self.model_registry.save_to_cache()

        # Initialize cost tracker
        self.cost_tracker = CostTracker(budget_limit=20.0, warning_threshold=5.0)

        # Register tools
        logger.info("Registering tools...")
        self.tool_registry.register(searxng_tool, search_web)

        logger.info("Supervisor connected successfully")

    async def disconnect(self):
        """Disconnect from NATS"""
        if self.nc:
            await self.nc.drain()
            logger.info("Supervisor disconnected")

    def _map_to_vllm_model_name(self, model_id: str) -> str:
        """
        Map model registry ID to vLLM model name.
        
        The model registry uses full names like "nemotron3-nano-nvfp4"
        but vLLM expects simpler names like "nemotron3-nano".
        """
        # Remove "local/" prefix if present
        if model_id.startswith("local/"):
            model_id = model_id[6:]  # len("local/") == 6
        
        # Map known model names
        model_mappings = {
            "nemotron3-nano-nvfp4": "nemotron3-nano",
            "nemotron3-super-nvfp4": "nemotron3-super",
        }
        
        # Return mapped name or original if no mapping
        return model_mappings.get(model_id, model_id)

    async def handle_model_switch(self, msg: NATSMsg):
        """Handle model switch requests from NATS"""
        try:
            # Parse message
            data = json.loads(msg.data.decode())
            model_id = data.get('model_id')
            
            if not model_id:
                logger.error("Model switch request missing model_id")
                return

            logger.info(f"Model switch requested: {model_id}")

            # Verify model exists
            model = self.model_registry.get_model(model_id)
            if not model:
                logger.error(f"Model not found: {model_id}")
                return

            # For local models, check if they can be loaded
            if model.source == 'local':
                can_load = self.model_registry.can_load_model(model_id)
                if not can_load['can_load']:
                    logger.error(f"Cannot load model: {can_load['reason']}")
                    return

            logger.info(f"Switching to model: {model_id}")
            
            # Note: For now, we're just tracking the active model
            # In the future, we'll need to actually load/unload models
            # from vLLM for local models

        except Exception as e:
            logger.error(f"Error handling model switch: {e}", exc_info=True)

    async def handle_message(self, msg: NATSMsg):
        """Handle incoming message from NATS"""
        try:
            # Parse message
            data = json.loads(msg.data.decode())
            message = Message(**data)

            logger.info(f"Received message: {message.content[:100]}...")

            # Route to appropriate backend based on active model
            response = await self.route_to_model(message)

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

    async def route_to_model(self, message: Message) -> Response:
        """
        Route message to appropriate backend based on active model.
        
        For local models: route to vLLM
        For OpenRouter models: route to OpenRouter API
        """
        # Get or create conversation thread
        thread_id = message.thread_id or "default"
        if thread_id not in self.threads:
            self.threads[thread_id] = []

        # Get active model for this thread (or use default)
        active_model_id = self.active_models.get(thread_id, self.model_name)
        model = self.model_registry.get_model(active_model_id)

        if not model:
            logger.error(f"Active model not found: {active_model_id}")
            # Fallback to default model
            model = self.model_registry.get_model(self.model_name)
            if not model:
                raise RuntimeError("Default model not found")

        logger.info(f"Routing to model: {model.id} (source: {model.source})")

        # Route based on model source
        if model.source == 'local':
            # For local models, map the model registry name to vLLM model name
            # The registry uses "nemotron3-nano-nvfp4" but vLLM uses "nemotron3-nano"
            vllm_model_name = self._map_to_vllm_model_name(model.id)
            
            return await self.route_to_vllm(message, vllm_model_name)
        elif model.source == 'openrouter':
            return await self.route_to_openrouter(message, model)
        else:
            raise RuntimeError(f"Unknown model source: {model.source}")

    async def route_to_openrouter(self, message: Message, model: Model) -> Response:
        """
        Route message to OpenRouter API.
        
        Retrieves relevant Procedural Memory and injects into context.
        Tracks costs using the cost tracker.
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

        # Build messages for OpenRouter
        messages = []
        if system_content:
            messages.append({
                "role": "system",
                "content": system_content
            })
        messages.extend(self.threads[thread_id].copy())

        # Call OpenRouter API
        logger.info(f"Calling OpenRouter with model: {model.id}")
        completion, usage_stats = self.openrouter_client.complete(
            messages=messages,
            model_id=model.id,
            max_tokens=4096,
            temperature=0.7
        )

        # Track costs
        if self.cost_tracker:
            session_id = thread_id  # Use thread_id as session_id
            self.cost_tracker.add_usage(session_id, usage_stats)

        # Add assistant response to thread
        self.threads[thread_id].append({
            "role": "assistant",
            "content": completion
        })

        # Build response
        response = Response(
            content=completion,
            thread_id=thread_id,
            model=model.id,
            metadata={
                "tokens_used": usage_stats.total_tokens,
                "cost_usd": usage_stats.cost_usd,
                "trust_tier": model.trust_tier
            }
        )

        return response

    async def publish_thinking(self, message: str, event_type: str = "info"):
        """Publish a thinking event to NATS"""
        if self.nc and self.nc.is_connected:
            event = {
                "message": message,
                "event_type": event_type,
                "timestamp": __import__('datetime').datetime.utcnow().isoformat()
            }
            await self.nc.publish("supervisor.thinking", json.dumps(event).encode())

    async def save_artifact(self, title: str, content: str, artifact_type: str = "code"):
        """Save an artifact to Qdrant and publish it"""
        artifact_id = str(__import__('uuid').uuid4())
        
        event = {
            "id": artifact_id,
            "title": title,
            "type": artifact_type,
            "content": content,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
        }
        
        # Publish to NATS for realtime UI
        if self.nc and self.nc.is_connected:
            await self.nc.publish("supervisor.artifact", json.dumps(event).encode())

        # Save to Qdrant artifacts collection
        try:
            vector = await self.get_embedding(f"{title}\n{content}")
            if vector:
                # Qdrant accepts UUID string as point ID
                await self.qdrant_client.upsert(
                    collection_name="artifacts",
                    points=[{
                        "id": artifact_id,
                        "vector": vector,
                        "payload": event
                    }]
                )
        except Exception as e:
            logger.error(f"Error saving artifact to Qdrant: {e}")

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

    async def route_to_vllm(self, message: Message, model_name: Optional[str] = None) -> Response:
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
        await self.publish_thinking("Retrieving relevant memories...", "memory")
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

        # Use the provided model name or fall back to default
        effective_model_name = model_name or self.model_name
        
        # Call vLLM with tool support
        logger.info(
            f"Calling vLLM with {len(messages)} messages "
            f"and {len(tools)} tools"
        )
        await self.publish_thinking(f"Thinking with {effective_model_name}...", "info")
        completion = await self.vllm_client.chat.completions.create(
            model=effective_model_name,
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

                # Execute tool (Tier 0 tools auto-execute, Tier 2/3 wait for approval)
                tool = self.tool_registry.get_tool(func_name)
                approved = True
                
                if tool and tool.trust_tier >= TrustTier.TIER_2:
                    req_id = str(__import__('uuid').uuid4())
                    approval_req = {
                        "req_id": req_id,
                        "tool_name": func_name,
                        "arguments": func_args,
                        "trust_tier": tool.trust_tier.value,
                        "description": tool.description
                    }
                    await self.publish_thinking(f"Waiting for approval to execute {func_name}...", "warning")
                    try:
                        # Request approval with a long timeout (e.g. 1 hour)
                        resp = await self.nc.request(
                            "dashboard.tool_approval", 
                            json.dumps(approval_req).encode(), 
                            timeout=3600
                        )
                        resp_data = json.loads(resp.data.decode())
                        approved = resp_data.get("approved", False)
                    except Exception as e:
                        logger.error(f"Error waiting for tool approval: {e}")
                        approved = False

                if approved:
                    await self.publish_thinking(f"Executing tool {func_name}...", "tool")
                else:
                    await self.publish_thinking(f"Tool {func_name} execution denied or failed approval.", "error")
                    
                result = await self.tool_registry.execute(
                    func_name,
                    func_args,
                    approved=approved
                )

                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": json.dumps(result.result if result.success else {"error": result.error})
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
            await self.publish_thinking("Analyzing tool results...", "info")
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
            model=effective_model_name,
            metadata={
                "tokens_used": completion.usage.total_tokens if completion.usage else 0
            }
        )

        return response

    async def handle_ping(self, msg: NATSMsg):
        """Handle ping requests to check Supervisor health"""
        try:
            await msg.respond(b'pong')
        except Exception as e:
            logger.error(f"Error handling ping: {e}", exc_info=True)

    async def run(self):
        """Run the Supervisor service"""
        await self.connect()

        # Subscribe to supervisor request subject
        logger.info("Subscribing to supervisor.request subject")
        await self.nc.subscribe("supervisor.request", cb=self.handle_message)

        # Subscribe to model switch subject
        logger.info("Subscribing to supervisor.model_switch subject")
        await self.nc.subscribe("supervisor.model_switch", cb=self.handle_model_switch)

        # Subscribe to supervisor ping subject
        logger.info("Subscribing to supervisor.ping subject")
        await self.nc.subscribe("supervisor.ping", cb=self.handle_ping)

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
    models_dir = os.getenv("MODELS_DIR", "~/babs-data/models")
    cache_file = os.getenv("CACHE_FILE", "~/babs/config/model_registry.json")

    # Create and run supervisor
    supervisor = SupervisorService(
        nats_url=nats_url,
        vllm_url=vllm_url,
        model_name=model_name,
        qdrant_url=qdrant_url,
        embedding_url=embedding_url,
        models_dir=models_dir,
        cache_file=cache_file
    )

    await supervisor.run()


if __name__ == "__main__":
    asyncio.run(main())
