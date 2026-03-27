"use client";

import dynamic from "next/dynamic";

// SiteMap 使用地图 SDK（AMap 或 Leaflet），需要浏览器环境
const SiteMap = dynamic(() => import("@/components/map/SiteMap"), {
  ssr: false,
});

interface SiteMapClientProps {
  latitude: number;
  longitude: number;
  name: string;
}

export default function SiteMapClient(props: SiteMapClientProps) {
  return <SiteMap {...props} />;
}
