# Earshot web (M1)

React + Vite + TypeScript single-page app for Earshot. Owner: **M1 (Frontend & Auth)**.
See `CONTEXT.md` §7 (API), §6 (events), §9 (Cognito + web runtime config) and `TRACKER.md` (M1-01…M1-09).

## Scripts

```bash
npm install          # install dependencies
npm run dev          # local dev server on http://localhost:5173
npm run build        # type-check + production build to web/dist
npm run preview      # serve the production build locally
npm run lint         # type-check only (tsc --noEmit)
```

## Runtime config (no rebuild per stage)

The app does **not** bake stage values into the bundle. At startup it fetches `/config.json`:

```json
{ "apiUrl", "region", "userPoolId", "webClientId", "cognitoDomain", "stage" }
```

- In production, the base stack's `Web` construct (M1-04) deploys this file to the web
  bucket, so the same build runs in every stage (CONTEXT §9).
- Locally, `web/public/config.json` is used. It ships empty so mock mode works with no backend.

## Mock mode (build without a backend)

Set `VITE_USE_MOCKS=true` to serve the committed `contracts/samples/*.json` fixtures
instead of calling a live API (CONTEXT §12 "Mocks first"). This is the default local
workflow until the real API (M2) and ingest (M3) are deployed; M1-09 flips the app
over to the real backend.

```bash
echo "VITE_USE_MOCKS=true" > .env.local   # .env.local is gitignored
npm run dev
# or for a one-off: VITE_USE_MOCKS=true npm run dev
```

The fixtures are imported directly from `../contracts/samples/` in `src/lib/mocks.ts`,
so `contracts/samples/` stays the single source of truth with no copied files to drift.
Vite reads them via `server.fs.allow` in `vite.config.ts`. A small `MOCK DATA` badge is
shown in the corner whenever mock mode is active.
