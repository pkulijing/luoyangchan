# Plan: Refactor AMapContainer to use MarkerCluster

## Context
Currently 5000+ heritage sites are rendered as individual `AMap.Marker` instances, each added separately to the map. This causes several-second render delays. AMap provides a built-in `MarkerCluster` plugin that groups nearby markers into cluster bubbles, rendering a small number of cluster nodes instead of thousands of individual markers — dramatically improving initial load and pan/zoom performance.

## Files Modified

1. **`src/lib/amap.ts`** — added `"AMap.MarkerCluster"` to plugins list
2. **`src/components/map/AMapContainer.tsx`** — replaced individual marker management with a single `MarkerCluster` instance

The type definitions in `src/types/amap.d.ts` were already in place (`MarkerCluster`, `MarkerClusterOptions`) — no changes needed there.

## Implementation

### `src/lib/amap.ts`
Added `"AMap.MarkerCluster"` to the plugins array:
```ts
plugins: ["AMap.Geocoder", "AMap.Scale", "AMap.ToolBar", "AMap.MarkerCluster"],
```

### `src/components/map/AMapContainer.tsx`

**Ref change:**
- Removed: `markersRef = useRef<AMap.Marker[]>([])`
- Added: `clusterRef = useRef<AMap.MarkerCluster | null>(null)`

**Markers effect:**
- Cleanup: `clusterRef.current?.setMap(null); clusterRef.current = null;`
- Create `AMap.Marker` instances the same way (custom HTML, click handlers)
- Instead of `markers.forEach(m => m.setMap(map))`, create a single cluster:
  ```ts
  clusterRef.current = new AMap.MarkerCluster(mapRef.current, markers, {
    gridSize: 60,
    maxZoom: 16,
  });
  ```
- `setFitView(markers, ...)` preserved for initial viewport fitting

**Unmount cleanup:**
- Replaced iterating `markersRef` with `clusterRef.current?.setMap(null)`

## Key Design Decisions

- **Individual marker click events still work**: `MarkerCluster` renders individual markers when zoomed past `maxZoom: 16`; the `marker.on("click", ...)` handlers fire normally. Clicking a cluster bubble zooms in.
- **Custom marker HTML preserved**: Individual markers keep the colored dot + stem design; cluster bubbles use AMap's default style (number badge).
- **`gridSize: 60`**: Default cluster radius in pixels — good balance for 5000+ markers.
- **`maxZoom: 16`**: At zoom ≥ 16 markers always render individually.
- **`setFitView`**: Still called with the markers array so the viewport fits the filtered set.

## Verification

1. Run `npm run dev`, open the map page
2. Confirm markers appear as cluster bubbles at low zoom, expand into individual pins when zoomed in
3. Click an individual marker → InfoWindow appears correctly
4. Change a filter → cluster re-renders with the new filtered set
5. Check browser DevTools performance tab: initial marker render should be much faster
