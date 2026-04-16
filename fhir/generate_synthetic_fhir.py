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


def build_condition_resource(
    condition_id: str,
    patient_id: str,
    snomed_code: str,
    display: str,
    onset_datetime: str,
    recorded_date: str,
) -> dict[str, Any]:
    return {
        "resourceType": "Condition",
        "id": condition_id,
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "resolved",
                    "display": "Resolved",
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "confirmed",
                    "display": "Confirmed",
                }
            ]
        },
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                        "code": "problem-list-item",
                        "display": "Problem List Item",
                    }
                ],
                "text": "Problem List Item",
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": snomed_code,
                    "display": display,
                }
            ],
            "text": display,
        },
        "subject": {
            "reference": f"Patient/{patient_id}",
        },
        "onsetDateTime": onset_datetime,
        "recordedDate": recorded_date,
    }


def build_observation_resource(
    observation_id: str,
    patient_id: str,
    loinc_code: str,
    display: str,
    effective_datetime: str,
    value: float | str,
    unit: str | None = None,
    unit_code: str | None = None,
) -> dict[str, Any]:
    resource = {
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
    }

    if isinstance(value, str):
        resource["valueString"] = value
        return resource

    if unit is None or unit_code is None:
        raise ValueError("numeric observations require unit and unit_code")

    resource["valueQuantity"] = {
        "value": value,
        "unit": unit,
        "system": "http://unitsofmeasure.org",
        "code": unit_code,
    }
    return resource


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


def build_patient_seed_data() -> list[dict[str, Any]]:
    return [
        {
            "patient": build_patient_resource(
                "synthetic-patient-001",
                ["Elena"],
                "Morozova",
                "female",
                "1988-02-14",
            ),
            "conditions": [
                build_condition_resource(
                    "synthetic-condition-001",
                    "synthetic-patient-001",
                    "59621000",
                    "Essential hypertension",
                    "2019-05-11T00:00:00Z",
                    "2025-12-12",
                )
            ],
            "observations": [
                build_observation_resource(
                    "synthetic-observation-001-bp",
                    "synthetic-patient-001",
                    "85354-9",
                    "Blood pressure panel with all children optional",
                    "2026-04-10T08:15:00Z",
                    "Blood pressure 128/82 mmHg",
                ),
                build_observation_resource(
                    "synthetic-observation-001-glucose",
                    "synthetic-patient-001",
                    "2345-7",
                    "Glucose [Mass/volume] in Serum or Plasma",
                    "2026-02-18T09:00:00Z",
                    "Fasting glucose 96 mg/dL",
                ),
            ],
        },
        {
            "patient": build_patient_resource(
                "synthetic-patient-002",
                ["Ivan"],
                "Petrov",
                "male",
                "1975-09-03",
            ),
            "conditions": [
                build_condition_resource(
                    "synthetic-condition-002",
                    "synthetic-patient-002",
                    "44054006",
                    "Type 2 diabetes mellitus",
                    "2018-03-20T00:00:00Z",
                    "2025-11-05",
                )
            ],
            "observations": [
                build_observation_resource(
                    "synthetic-observation-002-a1c",
                    "synthetic-patient-002",
                    "4548-4",
                    "Hemoglobin A1c/Hemoglobin.total in Blood",
                    "2026-03-14T07:45:00Z",
                    "HbA1c 7.1%",
                ),
                build_observation_resource(
                    "synthetic-observation-002-ldl",
                    "synthetic-patient-002",
                    "13457-7",
                    "Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation",
                    "2026-01-20T07:45:00Z",
                    "LDL cholesterol 142 mg/dL",
                ),
            ],
        },
        {
            "patient": build_patient_resource(
                "synthetic-patient-003",
                ["Anna"],
                "Sokolova",
                "female",
                "1994-06-22",
            ),
            "conditions": [
                build_condition_resource(
                    "synthetic-condition-003",
                    "synthetic-patient-003",
                    "37796009",
                    "Migraine without aura",
                    "2021-08-09T00:00:00Z",
                    "2025-10-22",
                )
            ],
            "observations": [
                build_observation_resource(
                    "synthetic-observation-003-headache",
                    "synthetic-patient-003",
                    "75325-1",
                    "Headache severity",
                    "2026-04-01T18:00:00Z",
                    "Reported headaches 3 times in the last month",
                ),
                build_observation_resource(
                    "synthetic-observation-003-bp",
                    "synthetic-patient-003",
                    "85354-9",
                    "Blood pressure panel with all children optional",
                    "2026-01-08T08:40:00Z",
                    "Blood pressure 114/72 mmHg",
                ),
            ],
        },
        {
            "patient": build_patient_resource(
                "synthetic-patient-004",
                ["Maksim"],
                "Volkov",
                "male",
                "1981-11-30",
            ),
            "conditions": [
                build_condition_resource(
                    "synthetic-condition-004",
                    "synthetic-patient-004",
                    "195967001",
                    "Mild intermittent asthma",
                    "2016-04-17T00:00:00Z",
                    "2025-09-14",
                )
            ],
            "observations": [
                build_observation_resource(
                    "synthetic-observation-004-pef",
                    "synthetic-patient-004",
                    "33453-9",
                    "Expiratory flow peak",
                    "2026-03-28T11:10:00Z",
                    "Peak expiratory flow 410 L/min",
                ),
                build_observation_resource(
                    "synthetic-observation-004-oxygen",
                    "synthetic-patient-004",
                    "59408-5",
                    "Oxygen saturation in Arterial blood by Pulse oximetry",
                    "2026-03-28T11:10:00Z",
                    "Oxygen saturation 98% on room air",
                ),
            ],
        },
        {
            "patient": build_patient_resource(
                "synthetic-patient-005",
                ["Olga"],
                "Smirnova",
                "female",
                "1969-04-09",
            ),
            "conditions": [
                build_condition_resource(
                    "synthetic-condition-005",
                    "synthetic-patient-005",
                    "235595009",
                    "Gastroesophageal reflux disease",
                    "2017-01-23T00:00:00Z",
                    "2025-08-30",
                )
            ],
            "observations": [
                build_observation_resource(
                    "synthetic-observation-005-weight",
                    "synthetic-patient-005",
                    "29463-7",
                    "Body weight",
                    "2026-02-09T10:20:00Z",
                    "Body weight 82 kg",
                ),
                build_observation_resource(
                    "synthetic-observation-005-bp",
                    "synthetic-patient-005",
                    "85354-9",
                    "Blood pressure panel with all children optional",
                    "2026-02-09T10:20:00Z",
                    "Blood pressure 134/84 mmHg",
                ),
            ],
        },
    ]


def generate_synthetic_data(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir = ensure_output_dir(output_dir)
    seed_data = build_patient_seed_data()
    patients = [entry["patient"] for entry in seed_data]
    conditions = [
        resource for entry in seed_data for resource in entry.get("conditions", [])
    ]
    observations = [
        resource for entry in seed_data for resource in entry.get("observations", [])
    ]
    patient_bundle = make_bundle("synthetic-patients", "collection", patients)
    condition_bundle = make_bundle("synthetic-conditions", "collection", conditions)
    observation_bundle = make_bundle("synthetic-observations", "collection", observations)

    selected_patient = patients[0]
    selected_patient_id = selected_patient["id"]
    patient_summaries = build_patient_summaries(patients)

    save_json(output_dir / "synthetic_patients_bundle.json", patient_bundle)
    save_json(output_dir / "patients_bundle.json", patient_bundle)
    save_json(output_dir / "synthetic_conditions_bundle.json", condition_bundle)
    save_json(output_dir / "conditions_bundle.json", condition_bundle)
    save_json(output_dir / "patient_summaries.json", patient_summaries)

    for entry in seed_data:
        patient = entry["patient"]
        patient_id = patient["id"]
        patient_observation_bundle = make_bundle(
            f"synthetic-observations-{patient_id}",
            "collection",
            entry.get("observations", []),
        )
        patient_condition_bundle = make_bundle(
            f"synthetic-conditions-{patient_id}",
            "collection",
            entry.get("conditions", []),
        )
        save_json(output_dir / f"patient_{patient_id}.json", patient)
        save_json(
            output_dir / f"synthetic_observations_{patient_id}.json",
            patient_observation_bundle,
        )
        save_json(
            output_dir / f"observations_{patient_id}.json", patient_observation_bundle
        )
        save_json(
            output_dir / f"synthetic_conditions_{patient_id}.json",
            patient_condition_bundle,
        )
        save_json(output_dir / f"conditions_{patient_id}.json", patient_condition_bundle)

    return {
        "mode": "synthetic",
        "patient_bundle": patient_bundle,
        "patient_summaries": patient_summaries,
        "selected_patient_id": selected_patient_id,
        "selected_patient": selected_patient,
        "observation_bundle": observation_bundle,
        "condition_bundle": condition_bundle,
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
        f"{result['condition_bundle']['total']} conditions and "
        f"{result['observation_bundle']['total']} observations; "
        "recommended test patient is "
        f"{result['selected_patient_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
