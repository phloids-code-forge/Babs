"""
OpenRouter API Integration
Provides access to all OpenRouter models for Babs.
"""

import os
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


@dataclass
class Model:
    """Unified model representation for local and OpenRouter models."""
    id: str
    name: str
    source: str  # "local" or "openrouter"
    size_gb: Optional[float] = None
    context_window: int = 4096
    capabilities: List[str] = None
    quantization: Optional[str] = None
    memory_footprint_gb: Optional[float] = None
    cost_per_1m_input: Optional[float] = None
    cost_per_1m_output: Optional[float] = None
    status: str = "available"
    trust_tier: int = 3  # Default to untrusted for remote models

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


@dataclass
class UsageStats:
    """Token usage and cost for a completion."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    model_id: str


class OpenRouterClient:
    """Client for OpenRouter API (OpenAI-compatible)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set. OpenRouter integration disabled.")
            self.client = None
        else:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

        self._model_cache: Optional[List[Model]] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: int = 86400  # 24 hours

    def get_models(self, force_refresh: bool = False) -> List[Model]:
        """
        Fetch available models from OpenRouter.
        Results are cached for 24 hours.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            List of Model objects from OpenRouter
        """
        if not self.client:
            logger.warning("OpenRouter client not initialized")
            return []

        # Check cache
        if not force_refresh and self._model_cache:
            age = time.time() - self._cache_timestamp
            if age < self._cache_ttl:
                logger.debug(f"Using cached OpenRouter models (age: {age:.0f}s)")
                return self._model_cache

        try:
            logger.info("Fetching models from OpenRouter API")
            response = self.client.models.list()

            models = []
            for model_data in response.data:
                # Parse OpenRouter model metadata
                model_id = model_data.id
                pricing = getattr(model_data, 'pricing', {})

                # Extract costs (OpenRouter provides per-token, convert to per-1M)
                cost_input = None
                cost_output = None
                if pricing:
                    # Pricing is in dollars per token, multiply by 1M
                    cost_input = float(pricing.get('prompt', 0)) * 1_000_000
                    cost_output = float(pricing.get('completion', 0)) * 1_000_000

                # Extract context window
                context_window = getattr(model_data, 'context_length', 4096)

                # Map model to capabilities (heuristic based on name)
                capabilities = []
                model_lower = model_id.lower()
                if any(x in model_lower for x in ['claude', 'gpt-4', 'gemini-1.5', 'o1', 'deepseek-v3']):
                    capabilities.append('reasoning')
                if any(x in model_lower for x in ['code', 'coder', 'deepseek', 'qwen']):
                    capabilities.append('coding')
                if any(x in model_lower for x in ['vision', 'gpt-4', 'claude-3', 'gemini']):
                    capabilities.append('vision')

                model = Model(
                    id=f"openrouter/{model_id}",
                    name=model_id.replace('/', ' / '),  # Format for display
                    source="openrouter",
                    context_window=context_window,
                    capabilities=capabilities,
                    cost_per_1m_input=cost_input,
                    cost_per_1m_output=cost_output,
                    status="available",
                    trust_tier=3  # Remote models are always untrusted
                )
                models.append(model)

            # Update cache
            self._model_cache = models
            self._cache_timestamp = time.time()

            logger.info(f"Fetched {len(models)} models from OpenRouter")
            return models

        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter models: {e}")
            # Return cached models if available
            if self._model_cache:
                logger.warning("Returning stale cached models due to API error")
                return self._model_cache
            return []

    def complete(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Tuple[str, UsageStats]:
        """
        Generate a completion using an OpenRouter model.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model_id: OpenRouter model ID (with or without 'openrouter/' prefix)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters for the API

        Returns:
            Tuple of (completion text, usage stats)
        """
        if not self.client:
            raise RuntimeError("OpenRouter client not initialized (missing API key)")

        # Strip 'openrouter/' prefix if present
        if model_id.startswith("openrouter/"):
            model_id = model_id[11:]  # len("openrouter/") == 11

        try:
            logger.info(f"Requesting completion from OpenRouter: {model_id}")

            response = self.client.chat.completions.create(
                model=model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )

            # Extract completion
            completion = response.choices[0].message.content

            # Extract usage
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens

            # Calculate cost
            cost_usd = self._calculate_cost(
                model_id=f"openrouter/{model_id}",
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            stats = UsageStats(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                model_id=f"openrouter/{model_id}"
            )

            logger.info(f"OpenRouter completion: {output_tokens} tokens, ${cost_usd:.4f}")

            return completion, stats

        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            raise

    def _calculate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate USD cost for a completion.

        Args:
            model_id: Full model ID (e.g., "openrouter/anthropic/claude-3.5-sonnet")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        # Find model in cache
        if not self._model_cache:
            logger.warning("Model cache not populated, cost calculation may be inaccurate")
            return 0.0

        model = next((m for m in self._model_cache if m.id == model_id), None)
        if not model:
            logger.warning(f"Model {model_id} not found in cache, cost calculation unavailable")
            return 0.0

        if model.cost_per_1m_input is None or model.cost_per_1m_output is None:
            logger.warning(f"Pricing not available for {model_id}")
            return 0.0

        # Convert per-1M pricing to per-token
        input_cost = (input_tokens / 1_000_000) * model.cost_per_1m_input
        output_cost = (output_tokens / 1_000_000) * model.cost_per_1m_output

        return input_cost + output_cost


class CostTracker:
    """Track costs per session and enforce budget limits."""

    def __init__(self, budget_limit: float = 20.0, warning_threshold: float = 5.0):
        self.budget_limit = budget_limit
        self.warning_threshold = warning_threshold
        self.session_costs: Dict[str, List[UsageStats]] = {}

    def add_usage(self, session_id: str, usage: UsageStats) -> Dict[str, any]:
        """
        Add a usage record to a session.

        Args:
            session_id: Session/thread ID
            usage: UsageStats from a completion

        Returns:
            Dict with session totals and warnings
        """
        if session_id not in self.session_costs:
            self.session_costs[session_id] = []

        self.session_costs[session_id].append(usage)

        # Calculate totals
        total_cost = sum(u.cost_usd for u in self.session_costs[session_id])
        total_input_tokens = sum(u.input_tokens for u in self.session_costs[session_id])
        total_output_tokens = sum(u.output_tokens for u in self.session_costs[session_id])

        # Check thresholds
        warnings = []
        if total_cost >= self.budget_limit:
            warnings.append(f"BUDGET_LIMIT_EXCEEDED")
            logger.warning(f"Session {session_id} exceeded budget limit: ${total_cost:.2f}")
        elif total_cost >= self.warning_threshold:
            warnings.append(f"BUDGET_WARNING")
            logger.info(f"Session {session_id} approaching budget limit: ${total_cost:.2f}")

        return {
            "session_id": session_id,
            "total_cost_usd": total_cost,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "budget_limit_usd": self.budget_limit,
            "budget_remaining_usd": max(0, self.budget_limit - total_cost),
            "warnings": warnings,
            "breakdown": [asdict(u) for u in self.session_costs[session_id]]
        }

    def get_session_cost(self, session_id: str) -> Dict[str, any]:
        """Get cost summary for a session."""
        if session_id not in self.session_costs:
            return {
                "session_id": session_id,
                "total_cost_usd": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "budget_limit_usd": self.budget_limit,
                "budget_remaining_usd": self.budget_limit,
                "warnings": [],
                "breakdown": []
            }

        total_cost = sum(u.cost_usd for u in self.session_costs[session_id])
        total_input_tokens = sum(u.input_tokens for u in self.session_costs[session_id])
        total_output_tokens = sum(u.output_tokens for u in self.session_costs[session_id])

        return {
            "session_id": session_id,
            "total_cost_usd": total_cost,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "budget_limit_usd": self.budget_limit,
            "budget_remaining_usd": max(0, self.budget_limit - total_cost),
            "warnings": [],
            "breakdown": [asdict(u) for u in self.session_costs[session_id]]
        }
