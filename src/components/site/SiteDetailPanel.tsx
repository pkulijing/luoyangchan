"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_COLORS, BATCH_YEARS } from "@/lib/constants";
import type { SiteWithRelations, SiteCategory } from "@/lib/types";

interface SiteDetailPanelProps {
  releaseId: string | null;
  onClose: () => void;
  /** 点击面板内的站点链接时，切换到该站点 */
  onNavigate: (releaseId: string) => void;
}

export default function SiteDetailPanel({
  releaseId,
  onClose,
  onNavigate,
}: SiteDetailPanelProps) {
  const [site, setSite] = useState<SiteWithRelations | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!releaseId) {
      setSite(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(`/api/site/${releaseId}`)
      .then((res) => {
        if (!res.ok) throw new Error("站点未找到");
        return res.json();
      })
      .then((data) => {
        if (!cancelled) {
          setSite(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [releaseId]);

  const open = releaseId !== null;
  const categoryColor = site
    ? (CATEGORY_COLORS[site.category as SiteCategory] ?? "#95a5a6")
    : "#95a5a6";

  return (
    <>
      {/* 遮罩：点击关闭面板 */}
      {open && (
        <div
          className="absolute inset-0 z-20"
          onClick={onClose}
        />
      )}

      {/* 面板 */}
      <div
        className={`absolute top-0 right-0 h-full w-1/3 min-w-[320px] max-w-[85vw] z-30
          bg-white shadow-2xl transition-transform duration-300 ease-in-out
          ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h2 className="text-lg font-bold truncate pr-2">
            {loading ? "加载中..." : site?.name ?? ""}
          </h2>
          <button
            onClick={onClose}
            className="shrink-0 w-8 h-8 flex items-center justify-center rounded-full
                       hover:bg-gray-100 text-gray-500 hover:text-gray-800 text-xl leading-none"
            aria-label="关闭"
          >
            &times;
          </button>
        </div>

        {/* 内容 */}
        <div className="overflow-y-auto h-[calc(100%-53px)] p-4 space-y-5">
          {loading && (
            <div className="flex items-center justify-center py-12 text-gray-400">
              加载中...
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center py-12 text-red-500">
              {error}
            </div>
          )}

          {site && !loading && (
            <>
              {/* Badges */}
              <div className="flex flex-wrap gap-2">
                <Badge style={{ backgroundColor: categoryColor, color: "white" }}>
                  {site.category}
                </Badge>
                {site.era && <Badge variant="outline">{site.era}</Badge>}
                {site.batch && (
                  <Badge variant="secondary">
                    第{site.batch}批 ({BATCH_YEARS[site.batch] || "未知"})
                  </Badge>
                )}
                {site.is_open !== null && (
                  <Badge variant={site.is_open ? "default" : "destructive"}>
                    {site.is_open ? "开放" : "未开放"}
                  </Badge>
                )}
              </div>

              {/* 基本信息 */}
              <div className="space-y-2 text-sm">
                {site.address && (
                  <div>
                    <span className="text-muted-foreground">地址：</span>
                    {site.address}
                  </div>
                )}
                {site.province && (
                  <div>
                    <span className="text-muted-foreground">省份：</span>
                    {site.province}
                    {site.city ? ` · ${site.city}` : ""}
                  </div>
                )}
                {site.baike_url && (
                  <div>
                    <a
                      href={site.baike_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      百度百科 →
                    </a>
                  </div>
                )}
              </div>

              {/* 简介 */}
              {site.description && (
                <div>
                  <h3 className="text-sm font-semibold mb-1">简介</h3>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {site.description}
                  </p>
                </div>
              )}

              {/* 子记录 */}
              {site.children.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold mb-1">
                    包含分段（{site.children.length}）
                  </h3>
                  <ul className="space-y-1">
                    {site.children.map((child) => (
                      <li key={child.id}>
                        <button
                          className="text-blue-600 hover:underline text-sm text-left"
                          onClick={() => child.release_id && onNavigate(child.release_id)}
                        >
                          {child.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 父记录 + 兄弟 */}
              {site.parent && (
                <div>
                  <h3 className="text-sm font-semibold mb-1">所属文保单位</h3>
                  <button
                    className="text-blue-600 hover:underline text-sm font-medium"
                    onClick={() => site.parent!.release_id && onNavigate(site.parent!.release_id)}
                  >
                    {site.parent.name}
                  </button>
                  {site.siblings.length > 0 && (
                    <div className="mt-2">
                      <span className="text-xs text-muted-foreground">其他分段</span>
                      <ul className="mt-1 space-y-1">
                        {site.siblings.map((sib) => (
                          <li key={sib.id}>
                            <button
                              className="text-blue-600 hover:underline text-sm text-left"
                              onClick={() => sib.release_id && onNavigate(sib.release_id)}
                            >
                              {sib.name}
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* 查看完整详情 */}
              <div className="pt-2 border-t">
                <a
                  href={`/site/${site.release_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline"
                >
                  查看完整详情（新窗口）→
                </a>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
