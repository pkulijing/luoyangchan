"use client";

import { useEffect, useRef, useState } from "react";
import { loadAMap } from "@/lib/amap";
import { CATEGORY_COLORS } from "@/lib/constants";
import type { SiteCategory } from "@/lib/types";

const TEST_POINTS: {
  name: string;
  lnglat: [number, number]; // GCJ-02 [lng, lat]
  category: SiteCategory;
}[] = [
  { name: "故宫", lnglat: [116.397, 39.9163], category: "古建筑" },
  { name: "天坛", lnglat: [116.4107, 39.8822], category: "古建筑" },
  { name: "颐和园", lnglat: [116.2755, 39.9999], category: "古建筑" },
  { name: "明十三陵", lnglat: [116.2353, 40.2529], category: "古墓葬" },
  { name: "周口店遗址", lnglat: [115.9292, 39.7268], category: "古遗址" },
  { name: "卢沟桥", lnglat: [116.1869, 39.8439], category: "近现代重要史迹及代表性建筑" },
  { name: "云居寺塔及石经", lnglat: [115.7854, 39.6327], category: "石窟寺及石刻" },
  { name: "长城（八达岭）", lnglat: [116.0164, 40.3549], category: "古建筑" },
  // 堆叠测试：两个点用同一坐标
  { name: "国子监", lnglat: [116.4169, 39.9468], category: "古建筑" },
  { name: "孔庙", lnglat: [116.4169, 39.9468], category: "古建筑" },
];

export default function AMapExamplePage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<string[]>([]);

  function log(msg: string) {
    setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  }

  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;

    async function init() {
      log("开始加载高德 JS API 2.0...");
      const AMapSDK = await loadAMap();
      log(`高德 JS API 加载完成`);

      if (disposed || !containerRef.current) return;

      const key = process.env.NEXT_PUBLIC_AMAP_KEY ?? "";
      if (!key) {
        log("警告：NEXT_PUBLIC_AMAP_KEY 未设置");
      } else {
        log(`Key: ${key.slice(0, 8)}...（已隐藏）`);
      }

      log("初始化地图，中心：北京 [116.4, 39.9]");
      const map = new AMapSDK.Map(containerRef.current, {
        zoom: 10,
        center: [116.4, 39.9],
        viewMode: "2D",
      });
      map.addControl(new AMapSDK.Scale());
      log("比例尺控件已添加");

      // 测试 MarkerCluster
      log(`创建 ${TEST_POINTS.length} 个测试标记（含 2 个堆叠）...`);

      const dataPoints = TEST_POINTS.map((p) => ({
        lnglat: p.lnglat as [number, number],
        name: p.name,
        category: p.category,
      }));

      let renderMarkerCallCount = 0;

      const cluster = new AMapSDK.MarkerCluster(map, dataPoints, {
        gridSize: 60,
        maxZoom: 16,
        renderMarker(ctx) {
          renderMarkerCallCount++;
          const item = ctx.data[0] as unknown as {
            name: string;
            category: SiteCategory;
          };
          const color =
            CATEGORY_COLORS[item.category] ?? "#95a5a6";
          ctx.marker.setContent(`
            <div style="display:flex;flex-direction:column;align-items:center;transform:translateY(-8px)">
              <div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,0.3)"></div>
              <div style="width:2px;height:7px;background:${color};opacity:0.9"></div>
            </div>
          `);
          ctx.marker.setOffset(new AMapSDK.Pixel(-7, -21));
          ctx.marker.on("click", () => {
            log(`点击标记：${item.name}（${item.category}）`);
          });
        },
        renderClusterMarker(ctx) {
          const count = ctx.count;
          ctx.marker.setContent(`
            <div style="display:flex;align-items:center;justify-content:center;
                        width:36px;height:36px;border-radius:50%;
                        background:#fff;border:2px solid #666;
                        font-size:13px;font-weight:600;color:#333;
                        box-shadow:0 2px 6px rgba(0,0,0,0.25)">
              ${count}
            </div>
          `);
          ctx.marker.setOffset(new AMapSDK.Pixel(-18, -18));
        },
      });

      log(`MarkerCluster 已创建（gridSize:60, maxZoom:16）`);

      // 监听 zoomend 以验证 renderMarker 是否被重新调用
      map.on("zoomend", () => {
        const z = map.getZoom();
        log(`zoomend → zoom=${z}, renderMarker 累计调用: ${renderMarkerCallCount} 次`);
      });

      // fitView
      try {
        map.setFitView(null, false, [40, 40, 40, 40]);
        log("setFitView 完成");
      } catch (e) {
        log(`setFitView 失败: ${String(e)}`);
      }

      log("初始化完成 — 请缩放地图观察 renderMarker 调用次数变化");
      void cluster; // keep reference
    }

    init().catch((e) => log(`错误：${String(e)}`));

    return () => {
      disposed = true;
    };
  }, []);

  return (
    <div className="flex h-screen">
      <div ref={containerRef} className="flex-1" />
      <div className="w-80 bg-gray-900 text-green-400 font-mono text-xs p-3 overflow-y-auto flex flex-col gap-1">
        <div className="text-gray-400 mb-2 font-bold">
          高德 JS API 2.0 验证 Demo
        </div>
        {logs.map((l, i) => (
          <div key={i}>{l}</div>
        ))}
      </div>
    </div>
  );
}
