class ModerationServiceError(Exception):
    """Base exception for moderation service errors."""
    pass

class LLMUnavailableError(ModerationServiceError):
    """Raised when the LLM provider fails to respond or returns an error."""
    pass
