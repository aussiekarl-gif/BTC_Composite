"""Classify GitHub daily ntfy job evidence without claiming phone delivery.

Read-only; no GitHub mutation, no ntfy POST, no portfolio access.
"""
from __future__ import annotations

def classify_delivery_run(job_steps, marker_day, target_day):
    statuses = {step.get("name"): (step.get("conclusion"), step.get("status"))
                for step in job_steps}
    send = statuses.get("Send only one ntfy Cycle Trading message")
    reserve = statuses.get("Reserve Brisbane delivery date BEFORE sending")
    precheck = statuses.get("Skip expensive preparation if today's message is already reserved")
    if send and send[0] == "success":
        outcome = "POST_STEP_SUCCEEDED_NOT_DEVICE_DELIVERY"
    elif send and send[0] == "failure":
        outcome = "POST_STEP_FAILED_ACCEPTANCE_UNKNOWN"
    elif reserve and reserve[0] == "failure":
        outcome = "RESERVATION_FAILED_NO_SEND_CONFIRMED"
    elif precheck and precheck[0] == "success" and send and send[0] == "skipped":
        outcome = "SKIPPED_POSSIBLY_ALREADY_RESERVED"
    else:
        outcome = "UNKNOWN_NO_SEND_EVIDENCE"
    return {
        "target_day": target_day,
        "marker_matches_day": marker_day == target_day,
        "send_step": send[0] if send else "absent",
        "outcome": outcome,
        "confirmed_device_delivery": False,
    }
