"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import { gcj02ToWgs84 } from "@/lib/coordConvert";

// 测试坐标为 GCJ-02（高德坐标系），模拟从数据库读取的数据
const TEST_MARKERS = [
  { name: "北京", lng: 116.3912, lat: 39.9062 },
  { name: "上海", lng: 121.4737, lat: 31.2304 },
  { name: "广州", lng: 113.2642, lat: 23.1292 },
  { name: "成都", lng: 104.0656, lat: 30.6594 },
  { name: "西安", lng: 108.9481, lat: 34.2634 },
  { name: "南京", lng: 118.7969, lat: 32.0586 },
  { name: "杭州", lng: 120.1536, lat: 30.2937 },
  { name: "武汉", lng: 114.3054, lat: 30.5931 },
];

export default function MarkerExamplePage() {
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
      log("加载 Leaflet...");
      const L = (await import("leaflet")).default;
      log(`Leaflet ${L.version} 就绪`);

      if (disposed || !containerRef.current) return;

      const map = L.map(containerRef.current, {
        center: [35.0, 104.0], // [lat, lng]
        zoom: 5,
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
      log("天地图底图已添加");

      const leafletMarkers: ReturnType<typeof L.marker>[] = [];

      for (const point of TEST_MARKERS) {
        // GCJ-02 → WGS-84 坐标转换
        const [wgsLng, wgsLat] = gcj02ToWgs84(point.lng, point.lat);
        log(
          `${point.name}: GCJ-02(${point.lng}, ${point.lat}) → WGS-84(${wgsLng.toFixed(4)}, ${wgsLat.toFixed(4)})`,
        );

        const marker = L.marker([wgsLat, wgsLng], {
          title: point.name,
          icon: L.divIcon({
            html: `<div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
                     <div style="width:14px;height:14px;border-radius:50%;background:#e74c3c;border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.3)"></div>
                     <div style="width:2px;height:7px;background:#e74c3c;opacity:.9"></div>
                   </div>`,
            className: "",
            iconSize: [14, 21],
            iconAnchor: [7, 21],
          }),
        });
        marker.on("click", () => log(`点击了：${point.name}`));
        marker.addTo(map);
        leafletMarkers.push(marker);
      }

      log(`已添加 ${leafletMarkers.length} 个 Marker`);

      const group = L.featureGroup(leafletMarkers);
      map.fitBounds(group.getBounds(), { padding: [40, 40] });
      log("fitBounds() 完成");

      L.control.scale({ imperial: false }).addTo(map);
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
        /example/marker — Leaflet + 天地图 Marker 测试（{TEST_MARKERS.length}{" "}
        个点，含 GCJ-02→WGS-84 转换）
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
