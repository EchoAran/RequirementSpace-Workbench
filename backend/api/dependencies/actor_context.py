import uuid
from fastapi import Depends, Request
from backend.api.dependencies.auth import get_optional_user
from backend.database.model import UserModel
from backend.core.actor_context import ActorContext, _current_actor_context


async def get_actor_context(
    request: Request = None,
    user: UserModel | None = Depends(get_optional_user),
):
    """FastAPI dependency to resolve the ActorContext from request state and authenticated user."""
    request_id = None
    if request is not None:
        request_id = getattr(request.state, "request_id", None)
        if not request_id:
            request_id = request.headers.get("X-Request-ID")
            if not request_id:
                request_id = str(uuid.uuid4())
            request.state.request_id = request_id

    if user:
        actor = ActorContext.user(user_id=user.id, request_id=request_id)
    else:
        actor = ActorContext.system(request_id=request_id)

    # Set the ContextVar for the duration of the request
    token = _current_actor_context.set(actor)
    try:
        yield actor
    finally:
        _current_actor_context.reset(token)
