class RichAgentError(Exception):
    """Base exception for the SDK."""


class ApprovalRequiredError(RichAgentError):
    """Raised when a tool requires approval and none is available."""


class PermissionDeniedError(RichAgentError):
    """Raised when a permission check denies the action."""


class GuardrailTrippedError(RichAgentError):
    """Raised when a guardrail blocks input, tool use, or output."""


class ToolExecutionError(RichAgentError):
    """Raised when a tool execution fails."""


class RunTimeoutError(RichAgentError):
    """Raised when a run exceeds its timeout."""
