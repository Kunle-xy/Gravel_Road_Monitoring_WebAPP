# GravelRoad Iowa - Pavement Distress Analysis

Web app for analyzing gravel road conditions using DEM data. Automated rut, crown, and corrugation detection, interactive map visualization, and report generation.

**Author**: Kunle Oguntoye, PhD Student, Iowa State University (oguntoye@iastate.edu)

## Architecture

Two-server deployment with Cloudflare Tunnel (no open ports on ISU):

| Component | Server | Details |
|-----------|--------|---------|
| Next.js frontend | Vercel | https://webapp-mu-puce.vercel.app |
| FastAPI + PostgreSQL + Redis + Celery | ISU server | All services on localhost |
| Cloudflare Tunnel | ISU server → Cloudflare | https://api.prosper-gravelroad.com |

**AWS services**: S3 (raw uploads + tiles), CloudFront CDN (tile serving), SES (email)

```
Browser → Vercel (frontend)
            │
            │ /api/* rewrite
            ▼
       Cloudflare Tunnel (HTTPS)
       api.prosper-gravelroad.com
            │
            ▼
       ISU Server (localhost)
       ├── FastAPI :8000
       ├── PostgreSQL :5432
       ├── Redis :6379
       ├── Celery tile worker (-c 4)
       └── Celery analysis worker (-c 3)
```

## Project Structure

```
GravelRoad_Iowa/
├── FastAPI/              # Backend API (see FastAPI/README.md)
│   ├── app/
│   │   ├── routers/      # API endpoints (auth, upload, files, folders, tiles, rut, crown, corrugation)
│   │   ├── workers/      # Celery tasks
│   │   │   ├── tile_worker.py
│   │   │   ├── rut/      # Rut distress detection + reports
│   │   │   ├── crown/    # Crown distress detection + reports
│   │   │   └── corrugation/  # Corrugation detection + reports
│   │   ├── models.py     # DB models (7 tables)
│   │   ├── config.py     # Settings from .env
│   │   ├── auth.py       # JWT + password hashing
│   │   ├── celery_app.py # Celery config + task routing
│   │   └── database.py   # PostgreSQL connection
│   └── pyproject.toml    # UV dependencies
├── webapp/               # Next.js frontend (see webapp/README.md)
│   ├── app/
│   │   ├── components/   # React components (map, forms, sidebar)
│   │   ├── contexts/     # Auth, map, polygon, distress state
│   │   ├── dashboard/    # Map view + upload page + distress pages
│   │   └── lib/          # API client
│   └── next.config.ts    # API rewrite to Cloudflare Tunnel
└── docs/                 # Deployment and ops docs
```

## Key Workflows

1. **Upload**: Browser uploads TIFF directly to S3 via presigned URL (bypasses server limits). Multipart chunking for files >100MB.
2. **Processing**: Celery worker converts to COG, generates XYZ tile pyramid (zoom 15-21, WebP), uploads to S3.
3. **Viewing**: Browser loads tiles from CloudFront CDN onto Leaflet map.
4. **Distress Analysis**: User draws polygon on map, Celery worker runs detection (rut, crown, or corrugation), generates HTML/PDF reports.

## Distress Analysis Types

| Type | Measures | Severity Units | Output |
|------|----------|---------------|--------|
| **Rut** | Depth (inches) | Area (sq ft) | HTML plot + PDF report |
| **Crown** | Camber distress | Linear feet | HTML report |
| **Corrugation** | Washboarding depth | Area (sq ft) | HTML report |

All use Iowa DOT severity thresholds: Low (<1"), Medium (1-3"), High (>3").

## Docs

- [`docs/ADMIN_HANDOFF.md`](docs/ADMIN_HANDOFF.md) — Complete administrator handoff and fresh-server tutorial, including PostgreSQL, Redis, AWS, Cloudflare, systemd, frontend hosting, data transfer, and backups.
- `docs/deployment.md` — Server setup, services, AWS config
- `docs/operations.md` — Common tasks, troubleshooting, monitoring
