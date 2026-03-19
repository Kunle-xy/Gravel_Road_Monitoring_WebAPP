# GravelRoad Iowa - Pavement Distress Analysis

Web app for analyzing gravel road conditions using DEM data. Automated rut detection, interactive map visualization, and report generation.

**Author**: Kunle Oguntoye, PhD Student, Iowa State University (oguntoye@iastate.edu)

## Architecture

Three-server hybrid deployment:

| Component | Server | Details |
|-----------|--------|---------|
| Next.js frontend | Vercel | https://webapp-mu-puce.vercel.app |
| FastAPI + PostgreSQL + Redis | EC2 (52.15.33.164) | API, auth, task queue |
| Celery workers (tile + rut) | ISU server (129.186.252.201) | GPU processing |

**AWS services**: S3 (raw uploads + tiles), CloudFront CDN (tile serving), SES (email)

## Project Structure

```
GravelRoad_Iowa/
├── FastAPI/           # Backend API (see FastAPI/README.md)
│   ├── app/
│   │   ├── routers/   # API endpoints
│   │   ├── workers/   # Celery tasks (tile + rut)
│   │   ├── models.py  # DB models
│   │   └── config.py  # Settings
│   └── fastapi.service
├── webapp/            # Next.js frontend (see webapp/README.md)
└── docs/              # Deployment and ops docs
```

## Key Workflows

1. **Upload**: Browser uploads TIFF directly to S3 via presigned URL (bypasses server limits)
2. **Processing**: Celery worker on ISU converts to COG, generates tiles, uploads to S3
3. **Viewing**: Browser loads tiles from CloudFront CDN onto Leaflet map
4. **Rut Analysis**: User draws polygon, ISU worker runs detection, generates HTML/PDF reports

## Docs

See `docs/` for deployment, operations, and configuration details.
