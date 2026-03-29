# Frontend — GravelRoad Iowa

Next.js web app deployed on Vercel. Communicates with FastAPI backend via Cloudflare Tunnel.

**Live**: https://webapp-mu-puce.vercel.app
**API**: https://api.prosper-gravelroad.com

## Stack

Next.js 16, React 19, TypeScript, Tailwind CSS 4, Leaflet, React Context

## Setup (local dev)

```bash
npm install
cp .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

## Deployment

Deployed to Vercel via GitHub push to `main`. Environment variables set in Vercel dashboard:

- `NEXT_PUBLIC_API_URL` = `https://api.prosper-gravelroad.com`

API calls proxy through Next.js rewrites (`/api/*` → Cloudflare Tunnel → ISU server).

## Structure

```
app/
├── components/            # React components
│   ├── DistressForms/     # Rut, Crown, Corrugation analysis forms
│   ├── FolderTree/        # Project sidebar
│   ├── TiffFiles/         # File list + file cards
│   ├── TiffMapViewer.tsx  # Leaflet map with tile overlay
│   ├── Map.tsx            # Core map component
│   ├── DistressWidget.tsx # Analysis jobs sidebar
│   └── ProfileWidget.tsx  # User profile sidebar
├── contexts/              # React Context state
│   ├── AuthContext.tsx     # User auth state
│   ├── MapContext.tsx      # Map bounds/zoom
│   ├── PolygonContext.tsx  # Drawn polygon state
│   └── DistressContext.tsx # Analysis form state
├── dashboard/
│   ├── page.tsx           # Main map view
│   ├── upload/            # Presigned upload page
│   └── distress/[slug]/   # Distress analysis page
└── lib/
    ├── api.ts             # API client + endpoints
    └── auth.ts            # Auth helpers
```

## Upload Flow

Uses presigned S3 URLs to bypass Vercel's 4.5MB body limit:

1. `POST /upload/presign` — get signed S3 PUT URL
2. Browser PUTs file directly to S3 (with progress bar + ETA)
3. `POST /upload/complete` — notify backend, queue tile generation
4. For files >100MB: multipart upload with 10MB chunks
