"use client";

import { useEffect, useRef } from "react";
import { loadAMap } from "@/lib/amap";

interface SiteMapProps {
  latitude: number;
  longitude: number;
  name: string;
}

export default function SiteMap({ latitude, longitude, name }: SiteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<AMap.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let disposed = false;

    async function init() {
      await loadAMap();
      if (disposed || !containerRef.current) return;

      const map = new AMap.Map(containerRef.current, {
        zoom: 15,
        center: [longitude, latitude],
        viewMode: "2D",
        mapStyle: "amap://styles/whitesmoke",
        dragEnable: true,
        zoomEnable: true,
        scrollWheel: false,
      });

      new AMap.Marker({
        position: new AMap.LngLat(longitude, latitude),
        title: name,
        map,
      });

      mapRef.current = map;
    }

    init();

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
