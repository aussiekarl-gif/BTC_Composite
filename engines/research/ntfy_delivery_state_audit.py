"""Pure research-only model of daily ntfy reservation and ambiguous delivery.

A network timeout after a POST does not establish whether ntfy accepted it.
Do not automatically retry an ambiguous attempt: this would break at-most-once.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class DeliveryState:
    day: str = ""
    status: str = "NONE"  # NONE, RESERVED, ACCEPTED, UNKNOWN
    attempt_id: str = ""

def reserve(state: DeliveryState, day: str, attempt_id: str) -> DeliveryState:
    if not day or not attempt_id:
        raise ValueError("Missing day or attempt ID")
    if state.day == day and state.status != "NONE":
        return state
    return DeliveryState(day, "RESERVED", attempt_id)

def acknowledge(state: DeliveryState, attempt_id: str, accepted: bool | None) -> DeliveryState:
    if state.status != "RESERVED" or state.attempt_id != attempt_id:
        raise ValueError("Unmatched or repeated delivery acknowledgement")
    # None means ambiguous transport failure; do not permit automatic re-send.
    return DeliveryState(state.day, "ACCEPTED" if accepted is True else "UNKNOWN", attempt_id)

def should_send(state: DeliveryState, day: str) -> bool:
    # New day only; a same-day reserved or unknown attempt must not re-send.
    return state.day != day or state.status == "NONE"
