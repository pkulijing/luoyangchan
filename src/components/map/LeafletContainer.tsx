"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import {
  CATEGORY_COLORS,
  MAP_DEFAULT_CENTER,
  MAP_DEFAULT_ZOOM,
} from "@/lib/constants";
import { gcj02ToWgs84 } from "@/lib/coordConvert";
import type { SiteMarkerData } from "@/lib/types";

// MAP_DEFAULT_CENTER 是 [lng, lat]，Leaflet 需要 [lat, lng]
const DEFAULT_CENTER: [number, number] = [
  MAP_DEFAULT_CENTER[1],
  MAP_DEFAULT_CENTER[0],
];

// 聚合半径随缩放级别的线性衰减参数
// zoom <= CLUSTER_FULL_ZOOM 时 radius = CLUSTER_MAX_RADIUS
// zoom >= CLUSTER_ZERO_AT_ZOOM 时 radius = 0，中间线性插值
// 调整 CLUSTER_ZERO_AT_ZOOM 可改变"开始独立显示"的缩放阈值
const CLUSTER_MAX_RADIUS = 40;
const CLUSTER_FULL_ZOOM = 4;
const CLUSTER_ZERO_AT_ZOOM = 8; // 约等于"北京市"视野，可按需调整

function calcClusterRadius(zoom: number): number {
  if (zoom >= CLUSTER_ZERO_AT_ZOOM) return 0;
  if (zoom <= CLUSTER_FULL_ZOOM) return CLUSTER_MAX_RADIUS;
  return Math.round(
    ((CLUSTER_ZERO_AT_ZOOM - zoom) /
      (CLUSTER_ZERO_AT_ZOOM - CLUSTER_FULL_ZOOM)) *
      CLUSTER_MAX_RADIUS,
  );
}

interface LeafletContainerProps {
  sites: SiteMarkerData[];
  onSiteClick?: (siteId: string) => void;
}

export default function LeafletContainer({
  sites,
  onSiteClick,
}: LeafletContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const clusterRef = useRef<any>(null);
  const [mapReady, setMapReady] = useState(false);
  const [zoom, setZoom] = useState(MAP_DEFAULT_ZOOM);
  const prevSitesRef = useRef<SiteMarkerData[] | null>(null);

  // 初始化地图（只运行一次）
  useEffect(() => {
    if (!containerRef.current) return;

    let disposed = false;

    async function init() {
      const L = (await import("leaflet")).default;
      await import("leaflet.markercluster");

      if (disposed || !containerRef.current) return;

      const map = L.map(containerRef.current, {
        center: DEFAULT_CENTER,
        zoom: MAP_DEFAULT_ZOOM,
        zoomControl: false,
      });
      L.control.zoom({ position: "bottomleft" }).addTo(map);

      const tk = process.env.NEXT_PUBLIC_TIANDITU_TK ?? "";

      // 天地图矢量底图
      L.tileLayer(
        `http://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${tk}`,
        { subdomains: "01234567", maxZoom: 18, attribution: "天地图" },
      ).addTo(map);

      // 天地图中文注记图层
      L.tileLayer(
        `http://t{s}.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${tk}`,
        { subdomains: "01234567", maxZoom: 18 },
      ).addTo(map);

      L.control.scale({ imperial: false }).addTo(map);

      map.on("zoomend", () => {
        const z = map.getZoom();
        console.log(`[zoom] ${z} → clusterRadius: ${calcClusterRadius(z)}`);
        setZoom(z);
      });
      mapRef.current = map;
      setMapReady(true);
    }

    init().catch((error) => {
      console.error("[LeafletContainer] init failed", error);
    });

    return () => {
      disposed = true;
      if (clusterRef.current && mapRef.current) {
        mapRef.current.removeLayer(clusterRef.current);
        clusterRef.current = null;
      }
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      setMapReady(false);
    };
  }, []);

  // 构建单个标记的 popup HTML
  const buildPopupHtml = useCallback(
    (site: SiteMarkerData, color: string) =>
      `<div style="padding:8px;min-width:200px;">
         <h3 style="margin:0 0 8px;font-size:16px;font-weight:600;">${site.name}</h3>
         <p style="margin:0 0 4px;color:#666;font-size:13px;">
           <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px;"></span>
           ${site.category}
         </p>
         ${site.era ? `<p style="margin:0 0 4px;color:#666;font-size:13px;">时代：${site.era}</p>` : ""}
         <p style="margin:0 0 8px;color:#666;font-size:13px;">${site.province}</p>
         <a href="/site/${site.id}" style="color:#1890ff;font-size:13px;text-decoration:none;">查看详情 →</a>
       </div>`,
    [],
  );

  // 构建坐标重合的多条目 popup HTML（用于 debug）
  const buildStackedPopupHtml = useCallback(
    (stackedSites: SiteMarkerData[]) => {
      const items = stackedSites
        .map(
          (s) =>
            `<div style="padding:6px 0;border-bottom:1px solid #eee;">
               <a href="/site/${s.id}" style="color:#1890ff;font-size:13px;font-weight:500;text-decoration:none;">${s.name}</a>
               <span style="color:#999;font-size:12px;margin-left:6px;">${s.category}</span>
               ${s.era ? `<span style="color:#999;font-size:12px;"> · ${s.era}</span>` : ""}
             </div>`,
        )
        .join("");
      return `<div style="padding:8px;min-width:220px;max-height:300px;overflow-y:auto;">
                <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#e67e22;">
                  ⚠ ${stackedSites.length} 条数据共用此坐标
                </p>
                ${items}
              </div>`;
    },
    [],
  );

  // 更新标记（sites 或 mapReady 变化时重建聚合层）
  useEffect(() => {
    if (!mapRef.current || !mapReady) return;

    async function updateMarkers() {
      const L = (await import("leaflet")).default;
      await import("leaflet.markercluster");

      // 移除旧的聚合层
      if (clusterRef.current) {
        mapRef.current.removeLayer(clusterRef.current);
        clusterRef.current = null;
      }

      const validSites = sites.filter(
        (s) => s.latitude != null && s.longitude != null,
      );
      if (validSites.length === 0) return;

      const cluster = L.markerClusterGroup({
        maxClusterRadius: calcClusterRadius(zoom),
        disableClusteringAtZoom: 17,
        chunkedLoading: true,
        iconCreateFunction: (c) => {
          const count = c.getChildCount();
          return L.divIcon({
            html: `<div style="display:flex;align-items:center;justify-content:center;
                              width:36px;height:36px;border-radius:50%;
                              background:#fff;border:2px solid #666;
                              font-size:13px;font-weight:600;color:#333;
                              box-shadow:0 2px 6px rgba(0,0,0,0.25)">${count}</div>`,
            className: "",
            iconSize: [36, 36] as [number, number],
            iconAnchor: [18, 18] as [number, number],
          });
        },
      });

      // 按原始坐标分组，检测重合点
      const coordGroups = new Map<string, SiteMarkerData[]>();
      for (const site of validSites) {
        const key = `${site.longitude},${site.latitude}`;
        if (!coordGroups.has(key)) coordGroups.set(key, []);
        coordGroups.get(key)!.push(site);
      }

      for (const group of coordGroups.values()) {
        const site = group[0];
        const [wgsLng, wgsLat] = gcj02ToWgs84(site.longitude, site.latitude);

        if (group.length > 1) {
          // 多条数据共用坐标：显示堆叠标记
          const count = group.length;
          const marker = L.marker([wgsLat, wgsLng], {
            title: `${count} 条数据（坐标相同）`,
            icon: L.divIcon({
              html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-10px)">
                       <div style="min-width:20px;height:20px;border-radius:4px;background:#e67e22;border:2px solid #fff;
                                   box-shadow:0 1px 5px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;
                                   padding:0 4px;font-size:11px;font-weight:700;color:#fff;white-space:nowrap;">${count}</div>
                       <div style="width:2px;height:8px;background:#e67e22;opacity:0.9"></div>
                     </div>`,
              className: "",
              iconSize: [20, 30] as [number, number],
              iconAnchor: [10, 30] as [number, number],
            }),
          });
          marker.bindPopup(buildStackedPopupHtml(group), { maxWidth: 300 });
          cluster.addLayer(marker);
        } else {
          // 单条数据：正常标记
          const color = CATEGORY_COLORS[site.category] ?? "#95a5a6";
          const marker = L.marker([wgsLat, wgsLng], {
            title: site.name,
            icon: L.divIcon({
              html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
                       <div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,0.3)"></div>
                       <div style="width:2px;height:7px;background:${color};opacity:0.9"></div>
                     </div>`,
              className: "",
              iconSize: [14, 21] as [number, number],
              iconAnchor: [7, 21] as [number, number],
            }),
          });
          marker.bindPopup(buildPopupHtml(site, color), { maxWidth: 280 });
          marker.on("click", () => onSiteClick?.(site.id));
          cluster.addLayer(marker);
        }
      }

      mapRef.current.addLayer(cluster);
      clusterRef.current = cluster;

      // 只在 sites 真正变化时 fitBounds，调整 clusterRadius 不重置视角
      if (prevSitesRef.current !== sites) {
        prevSitesRef.current = sites;
        try {
          const bounds = cluster.getBounds();
          if (bounds.isValid()) {
            mapRef.current.fitBounds(bounds, { padding: [40, 40] });
          }
        } catch (e) {
          console.warn("[LeafletContainer] fitBounds failed", e);
        }
      }
    }

    updateMarkers().catch((e) =>
      console.error("[LeafletContainer] updateMarkers failed", e),
    );
  }, [
    sites,
    mapReady,
    zoom,
    buildPopupHtml,
    buildStackedPopupHtml,
    onSiteClick,
  ]);

  return <div ref={containerRef} className="w-full h-full" />;
}
