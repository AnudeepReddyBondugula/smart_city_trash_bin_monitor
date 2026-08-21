# Frontend Documentation

> **Status: planned.** No CityScope frontend is implemented in this repository.
> The components and routes below describe the intended application.

## Overview

The planned frontend is a **Next.js (App Router) + React** application for
monitoring ward-level waste bin fill levels, alerts, and analytics.

## Tech Stack

- **Framework:** Next.js (App Router)
- **Language:** TypeScript
- **UI:** Tailwind CSS
- **State Management:** React hooks (`useState`, `useEffect`)
- **Routing:** Next.js dynamic routes (`/dashboard/ward/[wardId]`)
- **Data Fetching:** `fetch` with cookie-based authentication
- **Polling:** 30s intervals for real-time updates

## Project Structure

Code
```text
frontend/
├── app/
│   ├── dashboard/
│   │   ├── page.tsx                # Main dashboard
│   │   ├── _components/
│   │   │   ├── AlertsBanner.tsx    # Red banner for critical wards
│   │   │   ├── StreamingHealth.tsx # Streaming health card
│   │   │   └── WardCard.tsx        # Individual ward summary
│   │   └── ward/[wardId]/
│   │       ├── page.tsx            # Ward detail analytics page
│   │       └── _components/
│   │           └── AnalyticsClient.tsx
│   └── layout.tsx                  # Global layout
├── public/                         # Static assets
├── styles/                         # Tailwind config
└── package.json`
```

## Key Components

### 1. Alerts Banner

- **Purpose:** Show number of wards needing immediate attention.
- **Behavior:**
    - Polls `/alerts/wards` every 30s.
    - Displays banner with count and reasons.
    - CTA buttons navigate to ward detail or filtered dashboard.

### 2. Ward Detail Analytics

- **Purpose:** Deep dive into a ward’s bin data.
- **Sections:**
    - **Time series graph:** avg & max fill levels.
    - **Bin distribution:** % bins `<50`, `50–80`, `>80`.
    - **Risk history:** intervals when ward was critical.

### 3. Streaming Health Card

- **Purpose:** Show data quality & reliability metrics.
- **Metrics:**
    - Late events %
    - Duplicates avoided
    - Invalid messages (DLQ)

## Setup & Installation

1. **Install dependencies:**
    `npm install`
    
2. **Run development server:**
    `npm run dev`
    Default: `http://localhost:3000` (localhost)
    
3. **Environment variables (**`.env.local`**):**
     `NEXT_PUBLIC_API_BASE=http://localhost:8000`
    
4. **Build for production:**
    `npm run build
     npm run start`
