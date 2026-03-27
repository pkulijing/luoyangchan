"use client";

import { useState, useMemo } from "react";
import type { FilterState, SiteListItem, SiteMarkerData } from "@/lib/types";

export function useFilters(sites: SiteListItem[]) {
  const [filters, setFilters] = useState<FilterState>({
    search: "",
    category: null,
    province: null,
    city: null,
    district: null,
  });

  const filteredSites = useMemo(() => {
    return sites.filter((site) => {
      if (filters.province && site.province !== filters.province) {
        return false;
      }
      if (filters.city && site.city !== filters.city) {
        return false;
      }
      if (filters.district && site.district !== filters.district) {
        return false;
      }
      if (filters.category && (filters.category as string) !== "all" && site.category !== filters.category) {
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

  // 从数据中动态提取省市县选项
  const provinces = useMemo(() => {
    const set = new Set<string>();
    for (const s of sites) {
      if (s.province) set.add(s.province);
    }
    return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
  }, [sites]);

  const cities = useMemo(() => {
    if (!filters.province) return [];
    const set = new Set<string>();
    for (const s of sites) {
      if (s.province === filters.province && s.city) set.add(s.city);
    }
    return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
  }, [sites, filters.province]);

  const districts = useMemo(() => {
    if (!filters.city) return [];
    const set = new Set<string>();
    for (const s of sites) {
      if (s.city === filters.city && s.district) set.add(s.district);
    }
    return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
  }, [sites, filters.city]);

  const markerData: SiteMarkerData[] = useMemo(() => {
    return filteredSites
      .filter((s) => s.latitude != null && s.longitude != null)
      .map((s) => ({
        id: s.id,
        release_id: s.release_id!,
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
    provinces,
    cities,
    districts,
  };
}
