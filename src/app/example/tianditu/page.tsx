"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";

export default function TiandituExamplePage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<string[]>([]);

  function log(msg: string) {
    setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  }

  useEffect(() => {
    if (!containerRef.current) return;

    let disposed = false;

    async function init() {
      log("开始加载 Leaflet...");
      const L = (await import("leaflet")).default;
      log(`Leaflet ${L.version} 加载完成`);

      if (disposed || !containerRef.current) return;

      log("初始化地图，中心：北京 [116.4, 39.9]");
      const map = L.map(containerRef.current, {
        center: [39.9, 116.4], // [lat, lng]
        zoom: 10,
      });

      const tk = process.env.NEXT_PUBLIC_TIANDITU_TK ?? "";
      if (!tk) {
        log("警告：NEXT_PUBLIC_TIANDITU_TK 未设置，瓦片可能无法加载");
      } else {
        log(`Token: ${tk.slice(0, 8)}...（已隐藏）`);
      }

      log("添加天地图矢量底图（vec_w）...");
      const vecLayer = L.tileLayer(
        `http://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${tk}`,
        { subdomains: "01234567", maxZoom: 18, attribution: "天地图" }
      );
      vecLayer.on("loading", () => log("vec_w：正在加载瓦片..."));
      vecLayer.on("load", () => log("vec_w：瓦片加载完成"));
      vecLayer.on("tileerror", (e) => log(`vec_w：瓦片加载失败 - ${String(e)}`));
      vecLayer.addTo(map);

      log("添加天地图中文注记图层（cva_w）...");
      const cvaLayer = L.tileLayer(
        `http://t{s}.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${tk}`,
        { subdomains: "01234567", maxZoom: 18 }
      );
      cvaLayer.on("load", () => log("cva_w：注记图层加载完成"));
      cvaLayer.addTo(map);

      log("添加标记：天安门广场");
      L.marker([39.9054, 116.3976], {
        icon: L.divIcon({
          html: `<div style="background:#e74c3c;color:#fff;padding:4px 8px;border-radius:4px;font-size:12px;white-space:nowrap;">天安门</div>`,
          className: "",
          iconAnchor: [30, 12],
        }),
      })
        .bindPopup("天安门广场<br>WGS-84: 39.9054, 116.3976")
        .addTo(map);

      L.control.scale({ imperial: false }).addTo(map);
      log("比例尺控件已添加");
      log("初始化完成，请查看地图是否正常显示");
    }

    init().catch((e) => log(`错误：${String(e)}`));

    return () => {
      disposed = true;
    };
  }, []);

  return (
    <div className="flex h-screen">
      {/* 地图区域 */}
      <div ref={containerRef} className="flex-1" />

      {/* 日志面板 */}
      <div className="w-80 bg-gray-900 text-green-400 font-mono text-xs p-3 overflow-y-auto flex flex-col gap-1">
        <div className="text-gray-400 mb-2 font-bold">
          天地图 + Leaflet 验证 Demo
        </div>
        {logs.map((l, i) => (
          <div key={i}>{l}</div>
        ))}
      </div>
    </div>
  );
}
