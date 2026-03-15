"""RustChain Email Alert Service."""

from .alerts import (
    RustChainEmailAlerts,
    SMTPConfig,
    EventType,
    DigestMode,
    Subscriber,
    Event,
    SubscriberStore,
)

__all__ = [
    "RustChainEmailAlerts",
    "SMTPConfig",
    "EventType",
    "DigestMode",
    "Subscriber",
    "Event",
    "SubscriberStore",
]
