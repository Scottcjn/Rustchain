# SPDX-License-Identifier: MIT
"""Load, validate, and safely probe the RustChain read-only API contract."""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from openapi_spec_validator import validate as validate_openapi_spec


PACKAGE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_ROOT.parent
DEFAULT_CONTRACT_PATH = PACKAGE_ROOT / "read_only_api.openapi.json"
EXPECTED_PATHS = {
    "/health",
    "/epoch",
    "/api/miners",
    "/wallet/balance",
}
HTTP_METHODS = {
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
}
MAX_RESPONSE_BYTES = 1024 * 1024
MINER_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")


class ContractError(ValueError):
    """Raised when the canonical contract cannot be loaded safely."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Keep a probe on the exact endpoints selected by the caller."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


@dataclass(frozen=True)
class ProbeResult:
    """Validation outcome for one live read-only endpoint probe."""

    operation_id: str
    url: str
    status: Optional[int]
    errors: Tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _object_without_duplicates(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    """Load strict JSON, rejecting duplicate keys and non-finite numbers."""

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
            object_pairs_hook=_object_without_duplicates,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ContractError(f"could not load JSON from {path}: {exc}") from exc


def _json_pointer(document: Mapping[str, Any], pointer: str) -> Any:
    if not pointer.startswith("#/"):
        raise ContractError(f"only local JSON references are supported: {pointer}")
    value: Any = document
    for raw_part in pointer[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, Mapping) or part not in value:
            raise ContractError(f"unresolved JSON reference: {pointer}")
        value = value[part]
    return value


def _matches_type(instance: Any, expected: str) -> bool:
    if expected == "null":
        return instance is None
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return (
            isinstance(instance, (int, float))
            and not isinstance(instance, bool)
            and math.isfinite(instance)
        )
    if expected == "string":
        return isinstance(instance, str)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "object":
        return isinstance(instance, dict)
    return False


def _display_type(expected: Any) -> str:
    if isinstance(expected, list):
        return " or ".join(str(item) for item in expected)
    return str(expected)


def validate_instance(
    instance: Any,
    schema: Mapping[str, Any],
    contract: Mapping[str, Any],
    location: str = "$",
) -> List[str]:
    """Validate an instance against the JSON Schema subset used by the contract."""

    errors: List[str] = []
    if "$ref" in schema:
        try:
            referenced = _json_pointer(contract, str(schema["$ref"]))
        except ContractError as exc:
            return [f"{location}: {exc}"]
        if not isinstance(referenced, Mapping):
            return [f"{location}: referenced schema is not an object"]
        return validate_instance(instance, referenced, contract, location)

    for branch in schema.get("allOf", []):
        if isinstance(branch, Mapping):
            errors.extend(validate_instance(instance, branch, contract, location))

    if "const" in schema and instance != schema["const"]:
        errors.append(
            f"{location}: expected constant {schema['const']!r}, got {instance!r}"
        )
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{location}: value {instance!r} is not in {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type is not None:
        choices = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_matches_type(instance, str(choice)) for choice in choices):
            errors.append(
                f"{location}: expected {_display_type(expected_type)}, "
                f"got {type(instance).__name__}"
            )
            return errors

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{location}: missing required property {key!r}")

        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            errors.append(f"{location}: schema properties must be an object")
            return errors
        for key, value in instance.items():
            child_location = f"{location}.{key}"
            if key in properties and isinstance(properties[key], Mapping):
                errors.extend(
                    validate_instance(value, properties[key], contract, child_location)
                )
            elif schema.get("additionalProperties") is False:
                errors.append(f"{child_location}: additional property is not allowed")
            elif isinstance(schema.get("additionalProperties"), Mapping):
                errors.extend(
                    validate_instance(
                        value,
                        schema["additionalProperties"],
                        contract,
                        child_location,
                    )
                )

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            errors.append(f"{location}: expected at least {min_items} items")
        if isinstance(max_items, int) and len(instance) > max_items:
            errors.append(f"{location}: expected at most {max_items} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, value in enumerate(instance):
                errors.extend(
                    validate_instance(
                        value, item_schema, contract, f"{location}[{index}]"
                    )
                )

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            errors.append(f"{location}: expected at least {min_length} characters")
        if isinstance(max_length, int) and len(instance) > max_length:
            errors.append(f"{location}: expected at most {max_length} characters")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            errors.append(f"{location}: value does not match pattern {pattern!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and instance < minimum:
            errors.append(f"{location}: value is below minimum {minimum}")
        if isinstance(maximum, (int, float)) and instance > maximum:
            errors.append(f"{location}: value is above maximum {maximum}")

    return errors


def _iter_operations(contract: Mapping[str, Any]):
    paths = contract.get("paths", {})
    if not isinstance(paths, Mapping):
        return
    for path, path_item in paths.items():
        if isinstance(path_item, Mapping) and isinstance(path_item.get("get"), Mapping):
            yield str(path), path_item["get"]


def contract_errors(contract: Any) -> List[str]:
    """Return structural and read-only policy violations in a contract."""

    errors: List[str] = []
    if not isinstance(contract, Mapping):
        return ["contract root must be a JSON object"]
    try:
        validate_openapi_spec(contract)
    except Exception as exc:  # validator exceptions differ across patch releases
        errors.append(f"OpenAPI 3.1 validation failed: {exc}")
    if contract.get("openapi") != "3.1.0":
        errors.append("contract must declare OpenAPI 3.1.0")
    if contract.get("security") != []:
        errors.append("contract must explicitly declare no global authentication")

    paths = contract.get("paths")
    if not isinstance(paths, Mapping):
        errors.append("contract paths must be an object")
        return errors
    actual_paths = set(paths)
    if actual_paths != EXPECTED_PATHS:
        errors.append(
            "contract paths must be exactly "
            f"{sorted(EXPECTED_PATHS)!r}; got {sorted(actual_paths)!r}"
        )

    operation_ids = set()
    for path, path_item in paths.items():
        if not isinstance(path_item, Mapping):
            errors.append(f"paths.{path} must be an object")
            continue
        methods = HTTP_METHODS.intersection(path_item)
        if methods != {"get"}:
            errors.append(f"{path} must define GET only; found {sorted(methods)!r}")
        operation = path_item.get("get")
        if not isinstance(operation, Mapping):
            continue
        operation_id = operation.get("operationId")
        if not isinstance(operation_id, str) or not operation_id:
            errors.append(f"GET {path} needs a non-empty operationId")
        elif operation_id in operation_ids:
            errors.append(f"duplicate operationId: {operation_id}")
        else:
            operation_ids.add(operation_id)
        if operation.get("security") != []:
            errors.append(f"GET {path} must explicitly require no authentication")

        implementation = operation.get("x-rustchain-implementation")
        if not isinstance(implementation, Mapping):
            errors.append(f"GET {path} needs implementation provenance")
        elif not implementation.get("file") or not implementation.get("handler"):
            errors.append(f"GET {path} implementation provenance is incomplete")

        fixtures = operation.get("x-rustchain-fixtures")
        if not isinstance(fixtures, list) or not fixtures:
            errors.append(f"GET {path} must list at least one offline fixture")

        responses = operation.get("responses")
        if not isinstance(responses, Mapping) or "200" not in responses:
            errors.append(f"GET {path} must define a 200 JSON response")
            continue
        for status, response in responses.items():
            try:
                numeric_status = int(status)
            except (TypeError, ValueError):
                errors.append(
                    f"GET {path} has a non-numeric response status {status!r}"
                )
                continue
            if numeric_status < 100 or numeric_status > 599:
                errors.append(f"GET {path} has invalid response status {status!r}")
            if not isinstance(response, Mapping):
                errors.append(f"GET {path} response {status} must be an object")
                continue
            content = response.get("content")
            if not isinstance(content, Mapping) or "application/json" not in content:
                errors.append(f"GET {path} response {status} must be application/json")
                continue
            media = content["application/json"]
            schema = media.get("schema") if isinstance(media, Mapping) else None
            if not isinstance(schema, Mapping):
                errors.append(f"GET {path} response {status} needs a JSON schema")
                continue
            if "$ref" in schema:
                try:
                    _json_pointer(contract, str(schema["$ref"]))
                except ContractError as exc:
                    errors.append(f"GET {path} response {status}: {exc}")

    metadata = contract.get("x-rustchain-compatibility")
    if not isinstance(metadata, Mapping):
        errors.append("contract needs x-rustchain-compatibility metadata")
    else:
        if metadata.get("probe_method") != "GET":
            errors.append("compatibility probes must be fixed to GET")
        if metadata.get("sends_credentials") is not False:
            errors.append("compatibility probes must explicitly forbid credentials")
        if not metadata.get("fixtures_directory"):
            errors.append("compatibility metadata needs fixtures_directory")
        if not metadata.get("generated_reference"):
            errors.append("compatibility metadata needs generated_reference")
        link_files = metadata.get("link_check_files")
        if not isinstance(link_files, list) or not link_files:
            errors.append("compatibility metadata needs link_check_files")
        route_check = metadata.get("documentation_route_check")
        if not isinstance(route_check, Mapping):
            errors.append("compatibility metadata needs documentation_route_check")
        else:
            for field in (
                "files",
                "authoritative_sources",
                "public_hosts",
                "route_prefixes",
                "exact_routes",
            ):
                if (
                    not isinstance(route_check.get(field), list)
                    or not route_check[field]
                ):
                    errors.append(f"documentation_route_check needs {field}")

    return errors


def load_contract(path: Path = DEFAULT_CONTRACT_PATH) -> Mapping[str, Any]:
    contract = load_json(Path(path))
    errors = contract_errors(contract)
    if errors:
        raise ContractError("invalid API contract:\n  - " + "\n  - ".join(errors))
    return contract


def operation_for_id(
    contract: Mapping[str, Any], operation_id: str
) -> Tuple[str, Mapping[str, Any]]:
    for path, operation in _iter_operations(contract):
        if operation.get("operationId") == operation_id:
            return path, operation
    raise ContractError(f"unknown operation_id: {operation_id}")


def response_schema(
    operation: Mapping[str, Any], status: int
) -> Optional[Mapping[str, Any]]:
    responses = operation.get("responses", {})
    response = responses.get(str(status)) if isinstance(responses, Mapping) else None
    if not isinstance(response, Mapping):
        return None
    content = response.get("content", {})
    media = content.get("application/json") if isinstance(content, Mapping) else None
    schema = media.get("schema") if isinstance(media, Mapping) else None
    return schema if isinstance(schema, Mapping) else None


def validate_response(
    contract: Mapping[str, Any], operation_id: str, status: int, body: Any
) -> List[str]:
    try:
        _, operation = operation_for_id(contract, operation_id)
    except ContractError as exc:
        return [str(exc)]
    schema = response_schema(operation, status)
    if schema is None:
        return [f"status {status} is not declared for {operation_id}"]
    return validate_instance(body, schema, contract, "$.body")


def fixture_directory(
    contract: Mapping[str, Any], repository_root: Path = REPOSITORY_ROOT
) -> Path:
    metadata = contract["x-rustchain-compatibility"]
    return repository_root / str(metadata["fixtures_directory"])


def expected_fixture_names(contract: Mapping[str, Any]) -> List[str]:
    names: List[str] = []
    for _, operation in _iter_operations(contract):
        names.extend(str(name) for name in operation.get("x-rustchain-fixtures", []))
    return names


def validate_fixture(
    contract: Mapping[str, Any], fixture: Any, fixture_name: str = "fixture"
) -> List[str]:
    errors: List[str] = []
    if not isinstance(fixture, Mapping):
        return [f"{fixture_name}: fixture root must be an object"]
    required = {"fixture_version", "operation_id", "status", "content_type", "body"}
    missing = sorted(required.difference(fixture))
    extra = sorted(set(fixture).difference(required))
    if missing:
        errors.append(f"{fixture_name}: missing fixture fields {missing!r}")
    if extra:
        errors.append(f"{fixture_name}: unknown fixture fields {extra!r}")
    if fixture.get("fixture_version") != 1:
        errors.append(f"{fixture_name}: fixture_version must be 1")
    operation_id = fixture.get("operation_id")
    status = fixture.get("status")
    if not isinstance(operation_id, str):
        errors.append(f"{fixture_name}: operation_id must be a string")
    if not isinstance(status, int) or isinstance(status, bool):
        errors.append(f"{fixture_name}: status must be an integer")
    if fixture.get("content_type") != "application/json":
        errors.append(f"{fixture_name}: content_type must be application/json")
    if errors:
        return errors
    response_errors = validate_response(contract, operation_id, status, fixture["body"])
    errors.extend(f"{fixture_name}: {error}" for error in response_errors)
    return errors


def validate_fixtures(
    contract: Mapping[str, Any], fixtures_path: Optional[Path] = None
) -> Mapping[str, List[str]]:
    """Validate the exact fixture set declared by the canonical contract."""

    directory = (
        Path(fixtures_path)
        if fixtures_path is not None
        else fixture_directory(contract)
    )
    expected = expected_fixture_names(contract)
    results: Dict[str, List[str]] = {}
    if len(expected) != len(set(expected)):
        results["<contract>"] = ["fixture names must be unique across operations"]
        return results
    try:
        actual = sorted(
            path.name for path in directory.glob("*.json") if path.is_file()
        )
    except OSError as exc:
        return {"<fixtures>": [f"could not list {directory}: {exc}"]}
    if sorted(expected) != actual:
        results["<fixtures>"] = [
            f"declared fixtures {sorted(expected)!r} do not match files {actual!r}"
        ]
    for name in expected:
        path = directory / name
        try:
            fixture = load_json(path)
        except ContractError as exc:
            results[name] = [str(exc)]
            continue
        results[name] = validate_fixture(contract, fixture, name)
    return results


def _validated_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ContractError("base URL scheme must be http or https")
    if not parsed.hostname:
        raise ContractError("base URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ContractError("base URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ContractError("base URL must not contain a query string or fragment")
    return base_url.rstrip("/")


def _probe_url(
    base_url: str, path: str, operation: Mapping[str, Any], miner_id: str
) -> str:
    probe = operation.get("x-rustchain-probe", {})
    query = probe.get("query", {}) if isinstance(probe, Mapping) else {}
    values: Dict[str, str] = {}
    if isinstance(query, Mapping):
        for key, value in query.items():
            values[str(key)] = miner_id if value == "$miner_id" else str(value)
    suffix = "?" + urllib.parse.urlencode(values) if values else ""
    return f"{base_url}{path}{suffix}"


def _read_probe_response(response: Any) -> Tuple[int, str, bytes]:
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    headers = getattr(response, "headers", {})
    content_type = headers.get("Content-Type", "") if headers is not None else ""
    payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ContractError(f"response exceeds {MAX_RESPONSE_BYTES} bytes")
    return int(status), str(content_type), payload


def probe_base_url(
    contract: Mapping[str, Any],
    base_url: str,
    miner_id: str = "compatibility-probe",
    timeout: float = 5.0,
    fetcher: Optional[Callable[..., Any]] = None,
) -> List[ProbeResult]:
    """Probe all contract endpoints using GET requests only.

    The caller must opt in by supplying a base URL. No credentials, request
    bodies, write methods, or TLS bypasses are supported.
    """

    base_url = _validated_base_url(base_url)
    if not MINER_ID_RE.fullmatch(miner_id):
        raise ContractError("miner_id must match [A-Za-z0-9._:-]{1,80}")
    if timeout <= 0 or timeout > 30:
        raise ContractError("timeout must be greater than 0 and at most 30 seconds")
    request_open = fetcher or urllib.request.build_opener(_NoRedirect()).open
    results: List[ProbeResult] = []

    for path, operation in _iter_operations(contract):
        operation_id = str(operation["operationId"])
        url = _probe_url(base_url, path, operation, miner_id)
        request = urllib.request.Request(
            url,
            data=None,
            headers={
                "Accept": "application/json",
                "User-Agent": "rustchain-compatibility-lab/1",
            },
            method="GET",
        )
        status: Optional[int] = None
        errors: List[str] = []
        response: Any = None
        try:
            response = request_open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        except (OSError, urllib.error.URLError, ValueError) as exc:
            errors.append(f"request failed: {exc}")

        if response is None and not errors:
            errors.append("request returned no response")
        elif response is not None:
            try:
                status, content_type, payload = _read_probe_response(response)
                if content_type.split(";", 1)[0].strip().lower() != "application/json":
                    errors.append(
                        "expected Content-Type application/json, "
                        f"got {content_type or '<missing>'}"
                    )
                try:
                    body = json.loads(
                        payload.decode("utf-8"),
                        parse_constant=_reject_json_constant,
                        object_pairs_hook=_object_without_duplicates,
                    )
                except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"response is not strict JSON: {exc}")
                else:
                    errors.extend(
                        validate_response(contract, operation_id, status, body)
                    )
            except (ContractError, OSError, ValueError) as exc:
                errors.append(str(exc))
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()

        results.append(ProbeResult(operation_id, url, status, tuple(errors)))

    return results
