from dataclasses import dataclass, field
from typing import Optional

from .quota import QuotaConfig


@dataclass
class TenantConfig:
    tenant_id: str
    session_namespace: Optional[str] = None
    data_residency: Optional[str] = None
    quota: QuotaConfig = field(default_factory=QuotaConfig)
