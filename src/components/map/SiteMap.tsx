"use client";

import { useEffect, useRef } from "react";
import { MAP_PROVIDER } from "@/lib/mapProvider";

interface SiteMapProps {
  latitude: number;
  longitude: number;
  name: string;
}

export default function SiteMap(props: SiteMapProps) {
  return MAP_PROVIDER === "amap" ? (
    <SiteMapAMap {...props} />
  ) : (
    <SiteMapLeaflet {...props} />
  );
}

function SiteMapAMap({ latitude, longitude, name }: SiteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<AMap.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;

    async function init() {
      const { loadAMap } = await import("@/lib/amap");
      await loadAMap();
      if (disposed || !containerRef.current) return;

      const map = new AMap.Map(containerRef.current, {
        center: [longitude, latitude], // GCJ-02 [lng, lat]，和 AMap 一致
        zoom: 15,
        scrollWheel: false,
      });

      new AMap.Marker({
        position: [longitude, latitude],
        title: name,
        content: `<div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
                   <div style="width:16px;height:16px;border-radius:50%;background:#e74c3c;border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,0.3)"></div>
                   <div style="width:2px;height:8px;background:#e74c3c;opacity:0.9"></div>
                 </div>`,
        offset: new AMap.Pixel(-8, -26),
        map,
      });

      mapRef.current = map;
    }

    init().catch((e) => console.error("[SiteMap] init failed", e));

    return () => {
      disposed = true;
      if (mapRef.current) {
        mapRef.current.destroy();
        mapRef.current = null;
      }
    };
  }, [latitude, longitude, name]);

  return <div ref={containerRef} className="w-full h-full" />;
}

function SiteMapLeaflet({ latitude, longitude, name }: SiteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;

    async function init() {
      await import("leaflet/dist/leaflet.css");
      const L = (await import("leaflet")).default;
      const { gcj02ToWgs84 } = await import("@/lib/coordConvert");

      if (disposed || !containerRef.current) return;

      const [wgsLng, wgsLat] = gcj02ToWgs84(longitude, latitude);

      const map = L.map(containerRef.current, {
        center: [wgsLat, wgsLng],
        zoom: 15,
        zoomControl: true,
        scrollWheelZoom: false,
      });

      const tk = process.env.NEXT_PUBLIC_TIANDITU_TK ?? "";

      L.tileLayer(
        `http://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${tk}`,
        { subdomains: "01234567", maxZoom: 18, attribution: "天地图" },
      ).addTo(map);

      L.tileLayer(
        `http://t{s}.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${tk}`,
        { subdomains: "01234567", maxZoom: 18 },
      ).addTo(map);

      L.marker([wgsLat, wgsLng], {
        title: name,
        icon: L.divIcon({
          html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
                   <div style="width:16px;height:16px;border-radius:50%;background:#e74c3c;border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,0.3)"></div>
                   <div style="width:2px;height:8px;background:#e74c3c;opacity:0.9"></div>
                 </div>`,
          className: "",
          iconSize: [16, 26] as [number, number],
          iconAnchor: [8, 26] as [number, number],
        }),
      }).addTo(map);

      mapRef.current = map;
    }

    init().catch((e) => console.error("[SiteMap] init failed", e));

    return () => {
      disposed = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [latitude, longitude, name]);

  return <div ref={containerRef} className="w-full h-full" />;
}
