import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "docs" / "api" / "validate_openapi.py"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_openapi_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_spec(tmp_path, content):
    spec_path = tmp_path / "openapi.yaml"
    spec_path.write_text(content)
    return spec_path


def test_load_spec_reports_missing_file(tmp_path):
    module = load_validator_module()
    validator = module.OpenAPIValidator(str(tmp_path / "missing.yaml"))

    assert validator.load_spec() is False
    assert validator.errors == [f"File not found: {tmp_path / 'missing.yaml'}"]


def test_validate_root_requires_openapi_info_and_paths(tmp_path):
    module = load_validator_module()
    spec_path = write_spec(tmp_path, "openapi: 2.0.0\ninfo:\n  title: RustChain\n")
    validator = module.OpenAPIValidator(str(spec_path))
    assert validator.load_spec() is True

    assert validator.validate_root() is False

    assert "Unsupported OpenAPI version: 2.0.0. Expected 3.0.x" in validator.errors
    assert "Missing required root field: paths" in validator.errors
    assert "Missing required info field: version" in validator.errors


def test_validate_paths_reports_invalid_paths_and_response_descriptions(tmp_path):
    module = load_validator_module()
    validator = module.OpenAPIValidator("unused.yaml")
    validator.spec = {
        "paths": {
            "api/health": {
                "get": {
                    "parameters": [{"name": "limit", "in": "body"}],
                    "responses": {"200": {}},
                }
            }
        }
    }

    assert validator.validate_paths() is False

    assert "Path must start with '/': api/health" in validator.errors
    assert "Missing description for response 200: GET api/health" in validator.errors
    assert "Invalid parameter location: body in GET api/health" in validator.errors
    assert "Missing summary: GET api/health" in validator.warnings


def test_validate_references_and_security_report_undefined_names():
    module = load_validator_module()
    validator = module.OpenAPIValidator("unused.yaml")
    validator.spec = {
        "openapi": "3.0.0",
        "info": {"title": "RustChain", "version": "1.0.0"},
        "paths": {
            "/wallet": {
                "get": {
                    "summary": "Wallet",
                    "security": [{"ApiKeyAuth": []}],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Wallet"}
                                }
                            },
                        }
                    },
                }
            }
        },
        "components": {"schemas": {}, "securitySchemes": {}},
    }

    assert validator.validate_references() is False
    assert validator.validate_security() is False

    assert "Undefined schema reference: Wallet" in validator.errors
    assert "Undefined security scheme 'ApiKeyAuth' used in GET /wallet" in validator.errors


def test_validate_accepts_minimal_valid_spec(tmp_path, capsys):
    module = load_validator_module()
    spec_path = write_spec(
        tmp_path,
        """
openapi: 3.0.3
info:
  title: RustChain
  version: 1.0.0
paths:
  /health:
    get:
      summary: Health
      responses:
        '200':
          description: ok
components:
  schemas:
    Health:
      type: object
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
""",
    )
    validator = module.OpenAPIValidator(str(spec_path))

    assert validator.validate() is True

    output = capsys.readouterr().out
    assert "Specification loaded successfully" in output
    assert "No errors or warnings found" in output
    assert validator.errors == []
    assert validator.warnings == []
