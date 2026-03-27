export type MapProvider = "amap" | "tianditu";

export const MAP_PROVIDER: MapProvider =
  (process.env.NEXT_PUBLIC_MAP_PROVIDER as MapProvider) || "amap";

export function isAMap(): boolean {
  return MAP_PROVIDER === "amap";
}
