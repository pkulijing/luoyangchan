"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { loadAMap } from "@/lib/amap";
import {
  CATEGORY_COLORS,
  MAP_DEFAULT_CENTER,
  MAP_DEFAULT_ZOOM,
} from "@/lib/constants";
import type { SiteMarkerData } from "@/lib/types";

// 聚合半径随缩放级别的线性衰减参数（对齐 LeafletContainer）
const CLUSTER_MAX_GRID = 80; // 对应 Leaflet maxClusterRadius=40，gridSize 单位是像素网格
const CLUSTER_FULL_ZOOM = 4;
const CLUSTER_ZERO_AT_ZOOM = 8;
const TEXT_LABEL_MIN_ZOOM = 9;

// 类别图标 SVG path（12x12 视口，白色线条）
const CATEGORY_ICONS: Record<string, string> = {
  古遗址: `<path d="M2 9V2h2v2h1V3h2v2h1V2h2v7" stroke="white" stroke-width="1.2" fill="none" stroke-linejoin="round"/>`,
  古墓葬: `<path d="M2 9Q6 3 10 9" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round"/>`,
  古建筑: `<path d="M6 2L2 5h8L6 2zM3 5v4h6V5" stroke="white" stroke-width="1.2" fill="none" stroke-linejoin="round"/>`,
  石窟寺及石刻: `<path d="M2 10H10M4 10V3H8V10" stroke="white" stroke-width="1.2" fill="none" stroke-linejoin="round"/>`,
  近现代重要史迹及代表性建筑: `<path d="M6 1L7.2 4.5H10.5L8 6.8L9 10.2L6 8L3 10.2L4 6.8L1.5 4.5H4.8Z" fill="white"/>`,
  其他: `<path d="M6 2v8M2 6h8M3 3l6 6M9 3l-6 6" stroke="white" stroke-width="1.2" stroke-linecap="round"/>`,
};

function buildIconMarkerHtml(
  color: string,
  category: string,
  markType?: string,
): string {
  const iconPath = CATEGORY_ICONS[category] || CATEGORY_ICONS["其他"];
  const ringColor =
    markType === "visited"
      ? "#16a34a"
      : markType === "wishlist"
        ? "#f59e0b"
        : "";
  const ring = ringColor
    ? `outline:2.5px solid ${ringColor};outline-offset:1px;`
    : "";
  return `<div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
            <div style="width:18px;height:18px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;${ring}">
              <svg width="12" height="12" viewBox="0 0 12 12">${iconPath}</svg>
            </div>
            <div style="width:2px;height:6px;background:${color};opacity:0.9"></div>
          </div>`;
}

function calcGridSize(zoom: number): number {
  // zoom >= CLUSTER_ZERO_AT_ZOOM 时不使用聚合（通过 maxZoom 控制）
  if (zoom <= CLUSTER_FULL_ZOOM) return CLUSTER_MAX_GRID;
  if (zoom >= CLUSTER_ZERO_AT_ZOOM) return 1;
  return Math.round(
    ((CLUSTER_ZERO_AT_ZOOM - zoom) /
      (CLUSTER_ZERO_AT_ZOOM - CLUSTER_FULL_ZOOM)) *
      CLUSTER_MAX_GRID,
  );
}

interface AMapContainerProps {
  sites: SiteMarkerData[];
  onSiteClick?: (releaseId: string) => void;
}

export default function AMapContainer({
  sites,
  onSiteClick,
}: AMapContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<AMap.Map | null>(null);
  const clusterRef = useRef<AMap.MarkerCluster | null>(null);
  const infoWindowRef = useRef<AMap.InfoWindow | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [zoom, setZoom] = useState(MAP_DEFAULT_ZOOM);
  const prevSitesRef = useRef<SiteMarkerData[] | null>(null);
  const userLocatedRef = useRef(false);
  const geoResolvedRef = useRef(false);
  const onSiteClickRef = useRef(onSiteClick);
  onSiteClickRef.current = onSiteClick;

  // 初始化地图（只运行一次）
  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;

    async function init() {
      await loadAMap();
      if (disposed || !containerRef.current) return;

      const map = new AMap.Map(containerRef.current, {
        zoom: MAP_DEFAULT_ZOOM,
        center: MAP_DEFAULT_CENTER, // [lng, lat] GCJ-02
        viewMode: "2D",
      });

      map.addControl(new AMap.Scale());

      map.on("zoomend", () => {
        const z = map.getZoom();
        setZoom(z);
      });

      // 事件委托：拦截 InfoWindow 内 [data-release-id] 链接点击
      containerRef.current.addEventListener("click", (e) => {
        const target = (e.target as HTMLElement).closest<HTMLElement>(
          "[data-release-id]",
        );
        if (target) {
          e.preventDefault();
          const releaseId = target.dataset.releaseId;
          if (releaseId) {
            infoWindowRef.current?.close();
            onSiteClickRef.current?.(releaseId);
          }
        }
      });

      mapRef.current = map;
      setMapReady(true);

      // 地理定位（使用浏览器原生 API）
      const isInChina = (lat: number, lng: number) =>
        lat >= 18 && lat <= 54 && lng >= 73 && lng <= 135;
      const BEIJING_TIANANMEN: [number, number] = [116.3975, 39.9087];

      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            if (disposed) return;
            const { latitude, longitude } = position.coords;
            console.log(`[Geolocation] 用户位置: ${latitude}, ${longitude}`);
            userLocatedRef.current = true;
            geoResolvedRef.current = true;
            if (isInChina(latitude, longitude)) {
              map.setZoomAndCenter(11, [longitude, latitude]);
            } else {
              map.setZoomAndCenter(11, BEIJING_TIANANMEN);
            }
          },
          (error) => {
            console.warn("[Geolocation] 获取位置失败:", error.message);
            geoResolvedRef.current = true;
          },
          { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
        );
      }
    }

    init().catch((error) => {
      console.error("[AMapContainer] init failed", error);
    });

    return () => {
      disposed = true;
      clusterRef.current?.setMap(null);
      clusterRef.current = null;
      infoWindowRef.current?.close();
      infoWindowRef.current = null;
      if (mapRef.current) {
        mapRef.current.destroy();
        mapRef.current = null;
      }
      setMapReady(false);
    };
  }, []);

  // 构建坐标重合的多条目弹窗 HTML
  const buildStackedPopupHtml = useCallback(
    (stackedSites: SiteMarkerData[]) => {
      const items = stackedSites
        .map((s) => {
          const prefix =
            s.markType === "visited"
              ? `<span style="color:#16a34a;margin-right:2px;">✓</span>`
              : s.markType === "wishlist"
                ? `<span style="color:#f59e0b;margin-right:2px;">☆</span>`
                : "";
          return `<div style="padding:6px 0;border-bottom:1px solid #eee;">
               ${prefix}<a href="#" data-release-id="${s.release_id}" style="color:#1890ff;font-size:13px;font-weight:500;text-decoration:none;cursor:pointer;">${s.name}</a>
               <span style="color:#999;font-size:12px;margin-left:6px;">${s.category}</span>
               ${s.era ? `<span style="color:#999;font-size:12px;"> · ${s.era}</span>` : ""}
             </div>`;
        })
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

  // 更新标记（sites / zoom / mapReady 变化时重建聚合层）
  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    const map = mapRef.current;

    // 清除旧的聚合和弹窗
    clusterRef.current?.setMap(null);
    clusterRef.current = null;
    infoWindowRef.current?.close();

    const validSites = sites.filter(
      (s) => s.latitude != null && s.longitude != null,
    );
    if (validSites.length === 0) return;

    // 按坐标分组
    const coordGroups = new Map<string, SiteMarkerData[]>();
    for (const site of validSites) {
      const key = `${site.longitude},${site.latitude}`;
      if (!coordGroups.has(key)) coordGroups.set(key, []);
      coordGroups.get(key)!.push(site);
    }

    // 构建数据点（堆叠的合并为一个点）
    type DataPoint = AMap.MarkerClusterDataOption & {
      _site?: SiteMarkerData;
      _stacked?: SiteMarkerData[];
    };

    const dataPoints: DataPoint[] = [];
    for (const group of coordGroups.values()) {
      const first = group[0];
      if (group.length > 1) {
        dataPoints.push({
          lnglat: [first.longitude, first.latitude],
          _stacked: group,
        });
      } else {
        dataPoints.push({
          lnglat: [first.longitude, first.latitude],
          _site: first,
        });
      }
    }

    // 创建共享 InfoWindow
    if (!infoWindowRef.current) {
      infoWindowRef.current = new AMap.InfoWindow({
        isCustom: false,
        offset: new AMap.Pixel(0, -30),
      });
    }
    const infoWindow = infoWindowRef.current;

    const currentZoom = map.getZoom();
    const useTextLabel = currentZoom >= TEXT_LABEL_MIN_ZOOM;
    const gridSize = calcGridSize(currentZoom);

    console.log(
      `[AMapContainer] zoom=${currentZoom} → gridSize=${gridSize}, textLabel=${useTextLabel}`,
    );

    // zoom >= CLUSTER_ZERO_AT_ZOOM 时，设 maxZoom 为当前 zoom-1 强制不聚合
    const effectiveMaxZoom =
      currentZoom >= CLUSTER_ZERO_AT_ZOOM ? currentZoom - 1 : 16;

    const cluster = new AMap.MarkerCluster(map, dataPoints, {
      gridSize,
      maxZoom: effectiveMaxZoom,
      renderMarker(ctx) {
        const data = ctx.data[0] as unknown as DataPoint;

        if (data._stacked) {
          // 堆叠标记
          const count = data._stacked.length;
          ctx.marker.setContent(
            `<div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-10px)">
               <div style="min-width:20px;height:20px;border-radius:4px;background:#e67e22;border:2px solid #fff;
                           box-shadow:0 1px 5px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;
                           padding:0 4px;font-size:11px;font-weight:700;color:#fff;white-space:nowrap;">${count}</div>
               <div style="width:2px;height:8px;background:#e67e22;opacity:0.9"></div>
             </div>`,
          );
          ctx.marker.setOffset(new AMap.Pixel(-10, -30));
          ctx.marker.on("click", () => {
            const html = buildStackedPopupHtml(data._stacked!);
            infoWindow.setContent(html);
            infoWindow.open(map, [
              data._stacked![0].longitude,
              data._stacked![0].latitude,
            ]);
          });
        } else if (data._site) {
          // 单站点标记
          const site = data._site;
          const color = CATEGORY_COLORS[site.category] ?? "#95a5a6";
          const markPrefix =
            site.markType === "visited"
              ? "✓ "
              : site.markType === "wishlist"
                ? "☆ "
                : "";
          const markBorder =
            site.markType === "visited"
              ? "border:2px solid #16a34a;"
              : site.markType === "wishlist"
                ? "border:2px solid #f59e0b;"
                : "";

          if (useTextLabel) {
            ctx.marker.setContent(
              `<div style="display:flex;flex-direction:column;align-items:center">
                 <div style="padding:2px 6px;border-radius:3px;background:${color};
                             font-size:12px;font-weight:600;color:#fff;white-space:nowrap;
                             box-shadow:0 1px 4px rgba(0,0,0,0.3);line-height:1.3;${markBorder}">${markPrefix}${site.name}</div>
                 <div style="width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;
                             border-top:4px solid ${color}"></div>
               </div>`,
            );
            ctx.marker.setOffset(new AMap.Pixel(0, -24));
          } else {
            ctx.marker.setContent(
              buildIconMarkerHtml(color, site.category, site.markType),
            );
            ctx.marker.setOffset(new AMap.Pixel(-9, -24));
          }
          ctx.marker.on("click", () =>
            onSiteClickRef.current?.(site.release_id),
          );
        }
      },
      renderClusterMarker(ctx) {
        const count = ctx.count;
        ctx.marker.setContent(
          `<div style="display:flex;align-items:center;justify-content:center;
                      width:36px;height:36px;border-radius:50%;
                      background:#fff;border:2px solid #666;
                      font-size:13px;font-weight:600;color:#333;
                      box-shadow:0 2px 6px rgba(0,0,0,0.25)">
            ${count}
          </div>`,
        );
        ctx.marker.setOffset(new AMap.Pixel(-18, -18));
      },
    });

    clusterRef.current = cluster;

    // fitBounds 逻辑：只在站点集合真正变化时执行
    const prevIds = prevSitesRef.current?.map((s) => s.id).join(",") ?? null;
    const currIds = sites.map((s) => s.id).join(",");
    if (prevIds !== currIds) {
      const isFirstLoad = prevSitesRef.current === null;
      prevSitesRef.current = sites;

      const doFitView = () => {
        try {
          // MarkerCluster 内部的 marker 不算地图直接覆盖物，
          // setFitView(null) 无法自动 fit，需手动计算边界
          if (validSites.length === 1) {
            map.setZoomAndCenter(14, [
              validSites[0].longitude,
              validSites[0].latitude,
            ]);
          } else {
            const lngs = validSites.map((s) => s.longitude);
            const lats = validSites.map((s) => s.latitude);
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const bounds = new (AMap as any).Bounds(
              [Math.min(...lngs), Math.min(...lats)],
              [Math.max(...lngs), Math.max(...lats)],
            );
            (map as any).setBounds(bounds, false, [40, 40, 40, 40]);
          }
        } catch (e) {
          console.warn("[AMapContainer] fitBounds failed", e);
        }
      };

      if (!isFirstLoad) {
        doFitView();
      } else if (geoResolvedRef.current) {
        if (userLocatedRef.current) {
          console.log("[AMapContainer] 用户已定位，跳过 fitView");
        } else {
          doFitView();
        }
      } else {
        setTimeout(() => {
          if (userLocatedRef.current) {
            console.log("[AMapContainer] 用户已定位，跳过 fitView");
          } else {
            doFitView();
          }
        }, 3000);
      }
    } else {
      prevSitesRef.current = sites;
    }
  }, [sites, mapReady, zoom, buildStackedPopupHtml]);

  return <div ref={containerRef} className="w-full h-full" />;
}
