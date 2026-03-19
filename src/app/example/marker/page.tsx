"use client";

import { useEffect, useRef } from "react";
import { loadAMap } from "@/lib/amap";

// 几个有代表性的城市坐标（GCJ-02，高德直接用）
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
      log("loadAMap() 开始...");
      await loadAMap();
      log("loadAMap() 完成");

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

      const markers: AMap.Marker[] = [];

      for (const point of TEST_MARKERS) {
        const marker = new AMap.Marker({
          position: new AMap.LngLat(point.lng, point.lat),
          title: point.name,
          content: `
            <div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
              <div style="width:14px;height:14px;border-radius:50%;background:#e74c3c;border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.3)"></div>
              <div style="width:2px;height:7px;background:#e74c3c;opacity:.9"></div>
            </div>
          `,
          offset: new AMap.Pixel(-7, -21),
        });
        marker.on("click", () => log(`点击了：${point.name}`));
        marker.setMap(map);
        markers.push(marker);
      }

      log(`已添加 ${markers.length} 个 Marker`);
      map.setFitView(markers, false, [40, 40, 40, 40]);
      log("setFitView() 完成");
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
        /example/marker — 基础 AMap.Marker 测试（{TEST_MARKERS.length} 个点）
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
