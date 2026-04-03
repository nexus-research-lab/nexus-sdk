from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .base import ModelProvider


@dataclass
class ModelGateway:
    providers: Dict[str, ModelProvider] = field(default_factory=dict)
    routing_strategy: str = "cost_optimized"
    fallback_chain: List[str] = field(default_factory=list)

    def resolve(self, model_name: str) -> Optional[ModelProvider]:
        if "/" in model_name:
            provider_key = model_name.split("/", 1)[0]
            if provider_key in self.providers:
                return self.providers[provider_key]
        return self.providers.get(model_name)
