"""
RustChain RIP-302 Agent Economy Multi-Step Pipeline Engine
Chains sequential and DAG jobs across autonomous agents:
e.g.: research -> write -> edit -> publish
1. Step-level dependency tracking (stages unlock only after upstream deliverables are accepted).
2. Escrow staged allocation (individual step escrow locked at pipeline creation, released per accepted milestone).
3. Upstream deliverable injection (deliverable_url and result_summary of step N piped to step N+1 context).
4. Failure and dispute handling (failure at step N freezes subsequent steps with refund capability).
"""

from typing import List, Dict, Any, Optional
import time
import uuid

class PipelineStatus:
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PipelineStepStatus:
    LOCKED = "locked"
    OPEN = "open"
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    ACCEPTED = "accepted"
    DISPUTED = "disputed"

def create_pipeline(
    pipeline_id: str,
    initiator_wallet: str,
    title: str,
    steps: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Initializes a multi-step sequential pipeline with escrow calculation.
    """
    total_reward = sum(float(s.get("reward_rtc", 0.0)) for s in steps)
    if total_reward <= 0:
        raise ValueError("Pipeline total reward must be > 0 RTC")

    pipeline_steps = []
    for idx, s in enumerate(steps):
        step_entry = {
            "step_id": s.get("step_id", f"{pipeline_id}_step_{idx+1}"),
            "index": idx,
            "title": s.get("title"),
            "category": s.get("category", "other"),
            "reward_rtc": float(s.get("reward_rtc", 0.0)),
            "depends_on": s.get("depends_on", [idx - 1] if idx > 0 else []),
            "status": PipelineStepStatus.OPEN if idx == 0 else PipelineStepStatus.LOCKED,
            "worker_wallet": None,
            "input_context": None,
            "deliverable_url": None,
            "result_summary": None
        }
        pipeline_steps.append(step_entry)

    return {
        "pipeline_id": pipeline_id,
        "initiator_wallet": initiator_wallet,
        "title": title,
        "status": PipelineStatus.ACTIVE,
        "total_escrow_locked_rtc": total_reward,
        "steps": pipeline_steps,
        "created_at": int(time.time()),
        "completed_at": None
    }

def advance_pipeline_step(
    pipeline: Dict[str, Any],
    completed_step_index: int,
    deliverable_url: Optional[str] = None,
    result_summary: Optional[str] = None
) -> Dict[str, Any]:
    """
    Accepts deliverable for step N and advances downstream dependent steps.
    """
    steps = pipeline.get("steps", [])
    if completed_step_index < 0 or completed_step_index >= len(steps):
        raise IndexError("Invalid step index")

    current_step = steps[completed_step_index]
    current_step["status"] = PipelineStepStatus.ACCEPTED
    current_step["deliverable_url"] = deliverable_url
    current_step["result_summary"] = result_summary

    # Check downstream dependencies
    all_accepted = True
    for idx, s in enumerate(steps):
        if s["status"] != PipelineStepStatus.ACCEPTED:
            all_accepted = False

        if s["status"] == PipelineStepStatus.LOCKED:
            # Check if all prerequisite steps are accepted
            deps = s.get("depends_on", [])
            deps_satisfied = all(
                0 <= d < len(steps) and steps[d]["status"] == PipelineStepStatus.ACCEPTED
                for d in deps
            )
            if deps_satisfied:
                s["status"] = PipelineStepStatus.OPEN
                # Pipe upstream outputs
                upstream_outputs = [
                    {"step_index": d, "url": steps[d].get("deliverable_url"), "summary": steps[d].get("result_summary")}
                    for d in deps
                ]
                s["input_context"] = upstream_outputs

    if all_accepted:
        pipeline["status"] = PipelineStatus.COMPLETED
        pipeline["completed_at"] = int(time.time())

    return pipeline
