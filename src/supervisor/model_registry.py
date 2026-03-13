"""
Model Registry
Unified catalog of local and OpenRouter models.
Scans local storage and merges with OpenRouter catalog.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import asdict

from src.supervisor.openrouter import OpenRouterClient, Model

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Central registry for all available models (local + OpenRouter)."""

    def __init__(
        self,
        models_dir: str = "~/babs-data/models",
        cache_file: str = "~/babs/config/model_registry.json",
        openrouter_client: Optional[OpenRouterClient] = None
    ):
        self.models_dir = Path(models_dir).expanduser()
        self.cache_file = Path(cache_file).expanduser()
        self.openrouter_client = openrouter_client or OpenRouterClient()

        # Ensure cache directory exists
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        self._local_models: List[Model] = []
        self._openrouter_models: List[Model] = []

    def scan_local_models(self) -> List[Model]:
        """
        Scan local storage for downloaded models.
        Looks for directories with config.json files.

        Returns:
            List of local Model objects
        """
        models = []

        if not self.models_dir.exists():
            logger.warning(f"Models directory does not exist: {self.models_dir}")
            return models

        logger.info(f"Scanning local models in {self.models_dir}")

        for model_dir in self.models_dir.iterdir():
            if not model_dir.is_dir():
                continue

            # Look for config.json
            config_path = model_dir / "config.json"
            if not config_path.exists():
                logger.debug(f"Skipping {model_dir.name} (no config.json)")
                continue

            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)

                # Extract model metadata
                model_id = f"local/{model_dir.name}"
                model_name = config.get("model_type", model_dir.name)

                # Extract architecture info
                architectures = config.get("architectures", [])
                if architectures:
                    model_name = architectures[0]

                # Extract context window
                max_position_embeddings = config.get("max_position_embeddings", 4096)

                # Extract quantization info
                quant_method = config.get("quant_method", None)
                if not quant_method and "quantization_config" in config:
                    quant_method = config["quantization_config"].get("quant_method", "unknown")

                # Calculate model size on disk
                size_gb = self._calculate_directory_size(model_dir)

                # Estimate memory footprint (rough heuristic: 1.3x disk size for NVFP4, 1.5x for FP8)
                memory_multiplier = 1.3 if quant_method == "modelopt" else 1.5
                memory_footprint = size_gb * memory_multiplier

                # Infer capabilities from model name
                capabilities = []
                name_lower = model_dir.name.lower()
                if any(x in name_lower for x in ['nemotron', 'llama', 'qwen', 'deepseek', 'mixtral']):
                    capabilities.extend(['reasoning', 'coding'])
                if 'vision' in name_lower or 'vlm' in name_lower:
                    capabilities.append('vision')

                # Determine status (assume loaded if currently running)
                status = self._check_model_status(model_dir.name)

                model = Model(
                    id=model_id,
                    name=model_dir.name,
                    source="local",
                    size_gb=round(size_gb, 1),
                    context_window=max_position_embeddings,
                    capabilities=capabilities,
                    quantization=quant_method,
                    memory_footprint_gb=round(memory_footprint, 1),
                    cost_per_1m_input=None,
                    cost_per_1m_output=None,
                    status=status,
                    trust_tier=0  # Local models are fully trusted
                )

                models.append(model)
                logger.info(f"Found local model: {model_id} ({size_gb:.1f}GB)")

            except Exception as e:
                logger.error(f"Failed to parse config for {model_dir.name}: {e}")
                continue

        self._local_models = models
        return models

    def _calculate_directory_size(self, directory: Path) -> float:
        """
        Calculate total size of a directory in GB.

        Args:
            directory: Path to directory

        Returns:
            Size in GB
        """
        total_bytes = 0
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_bytes += file_path.stat().st_size

        return total_bytes / (1024 ** 3)  # Convert bytes to GB

    def _check_model_status(self, model_name: str) -> str:
        """
        Check if a model is currently loaded in vLLM.

        Args:
            model_name: Model directory name

        Returns:
            "loaded", "available", or "error"
        """
        # TODO: Query vLLM /v1/models endpoint to check if loaded
        # For now, assume models are available but not loaded
        # Exception: if model_name matches the currently running model, mark as loaded

        # Check if this is the Nano model that's currently running
        if "nano" in model_name.lower():
            return "loaded"

        return "available"

    def fetch_openrouter_models(self, force_refresh: bool = False) -> List[Model]:
        """
        Fetch models from OpenRouter.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            List of OpenRouter Model objects
        """
        models = self.openrouter_client.get_models(force_refresh=force_refresh)
        self._openrouter_models = models
        logger.info(f"Fetched {len(models)} models from OpenRouter")
        return models

    def list_all(self, refresh_openrouter: bool = False) -> Dict[str, List[Model]]:
        """
        Get all models (local + OpenRouter).

        Args:
            refresh_openrouter: Force refresh of OpenRouter catalog

        Returns:
            Dict with "local" and "openrouter" keys containing model lists
        """
        local = self.scan_local_models()
        openrouter = self.fetch_openrouter_models(force_refresh=refresh_openrouter)

        return {
            "local": local,
            "openrouter": openrouter
        }

    def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a specific model by ID.

        Args:
            model_id: Full model ID (e.g., "local/nemotron3-nano" or "openrouter/anthropic/claude-3.5")

        Returns:
            Model object or None if not found
        """
        # Search local models
        for model in self._local_models:
            if model.id == model_id:
                return model

        # Search OpenRouter models
        for model in self._openrouter_models:
            if model.id == model_id:
                return model

        logger.warning(f"Model not found: {model_id}")
        return None

    def save_to_cache(self):
        """Save current registry state to disk cache."""
        data = {
            "local": [asdict(m) for m in self._local_models],
            "openrouter": [asdict(m) for m in self._openrouter_models]
        }

        try:
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved model registry to {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to save model registry: {e}")

    def load_from_cache(self) -> bool:
        """
        Load registry from disk cache.

        Returns:
            True if cache loaded successfully, False otherwise
        """
        if not self.cache_file.exists():
            logger.debug("No cache file found")
            return False

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)

            # Reconstruct Model objects
            self._local_models = [
                Model(**m) for m in data.get("local", [])
            ]
            self._openrouter_models = [
                Model(**m) for m in data.get("openrouter", [])
            ]

            logger.info(f"Loaded model registry from cache: {len(self._local_models)} local, {len(self._openrouter_models)} OpenRouter")
            return True

        except Exception as e:
            logger.error(f"Failed to load model registry cache: {e}")
            return False

    def get_memory_usage_summary(self) -> Dict[str, float]:
        """
        Calculate current and potential memory usage.

        Returns:
            Dict with memory stats in GB
        """
        loaded_models = [m for m in self._local_models if m.status == "loaded"]
        available_models = [m for m in self._local_models if m.status == "available"]

        current_usage = sum(m.memory_footprint_gb or 0 for m in loaded_models)
        available_capacity = sum(m.memory_footprint_gb or 0 for m in available_models)

        # Spark has 128GB total, 115GB ceiling for models
        total_capacity = 115.0
        system_overhead = 13.0  # OS, Docker, services

        return {
            "total_capacity_gb": total_capacity,
            "system_overhead_gb": system_overhead,
            "current_usage_gb": round(current_usage, 1),
            "available_capacity_gb": round(available_capacity, 1),
            "free_gb": round(total_capacity - current_usage, 1),
            "loaded_models": len(loaded_models),
            "available_models": len(available_models)
        }

    def can_load_model(self, model_id: str) -> Dict[str, any]:
        """
        Check if a model can be loaded without exceeding memory limits.

        Args:
            model_id: Model ID to check

        Returns:
            Dict with can_load (bool) and reason (str)
        """
        model = self.get_model(model_id)
        if not model:
            return {"can_load": False, "reason": "Model not found"}

        if model.source != "local":
            return {"can_load": True, "reason": "Remote model (no memory constraint)"}

        if not model.memory_footprint_gb:
            return {"can_load": False, "reason": "Memory footprint unknown"}

        memory_summary = self.get_memory_usage_summary()
        free_memory = memory_summary["free_gb"]

        if model.memory_footprint_gb > free_memory:
            return {
                "can_load": False,
                "reason": f"Insufficient memory: need {model.memory_footprint_gb:.1f}GB, have {free_memory:.1f}GB free"
            }

        return {
            "can_load": True,
            "reason": f"Sufficient memory: {free_memory:.1f}GB free"
        }
