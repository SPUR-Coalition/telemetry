#!/usr/bin/env python3
"""Reproduce the executable C2PA text survivability matrix rows."""

import codecs
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

from check_registry import check_registry_and_matrix


ROOT = Path(__file__).parent.parent
MATRIX_PATH = ROOT / "survivability-matrix-c2pa-text.json"
MAGIC = b"C2PATXT"
WRAPPER_VERSION = 0
BYTE_ENCODING_ALGORITHM = 1


def _load_matrix():
    with MATRIX_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def _decode_fixture(escaped):
    """Decode the matrix's ASCII Unicode-escape representation exactly once."""
    if not isinstance(escaped, str) or not escaped.isascii():
        raise ValueError("fixture marked_text_unicode_escape must be an ASCII escape string")
    return codecs.decode(escaped.encode("ascii"), "unicode_escape")


def _selector_byte(character):
    codepoint = ord(character)
    if 0xFE00 <= codepoint <= 0xFE0F:
        return codepoint - 0xFE00
    if 0xE0100 <= codepoint <= 0xE01EF:
        return codepoint - 0xE0100 + 16
    return None


def _extract_manifest(text):
    """Decode one Appendix A.8 C2PATextManifestWrapper, or return None."""
    marker = text.find("\ufeff")
    if marker < 0:
        return None

    wrapper = bytearray()
    for character in text[marker + 1 :]:
        value = _selector_byte(character)
        if value is None:
            break
        wrapper.append(value)

    if not wrapper.startswith(MAGIC):
        return None
    header_length = len(MAGIC) + 1 + 1 + 4
    if len(wrapper) < header_length:
        raise ValueError("C2PATextManifestWrapper is truncated")
    if wrapper[len(MAGIC)] != WRAPPER_VERSION:
        raise ValueError("C2PATextManifestWrapper has an unsupported version")
    if wrapper[len(MAGIC) + 1] != BYTE_ENCODING_ALGORITHM:
        raise ValueError("C2PATextManifestWrapper has an unsupported encoding algorithm")

    manifest_length = int.from_bytes(wrapper[len(MAGIC) + 2 : header_length], "big")
    manifest = bytes(wrapper[header_length:])
    if len(manifest) != manifest_length:
        raise ValueError(
            "C2PATextManifestWrapper manifest length does not match its payload"
        )
    return manifest


def _strip_default_ignorables(text):
    return "".join(
        character
        for character in text
        if character != "\ufeff" and _selector_byte(character) is None
    )


def _apply_transform(name, marked_text, source_text):
    transforms = {
        "baseline": lambda: marked_text,
        "utf8_round_trip": lambda: marked_text.encode("utf-8").decode("utf-8"),
        "utf16le_round_trip": lambda: marked_text.encode("utf-16le").decode("utf-16le"),
        "unicode_nfc": lambda: unicodedata.normalize("NFC", marked_text),
        "unicode_nfd": lambda: unicodedata.normalize("NFD", marked_text),
        "json_string_round_trip": lambda: json.loads(
            json.dumps(marked_text, ensure_ascii=True)
        ),
        "exact_unicode_copy": lambda: marked_text[:],
        "aggregation_with_prefix_and_suffix": lambda: (
            "Preface. " + marked_text + " Epilogue."
        ),
        "default_ignorable_stripping": lambda: _strip_default_ignorables(marked_text),
        "fragment_extraction_wrapper_omitted": lambda: source_text,
    }
    try:
        return transforms[name]()
    except KeyError as error:
        raise ValueError(f"no executable transform registered for {name}") from error


def run_checks():
    """Return (executed, skipped, failures) for all matrix rows."""
    try:
        matrix = _load_matrix()
    except (OSError, json.JSONDecodeError) as error:
        return 0, 0, [f"matrix could not be loaded: {error}"]
    matrix_violations = check_registry_and_matrix(matrix=matrix)
    if matrix_violations:
        return 0, 0, [
            f"matrix conformance failed: {violation}"
            for violation in matrix_violations
        ]
    fixture = matrix["fixture"]
    marked_text = _decode_fixture(fixture["marked_text_unicode_escape"])
    expected_manifest = bytes.fromhex(fixture["manifest_hex"])
    expected_digest = fixture["marked_text_utf8_sha256"]
    actual_digest = "sha256:" + hashlib.sha256(marked_text.encode("utf-8")).hexdigest()
    failures = []

    if actual_digest != expected_digest:
        failures.append(
            f"fixture UTF-8 digest mismatch: expected {expected_digest}, got {actual_digest}"
        )
    if not marked_text.startswith(fixture["source_text"]):
        failures.append("fixture marked text does not preserve source_text as its prefix")
    try:
        baseline_manifest = _extract_manifest(marked_text)
    except ValueError as error:
        failures.append(f"fixture wrapper is malformed: {error}")
        baseline_manifest = None
    if baseline_manifest != expected_manifest:
        failures.append("fixture wrapper does not decode to manifest_hex")

    executed = 0
    skipped = 0
    for row in matrix["transforms"]:
        name = row["transform"]
        expected = row["observed_result"]
        if expected == "not_tested":
            print(f"  SKIP  {name} [not_tested]")
            skipped += 1
            continue

        executed += 1
        try:
            transformed = _apply_transform(name, marked_text, fixture["source_text"])
            recovered = _extract_manifest(transformed)
            if recovered is not None and recovered != expected_manifest:
                actual = "manifest_mismatch"
            elif recovered == expected_manifest:
                actual = "association_recovered"
            elif expected == "association_removed_by_definition":
                actual = "association_removed_by_definition"
            else:
                actual = "association_removed"
        except (TypeError, UnicodeError, ValueError) as error:
            failures.append(f"{name}: transform or wrapper decode failed: {error}")
            print(f"  FAIL  {name}")
            continue

        if actual == expected:
            print(f"  PASS  {name}: {actual}")
        else:
            failures.append(f"{name}: expected {expected}, observed {actual}")
            print(f"  FAIL  {name}: expected {expected}, observed {actual}")

    return executed, skipped, failures


def main():
    executed, skipped, failures = run_checks()
    for failure in failures:
        print(f"ERROR: {failure}")
    status = "PASS" if not failures else "FAIL"
    print(
        f"Survivability matrix: {status} "
        f"({executed} executable rows, {skipped} not_tested rows skipped, "
        f"{len(failures)} failures)"
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
