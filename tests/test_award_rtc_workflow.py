# SPDX-License-Identifier: MIT

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "award-rtc.yml"


def test_award_rtc_workflow_uses_local_action() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "uses: ./.github/actions/rtc-auto-bounty" in workflow
    assert "BossChaos/rtc-award-action" not in workflow


def test_award_rtc_workflow_no_longer_requires_wallet_file() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "wallet_file" not in workflow
    assert "api_url" not in workflow


def test_award_rtc_workflow_passes_live_transfer_secrets() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "rtc-vps-host: ${{ secrets.RTC_VPS_HOST }}" in workflow
    assert "rtc-admin-key: ${{ secrets.RTC_ADMIN_KEY }}" in workflow
    assert "github-token: ${{ secrets.GITHUB_TOKEN }}" in workflow
