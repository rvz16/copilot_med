from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def ensure_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_patient_resource(
    patient_id: str,
    given_names: list[str],
    family_name: str,
    gender: str,
    birth_date: str,
) -> dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "active": True,
        "name": [
            {
                "use": "official",
                "family": family_name,
                "given": given_names,
            }
        ],
        "gender": gender,
        "birthDate": birth_date,
    }


def build_observation_resource(
    observation_id: str,
    patient_id: str,
    loinc_code: str,
    display: str,
    value: float,
    unit: str,
    unit_code: str,
    effective_datetime: str,
) -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": loinc_code,
                    "display": display,
                }
            ],
            "text": display,
        },
        "subject": {
            "reference": f"Patient/{patient_id}",
        },
        "effectiveDateTime": effective_datetime,
        "valueQuantity": {
            "value": value,
            "unit": unit,
            "system": "http://unitsofmeasure.org",
            "code": unit_code,
        },
    }


def make_bundle(
    bundle_id: str, bundle_type: str, resources: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": bundle_type,
        "total": len(resources),
        "entry": [{"resource": resource} for resource in resources],
    }


def patient_display_name(patient: dict[str, Any]) -> str:
    names = patient.get("name") or []
    if not names:
        return "Unknown"

    name = names[0]
    given = " ".join(name.get("given") or [])
    family = name.get("family") or ""
    full_name = " ".join(part for part in [given, family] if part).strip()
    return full_name or "Unknown"


def build_patient_summaries(patients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for patient in patients:
        summaries.append(
            {
                "id": patient.get("id"),
                "name": patient_display_name(patient),
                "gender": patient.get("gender"),
                "birthDate": patient.get("birthDate"),
            }
        )
    return summaries


def generate_synthetic_data(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir = ensure_output_dir(output_dir)

    patients = [
        build_patient_resource(
            "synthetic-patient-001", ["Elena"], "Morozova", "female", "1988-02-14"
        ),
        build_patient_resource(
            "synthetic-patient-002", ["Ivan"], "Petrov", "male", "1975-09-03"
        ),
        build_patient_resource(
            "synthetic-patient-003", ["Anna"], "Sokolova", "female", "1994-06-22"
        ),
        build_patient_resource(
            "synthetic-patient-004", ["Maksim"], "Volkov", "male", "1981-11-30"
        ),
        build_patient_resource(
            "synthetic-patient-005", ["Olga"], "Smirnova", "female", "1969-04-09"
        ),
    ]
    patient_bundle = make_bundle("synthetic-patients", "collection", patients)

    selected_patient = patients[0]
    selected_patient_id = selected_patient["id"]
    observations = [
        build_observation_resource(
            "synthetic-observation-glucose-001",
            selected_patient_id,
            "2345-7",
            "Glucose [Mass/volume] in Serum or Plasma",
            96.0,
            "mg/dL",
            "mg/dL",
            "2026-04-10T08:15:00Z",
        ),
        build_observation_resource(
            "synthetic-observation-hemoglobin-001",
            selected_patient_id,
            "718-7",
            "Hemoglobin [Mass/volume] in Blood",
            13.8,
            "g/dL",
            "g/dL",
            "2026-04-10T08:20:00Z",
        ),
        build_observation_resource(
            "synthetic-observation-creatinine-001",
            selected_patient_id,
            "2160-0",
            "Creatinine [Mass/volume] in Serum or Plasma",
            0.92,
            "mg/dL",
            "mg/dL",
            "2026-04-10T08:25:00Z",
        ),
    ]
    observation_bundle = make_bundle(
        "synthetic-observations", "collection", observations
    )
    patient_summaries = build_patient_summaries(patients)

    save_json(output_dir / "synthetic_patients_bundle.json", patient_bundle)
    save_json(output_dir / "patients_bundle.json", patient_bundle)
    save_json(output_dir / "patient_summaries.json", patient_summaries)
    save_json(output_dir / f"patient_{selected_patient_id}.json", selected_patient)
    save_json(
        output_dir / f"synthetic_observations_{selected_patient_id}.json",
        observation_bundle,
    )
    save_json(
        output_dir / f"observations_{selected_patient_id}.json", observation_bundle
    )

    return {
        "mode": "synthetic",
        "patient_bundle": patient_bundle,
        "patient_summaries": patient_summaries,
        "selected_patient_id": selected_patient_id,
        "selected_patient": selected_patient,
        "observation_bundle": observation_bundle,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic FHIR Patient and Observation data."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory where generated JSON files will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = generate_synthetic_data(output_dir=args.output_dir)
    print("mode: synthetic")
    print(
        "generated "
        f"{result['patient_bundle']['total']} patients and "
        f"{result['observation_bundle']['total']} observations for "
        f"{result['selected_patient_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
