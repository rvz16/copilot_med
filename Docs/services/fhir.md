# FHIR Utilities and Local FHIR Server

## Purpose

The `fhir/` folder serves two roles:

1. it defines the local HAPI FHIR container used by the integrated stack
2. it provides helper scripts to fetch live data or generate synthetic fallback data

## What Uses FHIR in This Repository

- `real_time_analysis` reads patient context from FHIR
- `knowledge-extractor` optionally writes extracted artifacts back to FHIR
- the local helper scripts populate the HAPI FHIR instance used by those services

## Main Files

| File | Role |
| --- | --- |
| `Dockerfile` | local HAPI FHIR container image |
| `application.yaml` | HAPI FHIR configuration |
| `fetch_fhir_data.py` | live fetch with synthetic fallback |
| `generate_synthetic_fhir.py` | standalone synthetic patient/observation generation |
| `retrieve_and_import.sh` | end-to-end bootstrap and import helper |
| `output/` | generated/fetched JSON artifacts |

## Local FHIR Container

The root `docker-compose.yml` exposes:

- UI: `http://localhost:8092/`
- FHIR base: `http://localhost:8092/fhir`

Other containers use:

- `http://fhir:8092/fhir`

## Data Bootstrap Options

### Live fetch

`fetch_fhir_data.py` tries to:

- call a live FHIR server
- save patient bundles and observations under `fhir/output/`

### Synthetic fallback

If live fetch fails, the script can generate:

- synthetic patients
- synthetic observations

This makes the rest of the stack testable even when the original lab server is unavailable.

### Import into local FHIR

`retrieve_and_import.sh`:

1. starts the local container
2. waits for `/metadata`
3. runs the fetch/generate step
4. imports resources with `PUT` so resource IDs are preserved

## Output Files

Typical generated artifacts:

- `patients_bundle.json`
- `patient_summaries.json`
- `patient_<id>.json`
- `observations_<id>.json`
- `synthetic_patients_bundle.json`
- `synthetic_observations_<id>.json`

## Repository Role

This folder is not the core application logic, but it is important because it gives the stack a local interoperability target for:

- patient context retrieval
- resource persistence
- offline demos

Without it, the realtime and extraction services can still run, but the FHIR-backed features become limited or unavailable.
