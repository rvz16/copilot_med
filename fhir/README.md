# Local FHIR Service

This directory contains the bundled HAPI FHIR server and the helper scripts used to import live or synthetic data into it.

## URLs

- Host: `http://localhost:8092/fhir`
- Docker network: `http://fhir:8092/fhir`

## Common Tasks

Start only the FHIR container:

```bash
docker compose up -d --build fhir
```

Import synthetic demo data:

```bash
python3 -m pip install -r fhir/requirements.txt
./fhir/retrieve_and_import.sh --force-synthetic
```

Fetch from a live FHIR and save JSON locally:

```bash
python3 fhir/fetch_fhir_data.py --base-url https://example.org/fhir
```

Fetch from a live FHIR and import into the bundled local FHIR:

```bash
python3 fhir/fetch_fhir_data.py \
  --base-url https://example.org/fhir \
  --import-base-url http://localhost:8092/fhir
```

Clean generated demo resources:

```bash
python3 fhir/cleanup_generated_resources.py \
  --base-url http://localhost:8092/fhir \
  --patient-id synthetic-patient-001 \
  --apply
```
