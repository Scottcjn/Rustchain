import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "postman"
    / "validate_postman_collection.py"
)
SPEC = importlib.util.spec_from_file_location("postman_validator", MODULE_PATH)
postman_validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(postman_validator)


def test_generate_checklist_flattens_folders_and_postman_url_paths():
    collection = {
        "item": [
            {
                "name": "Status",
                "item": [
                    {
                        "name": "Network stats",
                        "request": {
                            "method": "POST",
                            "url": {"path": ["api", "stats"]},
                        },
                        "response": [{"name": "ok"}],
                    }
                ],
            }
        ]
    }

    checklist = postman_validator.generate_checklist(collection)

    assert checklist == [
        {
            "folder": "Status",
            "name": "Network stats",
            "method": "POST",
            "url": "{{base_url}}/api/stats",
            "has_examples": True,
        }
    ]


def test_generate_checklist_defaults_missing_fields_and_empty_url_path():
    collection = {
        "item": [
            {
                "request": {
                    "url": {"path": []},
                },
                "response": [],
            }
        ]
    }

    checklist = postman_validator.generate_checklist(collection)

    assert checklist == [
        {
            "folder": "",
            "name": "Unknown",
            "method": "GET",
            "url": "N/A",
            "has_examples": False,
        }
    ]


def test_generate_checklist_preserves_string_urls():
    collection = {
        "item": [
            {
                "name": "External docs",
                "request": {
                    "method": "GET",
                    "url": "https://rustchain.org/health",
                },
            }
        ]
    }

    checklist = postman_validator.generate_checklist(collection)

    assert checklist[0]["url"] == "https://rustchain.org/health"
    assert checklist[0]["has_examples"] is False
