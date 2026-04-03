from dataclasses import dataclass
from typing import Optional


@dataclass
class QuotaConfig:
    daily_tokens: Optional[int] = None
    monthly_budget_usd: Optional[float] = None
    concurrent_runs: Optional[int] = None
