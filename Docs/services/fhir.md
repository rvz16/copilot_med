# FHIR

## Purpose

The `fhir/` directory contains:

1. the bundled HAPI FHIR server used by the root Docker Compose stack
2. helper scripts for importing live or synthetic data
3. cleanup tooling for MedCoPilot-generated demo artifacts

## Runtime Role

- `realtime-analysis` reads patient context from FHIR
- `knowledge-extractor` can write extracted artifacts back to FHIR
- the root stack defaults both services to the bundled local FHIR unless overridden

## Host Access

In the shipped root stack:

- FHIR base URL: `http://localhost:8092/fhir`
- Capability statement: `http://localhost:8092/fhir/metadata`

Inside Docker Compose, other containers use:

- `http://fhir:8092/fhir`

## Important Files

| File | Role |
| --- | --- |
| `Dockerfile` | HAPI FHIR image |
| `application.yaml` | HAPI configuration |
| `fetch_fhir_data.py` | fetch live data with synthetic fallback |
| `generate_synthetic_fhir.py` | generate synthetic demo resources |
| `retrieve_and_import.sh` | start local FHIR and import live or synthetic data |
| `cleanup_generated_resources.py` | remove MedCoPilot-generated legacy data |
| `output/` | saved JSON artifacts |

## Import Synthetic Demo Data

The bundled local FHIR starts empty. To preload synthetic sample patients:

```bash
python3 -m pip install -r fhir/requirements.txt
./fhir/retrieve_and_import.sh --force-synthetic
```

After import, sample patient IDs include:

- `synthetic-patient-001`
- `synthetic-patient-002`
- `synthetic-patient-003`
- `synthetic-patient-004`
- `synthetic-patient-005`

## Import From A Live FHIR

To fetch from a live endpoint first and fall back to synthetic data only if that fetch fails:

```bash
python3 fhir/fetch_fhir_data.py --base-url https://example.org/fhir
```

To import fetched data into the bundled local FHIR:

```bash
python3 fhir/fetch_fhir_data.py \
  --base-url https://example.org/fhir \
  --import-base-url http://localhost:8092/fhir
```

## Switch The Application To An External FHIR

Set these root `.env` variables:

```bash
MEDCOPILOT_FHIR_BASE_URL=https://example.org/fhir
MEDCOPILOT_FHIR_HEADERS_JSON='{"Authorization":"Bearer <token>"}'
MEDCOPILOT_FHIR_VERIFY_SSL=true
```

If only one service should be redirected, use the per-service overrides instead:

- `REALTIME_ANALYSIS_FHIR_*`
- `KNOWLEDGE_EXTRACTOR_FHIR_*`

## Clean Generated Demo Resources

If an earlier demo run wrote noisy generated content, clean it with:

```bash
python3 fhir/cleanup_generated_resources.py \
  --base-url http://localhost:8092/fhir \
  --patient-id synthetic-patient-001 \
  --apply
```

The cleanup tool targets MedCoPilot-generated conversational artifacts and older generated SOAP documents.
