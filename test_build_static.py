# SPDX-License-Identifier: MIT

import json

import build_static


def test_load_projects_returns_empty_list_when_data_file_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert build_static.load_projects() == []


def test_generate_project_card_can_render_a_single_project_without_global_state():
    project = {
        "name": "Example Chain",
        "url": "https://example.test",
        "github_repo": "example/chain",
        "bcos_tier": "L0",
        "latest_attested_sha": "abcdef1234567890",
        "sbom_hash": "1234567890abcdef",
        "categories": ["blockchain", "agent infra"],
        "review_note": "Reviewed for BCOS metadata.",
    }

    html = build_static.generate_project_card(project)

    assert 'data-project-index="0"' in html
    assert "Example Chain" in html
    assert "Reviewed for BCOS metadata." in html
    assert "BCOS-L0-green" in html


def test_load_projects_reads_projects_array(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "projects.json").write_text(
        json.dumps({"projects": [{"name": "Loaded Project"}]}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert build_static.load_projects() == [{"name": "Loaded Project"}]
