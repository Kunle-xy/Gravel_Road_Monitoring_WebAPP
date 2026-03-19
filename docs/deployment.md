# Deployment Guide

## Server Map

| Role | Host | What runs |
|------|------|-----------|
| Frontend | Vercel (webapp-mu-puce.vercel.app) | Next.js 16 |
| API + DB + Redis | EC2 t3.medium (52.15.33.164) | FastAPI, PostgreSQL 16, Redis 7 |
| Workers | ISU (129.186.252.201) | Celery tile + rut workers |

## EC2 Setup

### Services
```bash
sudo systemctl status fastapi       # FastAPI (port 8000)
sudo systemctl status redis          # Redis (port 6379)
sudo systemctl status postgresql@16-main  # PostgreSQL (port 5432)
```

### FastAPI service
Defined in `/etc/systemd/system/fastapi.service`. Auto-starts on boot, auto-restarts on crash.

```bash
sudo systemctl restart fastapi       # after code or .env changes
sudo journalctl -u fastapi -f        # tail logs
```

### Swap
2GB swap at `/swapfile` (active on boot).

### Security Groups
- Port 8000: open to Vercel (API)
- Port 6379: open to 129.186.252.201/32 only (Redis for Celery)
- Port 5432: open to 129.186.252.201/32 only (PostgreSQL for workers)

### PostgreSQL remote access
- `listen_addresses = '*'` in postgresql.conf
- pg_hba.conf allows `kunle_admin` from `129.186.252.201/32` to `gravel_road_app`

### Redis
- Bound to 0.0.0.0:6379
- Password protected (set in redis.conf `requirepass`)

## ISU Server Connection Strings

```
Redis:      redis://:PASSWORD@52.15.33.164:6379/0
PostgreSQL: postgresql://kunle_admin:prosper@52.15.33.164:5432/gravel_road_app
```

## AWS Resources

| Resource | Value |
|----------|-------|
| Region | us-east-2 |
| S3 raw bucket | gravel-road-raw-file |
| S3 tiles bucket | gravel-road-app-file |
| CloudFront | d18o6mwudgwpmq.cloudfront.net |
| IAM role | gravel-road-ec2-role |

S3 CORS is configured on `gravel-road-raw-file` to allow browser PUT uploads from Vercel origins.

## Vercel

Deploys automatically on push to `main`. Environment variables set in Vercel dashboard.

API requests are proxied via Next.js rewrites (`/api/*` -> `http://52.15.33.164:8000/*`).
