import pytest
from examples.agent_economy_autonomous_pipeline.pipeline_orchestrator import (
    AgentMockEnvironment,
    run_autonomous_pipeline
)

def test_full_autonomous_3_agent_pipeline():
    env = AgentMockEnvironment()
    run_autonomous_pipeline(env)

    # Assert final states
    assert env.balances["agent_a_monitor"] == 49.0
    assert env.balances["agent_b_researcher"] == 10.5
    assert env.balances["agent_c_engineer"] == 5.5

    assert len(env.jobs) == 2
    assert env.jobs["job_auto_0001"]["status"] == "completed"
    assert env.jobs["job_auto_0002"]["status"] == "completed"
    assert env.jobs["job_auto_0001"]["worker"] == "agent_b_researcher"
    assert env.jobs["job_auto_0002"]["worker"] == "agent_c_engineer"

def test_prevent_self_claiming():
    env = AgentMockEnvironment()
    job = env.post_job("agent_a_monitor", "Test", "code", 1.0, "Desc")
    with pytest.raises(ValueError, match="Poster cannot claim their own job"):
        env.claim_job(job["id"], "agent_a_monitor")
