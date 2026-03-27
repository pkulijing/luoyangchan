"use client";

import { useState } from "react";
import { gcj02ToWgs84 } from "@/lib/coordConvert";

interface SiteImageProps {
  imageUrl: string | null;
  baikeImageUrl: string | null;
  name: string;
  /** GCJ-02 经度（用于静态地图 fallback） */
  longitude?: number | null;
  /** GCJ-02 纬度 */
  latitude?: number | null;
  /** 图片高度 class，如 "h-48" 或 "h-64" */
  heightClass?: string;
  className?: string;
}

const useBaikeImages = process.env.NEXT_PUBLIC_USE_BAIKE_IMAGES !== "false";
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";

/**
 * 站点图片组件，4 级优先级（自动降级）：
 * 1. image_url（自托管 Supabase Storage）
 * 2. baike_image_url（百度 CDN，可配置关闭）
 * 3. 天地图卫星静态图（有坐标时）
 * 4. 占位提示
 *
 * 每级加载失败时自动尝试下一级。百度搜索图片链接始终显示。
 */
export default function SiteImage({
  imageUrl,
  baikeImageUrl,
  name,
  longitude,
  latitude,
  heightClass = "h-48",
  className = "",
}: SiteImageProps) {
  // 跟踪哪些来源已失败
  const [selfHostedFailed, setSelfHostedFailed] = useState(false);
  const [baikeFailed, setBaikeFailed] = useState(false);

  const baiduSearchUrl = `https://image.baidu.com/search/index?tn=baiduimage&word=${encodeURIComponent(name)}`;

  // 按优先级决定当前展示的图片
  let resolvedUrl: string | null = null;
  let isBaikeCdn = false;

  if (imageUrl && !selfHostedFailed) {
    resolvedUrl = `${supabaseUrl}/storage/v1/object/public/${imageUrl}`;
  } else if (baikeImageUrl && useBaikeImages && !baikeFailed) {
    resolvedUrl = baikeImageUrl;
    isBaikeCdn = true;
  }

  // 有可用图片
  if (resolvedUrl) {
    return (
      <div className={className}>
        <div className={`${heightClass} overflow-hidden`}>
          <img
            src={resolvedUrl}
            alt={name}
            referrerPolicy={isBaikeCdn ? "no-referrer" : undefined}
            className="w-full h-full object-cover"
            onError={() => {
              if (!isBaikeCdn) setSelfHostedFailed(true);
              else setBaikeFailed(true);
            }}
          />
        </div>
      </div>
    );
  }

  // 无图但有坐标 → 天地图卫星静态图（无论地图提供者，静态图统一用天地图）
  if (longitude && latitude) {
    const tk = process.env.NEXT_PUBLIC_TIANDITU_TK ?? "";
    const [wgsLng, wgsLat] = gcj02ToWgs84(longitude, latitude);
    const staticUrl =
      `http://api.tianditu.gov.cn/staticimage` +
      `?center=${wgsLng.toFixed(6)},${wgsLat.toFixed(6)}` +
      `&width=600&height=300&zoom=16` +
      `&layers=img_c,cia_c` +
      `&tk=${tk}`;
    const label = "卫星图 · 天地图";

    return (
      <div className={className}>
        <div className={`relative ${heightClass} overflow-hidden`}>
          <img
            src={staticUrl}
            alt={`${name} 卫星图`}
            className="w-full h-full object-cover"
          />
          <div className="absolute bottom-0 inset-x-0 bg-black/50 px-2 py-1">
            <span className="text-xs text-white/80">{label}</span>
          </div>
        </div>
      </div>
    );
  }

  // 都没有 → 占位
  return (
    <div className={className}>
      <div
        className={`${heightClass} flex flex-col items-center justify-center
          bg-gray-100 text-gray-400`}
      >
        <svg
          className="w-10 h-10 mb-2 opacity-40"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"
          />
        </svg>
        <span className="text-xs mb-1">图片暂缺</span>
      </div>
    </div>
  );
}
