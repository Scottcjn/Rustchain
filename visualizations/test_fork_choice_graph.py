# SPDX-License-Identifier: MIT

import fork_choice_graph


def test_root_serves_dashboard_html():
    app = fork_choice_graph.create_app()

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"RustChain Fork Choice Graph" in response.data


def test_dashboard_html_route_serves_file():
    app = fork_choice_graph.create_app()

    response = app.test_client().get("/fork_choice_graph.html")

    assert response.status_code == 200
    assert b"RustChain Fork Choice Graph" in response.data


def test_api_health_defaults_to_object_when_not_refreshed():
    app = fork_choice_graph.create_app()
    fork_choice_graph._fork_store["health"] = None

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"ok": False}


def test_api_dashboard_defaults_health_to_object_when_not_refreshed():
    app = fork_choice_graph.create_app()
    fork_choice_graph._fork_store["health"] = None

    response = app.test_client().get("/api/dashboard")

    assert response.status_code == 200
    assert response.get_json()["health"] == {"ok": False}
