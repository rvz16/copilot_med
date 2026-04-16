from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

FHIR_JSON_MIME = "application/fhir+json"
DEFAULT_BASE_URL = "http://localhost:8092/fhir"
MEDCOPILOT_TAG_SYSTEM = "https://medcopilot.ai/fhir/tags"
MEDCOPILOT_IDENTIFIER_SYSTEM = "https://medcopilot.ai/fhir/identifiers"
NOISE_PREFIXES = (
    "понимаю",
    "давайте",
    "опишите",
    "расскажите",
    "скажите",
    "это ",
    "скорее",
    "как ",
    "и началась",
    "прямая",
    "примая",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete legacy conversational noise and generated SOAP records from a FHIR server."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--patient-id", default="")
    parser.add_argument("--apply", action="store_true", help="Actually delete flagged resources.")
    parser.add_argument("--count", type=int, default=500)
    return parser.parse_args()


def request_json(url: str, method: str = "GET") -> dict[str, Any]:
    request = urllib.request.Request(url, method=method, headers={"Accept": FHIR_JSON_MIME})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.code} {exc.reason}") from exc


def request_no_content(url: str, method: str) -> None:
    request = urllib.request.Request(url, method=method, headers={"Accept": FHIR_JSON_MIME})
    try:
        with urllib.request.urlopen(request, timeout=20):
            return
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.code} {exc.reason}") from exc


def fetch_resources(base_url: str, resource_type: str, count: int) -> list[dict[str, Any]]:
    bundle = request_json(f"{base_url.rstrip('/')}/{resource_type}?_count={count}")
    entries = bundle.get("entry") or []
    return [entry.get("resource", {}) for entry in entries if isinstance(entry, dict)]


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip(" \t\r\n-:.")


def extract_reference_id(resource: dict[str, Any]) -> str | None:
    for key in ("subject", "patient"):
        reference = resource.get(key)
        if not isinstance(reference, dict):
            continue
        raw_reference = reference.get("reference")
        if isinstance(raw_reference, str) and "/" in raw_reference:
            return raw_reference.rsplit("/", 1)[-1]
    return None


def is_medcopilot_generated(resource: dict[str, Any]) -> bool:
    meta = resource.get("meta")
    if isinstance(meta, dict):
        for tag in meta.get("tag") or []:
            if not isinstance(tag, dict):
                continue
            if tag.get("system") == MEDCOPILOT_TAG_SYSTEM:
                return True

    for identifier in resource.get("identifier") or []:
        if not isinstance(identifier, dict):
            continue
        if identifier.get("system") == MEDCOPILOT_IDENTIFIER_SYSTEM:
            return True

    description = clean_text(resource.get("description")).casefold()
    if "structured soap note generated after consultation" in description:
        return True
    if "soap-заметка консультации" in description:
        return True
    return False


def looks_like_conversational_condition(resource: dict[str, Any]) -> bool:
    if resource.get("resourceType") != "Condition":
        return False
    text = clean_text((resource.get("code") or {}).get("text"))
    normalized = text.casefold()
    if not normalized:
        return False
    if "?" in normalized:
        return True
    if any(normalized.startswith(prefix) for prefix in NOISE_PREFIXES):
        return True
    if any(marker in normalized for marker in ("усталост", "сонлив", "сухост", "слабост", "жажд")) and "синдром" not in normalized:
        return True
    return len(normalized.split()) > 9


def should_delete(resource: dict[str, Any], patient_id: str) -> bool:
    resource_patient_id = extract_reference_id(resource)
    if patient_id and resource_patient_id != patient_id:
        return False
    if resource_patient_id == "string":
        return True
    if looks_like_conversational_condition(resource):
        return True
    if resource.get("resourceType") == "DocumentReference" and is_medcopilot_generated(resource):
        return True
    return False


def describe_resource(resource: dict[str, Any]) -> str:
    resource_type = resource.get("resourceType", "Resource")
    resource_id = resource.get("id", "<no-id>")
    text = clean_text(
        (resource.get("code") or {}).get("text")
        or resource.get("valueString")
        or (resource.get("medicationCodeableConcept") or {}).get("text")
        or resource.get("description")
    )
    patient_id = extract_reference_id(resource) or "unknown-patient"
    return f"{resource_type}/{resource_id} patient={patient_id} text={json.dumps(text, ensure_ascii=False)}"


def delete_resource(base_url: str, resource: dict[str, Any]) -> None:
    resource_type = resource.get("resourceType")
    resource_id = resource.get("id")
    if not resource_type or not resource_id:
        return
    request_no_content(f"{base_url.rstrip('/')}/{resource_type}/{resource_id}", method="DELETE")


def main() -> int:
    args = parse_args()
    flagged: list[dict[str, Any]] = []

    for resource_type in ("Condition", "Observation", "MedicationStatement", "AllergyIntolerance", "DocumentReference"):
        for resource in fetch_resources(args.base_url, resource_type, args.count):
            if should_delete(resource, args.patient_id):
                flagged.append(resource)

    if not flagged:
        print("No resources matched cleanup rules.")
        return 0

    print(f"Flagged {len(flagged)} resources:")
    for resource in flagged:
        print(f"- {describe_resource(resource)}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to delete the flagged resources.")
        return 0

    for resource in flagged:
        delete_resource(args.base_url, resource)

    print(f"Deleted {len(flagged)} resources from {args.base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
