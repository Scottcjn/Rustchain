# SPDX-License-Identifier: MIT
import io
import unittest
import urllib.error
from unittest import mock

from flask import Flask

from node import beacon_api as beacon_module


def _client():
    app = Flask(__name__)
    app.register_blueprint(beacon_module.beacon_api, url_prefix="/beacon")
    app.config.update(TESTING=True)
    return app.test_client()


class TestBeaconAvatarProxy(unittest.TestCase):
    def test_returns_bounded_image_with_hardening_headers(self):
        with mock.patch.object(
            beacon_module,
            "_fetch_bottube_avatar",
            return_value=(b"<svg></svg>", "image/svg+xml"),
        ):
            response = _client().get("/beacon/api/avatar/sophia-elya.svg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"<svg></svg>")
        self.assertEqual(response.content_type, "image/svg+xml")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(response.headers["Cache-Control"], "public, max-age=86400")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn(
            "script-src 'none'", response.headers["Content-Security-Policy"]
        )

    def test_rejects_paths_that_could_escape_fixed_origin(self):
        with mock.patch.object(beacon_module, "_fetch_bottube_avatar") as fetch:
            for filename in ("not-an-image.txt", "avatar.svg%3Fraw=1", ".svg"):
                response = _client().get(f"/beacon/api/avatar/{filename}")
                self.assertEqual(response.status_code, 400)
        fetch.assert_not_called()

    def test_maps_upstream_not_found_without_leaking_details(self):
        missing = urllib.error.HTTPError(
            "https://bottube.ai/avatar/missing.svg",
            404,
            "Not Found",
            {},
            io.BytesIO(),
        )
        with mock.patch.object(
            beacon_module, "_fetch_bottube_avatar", side_effect=missing
        ):
            response = _client().get("/beacon/api/avatar/missing.svg")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "avatar unavailable"})


if __name__ == "__main__":
    unittest.main()
