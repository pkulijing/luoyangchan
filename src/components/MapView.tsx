"use client";

import { useCallback, useState } from "react";
import dynamic from "next/dynamic";
import FilterPanel from "@/components/filters/FilterPanel";
import SiteDetailPanel from "@/components/site/SiteDetailPanel";
import { useFilters } from "@/hooks/useFilters";
import type { SiteListItem } from "@/lib/types";

const LeafletContainer = dynamic(
  () => import("@/components/map/LeafletContainer"),
  { ssr: false }
);

export default function MapView({ sites }: { sites: SiteListItem[] }) {
  const { filters, setFilters, filteredSites, markerData, provinces, cities, districts } = useFilters(sites);
  const [selectedReleaseId, setSelectedReleaseId] = useState<string | null>(null);

  const handleSiteClick = useCallback((releaseId: string) => {
    setSelectedReleaseId(releaseId);
  }, []);

  const handlePanelClose = useCallback(() => {
    setSelectedReleaseId(null);
  }, []);

  return (
    <main className="relative w-screen h-screen overflow-hidden">
      {/* z-0 给 Leaflet 创建独立 stacking context，避免内部高 z-index 的 pane 盖住 UI 浮层 */}
      <div className="absolute inset-0 z-0">
        <LeafletContainer sites={markerData} onSiteClick={handleSiteClick} />
      </div>

      <div className="absolute top-4 left-4 z-10">
        <FilterPanel
          filters={filters}
          onFiltersChange={setFilters}
          totalCount={sites.length}
          filteredCount={filteredSites.length}
          provinces={provinces}
          cities={cities}
          districts={districts}
        />
      </div>

      <div className="absolute top-4 right-16 z-10">
        <div className="bg-white/95 backdrop-blur-sm shadow-lg rounded-lg px-4 py-2">
          <h1 className="text-lg font-bold">洛阳铲</h1>
          <p className="text-xs text-muted-foreground">
            全国重点文物保护单位地图
          </p>
        </div>
      </div>

      <SiteDetailPanel
        releaseId={selectedReleaseId}
        onClose={handlePanelClose}
        onNavigate={handleSiteClick}
      />
    </main>
  );
}
