import logging

logger = logging.getLogger(__name__)

DEFAULT_FAILURE_THRESHOLD = 3


class FailureTracker:
    """Track consecutive failures per deployment and auto-pause at threshold."""

    def __init__(self, threshold: int = DEFAULT_FAILURE_THRESHOLD):
        self._threshold = threshold
        self._failures: dict[str, int] = {}
        self._paused: set[str] = set()

    def record_failure(self, deployment_id: str) -> bool:
        """Record a failure. Returns True if deployment should be auto-paused."""
        count = self._failures.get(deployment_id, 0) + 1
        self._failures[deployment_id] = count
        if count >= self._threshold:
            self._paused.add(deployment_id)
            logger.warning(f"Deployment {deployment_id} auto-paused after {count} consecutive failures")
            return True
        return False

    def record_success(self, deployment_id: str) -> None:
        """Reset failure counter on success."""
        self._failures.pop(deployment_id, None)

    def is_paused(self, deployment_id: str) -> bool:
        return deployment_id in self._paused

    def reset(self, deployment_id: str) -> None:
        self._failures.pop(deployment_id, None)
        self._paused.discard(deployment_id)

    @property
    def status(self) -> dict:
        return {
            "tracked": len(self._failures),
            "paused": list(self._paused),
        }
