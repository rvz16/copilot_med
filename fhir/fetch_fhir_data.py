from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import requests
from generate_synthetic_fhir import (
    OUTPUT_DIR,
    ensure_output_dir,
    generate_synthetic_data,
    save_json,
)

DEFAULT_BASE_URL = "http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir"
DEFAULT_TIMEOUT = 10
FHIR_JSON_MIME = "application/fhir+json"


class FHIRFetchError(RuntimeError):
    pass


class FHIRImportError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch FHIR patient data with synthetic fallback."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="FHIR base URL used for the live fetch attempt.",
    )
    parser.add_argument(
        "--force-synthetic",
        action="store_true",
        help="Skip live FHIR calls and generate synthetic data immediately.",
    )
    parser.add_argument(
        "--import-base-url",
        help="If set, import fetched or synthetic resources into this FHIR server.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory where JSON files will be written.",
    )
    return parser.parse_args()


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": FHIR_JSON_MIME})
    return session


def request_json(session: requests.Session, url: str) -> dict[str, Any]:
    try:
        response = session.get(url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise FHIRFetchError(f"request failed for {url}: {exc}") from exc
    except ValueError as exc:
        raise FHIRFetchError(f"invalid JSON returned from {url}") from exc


def resource_url(base_url: str, resource_path: str) -> str:
    return f"{base_url.rstrip('/')}/{resource_path.lstrip('/')}"


def check_server_available(session: requests.Session, base_url: str) -> None:
    metadata_url = resource_url(base_url, "metadata")
    request_json(session, metadata_url)


def extract_bundle_resources(
    bundle: dict[str, Any], resource_type: str | None = None
) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for entry in bundle.get("entry") or []:
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue
        if resource_type and resource.get("resourceType") != resource_type:
            continue
        resources.append(resource)
    return resources


def format_patient_name(patient: dict[str, Any]) -> str:
    for name in patient.get("name") or []:
        given = " ".join(name.get("given") or [])
        family = name.get("family") or ""
        full_name = " ".join(part for part in [given, family] if part).strip()
        if full_name:
            return full_name
    return "Unknown"


def extract_patient_summaries(patient_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for patient in extract_bundle_resources(patient_bundle, "Patient"):
        summaries.append(
            {
                "id": patient.get("id"),
                "name": format_patient_name(patient),
                "gender": patient.get("gender"),
                "birthDate": patient.get("birthDate"),
            }
        )
    return summaries


def print_patient_summaries(summaries: list[dict[str, Any]]) -> None:
    if not summaries:
        print("no patient summaries available")
        return

    print("patients:")
    for summary in summaries:
        print(f"- {summary.get('id')}: {summary.get('name')}")


def print_synthetic_summary(result: dict[str, Any]) -> None:
    print(
        f"synthetic fallback saved {len(result['patient_summaries'])} patients and "
        f"{result.get('condition_bundle', {}).get('total', 0)} conditions and "
        f"{result['observation_bundle'].get('total', 0)} observations and "
        f"{result.get('medication_bundle', {}).get('total', 0)} medications"
    )
    print(f"selected patient id: {result['selected_patient_id']}")


def select_patient_id(summaries: list[dict[str, Any]]) -> str:
    for summary in summaries:
        patient_id = summary.get("id")
        if patient_id:
            return patient_id
    raise FHIRFetchError("live patient bundle did not contain a patient id")


def fetch_live_data(base_url: str, output_dir: Path) -> dict[str, Any]:
    output_dir = ensure_output_dir(output_dir)
    session = build_session()
    check_server_available(session, base_url)

    patient_bundle = request_json(session, resource_url(base_url, "Patient?_count=5"))
    save_json(output_dir / "patients_bundle.json", patient_bundle)

    patient_summaries = extract_patient_summaries(patient_bundle)
    if not patient_summaries:
        raise FHIRFetchError(
            "live patient bundle did not contain any Patient resources"
        )
    save_json(output_dir / "patient_summaries.json", patient_summaries)

    print_patient_summaries(patient_summaries)

    selected_patient_id = select_patient_id(patient_summaries)
    print(f"selected patient id: {selected_patient_id}")

    selected_patient = request_json(
        session, resource_url(base_url, f"Patient/{selected_patient_id}")
    )
    save_json(output_dir / f"patient_{selected_patient_id}.json", selected_patient)

    condition_bundle = request_json(
        session,
        resource_url(base_url, f"Condition?patient={selected_patient_id}&_count=10"),
    )
    save_json(output_dir / f"conditions_{selected_patient_id}.json", condition_bundle)

    observation_bundle = request_json(
        session,
        resource_url(base_url, f"Observation?patient={selected_patient_id}&_count=10"),
    )
    save_json(
        output_dir / f"observations_{selected_patient_id}.json", observation_bundle
    )
    medication_bundle = request_json(
        session,
        resource_url(base_url, f"MedicationStatement?patient={selected_patient_id}&_count=10"),
    )
    save_json(output_dir / f"medications_{selected_patient_id}.json", medication_bundle)
    allergy_bundle = request_json(
        session,
        resource_url(base_url, f"AllergyIntolerance?patient={selected_patient_id}&_count=10"),
    )
    save_json(output_dir / f"allergies_{selected_patient_id}.json", allergy_bundle)

    return {
        "mode": "live",
        "patient_bundle": patient_bundle,
        "patient_summaries": patient_summaries,
        "selected_patient_id": selected_patient_id,
        "selected_patient": selected_patient,
        "condition_bundle": condition_bundle,
        "observation_bundle": observation_bundle,
        "medication_bundle": medication_bundle,
        "allergy_bundle": allergy_bundle,
    }


def collect_resources_for_import(result: dict[str, Any]) -> list[dict[str, Any]]:
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}

    for resource in extract_bundle_resources(result["patient_bundle"], "Patient"):
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if resource_type and resource_id:
            by_identity[(resource_type, resource_id)] = resource

    selected_patient = result.get("selected_patient")
    if isinstance(selected_patient, dict):
        resource_type = selected_patient.get("resourceType")
        resource_id = selected_patient.get("id")
        if resource_type and resource_id:
            by_identity[(resource_type, resource_id)] = selected_patient

    for resource in extract_bundle_resources(
        result["observation_bundle"], "Observation"
    ):
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if resource_type and resource_id:
            by_identity[(resource_type, resource_id)] = resource

    condition_bundle = result.get("condition_bundle")
    if isinstance(condition_bundle, dict):
        for resource in extract_bundle_resources(condition_bundle, "Condition"):
            resource_type = resource.get("resourceType")
            resource_id = resource.get("id")
            if resource_type and resource_id:
                by_identity[(resource_type, resource_id)] = resource

    for bundle_key, resource_type in (
        ("medication_bundle", "MedicationStatement"),
        ("allergy_bundle", "AllergyIntolerance"),
    ):
        bundle = result.get(bundle_key)
        if not isinstance(bundle, dict):
            continue
        for resource in extract_bundle_resources(bundle, resource_type):
            resource_id = resource.get("id")
            if resource_id:
                by_identity[(resource_type, resource_id)] = resource

    return list(by_identity.values())


def import_resources(base_url: str, resources: list[dict[str, Any]]) -> dict[str, int]:
    session = build_session()
    session.headers.update({"Content-Type": FHIR_JSON_MIME})
    imported = 0
    skipped = 0

    try:
        request_json(session, resource_url(base_url, "metadata"))
    except FHIRFetchError as exc:
        raise FHIRImportError(
            f"local FHIR server is unavailable at {base_url}: {exc}"
        ) from exc

    for resource in resources:
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if not resource_type or not resource_id:
            skipped += 1
            continue

        try:
            response = session.put(
                resource_url(base_url, f"{resource_type}/{resource_id}"),
                json=resource,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            imported += 1
        except requests.RequestException as exc:
            raise FHIRImportError(
                f"failed to import {resource_type}/{resource_id} into {base_url}: {exc}"
            ) from exc

    return {"imported": imported, "skipped": skipped}


def main() -> int:
    args = parse_args()
    output_dir = ensure_output_dir(args.output_dir)

    if args.force_synthetic:
        print("live fetch skipped because --force-synthetic was set")
        result = generate_synthetic_data(output_dir=output_dir)
        print_synthetic_summary(result)
    else:
        try:
            result = fetch_live_data(args.base_url, output_dir)
            print(
                f"live fetch saved {len(result['patient_summaries'])} patients and "
                f"{result.get('condition_bundle', {}).get('total', 0)} conditions and "
                f"{result['observation_bundle'].get('total', 0)} observations and "
                f"{result.get('medication_bundle', {}).get('total', 0)} medications"
            )
        except FHIRFetchError as exc:
            print(f"live fetch failed: {exc}")
            print("switching to synthetic fallback data")
            result = generate_synthetic_data(output_dir=output_dir)
            print_synthetic_summary(result)

    if args.import_base_url:
        resources = collect_resources_for_import(result)
        try:
            import_summary = import_resources(args.import_base_url, resources)
        except FHIRImportError as exc:
            print(f"import failed: {exc}")
            print(f"mode: {result['mode']}")
            return 1

        print(
            f"imported {import_summary['imported']} resources into {args.import_base_url}"
            + (
                f", skipped {import_summary['skipped']}"
                if import_summary["skipped"]
                else ""
            )
        )

    print(f"mode: {result['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
