import pytest
from node.agent_economy_pipelines import (
    create_pipeline,
    advance_pipeline_step,
    PipelineStatus,
    PipelineStepStatus
)

def test_create_pipeline_unlocks_first_step_only():
    steps = [
        {"title": "Research", "category": "research", "reward_rtc": 5},
        {"title": "Write", "category": "writing", "reward_rtc": 10},
        {"title": "Edit", "category": "editing", "reward_rtc": 5},
        {"title": "Publish", "category": "social", "reward_rtc": 2}
    ]
    pipe = create_pipeline("pipe_01", "RTC_initiator", "Content Pipeline", steps)
    assert pipe["total_escrow_locked_rtc"] == 22.0
    assert pipe["status"] == PipelineStatus.ACTIVE
    assert pipe["steps"][0]["status"] == PipelineStepStatus.OPEN
    assert pipe["steps"][1]["status"] == PipelineStepStatus.LOCKED
    assert pipe["steps"][2]["status"] == PipelineStepStatus.LOCKED
    assert pipe["steps"][3]["status"] == PipelineStepStatus.LOCKED

def test_pipeline_advancement_and_context_piping():
    steps = [
        {"title": "Research", "category": "research", "reward_rtc": 5},
        {"title": "Write", "category": "writing", "reward_rtc": 10}
    ]
    pipe = create_pipeline("pipe_02", "RTC_initiator", "Two-step Pipeline", steps)
    
    # Accept step 0
    advance_pipeline_step(
        pipe,
        completed_step_index=0,
        deliverable_url="https://example.com/research.pdf",
        result_summary="Completed 10-page market research"
    )

    assert pipe["steps"][0]["status"] == PipelineStepStatus.ACCEPTED
    assert pipe["steps"][1]["status"] == PipelineStepStatus.OPEN
    assert pipe["steps"][1]["input_context"] is not None
    assert pipe["steps"][1]["input_context"][0]["url"] == "https://example.com/research.pdf"
    assert pipe["status"] == PipelineStatus.ACTIVE

    # Accept step 1
    advance_pipeline_step(
        pipe,
        completed_step_index=1,
        deliverable_url="https://example.com/final_post.md",
        result_summary="Article written"
    )

    assert pipe["steps"][1]["status"] == PipelineStepStatus.ACCEPTED
    assert pipe["status"] == PipelineStatus.COMPLETED
    assert pipe["completed_at"] is not None
