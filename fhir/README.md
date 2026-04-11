# Local FHIR service

This folder contains the local HAPI FHIR R4 server plus helper scripts for pulling test data from the lab FHIR instance and importing it into the local Docker-backed database.

## Service URLs

After startup:

- UI: `http://localhost:8092/`
- FHIR base URL: `http://localhost:8092/fhir`
- Capability statement: `http://localhost:8092/fhir/metadata`

Inside Docker Compose, other containers should use:

- `http://fhir:8092/fhir`

## Files in this folder

- `fetch_fhir_data.py`: tries the lab server first, saves live JSON, and falls back to synthetic FHIR data if the lab server is unavailable
- `generate_synthetic_fhir.py`: generates standalone synthetic Patient and Observation JSON
- `retrieve_and_import.sh`: starts the local HAPI container, waits for it to be ready, then runs the fetch script and imports the resulting resources into the local FHIR database
- `requirements.txt`: minimal Python dependency list for the helper scripts
- `output/`: saved JSON artifacts

## Python setup

Install the helper dependency:

```powershell
python -m pip install -r .\fhir\requirements.txt
```

## Start only the local FHIR server

```powershell
docker compose up -d --build fhir
```

## Retrieve data without importing

This tries the lab server at ``. If that server fails, the script writes synthetic fallback data instead.

```powershell
python .\fhir\fetch_fhir_data.py
```

Useful flags:

- `--force-synthetic` to skip live calls entirely
- `--base-url` to override the lab FHIR endpoint
- `--import-base-url` to write the fetched or synthetic resources into another FHIR server

Example:

```powershell
python .\fhir\fetch_fhir_data.py --force-synthetic --import-base-url http://localhost:8092/fhir
```

## One-command retrieve and import

The shell helper is intended for Git Bash, WSL, or Linux/macOS shells. It starts the local FHIR container, waits for `/metadata`, then imports Patients and Observations with `PUT` so their original IDs are preserved.

```bash
./fhir/retrieve_and_import.sh
```

You can override the target local server with `LOCAL_FHIR_BASE_URL` or the Python interpreter with `PYTHON_BIN`.

## Output files

After running the scripts, `fhir/output/` contains:

- `patients_bundle.json`
- `patient_summaries.json`
- `patient_<id>.json`
- `observations_<id>.json`
- `synthetic_patients_bundle.json` when synthetic mode is used
- `synthetic_observations_<id>.json` when synthetic mode is used

The fetch script always prints which mode was used: `live` or `synthetic`.

## Quick API checks

Read server metadata:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8092/fhir/metadata"
```

Search patients:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8092/fhir/Patient"
```

## Notes

- The first startup can take a little time while the HAPI container initializes.
- The container runs as `root` in Compose so the mounted `fhir-data` volume is writable for the embedded H2 database.
- The main Compose file points `realtime-analysis` to this local FHIR service by default.
- To fully reset stored FHIR data, stop the stack and remove the `fhir-data` Docker volume.
- Replace BASE URL in the fetch_fhir_data.py for actual server with data that also provides fhir interface