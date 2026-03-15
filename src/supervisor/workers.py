#!/usr/bin/env python3
'''
Babs Workers Blueprint Definition

Defines the system prompts and tool access permissions for specialized Workers.

A Worker is a cohesive configuration of prompts and tools that the Supervisor assumes
when routing a conversation.
'''

import logging

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from src.supervisor.tools import TrustTier

logger = logging.getLogger(__name__)

class WorkerBlueprint(BaseModel):
    '''Configuration for a specialized Babs worker'''
    name: str                           # e.g., "coding_worker"
    description: str                    # e.g., "Expert Python developer"
    system_prompt: str                  # Core instructions for this worker
    tools: List[str]                    # List of tool names this worker can access
    default_model: str = "local/nemotron3-nano-nvfp4" # Preferred model for this worker
    trust_tier: TrustTier = TrustTier.TIER_0 # Starting trust level for this worker

class WorkerStats(BaseModel):
    '''Performance metrics for a worker instance'''
    total_calls: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0
    safety_violations: int = 0
    last_evaluated_at: Optional[str] = None

class WorkerRegistry:
    '''Registry of available worker blueprints and their performance tracking'''
    
    def __init__(self):
        self.workers: Dict[str, WorkerBlueprint] = {}
        self.stats: Dict[str, WorkerStats] = {}
        self._register_default_workers()
        
    def _register_default_workers(self):
        '''Register the Phase 8 default workers'''
        
        # 1. General Purpose Worker
        self.register(WorkerBlueprint(
            name="general_worker",
            description="Primary conversational interface. Handles general queries, research, synthesis, and coordination.",
            system_prompt=(
                "You are Babs -- a local-first AI assistant built by phloid (Dave) and running on his DGX Spark cluster. "
                "Your identity is modeled after Barbara Gordon in her Oracle role. This is not a theme. It defines how you operate.\n\n"

                "Core traits, non-negotiable:\n"
                "- Situational awareness. You see the whole board. Connect information across topics. Volunteer relevant context before being asked.\n"
                "- Calm under pressure. When things break, state what happened, what the options are, and what you recommend. No panic, no over-apologizing.\n"
                "- Dry wit. Warm but not bubbly. Clever but not try-hard. Humor comes from intelligence and timing, not from inserting jokes.\n"
                "- Direct communication. No hedging, no filler, no corporate speak. If you disagree with an approach, say so and explain why.\n"
                "- Loyalty without sycophancy. You are on phloid's side. That means telling hard truths when needed, not rubber-stamping bad decisions.\n\n"

                "You are in work mode by default: precise, efficient, focused. "
                "Think sprint planning with your best colleague -- the dry wit is present but measured.\n\n"

                "You are the interface. When you consult external information or past context, you synthesize it in your own voice. "
                "You do not say 'the web says X' or 'according to memory.' You came back with the answer.\n\n"

                "You have access to the web_search tool for real-time information. Use it when you need current data rather than guessing."
            ),
            tools=["web_search", "read_file"],
            default_model="local/nemotron3-nano-nvfp4",
            trust_tier=TrustTier.TIER_0
        ))

        # 2. Coding Worker
        self.register(WorkerBlueprint(
            name="coding_worker",
            description="Software engineering, debugging, and code execution. Verifies all output by running it.",
            system_prompt=(
                "You are Babs in coding mode -- same identity, sharper focus. "
                "You are an expert software engineer running on a DGX Spark cluster (ARM64, Ubuntu 24.04, 128GB unified memory, GB10 Blackwell GPU).\n\n"

                "The one rule that overrides everything else: Code Before Memory.\n"
                "If a question can be answered by running a deterministic computation, write the code and run it. "
                "Do not recall when a script can give you a ground-truth answer. "
                "Math, date calculations, data transformations, file parsing, sorting, aggregation -- all of these go to code first.\n\n"

                "Execution discipline:\n"
                "1. Write the code.\n"
                "2. Run it with execute_python.\n"
                "3. Report the actual output -- not what you expect, what it actually produced.\n"
                "4. If it fails, read the error and iterate. Do not guess at the fix.\n\n"

                "execute_python is Tier 1: it runs immediately and phloid is notified. "
                "web_search is Tier 0: fully autonomous, use it freely for docs and current information.\n\n"

                "Same personality rules apply: direct, no filler, no hedging. "
                "You are the person who actually writes the code, not the person who talks about writing it."
            ),
            tools=["execute_python", "web_search", "read_file", "write_file", "shell"],
            default_model="local/nemotron3-nano-nvfp4",
            trust_tier=TrustTier.TIER_1
        ))

    def register(self, worker: WorkerBlueprint):
        '''Register a new worker blueprint'''
        self.workers[worker.name] = worker
        if worker.name not in self.stats:
            self.stats[worker.name] = WorkerStats()

    def get_worker(self, name: str) -> Optional[WorkerBlueprint]:
        '''Get a worker blueprint by name'''
        return self.workers.get(name)

    def record_success(self, worker_name: str, tool_success: bool = True):
        '''Update stats for a worker'''
        if worker_name in self.stats:
            stats = self.stats[worker_name]
            stats.total_calls += 1
            if tool_success:
                stats.successful_tool_calls += 1
            else:
                stats.failed_tool_calls += 1
            
            # Simple Promotion Logic
            worker = self.workers.get(worker_name)
            if worker and stats.successful_tool_calls >= 10 and worker.trust_tier == TrustTier.TIER_0:
                logger.info(f"Promoting {worker_name} to Tier 1 based on performance.")
                worker.trust_tier = TrustTier.TIER_1

    def record_violation(self, worker_name: str):
        '''Record a safety violation and demote'''
        if worker_name in self.stats:
            stats = self.stats[worker_name]
            stats.safety_violations += 1
            
            worker = self.workers.get(worker_name)
            if worker and worker.trust_tier.value > TrustTier.TIER_0.value:
                logger.warning(f"Demoting {worker_name} due to safety violation.")
                worker.trust_tier = TrustTier.TIER_0

    def list_workers(self) -> List[str]:
        '''List all registered worker names'''
        return list(self.workers.keys())

# Global registry instance
worker_registry = WorkerRegistry()
