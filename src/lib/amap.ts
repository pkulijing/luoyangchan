let amapLoaded = false;

export async function loadAMap(): Promise<typeof AMap> {
  if (typeof window === "undefined") {
    throw new Error("loadAMap() must run in the browser");
  }

  if (amapLoaded && window.AMap) {
    return window.AMap;
  }

  const { default: AMapLoader } = await import("@amap/amap-jsapi-loader");

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any)._AMapSecurityConfig = {
    securityJsCode: process.env.NEXT_PUBLIC_AMAP_SECRET || "",
  };

  const AMapInstance = await AMapLoader.load({
    key: process.env.NEXT_PUBLIC_AMAP_KEY || "",
    version: "2.0",
    plugins: ["AMap.Geocoder", "AMap.Scale", "AMap.ToolBar", "AMap.MarkerCluster"],
  });

  amapLoaded = true;
  return AMapInstance;
}
