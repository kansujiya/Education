"""Event listeners — small async handlers that react to events on the bus."""

# Side-effect imports register the M-4 listeners.
from api.listeners import progress as _progress_listener  # noqa: F401
from api.listeners import spaced_rep as _sr_listener  # noqa: F401
from api.listeners.dispatcher import (
    REGISTRY,
    Listener,
    dispatch_event,
    register,
)

__all__ = ["REGISTRY", "Listener", "dispatch_event", "register"]
