"use client";

import { useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SlidersHorizontal, X } from "lucide-react";
import { SITE_CATEGORIES } from "@/lib/constants";
import type { FilterState, SiteCategory } from "@/lib/types";

interface FilterPanelProps {
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  totalCount: number;
  filteredCount: number;
  provinces: string[];
  cities: string[];
  districts: string[];
}

export default function FilterPanel({
  filters,
  onFiltersChange,
  totalCount,
  filteredCount,
  provinces,
  cities,
  districts,
}: FilterPanelProps) {
  const [open, setOpen] = useState(false);

  const updateFilter = (key: keyof FilterState, value: string | null) => {
    const next = { ...filters, [key]: value };
    // 级联清除：改省时清市县，改市时清县
    if (key === "province") {
      next.city = null;
      next.district = null;
    } else if (key === "city") {
      next.district = null;
    }
    onFiltersChange(next);
  };

  const clearFilters = () => {
    onFiltersChange({ search: "", category: null, province: null, city: null, district: null });
  };

  const hasActiveFilters =
    filters.province || filters.category || filters.search || filters.city || filters.district;

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 bg-white/95 backdrop-blur-sm shadow-lg rounded-lg px-3 py-2 hover:bg-white transition-colors"
      >
        <SlidersHorizontal size={16} />
        <span className="text-sm font-medium">筛选</span>
        {hasActiveFilters && (
          <Badge variant="secondary" className="ml-1">
            {filteredCount} / {totalCount}
          </Badge>
        )}
      </button>
    );
  }

  return (
    <div className="w-80 bg-white/95 backdrop-blur-sm shadow-lg rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">筛选</h2>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            {filteredCount} / {totalCount}
          </Badge>
          <button
            onClick={() => setOpen(false)}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      <Input
        placeholder="搜索文保单位名称..."
        value={filters.search}
        onChange={(e) => updateFilter("search", e.target.value)}
      />

      {/* 省市县三级联动 */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-muted-foreground">地区</label>
        <Select
          value={filters.province || ""}
          onValueChange={(v) => updateFilter("province", v === "all" ? null : v)}
        >
          <SelectTrigger>
            <SelectValue placeholder="全部省份" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部省份</SelectItem>
            {provinces.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {cities.length > 0 && (
          <Select
            value={filters.city || ""}
            onValueChange={(v) => updateFilter("city", v === "all" ? null : v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="全部城市" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部城市</SelectItem>
              {cities.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {districts.length > 0 && (
          <Select
            value={filters.district || ""}
            onValueChange={(v) => updateFilter("district", v === "all" ? null : v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="全部区县" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部区县</SelectItem>
              {districts.map((d) => (
                <SelectItem key={d} value={d}>
                  {d}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium text-muted-foreground">类型</label>
        <Select
          value={filters.category || ""}
          onValueChange={(v) => updateFilter("category", v === "all" ? null : v)}
        >
          <SelectTrigger>
            <SelectValue placeholder="全部类型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部类型</SelectItem>
            {SITE_CATEGORIES.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {hasActiveFilters && (
        <Button variant="outline" size="sm" onClick={clearFilters} className="w-full">
          清除筛选
        </Button>
      )}
    </div>
  );
}
