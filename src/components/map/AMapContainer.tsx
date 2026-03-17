"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { loadAMap } from "@/lib/amap";
import {
  CATEGORY_COLORS,
  MAP_DEFAULT_CENTER,
  MAP_DEFAULT_ZOOM,
} from "@/lib/constants";
import type { SiteMarkerData } from "@/lib/types";

interface AMapContainerProps {
  sites: SiteMarkerData[];
  onSiteClick?: (siteId: string) => void;
}

export default function AMapContainer({
  sites,
  onSiteClick,
}: AMapContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<AMap.Map | null>(null);
  const markersRef = useRef<AMap.Marker[]>([]);
  const [mapReady, setMapReady] = useState(false);

  const handleSiteClick = useCallback(
    (site: SiteMarkerData) => {
      if (!mapRef.current) return;

      const infoWindow = new AMap.InfoWindow({
        content: `
          <div style="padding: 8px; min-width: 200px;">
            <h3 style="margin: 0 0 8px; font-size: 16px; font-weight: 600;">${site.name}</h3>
            <p style="margin: 0 0 4px; color: #666; font-size: 13px;">
              <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${CATEGORY_COLORS[site.category]}; margin-right: 6px;"></span>
              ${site.category}
            </p>
            ${site.era ? `<p style="margin: 0 0 4px; color: #666; font-size: 13px;">时代：${site.era}</p>` : ""}
            <p style="margin: 0 0 8px; color: #666; font-size: 13px;">${site.province}</p>
            <a href="/site/${site.id}" style="color: #1890ff; font-size: 13px; text-decoration: none;">查看详情 →</a>
          </div>
        `,
        offset: new AMap.Pixel(0, -30),
      });

      infoWindow.open(
        mapRef.current,
        new AMap.LngLat(site.longitude, site.latitude),
      );
      onSiteClick?.(site.id);
    },
    [onSiteClick],
  );

  useEffect(() => {
    if (!containerRef.current) return;

    let disposed = false;

    async function init() {
      await loadAMap();

      if (disposed || !containerRef.current) return;

      const map = new AMap.Map(containerRef.current, {
        zoom: MAP_DEFAULT_ZOOM,
        center: MAP_DEFAULT_CENTER,
        viewMode: "2D",
        mapStyle: "amap://styles/whitesmoke",
      });

      map.addControl(new AMap.Scale());
      map.addControl(new AMap.ToolBar({ position: "RT" }));

      mapRef.current = map;
      setMapReady(true);
    }

    init().catch((error) => {
      console.error("[AMapContainer] init failed", error);
    });

    return () => {
      disposed = true;
      markersRef.current.forEach((marker) => marker.setMap(null));
      markersRef.current = [];
      if (mapRef.current) {
        mapRef.current.destroy();
        mapRef.current = null;
      }
      setMapReady(false);
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !mapReady) return;

    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current = [];

    const markers = sites
      .filter((s) => s.latitude != null && s.longitude != null)
      .map((site) => {
        const marker = new AMap.Marker({
          position: new AMap.LngLat(site.longitude, site.latitude),
          title: site.name,
          // Use a high-contrast marker style so visibility issues are easy to spot.
          content: `
            <div style="display: flex; flex-direction: column; align-items: center; transform: translateY(-8px);">
              <div style="width: 14px; height: 14px; border-radius: 50%; background: ${CATEGORY_COLORS[site.category]}; border: 2px solid #fff; box-shadow: 0 1px 5px rgba(0,0,0,0.3);"></div>
              <div style="width: 2px; height: 7px; background: ${CATEGORY_COLORS[site.category]}; opacity: 0.9;"></div>
            </div>
          `,
          offset: new AMap.Pixel(-7, -21),
          extData: site,
        });

        marker.on("click", () => handleSiteClick(site));
        return marker;
      });

    if (markers.length > 0) {
      markers.forEach((marker) => marker.setMap(mapRef.current));
      markersRef.current = markers;

      // Ensure markers are inside viewport; otherwise users may think nothing is rendered.
      try {
        mapRef.current.setFitView(markers, false, [40, 40, 40, 40]);
      } catch (error) {
        console.warn("[AMapContainer] fit view failed", error);
      }
    }
  }, [sites, handleSiteClick, mapReady]);

  return <div ref={containerRef} className="w-full h-full" />;
}
