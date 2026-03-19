"use client";

import { useEffect, useRef } from "react";
import { loadAMap } from "@/lib/amap";

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
      log("loadAMap() 开始...");
      await loadAMap();
      log("loadAMap() 完成");
      log(`AMap.MarkerCluster 可用：${typeof AMap.MarkerCluster}`);

      if (disposed || !containerRef.current) return;

      const map = new AMap.Map(containerRef.current, {
        zoom: 5,
        center: [104.0, 35.0],
        viewMode: "2D",
        mapStyle: "amap://styles/whitesmoke",
      });
      log("AMap.Map 创建完成");

      map.addControl(new AMap.Scale());
      map.addControl(new AMap.ToolBar({ position: "RT" }));

      // AMap 2.0 MarkerCluster 数据驱动模式：
      // - 第二个参数是 { lnglat, ...自定义字段 } 数组
      // - renderMarker：每个未聚合的单点，可按数据自定义样式（支持不同颜色）
      // - renderClusterMarker：聚合气泡
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const dataPoints = TEST_POINTS.map((p) => ({ lnglat: [p.lng, p.lat], name: p.name, color: p.color }));
      log(`数据点已准备，共 ${dataPoints.length} 个`);

      function markerContent(color: string) {
        return `
          <div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
            <div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.3)"></div>
            <div style="width:2px;height:7px;background:${color};opacity:.9"></div>
          </div>`;
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const cluster = new (AMap as any).MarkerCluster(map, dataPoints, {
        gridSize: 60,
        maxZoom: 16,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        renderMarker(ctx: any) {
          const { color, name } = ctx.data[0];
          ctx.marker.setContent(markerContent(color));
          ctx.marker.setOffset(new AMap.Pixel(-7, -21));
          ctx.marker.setTitle(name);
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        renderClusterMarker(ctx: any) {
          const count = ctx.count;
          ctx.marker.setContent(`
            <div style="display:flex;align-items:center;justify-content:center;
                        width:36px;height:36px;border-radius:50%;
                        background:#fff;border:2px solid #666;
                        font-size:13px;font-weight:600;color:#333;
                        box-shadow:0 2px 6px rgba(0,0,0,.25)">
              ${count}
            </div>`);
          ctx.marker.setOffset(new AMap.Pixel(-18, -18));
        },
      });

      log(`MarkerCluster 创建完成：${typeof cluster}`);
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
        /example/markercluster — AMap.MarkerCluster 测试（{TEST_POINTS.length} 个固定城市坐标，gridSize=60，maxZoom=16）
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div ref={containerRef} className="flex-1" />
        <div
          ref={logRef}
          className="w-72 overflow-y-auto bg-gray-900 text-green-400 text-xs font-mono p-2 space-y-1"
        />
      </div>
    </div>
  );
}
