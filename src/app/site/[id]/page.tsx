"use client";

import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CATEGORY_COLORS, BATCH_YEARS } from "@/lib/constants";
import { MOCK_SITES } from "@/lib/mock-data";
import type { SiteCategory } from "@/lib/types";

const SiteMap = dynamic(() => import("@/components/map/SiteMap"), {
  ssr: false,
});

export default function SiteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const site = MOCK_SITES.find((s) => s.id === params.id);

  if (!site) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">未找到该文保单位</h1>
          <Button onClick={() => router.push("/")}>返回地图</Button>
        </div>
      </div>
    );
  }

  const categoryColor = CATEGORY_COLORS[site.category as SiteCategory];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 flex items-center gap-4">
        <Button variant="ghost" onClick={() => router.push("/")}>
          ← 返回地图
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{site.name}</h1>
          <p className="text-sm text-muted-foreground">{site.code}</p>
        </div>
      </header>

      <div className="max-w-4xl mx-auto p-6 space-y-6">
        <div className="flex flex-wrap gap-2">
          <Badge
            style={{ backgroundColor: categoryColor, color: "white" }}
          >
            {site.category}
          </Badge>
          {site.era && <Badge variant="outline">{site.era}</Badge>}
          <Badge variant="secondary">
            第{site.batch}批 ({BATCH_YEARS[site.batch] || "未知"})
          </Badge>
          {site.is_open !== null && (
            <Badge variant={site.is_open ? "default" : "destructive"}>
              {site.is_open ? "开放" : "未开放"}
            </Badge>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">基本信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <span className="text-sm font-medium text-muted-foreground">地址</span>
                <p>{site.address || `${site.province} ${site.city || ""}`}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">省份</span>
                <p>{site.province}</p>
              </div>
              {site.city && (
                <div>
                  <span className="text-sm font-medium text-muted-foreground">城市</span>
                  <p>{site.city}</p>
                </div>
              )}
              {site.wikipedia_url && (
                <div>
                  <a
                    href={site.wikipedia_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline text-sm"
                  >
                    Wikipedia 页面 →
                  </a>
                </div>
              )}
            </CardContent>
          </Card>

          {site.latitude && site.longitude && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">位置</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64 rounded-md overflow-hidden">
                  <SiteMap
                    latitude={site.latitude}
                    longitude={site.longitude}
                    name={site.name}
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  {site.latitude.toFixed(4)}, {site.longitude.toFixed(4)}
                </p>
              </CardContent>
            </Card>
          )}
        </div>

        {site.description && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">简介</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="leading-relaxed">{site.description}</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
