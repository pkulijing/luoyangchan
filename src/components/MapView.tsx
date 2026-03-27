"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import FilterPanel from "@/components/filters/FilterPanel";
import SiteDetailPanel from "@/components/site/SiteDetailPanel";
import { UserMenu } from "@/components/auth/UserMenu";
import { useAuth } from "@/components/auth/AuthProvider";
import { createClient } from "@/lib/supabase/client";
import { useFilters } from "@/hooks/useFilters";
import { MAP_PROVIDER } from "@/lib/mapProvider";
import type { MarkType, SiteListItem } from "@/lib/types";

const MapContainer = dynamic(
  () =>
    MAP_PROVIDER === "amap"
      ? import("@/components/map/AMapContainer")
      : import("@/components/map/LeafletContainer"),
  { ssr: false },
);

export default function MapView({ sites }: { sites: SiteListItem[] }) {
  const [selectedReleaseId, setSelectedReleaseId] = useState<string | null>(null);

  // 获取用户标记
  const { user } = useAuth();
  const [userMarks, setUserMarks] = useState<Map<string, MarkType>>(new Map());
  const [marksVersion, setMarksVersion] = useState(0);

  useEffect(() => {
    if (!user) {
      setUserMarks(new Map());
      return;
    }
    const supabase = createClient();
    supabase
      .from("user_site_marks")
      .select("site_id, mark_type")
      .eq("user_id", user.id)
      .then(({ data }) => {
        if (data) {
          setUserMarks(new Map(data.map((d) => [d.site_id, d.mark_type as MarkType])));
        }
      });
  }, [user, marksVersion]);

  const handleMarkChange = useCallback(() => {
    setMarksVersion((v) => v + 1);
  }, []);

  // 筛选（传入 userMarks 以支持标记筛选）
  const {
    filters,
    setFilters,
    filteredSites,
    markerData,
    provinces,
    cities,
    districts,
  } = useFilters(sites, userMarks);

  // 合并标记状态到 markerData
  const markerDataWithMarks = useMemo(() => {
    if (userMarks.size === 0) return markerData;
    return markerData.map((m) => {
      const markType = userMarks.get(m.id);
      return markType ? { ...m, markType } : m;
    });
  }, [markerData, userMarks]);

  const handleSiteClick = useCallback((releaseId: string) => {
    setSelectedReleaseId(releaseId);
  }, []);

  const handlePanelClose = useCallback(() => {
    setSelectedReleaseId(null);
  }, []);

  return (
    <main className="relative w-screen h-screen overflow-hidden">
      {/* z-0 创建独立 stacking context，避免地图内部高 z-index 盖住 UI 浮层 */}
      <div className="absolute inset-0 z-0">
        <MapContainer sites={markerDataWithMarks} onSiteClick={handleSiteClick} />
      </div>

      {/* 顶部栏：筛选按钮 + 标题 + 用户菜单 */}
      <div className="absolute top-4 left-4 right-4 z-10 flex items-start justify-between pointer-events-none">
        <div className="pointer-events-auto">
          <FilterPanel
            filters={filters}
            onFiltersChange={setFilters}
            totalCount={sites.length}
            filteredCount={filteredSites.length}
            provinces={provinces}
            cities={cities}
            districts={districts}
            isLoggedIn={!!user}
          />
        </div>
        <div className="flex items-start gap-2 pointer-events-auto shrink-0 ml-2">
          <div className="bg-white/95 backdrop-blur-sm shadow-lg rounded-lg px-3 py-1.5 hidden sm:block">
            <h1 className="text-lg font-bold">洛阳铲</h1>
            <p className="text-xs text-muted-foreground">
              全国重点文物保护单位地图
            </p>
          </div>
          <div className="bg-white/95 backdrop-blur-sm shadow-lg rounded-lg p-1.5">
            <UserMenu />
          </div>
        </div>
      </div>

      <SiteDetailPanel
        releaseId={selectedReleaseId}
        onClose={handlePanelClose}
        onNavigate={handleSiteClick}
        onMarkChange={handleMarkChange}
      />
    </main>
  );
}
