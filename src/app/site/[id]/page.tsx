import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CATEGORY_COLORS, BATCH_YEARS } from "@/lib/constants";
import { getSiteById } from "@/lib/supabase/queries";
import BackButton from "@/components/site/BackButton";
import SiteMap from "@/components/map/SiteMap";
import type { SiteCategory } from "@/lib/types";
import Link from "next/link";

export default async function SiteDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const site = await getSiteById(id);

  if (!site) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">未找到该文保单位</h1>
          <BackButton />
        </div>
      </div>
    );
  }

  const categoryColor = CATEGORY_COLORS[site.category as SiteCategory];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 flex items-center gap-4">
        <BackButton />
        <h1 className="text-2xl font-bold">{site.name}</h1>
      </header>

      <div className="max-w-4xl mx-auto p-6 space-y-6">
        <div className="flex flex-wrap gap-2">
          <Badge style={{ backgroundColor: categoryColor, color: "white" }}>
            {site.category}
          </Badge>
          {site.era && <Badge variant="outline">{site.era}</Badge>}
          {site.batch && (
            <Badge variant="secondary">
              第{site.batch}批 ({BATCH_YEARS[site.batch!] || "未知"})
            </Badge>
          )}
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
              {site.address && (
                <div>
                  <span className="text-sm font-medium text-muted-foreground">
                    地址
                  </span>
                  <p>{site.address}</p>
                </div>
              )}
              <div>
                <span className="text-sm font-medium text-muted-foreground">
                  省份
                </span>
                <p>{site.province}</p>
              </div>
              {site.city && (
                <div>
                  <span className="text-sm font-medium text-muted-foreground">
                    城市
                  </span>
                  <p>{site.city}</p>
                </div>
              )}
              {site.wikipedia_url && (
                <div>
                  <Link
                    href={site.wikipedia_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline text-sm"
                  >
                    Wikipedia 页面 →
                  </Link>
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
