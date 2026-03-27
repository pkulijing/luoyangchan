import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CATEGORY_COLORS, BATCH_YEARS } from "@/lib/constants";
import { getSiteByReleaseId } from "@/lib/supabase/queries";
import BackButton from "@/components/site/BackButton";
import SiteImage from "@/components/site/SiteImage";
import type { SiteCategory } from "@/lib/types";
import Link from "next/link";

export default async function SiteDetailPage({
  params,
}: {
  params: Promise<{ releaseId: string }>;
}) {
  const { releaseId } = await params;
  const site = await getSiteByReleaseId(releaseId);

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
        <Link
          href={`/site/${site.release_id}/raw`}
          className="ml-auto text-xs text-gray-400 hover:text-gray-600"
        >
          raw
        </Link>
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
              {site.province && (
                <div>
                  <span className="text-sm font-medium text-muted-foreground">
                    省份
                  </span>
                  <p>{site.province}</p>
                </div>
              )}
              {site.city && (
                <div>
                  <span className="text-sm font-medium text-muted-foreground">
                    城市
                  </span>
                  <p>{site.city}</p>
                </div>
              )}
              {site.baike_url && (
                <div>
                  <Link
                    href={site.baike_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline text-sm"
                  >
                    百度百科 →
                  </Link>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">图片</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-md overflow-hidden">
                <SiteImage
                  imageUrl={site.image_url}
                  name={site.name}
                  longitude={site.longitude}
                  latitude={site.latitude}
                  heightClass="h-64"
                />
              </div>
              {site.latitude && site.longitude && (
                <p className="text-xs text-muted-foreground mt-2">
                  {site.latitude.toFixed(4)}, {site.longitude.toFixed(4)}
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 子记录列表（父记录详情页） */}
        {site.children.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                包含分段（{site.children.length}）
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1">
                {site.children.map((child) => (
                  <li key={child.id}>
                    <Link
                      href={`/site/${child.release_id}`}
                      className="text-blue-600 hover:underline text-sm"
                    >
                      {child.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* 所属文保单位 + 兄弟分段（子记录详情页） */}
        {site.parent && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">所属文保单位</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <Link
                  href={`/site/${site.parent.release_id}`}
                  className="text-blue-600 hover:underline font-medium"
                >
                  {site.parent.name}
                </Link>
              </div>
              {site.siblings.length > 0 && (
                <div>
                  <span className="text-sm font-medium text-muted-foreground">
                    其他分段
                  </span>
                  <ul className="mt-1 space-y-1">
                    {site.siblings.map((sib) => (
                      <li key={sib.id}>
                        <Link
                          href={`/site/${sib.release_id}`}
                          className="text-blue-600 hover:underline text-sm"
                        >
                          {sib.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        )}

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
