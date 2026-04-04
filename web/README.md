# 🖥️ Job Radar — Frontend

This is the Next.js frontend for Job Radar. It provides a dashboard for monitoring job listings, analyzing scores, and managing profiles.

## 🚀 Getting Started

We recommend using the **root-level commands** to manage the full stack.

### From the Root Directory:
```bash
# Setup both Backend & Frontend
make install

# Launch both Backend & Frontend
make dev
```

### From this Directory (`/web`):
If you only want to work on the frontend:
```bash
# Install dependencies
npm install

# Run the dev server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to see the dashboard.

## 🛠️ Stack

-   **Framework**: [Next.js 15 (App Router)](https://nextjs.org)
-   **Styling**: Tailwind CSS + Shadcn/UI
-   **API Client**: `openapi-fetch` (types generated from FastAPI)
-   **Icons**: Lucide React
-   **Charts**: Recharts

## 📡 API Integration

The frontend communicates with a FastAPI backend. TypeScript types are automatically generated from the backend's OpenAPI schema.

To regenerate types after a backend change:
```bash
# From the root directory
make types
```

---

For full installation and configuration details (including API keys and user profiles), please refer to the **[Main Project README](../README.md)**.
