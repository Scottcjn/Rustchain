# SPDX-License-Identifier: MIT

import hashlib
import http.server
import importlib.util
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).with_name("rustchain_termux_miner.py")
spec = importlib.util.spec_from_file_location("termux_miner_wrapper", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TermuxMinerSafetyTests(unittest.TestCase):
    def test_production_node_is_rejected_for_test_only(self):
        for url in ("https://rustchain.org", "https://www.rustchain.org/", "https://rustchain.org."):
            with self.subTest(url=url), self.assertRaises(ValueError):
                mod.validate_test_node_url(url)

    def test_local_test_node_is_allowed(self):
        self.assertEqual(
            mod.validate_test_node_url("http://127.0.0.1:58333/"),
            "http://127.0.0.1:58333",
        )

    def test_termux_detection_requires_android_and_termux_marker(self):
        with mock.patch.object(mod.platform, "system", return_value="Android"), mock.patch.dict(
            os.environ,
            {"PREFIX": "/data/data/com.termux/files/usr", "TERMUX_VERSION": "0.118.3"},
            clear=False,
        ):
            self.assertTrue(mod.is_termux_android())
        with mock.patch.object(mod.platform, "system", return_value="Linux"):
            self.assertFalse(mod.is_termux_android())

    def test_verification_modes_are_mutually_exclusive(self):
        parser = mod.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--dry-run", "--test-only"])

    def test_checksum_manifest_pins_termux_wrapper(self):
        root = Path(__file__).resolve().parents[2]
        wrapper = root / "miners" / "termux" / "rustchain_termux_miner.py"
        manifest = root / "miners" / "checksums.sha256"
        entries = {}
        for line in manifest.read_text(encoding="utf-8").splitlines():
            digest, artifact = line.split(maxsplit=1)
            entries[artifact] = digest
        self.assertEqual(
            entries.get("termux/rustchain_termux_miner.py"),
            hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        )

    def test_installer_pins_all_downloads_when_ref_advances(self):
        installer = Path(__file__).with_name("install.sh").resolve()
        sha_a = "a" * 40
        sha_b = "b" * 40
        payloads = {
            "linux/rustchain_linux_miner.py": b"linux-a\n",
            "linux/fingerprint_checks.py": b"fingerprint-a\n",
            "linux/miner_crypto.py": b"crypto-a\n",
            "termux/rustchain_termux_miner.py": b"wrapper-a\n",
        }
        manifest = "".join(
            f"{hashlib.sha256(data).hexdigest()}  {name}\n"
            for name, data in payloads.items()
        ).encode()
        requests_seen = []
        branch = {"sha": sha_a}

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                requests_seen.append(self.path)
                if self.path == "/api/repos/example/repo/commits/main":
                    body = json.dumps({"sha": branch["sha"]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    # The mutable ref advances immediately after resolution.
                    branch["sha"] = sha_b
                    return

                pinned_prefix = f"/raw/example/repo/{sha_a}/miners/"
                if self.path.startswith(pinned_prefix):
                    name = self.path[len(pinned_prefix):]
                    body = manifest if name == "checksums.sha256" else payloads.get(name)
                    if body is None:
                        self.send_error(404)
                        return
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                # A regressed installer which downloads through `main` after
                # resolution would receive branch-B bytes here.
                mutable_prefix = "/raw/example/repo/main/miners/"
                if self.path.startswith(mutable_prefix):
                    body = b"branch-b\n"
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_error(404)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with tempfile.TemporaryDirectory() as td:
                shell = f"""
set -euo pipefail
export RUSTCHAIN_REPO=example/repo
export RUSTCHAIN_REF=main
export RUSTCHAIN_GITHUB_API_BASE=http://127.0.0.1:{port}/api
export RUSTCHAIN_RAW_BASE=http://127.0.0.1:{port}/raw
source {str(installer)!r}
commit="$(resolve_ref_sha)"
[[ "$commit" == {sha_a!r} ]]
download_miner_stage "$commit" {td!r}
verify_sha {td!r} rustchain_linux_miner.py linux/rustchain_linux_miner.py >/dev/null
verify_sha {td!r} fingerprint_checks.py linux/fingerprint_checks.py >/dev/null
verify_sha {td!r} miner_crypto.py linux/miner_crypto.py >/dev/null
verify_sha {td!r} rustchain_termux_miner.py termux/rustchain_termux_miner.py >/dev/null
"""
                result = subprocess.run(
                    ["bash", "-c", shell], capture_output=True, text=True, check=False
                )
                self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        raw_requests = [p for p in requests_seen if p.startswith("/raw/")]
        self.assertEqual(len(raw_requests), 5)
        self.assertTrue(all(f"/{sha_a}/" in p for p in raw_requests), raw_requests)
        self.assertFalse(any("/main/" in p for p in raw_requests), raw_requests)

    def test_installer_expected_commit_fails_closed(self):
        installer = Path(__file__).with_name("install.sh").resolve()
        sha_a = "a" * 40
        sha_b = "b" * 40

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                body = json.dumps({"sha": sha_a}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            shell = f"""
set -euo pipefail
export RUSTCHAIN_REPO=example/repo
export RUSTCHAIN_REF=main
export RUSTCHAIN_EXPECTED_COMMIT={sha_b!r}
export RUSTCHAIN_GITHUB_API_BASE=http://127.0.0.1:{port}
source {str(installer)!r}
resolve_ref_sha
"""
            result = subprocess.run(
                ["bash", "-c", shell], capture_output=True, text=True, check=False
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match RUSTCHAIN_EXPECTED_COMMIT", result.stderr)

    def test_installer_places_down_marker_before_run_script(self):
        installer = Path(__file__).with_name("install.sh").read_text(encoding="utf-8")
        down = installer.index('touch "$SERVICE_DIR/down"')
        run = installer.index('> "$SERVICE_DIR/run"')
        self.assertLess(down, run)

    def test_installer_verifies_termux_wrapper(self):
        installer = Path(__file__).with_name("install.sh").read_text(encoding="utf-8")
        self.assertIn(
            'verify_sha "$tmp_stage" rustchain_termux_miner.py termux/rustchain_termux_miner.py',
            installer,
        )


if __name__ == "__main__":
    unittest.main()
