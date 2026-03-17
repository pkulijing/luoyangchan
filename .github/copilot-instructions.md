# Copilot Instructions for `luoyangchan`

## Product + scope

- This is a map-first MVP for browsing China national heritage sites (`heritage_sites`), not a generic CMS.
- Current UX is Chinese-first (labels/content are Chinese); preserve this tone in UI strings.

## Architecture you should keep

- Home page is a Server Component that fetches all site list rows once, then hands off to client UI: `src/app/page.tsx` -> `getAllSites()` -> `MapView`.
- Filtering is intentionally client-side (`src/hooks/useFilters.ts`), with map markers derived from filtered results.
- Only rows with coordinates become markers (`markerData` in `useFilters`); keep list vs marker responsibilities separate.
- Map runtime must stay client-only: `next/dynamic(..., { ssr: false })` in `MapView` and site detail map.
- AMap is loaded through a singleton helper (`src/lib/amap.ts`); do not initialize AMap loader in random components.

## Data + backend boundaries

- Supabase access is centralized in `src/lib/supabase/queries.ts`.
- Use server client (`src/lib/supabase/server.ts`) for App Router server components and data reads.
- Keep browser client (`src/lib/supabase/client.ts`) only for actual client-side data needs.
- DB schema/triggers/RLS live in `supabase/migrations/20240101000000_create_heritage_sites.sql`.
- RLS is public-read only right now; ingestion scripts rely on service role key.

## Canonical domain definitions

- `src/lib/types.ts` is the source of truth for `HeritageSite`, `SiteListItem`, `SiteCategory`, `FilterState`.
- `src/lib/constants.ts` is the source of truth for categories/colors/provinces/batch years/map defaults.
- If you add a new category or map behavior, update both types/constants and any UI that renders them.

## Map-specific implementation rules

- Info windows currently render HTML strings in `src/components/map/AMapContainer.tsx`; preserve escaping/safety awareness when injecting data.
- If adding AMap plugins, update both `loadAMap()` plugin list and `src/types/amap.d.ts` declarations.
- Keep map cleanup logic (`destroy`, cluster `setMap(null)`) to avoid memory leaks on rerender/unmount.

## Developer workflows (actual project)

- Frontend: `npm run dev`, `npm run build`, `npm run lint`.
- Local data platform: Supabase CLI + Docker (`supabase start`), default API at `http://127.0.0.1:54321`.
- Data pipeline (Python/uv in `scripts/`):
  1. `uv run python scrape_wikipedia.py`
  2. `uv run python fetch_coordinates.py`
  3. `uv run python seed_supabase.py --url ... --key ...`
- Python deps for scripts are managed in `scripts/pyproject.toml` (use `uv`, not ad-hoc pip flow).

## Change patterns that fit this codebase

- Prefer minimal, typed additions over framework-heavy abstractions.
- Preserve App Router split: server data fetch in route files, client interactivity in `"use client"` components/hooks.
- Reuse existing UI primitives under `src/components/ui/` and existing filter/map composition before creating new patterns.
