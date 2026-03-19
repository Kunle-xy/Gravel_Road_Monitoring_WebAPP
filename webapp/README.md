# Frontend — GravelRoad Iowa

Next.js web app deployed on Vercel. Communicates with FastAPI backend on EC2.

**Live**: https://webapp-mu-puce.vercel.app

## Stack

Next.js 16, TypeScript, Tailwind CSS, Leaflet, React Context

## Setup (local dev)

```bash
npm install
cp .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

## Deployment

Deployed to Vercel via GitHub push to `main`. API calls proxy through Next.js rewrites to EC2.

## Structure

```
app/
├── components/          # React components
│   ├── DistressForms/   # Rut analysis UI
│   ├── FolderTree/      # Project sidebar
│   ├── DashboardMap.tsx  # Leaflet map
│   └── ProfileWidget.tsx # Sidebar with files & jobs
├── contexts/            # Auth, polygon, toast state
├── dashboard/
│   ├── page.tsx         # Main map view
│   └── upload/          # Presigned upload page
└── lib/
    └── api.ts           # API client + endpoints
```

## Upload Flow

Uses presigned S3 URLs to bypass Vercel's 4.5MB body limit:

1. `POST /upload/presign` — get signed S3 PUT URL
2. Browser PUTs file directly to S3 (with progress bar + ETA)
3. `POST /upload/complete` — notify backend, queue processing
