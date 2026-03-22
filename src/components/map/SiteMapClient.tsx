"use client";

import dynamic from "next/dynamic";

// SiteMap 使用 Leaflet，需要浏览器环境，必须通过 dynamic + ssr:false 加载
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
