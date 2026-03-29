# Deployment Guide

## Server Map

| Role | Host | What runs |
|------|------|-----------|
| Frontend | Vercel (webapp-mu-puce.vercel.app) | Next.js 16 |
| API + DB + Redis + Workers | ISU server (129.186.252.201) | FastAPI, PostgreSQL 16, Redis 7, Celery |
| Tunnel | Cloudflare (api.prosper-gravelroad.com) | Encrypted tunnel to ISU |

## ISU Server Setup

### Systemd Services

All services auto-start on boot and auto-restart on crash:

```bash
sudo systemctl status fastapi          # FastAPI API (port 8000, localhost only)
sudo systemctl status celery-tiles     # Celery tile worker (-c 4)
sudo systemctl status celery-analysis  # Celery analysis worker (-c 3)
sudo systemctl status cloudflared      # Cloudflare Tunnel
sudo systemctl status postgresql       # PostgreSQL (port 5432, localhost only)
sudo systemctl status redis-server     # Redis (port 6379, localhost only)
```

### Service Files

- `/etc/systemd/system/fastapi.service` — Uvicorn on 127.0.0.1:8000
- `/etc/systemd/system/celery-tiles.service` — Tile generation queue
- `/etc/systemd/system/celery-analysis.service` — Rut/crown/corrugation queue
- `/etc/systemd/system/cloudflared.service` — Tunnel agent

### Network

**No inbound ports are open.** All external access goes through the Cloudflare Tunnel.

- PostgreSQL: bound to localhost only
- Redis: bound to localhost, password protected
- FastAPI: bound to 127.0.0.1 only
- Cloudflare Tunnel: outbound connection from ISU to Cloudflare edge

### Cloudflare Tunnel

- Tunnel name: `gravel-road`
- Tunnel ID: `2ae92001-f00d-48f1-b121-d71a92cb90d8`
- Domain: `api.prosper-gravelroad.com`
- Config: `/etc/cloudflared/config.yml`
- Credentials: `/etc/cloudflared/2ae92001-f00d-48f1-b121-d71a92cb90d8.json`

### Python Environment

Managed with **UV** (not pip):

```bash
cd ~/GravelRoad_Iowa/FastAPI
uv add <package>         # add dependency
uv run uvicorn ...       # run with venv
uv run celery ...        # run with venv
```

### Connection Strings (all localhost)

```
PostgreSQL: postgresql://kunle_admin:PASSWORD@localhost:5432/gravel_road_app
Redis:      redis://:PASSWORD@localhost:6379/0
```

## AWS Resources

| Resource | Value |
|----------|-------|
| Region | us-east-2 |
| S3 raw bucket | gravel-road-raw-file |
| S3 tiles bucket | gravel-road-app-file |
| CloudFront | d18o6mwudgwpmq.cloudfront.net |
| Domain | prosper-gravelroad.com (Cloudflare registrar) |

S3 CORS is configured on `gravel-road-raw-file` to allow browser PUT uploads from Vercel origins.

AWS credentials: set via `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env` (no IAM role — not on EC2).

## Vercel

Deploys automatically on push to `main`. Environment variables set in Vercel dashboard:

- `NEXT_PUBLIC_API_URL` = `https://api.prosper-gravelroad.com`

API requests proxy through Next.js rewrites (`/api/*` → `https://api.prosper-gravelroad.com/*`).
