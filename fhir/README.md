# Local FHIR service

This folder contains a local HAPI FHIR R4 server for development and testing.

## What it gives you

- FHIR REST API
- Built-in browser interface
- Persistent local storage in the Docker volume `fhir-data`

## Service URLs

After startup:

- UI: `http://localhost:8092/`
- FHIR base URL: `http://localhost:8092/fhir`
- Capability statement: `http://localhost:8092/fhir/metadata`

Inside Docker Compose, other containers should use:

- `http://fhir:8092/fhir`

## Start

Run only the FHIR server:

```powershell
docker compose up -d --build fhir
```

Run the full stack:

```powershell
docker compose up -d --build
```

## Stop

```powershell
docker compose stop fhir
```

## Open the interface

Open `http://localhost:8092/` in the browser.

The HAPI page lets you:

- inspect server status
- open the built-in FHIR tester
- browse the endpoint manually

## Quick API checks

Read server metadata:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8092/fhir/metadata"
```

Create a patient:

```powershell
$body = @{
  resourceType = "Patient"
  active = $true
  name = @(
    @{
      family = "Doe"
      given = @("Jane")
    }
  )
  gender = "female"
  birthDate = "1990-01-01"
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8092/fhir/Patient" `
  -ContentType "application/fhir+json" `
  -Body $body
```

Search patients:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8092/fhir/Patient"
```

## Notes

- The first startup can take a little time while the HAPI container initializes.
- The container runs as `root` in Compose so the mounted `fhir-data` volume is writable for the embedded H2 database.
- The main Compose file now points `realtime-analysis` to this local FHIR service by default.
- To fully reset stored FHIR data, stop the stack and remove the `fhir-data` Docker volume.
