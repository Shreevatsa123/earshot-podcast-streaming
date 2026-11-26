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

## Look and feel

Deep purple with layered gradients, adapted from the team's Nocturne design. Styling is
**Tailwind CSS v4** (utility classes in the components); the page backdrop, wordmark
gradient, rank numbers and equalizer animation live in `src/index.css`. Icons come from
`lucide-react`. Fonts: Outfit (headings), Plus Jakarta Sans (text), JetBrains Mono (times).

| Piece | File | Data |
|---|---|---|
| Top bar | `components/Navbar.tsx` | – |
| Hero spotlight with switcher | `components/HeroBillboard.tsx` | top 4 of the `/home` trending row |
| Rows and cards (Continue, ranked Top Today, episode, show) | `components/Shelf.tsx`, `components/Cards.tsx` | `/home` rows, `/shows?genre=` |
| Show details dialog | `components/ShowDetailModal.tsx` | `GET /shows/{id}` |
| Browse page | `pages/Browse.tsx` | `GET /genres`, `GET /shows?genre=` (genre in the URL) |
| Live Trending page | `pages/LiveTrending.tsx` | `GET /trending?limit=20` every 5 s while the tab is visible |
| Settings page | `pages/Settings.tsx`, `lib/region.ts` | listening region for events (§6), account |
| Search | `components/SearchOverlay.tsx` | `GET /shows` for all 8 genres, filtered in the browser (the API has no search route) |
| Player dock + expanded view | `components/PlayerDock.tsx`, `components/PlayerContext.tsx` | HTML5 `<audio>` on the episode's `audio_url` |

## Login (M1-05)

Every API route except `/health` needs a Cognito access token (CONTEXT §7.1), so the app
shows a login screen until someone is logged in.

- `src/auth/session.tsx` wraps `react-oidc-context`: authorization code + PKCE against the
  user pool, on Cognito's managed login pages (sign up is on the same page). After login,
  Cognito sends the browser back to the site's own address, which must be one of the web
  client's callback URLs: the CloudFront URL or `http://localhost:5173`.
- The access token goes on every API call (`Authorization: Bearer ...`). Tokens are kept in
  `localStorage` (logged in across tabs and reloads) and refreshed before they expire.
- A 401 from the API forgets the token, which brings back the login screen.
- Log out clears the tokens and then Cognito's own session (`/logout`).
- In mock mode there's no login: you're a demo listener.

**Real login on localhost:** copy your stage's live config over the empty local one, then
start the dev server without mock mode. Don't commit the copied file.

```bash
curl -s https://<your-cloudfront-domain>/config.json > public/config.json
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

Set `VITE_USE_MOCKS=true` to answer API calls from the committed fixtures in
`contracts/samples/` instead of the network (CONTEXT §12 "Mocks first"). This is the
default local workflow until the real API (M2) is deployed; M1-09 switches over.

```bash
echo "VITE_USE_MOCKS=true" > .env.local   # .env.local is gitignored
npm run dev
# or for a one-off: VITE_USE_MOCKS=true npm run dev
```

- `/home`, `/trending` and `/progress` use M2's sample responses as they are.
- `/shows` and `/shows/{id}` are built from `catalog.json` with the §7.3 shape and rules,
  so every one of the 48 shows opens with its real episodes.
- `src/lib/mocks.ts` is loaded with a dynamic import, so the fixtures go into a separate
  chunk and a normal build leaves them out.
- A `MOCK DATA` badge shows in the corner while mock mode is on.

Audio plays for real in mock mode too: it streams from the publisher's URL.
