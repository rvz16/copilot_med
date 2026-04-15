# MedCoPilot Repository Documentation

This `Docs/` folder documents the whole repository: what each top-level directory contains, how the services work together, what happens during a live consultation, where data is stored, how the APIs are shaped, and how to run or extend the stack.

## Start Here

1. [Repository Structure](./repository-structure.md)
2. [Runtime Architecture and Flows](./runtime-flows.md)
3. [Setup and Installation](./setup-installation.md)
4. [API Specifications](./api-specifications.md)

## Service Internals

- [Frontend](./services/frontend.md)
- [Session Manager](./services/session-manager.md)
- [Transcribation](./services/transcribation.md)
- [Realtime Analysis](./services/realtime-analysis.md)
- [Knowledge Extractor](./services/knowledge-extractor.md)
- [Post-Session Analytics](./services/post-session-analytics.md)
- [Clinical Recommendations Service](./services/clinical-recommendations.md)
- [FHIR Utilities and Local FHIR Server](./services/fhir.md)

## Operational Reference

- [Integration and Deployment](./integration-deployment.md)
- [Performance Metrics and Observability](./performance-metrics.md)
- [Privacy, Security, and Quality](./privacy-security-quality-report.md)

## External Assets Required by the Repository

### Clinical recommendation PDFs

The repository expects official clinical recommendation PDFs in:

```text
clinical_recommendations/pdf_files/
```

Download them from:

- [Google Drive folder with PDFs](https://drive.google.com/drive/folders/1m0AiEByrTHS7VP8iqhYoppIbBisRsARw?usp=sharing)

Without these files:

- the recommendation metadata service still starts
- list/detail/search endpoints still work
- PDF download endpoints return `404 PDF_NOT_FOUND`

### ASR model credentials

The `transcribation` service downloads its local Whisper model from Kaggle when not using the Groq path. See [Setup and Installation](./setup-installation.md) and [Transcribation](./services/transcribation.md).
