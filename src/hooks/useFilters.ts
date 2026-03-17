"use client";

import { useState, useMemo } from "react";
import type { FilterState, HeritageSite, SiteMarkerData } from "@/lib/types";

export function useFilters(sites: HeritageSite[]) {
  const [filters, setFilters] = useState<FilterState>({
    province: null,
    category: null,
    era: null,
    search: "",
  });

  const filteredSites = useMemo(() => {
    return sites.filter((site) => {
      if (filters.province && filters.province !== "all" && site.province !== filters.province) {
        return false;
      }
      if (filters.category && (filters.category as string) !== "all" && site.category !== filters.category) {
        return false;
      }
      if (filters.era && site.era && !site.era.includes(filters.era)) {
        return false;
      }
      if (
        filters.search &&
        !site.name.toLowerCase().includes(filters.search.toLowerCase())
      ) {
        return false;
      }
      return true;
    });
  }, [sites, filters]);

  const markerData: SiteMarkerData[] = useMemo(() => {
    return filteredSites
      .filter((s) => s.latitude != null && s.longitude != null)
      .map((s) => ({
        id: s.id,
        name: s.name,
        latitude: s.latitude!,
        longitude: s.longitude!,
        category: s.category,
        era: s.era,
        province: s.province,
      }));
  }, [filteredSites]);

  return {
    filters,
    setFilters,
    filteredSites,
    markerData,
  };
}
