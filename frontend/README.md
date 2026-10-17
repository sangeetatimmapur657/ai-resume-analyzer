# Matchbook frontend

This is the Next.js and TypeScript interface for the AI Resume Analyzer. The complete setup guide, architecture, API contract, privacy notes, scoring explanation, and evidence matrix are in the workspace [README](../README.md).

Set `NEXT_PUBLIC_API_URL` in `.env.local` to the FastAPI service URL (default: `http://localhost:8000`). Then run:

```powershell
npm install
npm run dev
```

Run `npm run lint`, `npx tsc --noEmit --incremental false`, and `npm run build` to check the frontend.
