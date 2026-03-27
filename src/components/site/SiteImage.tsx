"use client";

import { gcj02ToWgs84 } from "@/lib/coordConvert";

interface SiteImageProps {
  imageUrl: string | null;
  name: string;
  /** GCJ-02 经度（用于天地图静态图 fallback） */
  longitude?: number | null;
  /** GCJ-02 纬度 */
  latitude?: number | null;
  /** 图片高度 class，如 "h-48" 或 "h-64" */
  heightClass?: string;
  className?: string;
}

/**
 * 站点图片组件：
 * 1. 有 imageUrl → 显示图片
 * 2. 无图但有坐标 → 天地图卫星静态图
 * 3. 都没有 → 占位提示 + 百度搜索链接
 */
export default function SiteImage({
  imageUrl,
  name,
  longitude,
  latitude,
  heightClass = "h-48",
  className = "",
}: SiteImageProps) {
  const baiduSearchUrl = `https://image.baidu.com/search/index?tn=baiduimage&word=${encodeURIComponent(name)}`;

  // 有图片 URL
  if (imageUrl) {
    return (
      <div className={`${heightClass} overflow-hidden ${className}`}>
        <img
          src={imageUrl}
          alt={name}
          referrerPolicy="no-referrer"
          className="w-full h-full object-cover"
        />
      </div>
    );
  }

  // 无图但有坐标 → 天地图卫星静态图
  if (longitude && latitude) {
    const tk = process.env.NEXT_PUBLIC_TIANDITU_TK ?? "";
    const [wgsLng, wgsLat] = gcj02ToWgs84(longitude, latitude);
    const staticUrl = `http://api.tianditu.gov.cn/staticimage`
      + `?center=${wgsLng.toFixed(6)},${wgsLat.toFixed(6)}`
      + `&width=600&height=300&zoom=16`
      + `&layers=img_c,cia_c`
      + `&tk=${tk}`;

    return (
      <div className={`relative ${heightClass} overflow-hidden ${className}`}>
        <img
          src={staticUrl}
          alt={`${name} 卫星图`}
          className="w-full h-full object-cover"
        />
        <div className="absolute bottom-0 inset-x-0 bg-black/50 px-2 py-1">
          <span className="text-xs text-white/80">卫星图 · 天地图</span>
        </div>
      </div>
    );
  }

  // 都没有 → 占位
  return (
    <div
      className={`${heightClass} flex flex-col items-center justify-center
        bg-gray-100 text-gray-400 ${className}`}
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
      <a
        href={baiduSearchUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-blue-500 hover:underline"
      >
        去百度搜索图片 →
      </a>
    </div>
  );
}
