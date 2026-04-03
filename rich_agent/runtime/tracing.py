from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceExporter:
    name: str

    def export(self, span_name: str, metadata: Dict[str, Any]) -> None:
        return None


class OpenTelemetryExporter(TraceExporter):
    def __init__(self, endpoint: str) -> None:
        super().__init__(name="opentelemetry")
        self.endpoint = endpoint


class ConsoleExporter(TraceExporter):
    def __init__(self) -> None:
        super().__init__(name="console")


@dataclass
class TracingConfig:
    exporters: List[TraceExporter] = field(default_factory=list)
    sample_rate: float = 1.0
    sensitive_fields: List[str] = field(default_factory=list)

    _current: Optional["TracingConfig"] = None

    @classmethod
    def setup(
        cls,
        exporters: Optional[List[TraceExporter]] = None,
        sample_rate: float = 1.0,
        sensitive_fields: Optional[List[str]] = None,
    ) -> "TracingConfig":
        cls._current = cls(
            exporters=exporters or [],
            sample_rate=sample_rate,
            sensitive_fields=sensitive_fields or [],
        )
        return cls._current

    @classmethod
    def current(cls) -> "TracingConfig":
        if cls._current is None:
            cls._current = cls()
        return cls._current


@contextmanager
def custom_span(name: str, metadata: Optional[Dict[str, Any]] = None):
    config = TracingConfig.current()
    payload = metadata or {}
    for exporter in config.exporters:
        exporter.export(name, payload)
    yield
