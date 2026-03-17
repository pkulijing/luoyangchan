"use client";

import { useEffect, useRef, useCallback } from "react";
import { loadAMap } from "@/lib/amap";
import { CATEGORY_COLORS, MAP_DEFAULT_CENTER, MAP_DEFAULT_ZOOM } from "@/lib/constants";
import type { HeritageSite, SiteMarkerData } from "@/lib/types";

interface AMapContainerProps {
  sites: SiteMarkerData[];
  onSiteClick?: (siteId: string) => void;
}

export default function AMapContainer({ sites, onSiteClick }: AMapContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<AMap.Map | null>(null);
  const clusterRef = useRef<AMap.MarkerCluster | null>(null);

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

      infoWindow.open(mapRef.current, new AMap.LngLat(site.longitude, site.latitude));
      onSiteClick?.(site.id);
    },
    [onSiteClick]
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
    }

    init();

    return () => {
      disposed = true;
      if (clusterRef.current) {
        clusterRef.current.setMap(null);
        clusterRef.current = null;
      }
      if (mapRef.current) {
        mapRef.current.destroy();
        mapRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current) return;

    if (clusterRef.current) {
      clusterRef.current.setMap(null);
      clusterRef.current = null;
    }

    const markers = sites
      .filter((s) => s.latitude && s.longitude)
      .map((site) => {
        const marker = new AMap.Marker({
          position: new AMap.LngLat(site.longitude, site.latitude),
          title: site.name,
          content: `<div style="width: 12px; height: 12px; border-radius: 50%; background: ${CATEGORY_COLORS[site.category]}; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.3);"></div>`,
          offset: new AMap.Pixel(-6, -6),
          extData: site,
        });

        marker.on("click", () => handleSiteClick(site));
        return marker;
      });

    if (markers.length > 0) {
      const cluster = new AMap.MarkerCluster(mapRef.current, markers, {
        gridSize: 60,
        maxZoom: 18,
      });
      clusterRef.current = cluster;
    }
  }, [sites, handleSiteClick]);

  return (
    <div ref={containerRef} className="w-full h-full" />
  );
}
