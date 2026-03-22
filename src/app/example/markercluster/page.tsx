"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { gcj02ToWgs84 } from "@/lib/coordConvert";

// 测试坐标为 GCJ-02（高德坐标系），模拟数据库数据
const TEST_POINTS = [
  { name: "北京",  lng: 116.3912, lat: 39.9062, color: "#e74c3c" },
  { name: "上海",  lng: 121.4737, lat: 31.2304, color: "#9b59b6" },
  { name: "广州",  lng: 113.2642, lat: 23.1292, color: "#f39c12" },
  { name: "成都",  lng: 104.0656, lat: 30.6594, color: "#2ecc71" },
  { name: "西安",  lng: 108.9481, lat: 34.2634, color: "#e74c3c" },
  { name: "南京",  lng: 118.7969, lat: 32.0586, color: "#3498db" },
  { name: "杭州",  lng: 120.1536, lat: 30.2937, color: "#9b59b6" },
  { name: "武汉",  lng: 114.3054, lat: 30.5931, color: "#f39c12" },
  { name: "沈阳",  lng: 123.4291, lat: 41.7968, color: "#2ecc71" },
  { name: "昆明",  lng: 102.8329, lat: 24.8802, color: "#3498db" },
];

export default function MarkerClusterExamplePage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  function log(msg: string) {
    if (!logRef.current) return;
    const line = document.createElement("div");
    line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logRef.current.prepend(line);
  }

  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;

    async function init() {
      log("加载 Leaflet + MarkerCluster...");
      const L = (await import("leaflet")).default;
      await import("leaflet.markercluster");
      log(`Leaflet ${L.version} 就绪，MarkerClusterGroup 可用：${"markerClusterGroup" in L}`);

      if (disposed || !containerRef.current) return;

      const map = L.map(containerRef.current, {
        center: [35.0, 104.0],
        zoom: 5,
      });

      const tk = process.env.NEXT_PUBLIC_TIANDITU_TK ?? "";
      L.tileLayer(
        `http://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${tk}`,
        { subdomains: "01234567", maxZoom: 18, attribution: "天地图" }
      ).addTo(map);
      L.tileLayer(
        `http://t{s}.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${tk}`,
        { subdomains: "01234567", maxZoom: 18 }
      ).addTo(map);
      log("天地图底图已添加");

      const cluster = L.markerClusterGroup({
        maxClusterRadius: 60,        // 等效于 AMap gridSize: 60
        disableClusteringAtZoom: 17, // 等效于 AMap maxZoom: 16
        chunkedLoading: true,
        iconCreateFunction: (c) => {
          const count = c.getChildCount();
          return L.divIcon({
            html: `<div style="display:flex;align-items:center;justify-content:center;
                              width:36px;height:36px;border-radius:50%;
                              background:#fff;border:2px solid #666;
                              font-size:13px;font-weight:600;color:#333;
                              box-shadow:0 2px 6px rgba(0,0,0,.25)">${count}</div>`,
            className: "",
            iconSize: [36, 36],
            iconAnchor: [18, 18],
          });
        },
      });

      log(`MarkerClusterGroup 创建完成，开始添加 ${TEST_POINTS.length} 个点...`);

      for (const point of TEST_POINTS) {
        const [wgsLng, wgsLat] = gcj02ToWgs84(point.lng, point.lat);
        log(`${point.name}: GCJ-02 → WGS-84(${wgsLat.toFixed(4)}, ${wgsLng.toFixed(4)})`);

        const marker = L.marker([wgsLat, wgsLng], {
          title: point.name,
          icon: L.divIcon({
            html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
                     <div style="width:14px;height:14px;border-radius:50%;background:${point.color};border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.3)"></div>
                     <div style="width:2px;height:7px;background:${point.color};opacity:.9"></div>
                   </div>`,
            className: "",
            iconSize: [14, 21],
            iconAnchor: [7, 21],
          }),
        });
        marker.bindPopup(`<strong>${point.name}</strong>`);
        cluster.addLayer(marker);
      }

      map.addLayer(cluster);
      log("聚合层已添加到地图");

      const bounds = cluster.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40] });
        log("fitBounds() 完成");
      }

      L.control.scale({ imperial: false }).addTo(map);
      log("完成，缩小可看到聚合气泡，放大至 17 级聚合解散");
    }

    init().catch((err) => {
      log(`错误：${err}`);
      console.error(err);
    });

    return () => {
      disposed = true;
    };
  }, []);

  return (
    <div className="flex flex-col h-screen">
      <div className="p-3 bg-gray-800 text-white text-sm font-mono">
        /example/markercluster — Leaflet MarkerCluster 测试（{TEST_POINTS.length} 个点，maxClusterRadius=60，disableAt=17）
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div ref={containerRef} className="flex-1" />
        <div
          ref={logRef}
          className="w-80 overflow-y-auto bg-gray-900 text-green-400 text-xs font-mono p-2 space-y-1"
        />
      </div>
    </div>
  );
}
