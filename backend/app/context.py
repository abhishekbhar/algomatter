"""Request-scoped context variables.

trace_id is set by RequestLoggingMiddleware for every HTTP request and passed
explicitly in ARQ job payloads so background tasks can restore the same ID,
giving end-to-end traceability across async task boundaries.
"""
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
