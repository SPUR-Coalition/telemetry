#!/usr/bin/env python3
"""Deterministic conformance checks for the fingerprint registry and matrix."""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


ROOT = Path(__file__).parent.parent
REGISTRY_PATH = ROOT / "content-fingerprint-schemes.json"
MATRIX_PATH = ROOT / "survivability-matrix-c2pa-text.json"
REGISTRY_SCHEMA_PATH = ROOT / "content-fingerprint-schemes.schema.json"
MATRIX_SCHEMA_PATH = ROOT / "survivability-matrix.schema.json"
SHA256_PREFIX = "sha256:"
SHA256_LENGTH = len(SHA256_PREFIX) + 64

REQUIRED_TRANSFORMS = {
    "baseline",
    "utf8_round_trip",
    "utf16le_round_trip",
    "unicode_nfc",
    "unicode_nfd",
    "json_string_round_trip",
    "exact_unicode_copy",
    "aggregation_with_prefix_and_suffix",
    "default_ignorable_stripping",
    "fragment_extraction_wrapper_retained",
    "fragment_extraction_wrapper_omitted",
    "wordpress_editor_round_trip",
    "spip_editor_round_trip",
    "arc_xp_round_trip",
    "plain_text_export",
    "whitespace_collapse",
    "paraphrase_or_summary",
}
ALLOWED_OBSERVED_RESULTS = {
    "association_recovered",
    "association_removed",
    "association_removed_by_definition",
    "not_tested",
}
ALLOWED_REGISTRATION_STATUSES = {"registered", "reserved"}
ALLOWED_TIER_CEILINGS = {
    "claim",
    "origin_corroborated",
    "independently_verifiable",
}
SCHEME_PROPERTY_NAMES = {"content_borne", "identity_bearing", "verifiable"}
REGISTRATION_POLICY = "non-exclusive-discovery-only"
PROFILE_DIGEST_SEMANTICS_PHRASES = {
    "representation-data bytes",
    "content codings",
    "URI fragments",
}


def _load(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _schema_violations(instance, schema_path, label):
    """Validate an artifact against its locally resolved advertised schema."""
    schema = _load(schema_path)
    schema_id = schema.get("$id")
    advertised_id = instance.get("$schema") if isinstance(instance, dict) else None
    violations = []
    if not isinstance(schema_id, str) or not schema_id:
        return [f"{label} checked-in schema must declare a non-empty $id"]

    local_registry = Registry().with_resource(
        schema_id, Resource.from_contents(schema)
    )
    if not isinstance(advertised_id, str):
        violations.append(
            f"{label} advertised $schema does not resolve to its checked-in schema"
        )
    else:
        try:
            local_registry[advertised_id]
        except KeyError:
            violations.append(
                f"{label} advertised $schema does not resolve to its checked-in schema"
            )

    validator = Draft202012Validator(
        schema, registry=local_registry, format_checker=FormatChecker()
    )
    for error in sorted(
        validator.iter_errors(instance),
        key=lambda item: tuple(str(part) for part in item.path),
    ):
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        violations.append(f"{label} schema violation at {location}: {error.message}")
    return violations


def _is_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == SHA256_LENGTH
        and value.startswith(SHA256_PREFIX)
        and all(character in "0123456789abcdef" for character in value[len(SHA256_PREFIX):])
    )


def check_registry_and_matrix(registry=None, matrix=None):
    """Return violations of the discovery and survivability artifact contracts."""
    violations = []
    registry = _load(REGISTRY_PATH) if registry is None else registry
    matrix = _load(MATRIX_PATH) if matrix is None else matrix
    violations.extend(_schema_violations(registry, REGISTRY_SCHEMA_PATH, "registry"))
    violations.extend(_schema_violations(matrix, MATRIX_SCHEMA_PATH, "matrix"))
    if not isinstance(registry, dict):
        return violations + ["registry must be an object"]
    if not isinstance(matrix, dict):
        return violations + ["matrix must be an object"]
    if registry.get("registration_policy") != REGISTRATION_POLICY:
        violations.append(
            f"registry registration_policy must be {REGISTRATION_POLICY}"
        )
    digest_semantics = registry.get("profile_digest_semantics")
    if not isinstance(digest_semantics, str) or not all(
        phrase in digest_semantics for phrase in PROFILE_DIGEST_SEMANTICS_PHRASES
    ):
        violations.append(
            "registry profile_digest_semantics must define representation bytes, "
            "content coding, and fragment handling"
        )


    schemes = registry.get("schemes")
    if not isinstance(schemes, list):
        return ["registry schemes must be an array"]

    names = [entry.get("scheme") for entry in schemes if isinstance(entry, dict)]
    string_names = [name for name in names if isinstance(name, str)]
    if (
        len(names) != len(schemes)
        or len(string_names) != len(names)
        or len(string_names) != len(set(string_names))
    ):
        violations.append("registry scheme names must be present, strings, and unique")
    entries = {
        entry["scheme"]: entry
        for entry in schemes
        if isinstance(entry, dict)
        and isinstance(entry.get("scheme"), str)
        and entry["scheme"]
    }
    for position, entry in enumerate(schemes):
        if not isinstance(entry, dict):
            violations.append(f"registry entry[{position}] must be an object")
            continue
        name = entry.get("scheme")
        label = name if isinstance(name, str) and name else f"entry[{position}]"
        if not isinstance(name, str) or not name:
            violations.append(f"registry {label} must have a non-empty scheme name")

        status = entry.get("status")
        if not isinstance(status, str) or status not in ALLOWED_REGISTRATION_STATUSES:
            violations.append(f"{label} has an unknown registration status")

        properties = entry.get("scheme_properties")
        if not isinstance(properties, dict) or set(properties) != SCHEME_PROPERTY_NAMES:
            violations.append(f"{label} must declare exactly the three scheme properties")
            properties = {}
        elif not all(isinstance(value, bool) for value in properties.values()):
            violations.append(f"{label} scheme properties must be booleans")

        ceiling = entry.get("fingerprint_tier_ceiling")
        if not isinstance(ceiling, str) or ceiling not in ALLOWED_TIER_CEILINGS:
            violations.append(f"{label} has an unknown fingerprint tier ceiling")
        if ceiling == "independently_verifiable" and not all(
            properties.get(property_name) is True
            for property_name in SCHEME_PROPERTY_NAMES
        ):
            violations.append(
                f"{label} independently_verifiable ceiling exceeds its scheme properties"
            )

        has_profile_ref = "profile_ref" in entry
        has_profile_digest = "profile_digest" in entry
        if has_profile_ref != has_profile_digest:
            violations.append(f"{label} must bind profile_ref and profile_digest together")
        if status == "registered" and not (has_profile_ref and has_profile_digest):
            violations.append(f"{label} registered entry must bind a profile")
        if status == "reserved" and (has_profile_ref or has_profile_digest):
            violations.append(f"{label} reserved entry must not claim a profile")
        if has_profile_ref and (
            not isinstance(entry.get("profile_ref"), str)
            or "://" not in entry["profile_ref"]
        ):
            violations.append(f"{label} profile_ref is not absolute")
        if has_profile_digest and not _is_sha256(entry.get("profile_digest")):
            violations.append(f"{label} profile_digest is not a lowercase SHA-256 digest")

        limitations = entry.get("limitations")
        if not isinstance(limitations, list) or not limitations or not all(
            isinstance(item, str) and item for item in limitations
        ):
            violations.append(f"{label} must state concrete limitations")

    expected_entries = {
        "c2pa": {
            "status": "registered",
            "properties": {"content_borne": False, "identity_bearing": True, "verifiable": True},
            "ceiling": "origin_corroborated",
            "has_profile": True,
        },
        "c2pa-text": {
            "status": "registered",
            "properties": {"content_borne": True, "identity_bearing": True, "verifiable": True},
            "ceiling": "independently_verifiable",
            "has_profile": True,
        },
        "iscc+registry": {
            "status": "reserved",
            "properties": {"content_borne": False, "identity_bearing": False, "verifiable": False},
            "ceiling": "claim",
            "has_profile": False,
        },
    }
    for name, expected in expected_entries.items():
        entry = entries.get(name)
        if entry is None:
            violations.append(f"registry omits required scheme {name}")
            continue
        if entry.get("status") != expected["status"]:
            violations.append(f"{name} has incorrect registration status")
        if entry.get("scheme_properties") != expected["properties"]:
            violations.append(f"{name} has dishonest scheme capability properties")
        if entry.get("fingerprint_tier_ceiling") != expected["ceiling"]:
            violations.append(f"{name} has incorrect fingerprint tier ceiling")
        profile_fields = "profile_ref" in entry and "profile_digest" in entry
        if profile_fields != expected["has_profile"]:
            violations.append(f"{name} profile binding does not match its registration status")
        if expected["has_profile"]:
            if not isinstance(entry.get("profile_ref"), str) or "://" not in entry["profile_ref"]:
                violations.append(f"{name} profile_ref is not absolute")
            if not _is_sha256(entry.get("profile_digest")):
                violations.append(f"{name} profile_digest is not a lowercase SHA-256 digest")
        limitations = entry.get("limitations")
        if not isinstance(limitations, list) or not limitations or not all(isinstance(item, str) and item for item in limitations):
            violations.append(f"{name} must state concrete limitations")

    c2pa_text = entries.get("c2pa-text", {})
    if matrix.get("scheme") != "c2pa-text":
        violations.append("survivability matrix must identify c2pa-text")
    if matrix.get("profile_ref") != c2pa_text.get("profile_ref"):
        violations.append("matrix profile_ref does not match the c2pa-text registry entry")
    if matrix.get("profile_digest") != c2pa_text.get("profile_digest"):
        violations.append("matrix profile_digest does not match the c2pa-text registry entry")
    if matrix.get("runner") != "tests/check_survivability.py":
        violations.append(
            "matrix runner must identify tests/check_survivability.py"
        )
    if not isinstance(matrix.get("runner_version"), str) or not matrix["runner_version"]:
        violations.append("matrix runner_version must be a non-empty string")
    if matrix.get("implementation") != "C2PA 2.4 Appendix A.8 carrier fixture generator v1":
        violations.append("matrix implementation must identify the versioned fixture generator")

    qualification = matrix.get("qualification", "")
    for required_phrase in ("not a signed C2PA claim", "carrier recovery only", "does not prove"):
        if not isinstance(qualification, str) or required_phrase not in qualification:
            violations.append(f"matrix qualification omits honesty boundary: {required_phrase}")

    transforms = matrix.get("transforms")
    if not isinstance(transforms, list):
        violations.append("matrix transforms must be an array")
        return violations
    transform_names = [row.get("transform") for row in transforms if isinstance(row, dict)]
    string_transform_names = [
        name for name in transform_names if isinstance(name, str)
    ]
    if (
        len(transform_names) != len(transforms)
        or len(string_transform_names) != len(transform_names)
        or len(string_transform_names) != len(set(string_transform_names))
    ):
        violations.append("matrix transform names must be present, strings, and unique")
    missing = REQUIRED_TRANSFORMS - set(string_transform_names)
    if missing:
        violations.append("matrix omits required transforms: " + ", ".join(sorted(missing)))

    for position, row in enumerate(transforms):
        if not isinstance(row, dict):
            continue
        transform = row.get("transform")
        name = transform if isinstance(transform, str) and transform else f"row[{position}]"
        if not isinstance(row.get("operation"), str) or not row["operation"]:
            violations.append(f"matrix transform {name} omits its operation")
        observed_result = row.get("observed_result")
        if (
            not isinstance(observed_result, str)
            or observed_result not in ALLOWED_OBSERVED_RESULTS
        ):
            violations.append(f"matrix transform {name} has an unknown observed result")
        full_validation = row.get("full_c2pa_validation")
        if not isinstance(full_validation, str) or not full_validation.startswith("not_run"):
            violations.append(f"matrix transform {name} overstates full C2PA validation")

    return violations


def main():
    violations = check_registry_and_matrix()
    if violations:
        print("Registry/matrix conformance: FAIL")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print("Registry/matrix conformance: PASS (3 schemes, 17 transform rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
