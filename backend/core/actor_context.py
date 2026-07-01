from contextvars import ContextVar
from dataclasses import dataclass
from typing import Generator
import contextlib


@dataclass
class ActorContext:
    actor_type: str  # "user" | "ai" | "system" | "migration"
    user_id: int | None = None
    request_id: str | None = None
    source: str = ""

    @classmethod
    def system(cls, request_id: str | None = None) -> "ActorContext":
        return cls(actor_type="system", request_id=request_id, source="system_task")

    @classmethod
    def migration(cls) -> "ActorContext":
        return cls(actor_type="migration", source="migration")

    @classmethod
    def user(cls, user_id: int, request_id: str | None = None) -> "ActorContext":
        return cls(actor_type="user", user_id=user_id, request_id=request_id, source="api_request")

    @classmethod
    def ai(cls, user_id: int, request_id: str | None = None, source: str = "ai_generation") -> "ActorContext":
        return cls(actor_type="ai", user_id=user_id, request_id=request_id, source=source)


# ContextVar to store the current actor context
_current_actor_context: ContextVar[ActorContext] = ContextVar(
    "current_actor_context", default=ActorContext.system()
)


def get_current_actor() -> ActorContext:
    """Get the current actor context from the context variables, defaulting to system."""
    return _current_actor_context.get()


@contextlib.contextmanager
def set_actor(actor: ActorContext) -> Generator[None, None, None]:
    """Context manager to temporarily set the current actor context."""
    token = _current_actor_context.set(actor)
    try:
        yield
    finally:
        _current_actor_context.reset(token)
