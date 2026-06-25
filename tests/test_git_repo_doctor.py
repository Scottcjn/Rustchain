from __future__ import annotations

from pathlib import Path

from scripts import git_repo_doctor as doctor


def test_classifies_truncated_packfile() -> None:
    text = (
        "error: file .git/objects/pack/pack-9aa52800bc0d6c309d3179290b3575503e8b7a7f.pack "
        "is far too short to be a packfile"
    )
    assert doctor.classify_git_output(text) == "git_packfile_truncated"


def test_classifies_object_database_corruption() -> None:
    assert doctor.classify_git_output("fatal: bad object HEAD") == "git_object_database_corruption"


def test_probe_repo_flags_pack_corruption(monkeypatch) -> None:
    def fake_run_git(repo_path: Path, args: list[str], timeout: float) -> dict[str, object]:
        return {
            "args": args,
            "returncode": 128,
            "stdout_tail": "",
            "stderr_tail": "error: packfile pack-abcd.pack is far too short to be a packfile",
            "timed_out": False,
            "duration_seconds": 0.01,
        }

    monkeypatch.setattr(doctor, "run_git", fake_run_git)
    report = doctor.probe_repo(Path("/tmp/repo"))

    assert report["ok"] is False
    assert report["failure_detected"] is True
    assert report["failure_class"] == "git_packfile_truncated"
    assert report["corruption_detected"] is True
    assert report["corruption_class"] == "git_packfile_truncated"
    assert report["destructive_action_taken"] is False
    assert report["recommended_action"] == "do_not_reuse_checkout_fresh_clone_recommended"


def test_probe_repo_accepts_clean_status(monkeypatch) -> None:
    def fake_run_git(repo_path: Path, args: list[str], timeout: float) -> dict[str, object]:
        return {
            "args": args,
            "returncode": 0,
            "stdout_tail": "true\n",
            "stderr_tail": "",
            "timed_out": False,
            "duration_seconds": 0.01,
        }

    monkeypatch.setattr(doctor, "run_git", fake_run_git)
    report = doctor.probe_repo(Path("/tmp/repo"))

    assert report["ok"] is True
    assert report["failure_detected"] is False
    assert report["failure_class"] is None
    assert report["corruption_detected"] is False
    assert report["recommended_action"] == "repo_healthy"


def test_probe_repo_timeout_requires_fresh_clone(monkeypatch) -> None:
    def fake_run_git(repo_path: Path, args: list[str], timeout: float) -> dict[str, object]:
        return {
            "args": args,
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "timed_out": True,
            "duration_seconds": timeout,
        }

    monkeypatch.setattr(doctor, "run_git", fake_run_git)
    report = doctor.probe_repo(Path("/tmp/repo"))

    assert report["ok"] is False
    assert report["failure_detected"] is True
    assert report["failure_class"] == "git_repo_health_probe_timeout"
    assert report["recommended_action"] == "do_not_reuse_checkout_fresh_clone_recommended"


def test_probe_repo_can_run_optional_fsck(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run_git(repo_path: Path, args: list[str], timeout: float) -> dict[str, object]:
        calls.append(args)
        return {
            "args": args,
            "returncode": 0,
            "stdout_tail": "",
            "stderr_tail": "",
            "timed_out": False,
            "duration_seconds": 0.01,
        }

    monkeypatch.setattr(doctor, "run_git", fake_run_git)
    report = doctor.probe_repo(Path("/tmp/repo"), include_fsck=True)

    assert report["ok"] is True
    assert ["fsck", "--connectivity-only"] in calls
