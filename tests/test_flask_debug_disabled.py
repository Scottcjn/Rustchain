from pathlib import Path
import unittest


FILES_WITH_PUBLIC_FLASK_ENTRYPOINTS = [
    "bridge/bridge_api.py",
    "contributor_registry.py",
    "explorer/app.py",
    "keeper_explorer.py",
    "profile_badge_generator.py",
]


class FlaskDebugDisabledTests(unittest.TestCase):
    def test_public_flask_entrypoints_do_not_enable_debugger(self):
        repo = Path(__file__).resolve().parents[1]
        for relative_path in FILES_WITH_PUBLIC_FLASK_ENTRYPOINTS:
            with self.subTest(path=relative_path):
                text = (repo / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("debug=True", text)
                self.assertNotIn("debug = True", text)


if __name__ == "__main__":
    unittest.main()
