#!/usr/bin/env python3
'''
Babs Reflection (Dreaming) System

Responsible for periodically consolidating conversation history into
Episodic and Procedural memory.
'''

import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ReflectionLoop:
    '''Background process for memory consolidation'''
    
    def __init__(self, supervisor):
        self.supervisor = supervisor
        self.interval_sec = 300 # Run every 5 minutes by default
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    def start(self):
        '''Start the reflection background task'''
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Reflection loop started.")
            
    def stop(self):
        '''Stop the reflection background task'''
        self._running = False
        if self._task:
            self._task.cancel()
            logger.info("Reflection loop stopped.")

    async def _run_loop(self):
        '''Internal loop for periodic reflection'''
        while self._running:
            try:
                # Wait for interval or idle trigger
                await asyncio.sleep(self.interval_sec)
                
                # Perform "dreaming" consolidation
                await self.dream()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reflection loop: {e}", exc_info=True)

    async def dream(self):
        '''Consolidate recent threads into memories'''
        logger.info("Starting dream cycle...")
        
        # Get threads that need consolidation
        # For now, we iterate over in-memory threads
        threads_to_process = list(self.supervisor.threads.keys())
        
        for thread_id in threads_to_process:
            if thread_id == "default": continue # Skip default for now
            
            history = self.supervisor.threads.get(thread_id, [])
            if len(history) < 4: continue # Too short to summarize
            
            await self.supervisor.publish_thinking(f"Dreaming about thread {thread_id}...", "memory")
            
            # 1. Summarize into Episodic Memory
            # We ask the model to summarize the interaction
            summary = await self.summarize_thread(history)
            
            # 2. Save to Qdrant Episodic Memory
            await self.save_episodic_memory(thread_id, summary)
            
            # 3. Identify potential Procedural Memory improvements
            # (e.g., "When phloid says X, usually means Y")
            # This is more advanced, for now we just do episodic.
            
            # Clear or mark thread as consolidated (limited in-memory management)
            # In a real system, we'd delete from active buffer
            # self.supervisor.threads[thread_id] = [] 
            
        logger.info("Dream cycle complete.")

    async def summarize_thread(self, history: List[Dict[str, Any]]) -> str:
        '''Use LLM to summarize a conversation thread'''
        prompt = "Summarize the following conversation for long-term memory. Focus on the core user request, the steps taken, and the final outcome:\n\n"
        for msg in history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            prompt += f"{role.upper()}: {content}\n"
            
        # Call vLLM directly via supervisor's client
        try:
            response = await self.supervisor.vllm_client.chat.completions.create(
                model=self.supervisor.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to summarize thread: {e}")
            return "Failed to generate summary."

    async def save_episodic_memory(self, thread_id: str, summary: str):
        '''Save summary to Qdrant episodic_memory collection'''
        try:
            vector = await self.supervisor.get_embedding(summary)
            if not vector: return
            
            point_id = str(__import__('uuid').uuid4())
            payload = {
                "thread_id": thread_id,
                "summary": summary,
                "timestamp": datetime.utcnow().isoformat(),
                "type": "episodic"
            }
            
            await self.supervisor.qdrant_client.upsert(
                collection_name="episodic_memory",
                points=[{
                    "id": point_id,
                    "vector": vector,
                    "payload": payload
                }]
            )
            logger.info(f"Saved episodic memory for thread {thread_id}")
            
        except Exception as e:
            logger.error(f"Error saving episodic memory: {e}")
