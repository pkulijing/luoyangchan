"use client";

import dynamic from "next/dynamic";
import FilterPanel from "@/components/filters/FilterPanel";
import { useFilters } from "@/hooks/useFilters";
import type { SiteListItem } from "@/lib/types";

const AMapContainer = dynamic(
  () => import("@/components/map/AMapContainer"),
  { ssr: false }
);

export default function MapView({ sites }: { sites: SiteListItem[] }) {
  const { filters, setFilters, filteredSites, markerData } = useFilters(sites);

  return (
    <main className="relative w-screen h-screen overflow-hidden">
      <AMapContainer sites={markerData} />

      <div className="absolute top-4 left-4 z-10">
        <FilterPanel
          filters={filters}
          onFiltersChange={setFilters}
          totalCount={sites.length}
          filteredCount={filteredSites.length}
        />
      </div>

      <div className="absolute top-4 right-16 z-10">
        <div className="bg-white/95 backdrop-blur-sm shadow-lg rounded-lg px-4 py-2">
          <h1 className="text-lg font-bold">洛阳铲</h1>
          <p className="text-xs text-muted-foreground">全国重点文物保护单位地图</p>
        </div>
      </div>
    </main>
  );
}
