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
const TEXT_LABEL_MIN_ZOOM = 9; // zoom >= 此值时，圆点标记切换为文字标签

// 类别图标 SVG path（12x12 视口，白色线条）
const CATEGORY_ICONS: Record<string, string> = {
  // 古遗址：破墙（两边高，中间不规则缺口）
  古遗址: `<path d="M2 9V2h2v2h1V3h2v2h1V2h2v7" stroke="white" stroke-width="1.2" fill="none" stroke-linejoin="round"/>`,
  // 古墓葬：土丘/坟冢
  古墓葬: `<path d="M2 9Q6 3 10 9" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/>`,
  // 古建筑：传统屋顶
  古建筑: `<path d="M6 2L2 5h8L6 2zM3 5v4h6V5" stroke="white" stroke-width="1.2" fill="none" stroke-linejoin="round"/>`,
  // 石窟寺及石刻：墓碑（像"几"字）
  石窟寺及石刻: `<path d="M2 10H10M4 10V3H8V10" stroke="white" stroke-width="1.2" fill="none" stroke-linejoin="round"/>`,
  // 近现代：五角星
  近现代重要史迹及代表性建筑: `<path d="M6 1L7.2 4.5H10.5L8 6.8L9 10.2L6 8L3 10.2L4 6.8L1.5 4.5H4.8Z" fill="white"/>`,
  // 其他：星号
  其他: `<path d="M6 2v8M2 6h8M3 3l6 6M9 3l-6 6" stroke="white" stroke-width="1.2" stroke-linecap="round"/>`,
  // 历史分类（沿用相近图标）
  革命遗址及革命纪念建筑物: `<path d="M6 1L7.2 4.5H10.5L8 6.8L9 10.2L6 8L3 10.2L4 6.8L1.5 4.5H4.8Z" fill="white"/>`,
  古建筑及历史纪念建筑物: `<path d="M6 2L2 5h8L6 2zM3 5v4h6V5" stroke="white" stroke-width="1.2" fill="none" stroke-linejoin="round"/>`,
  石窟寺: `<path d="M2 10H10M4 10V3H8V10" stroke="white" stroke-width="1.2" fill="none" stroke-linejoin="round"/>`,
  石刻及其他: `<path d="M2 10H10M4 10V3H8V10" stroke="white" stroke-width="1.2" fill="none" stroke-linejoin="round"/>`,
};

// 生成带图标的标记 HTML
function buildIconMarkerHtml(color: string, category: string): string {
  const iconPath = CATEGORY_ICONS[category] || CATEGORY_ICONS["其他"];
  return `<div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
            <div style="width:18px;height:18px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center">
              <svg width="12" height="12" viewBox="0 0 12 12">${iconPath}</svg>
            </div>
            <div style="width:2px;height:6px;background:${color};opacity:0.9"></div>
          </div>`
}

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
  onSiteClick?: (releaseId: string) => void;
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
  // 标记是否已通过用户定位设置了初始视角，避免 fitBounds 覆盖
  const userLocatedRef = useRef(false);
  // 用 ref 追踪最新回调，避免在 init effect 中捕获旧闭包
  const onSiteClickRef = useRef(onSiteClick);
  onSiteClickRef.current = onSiteClick;

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
      // 事件委托：拦截 popup 内 [data-release-id] 链接点击
      containerRef.current!.addEventListener("click", (e) => {
        const target = (e.target as HTMLElement).closest<HTMLElement>(
          "[data-release-id]",
        );
        if (target) {
          e.preventDefault();
          const releaseId = target.dataset.releaseId;
          if (releaseId) {
            map.closePopup();
            onSiteClickRef.current?.(releaseId);
          }
        }
      });

      mapRef.current = map;
      setMapReady(true);

      // 尝试获取用户位置，成功则定位到用户位置
      // 中国大致范围：纬度 18-54，经度 73-135
      const isInChina = (lat: number, lng: number) =>
        lat >= 18 && lat <= 54 && lng >= 73 && lng <= 135;
      // 北京天安门坐标（WGS-84）
      const BEIJING_TIANANMEN: [number, number] = [39.9087, 116.3975];

      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            const { latitude, longitude } = position.coords;
            console.log(`[Geolocation] 用户位置: ${latitude}, ${longitude}`);
            // 判断是否在中国范围内
            // 先标记已定位，防止 fitBounds 覆盖
            userLocatedRef.current = true;
            if (isInChina(latitude, longitude)) {
              map.setView([latitude, longitude], 11);
              console.log("[Geolocation] 在中国范围内，定位到用户位置");
            } else {
              map.setView(BEIJING_TIANANMEN, 11);
              console.log("[Geolocation] 不在中国范围内，定位到北京天安门");
            }
            // zoomend 事件会自动更新 zoom 状态，无需手动 setZoom
          },
          (error) => {
            console.warn("[Geolocation] 获取位置失败:", error.message);
            // 定位失败，保持默认视角，后续会 fitBounds
          },
          { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 },
        );
      }
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

  // 构建坐标重合的多条目 popup HTML
  const buildStackedPopupHtml = useCallback(
    (stackedSites: SiteMarkerData[]) => {
      const items = stackedSites
        .map(
          (s) =>
            `<div style="padding:6px 0;border-bottom:1px solid #eee;">
               <a href="#" data-release-id="${s.release_id}" style="color:#1890ff;font-size:13px;font-weight:500;text-decoration:none;cursor:pointer;">${s.name}</a>
               <span style="color:#999;font-size:12px;margin-left:6px;">${s.category}</span>
               ${s.era ? `<span style="color:#999;font-size:12px;"> · ${s.era}</span>` : ""}
             </div>`,
        )
        .join("");
      return `<div style="padding:8px;min-width:220px;max-height:300px;overflow-y:auto;">
                <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#e67e22;">
                  ${stackedSites.length} 条数据共用此坐标
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
          // 单条数据：zoom 较大时显示文字标签，否则显示圆点
          const color = CATEGORY_COLORS[site.category] ?? "#95a5a6";
          const useTextLabel = zoom >= TEXT_LABEL_MIN_ZOOM;
          const icon = useTextLabel
            ? L.divIcon({
                html: `<div style="display:flex;flex-direction:column;align-items:center">
                         <div style="padding:2px 6px;border-radius:3px;background:${color};
                                     font-size:12px;font-weight:600;color:#fff;white-space:nowrap;
                                     box-shadow:0 1px 4px rgba(0,0,0,0.3);line-height:1.3">${site.name}</div>
                         <div style="width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;
                                     border-top:4px solid ${color}"></div>
                       </div>`,
                className: "",
                iconSize: [0, 0] as [number, number],
                iconAnchor: [0, 24] as [number, number],
              })
            : L.divIcon({
                html: buildIconMarkerHtml(color, site.category),
                className: "",
                iconSize: [18, 24] as [number, number],
                iconAnchor: [9, 24] as [number, number],
              });
          const marker = L.marker([wgsLat, wgsLng], {
            title: site.name,
            icon,
          });
          marker.on("click", () => onSiteClick?.(site.release_id));
          cluster.addLayer(marker);
        }
      }

      mapRef.current.addLayer(cluster);
      clusterRef.current = cluster;

      // 只在 sites 真正变化时 fitBounds，调整 clusterRadius 不重置视角
      // 如果用户已通过 Geolocation 定位，跳过首次 fitBounds
      if (prevSitesRef.current !== sites) {
        const isFirstLoad = prevSitesRef.current === null;
        prevSitesRef.current = sites;
        if (isFirstLoad && userLocatedRef.current) {
          // 用户已定位，不覆盖视角
          console.log("[LeafletContainer] 用户已定位，跳过 fitBounds");
        } else if (!isFirstLoad || !userLocatedRef.current) {
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
    }

    updateMarkers().catch((e) =>
      console.error("[LeafletContainer] updateMarkers failed", e),
    );
  }, [sites, mapReady, zoom, buildStackedPopupHtml, onSiteClick]);

  return <div ref={containerRef} className="w-full h-full" />;
}
