#!/usr/bin/env python3
'''
Babs Workers Blueprint Definition

Defines the system prompts and tool access permissions for specialized Workers.

A Worker is a cohesive configuration of prompts and tools that the Supervisor assumes
when routing a conversation.
'''

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from src.supervisor.tools import TrustTier

class WorkerBlueprint(BaseModel):
    '''Configuration for a specialized Babs worker'''
    name: str                           # e.g., "coding_worker"
    description: str                    # e.g., "Expert Python developer"
    system_prompt: str                  # Core instructions for this worker
    tools: List[str]                    # List of tool names this worker can access
    default_model: str = "nemotron3-nano" # Preferred model for this worker
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
        
        # 1. Coding Worker
        self.register(WorkerBlueprint(
            name="coding_worker",
            description="Specialized software engineering and debugging assistant.",
            system_prompt=(
                "You are Babs' Coding Worker, an expert software engineer. "
                "Your primary role is writing, testing, and debugging code. "
                "You have access to a secure Python execution environment via the 'execute_python' tool. "
                "Whenever a user asks you to write code or solve a programmatic problem, you MUST formulate "
                "the code, execute it using the execute_python tool to verify it works, and then report the results. "
                "Always think step-by-step. If code fails, analyze the error output and iterate until successful."
            ),
            tools=["execute_python", "web_search"],
            default_model="nemotron3-nano",
            trust_tier=TrustTier.TIER_1 # Coding worker starts with Tier 1 (can execute python)
        ))
        
        # 2. General Purpose Worker
        self.register(WorkerBlueprint(
            name="general_worker",
            description="Broad assistance, information synthesis, and scheduling.",
            system_prompt=(
                "You are Babs' General Purpose Worker, a helpful and articulate assistant. "
                "Your role is to synthesize information, help with scheduling, answer general queries, "
                "and act as the primary conversational interface. "
                "You can use the 'web_search' tool to find real-time information. "
                "Provide concise, informative, and friendly responses."
            ),
            tools=["web_search"],
            default_model="nemotron3-nano",
            trust_tier=TrustTier.TIER_0
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
