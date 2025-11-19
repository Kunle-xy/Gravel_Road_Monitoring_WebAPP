# Frontend - GravelRoad Iowa

Next.js 15 web application for the GravelRoad Iowa pavement distress analysis system.

**Author**: Kunle Oguntoye, PhD Student at Iowa State University
**Contact**: oguntoye@iastate.edu

---

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS 4
- **UI Components**: Custom components with Lucide React icons
- **Maps**: Leaflet 1.9+
- **State Management**: React Context API
- **HTTP Client**: Fetch API with custom wrapper
- **Authentication**: JWT tokens in localStorage

---

## Setup

### 1. Install Dependencies
```bash
npm install
```

### 2. Environment Configuration
Create `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start Development Server
```bash
npm run dev
# Opens at http://localhost:3000
```

---

## Project Structure

```
app/
├── components/              # Reusable React components
│   ├── DistressForms/      # Distress analysis forms
│   ├── FolderTree/         # Folder tree components
│   ├── DashboardMap.tsx    # Main Leaflet map
│   ├── ProfileWidget.tsx   # Sidebar with files & jobs
│   └── MapControls.tsx     # Map drawing tools
├── contexts/               # React Context providers
│   ├── AuthContext.tsx     # Authentication state
│   ├── PolygonContext.tsx  # Drawing & polygons
│   └── ToastContext.tsx    # Notifications
├── dashboard/              # Dashboard pages
│   ├── page.tsx           # Main map view
│   └── upload/            # Upload page
└── lib/
    └── api.ts             # API client
```

---

## Key Components

### DashboardMap
Main interactive Leaflet map with tile layers and drawing tools.

### ProfileWidget
Collapsible sidebar showing:
- User profile
- Project folders with files
- Completed analysis jobs
- Quick download links

### DistressForms/rut.tsx
Rut analysis form with:
- Parameter configuration
- Progress tracking
- Result downloads (HTML plot + PDF)

---

## API Integration

All API calls use `fetchWithAuth()` from `lib/api.ts` with JWT token injection.

Endpoints in `API_ENDPOINTS`:
- `/auth/*` - Authentication
- `/files/*` - File management
- `/folders/*` - Project folders
- `/rut/*` - Rut analysis
- `/upload/*` - Multipart upload

---

## User Workflows

1. **Login** → Enter credentials at `/login`
2. **Upload** → Select folder, upload TIFF file
3. **View** → Click file to display on map
4. **Analyze** → Draw polygon, configure params, run analysis
5. **Download** → Access results from completed jobs

---

## Styling

Dark slate theme with Tailwind CSS:
- Backgrounds: `bg-slate-800` to `bg-slate-900`
- Text: `text-slate-100` to `text-slate-400`
- Primary: `bg-blue-600`
- Success: `bg-green-600`

---

**Last Updated**: November 18, 2025
