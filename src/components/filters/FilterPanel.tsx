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
import { SearchableSelect } from "@/components/ui/searchable-select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SlidersHorizontal, X } from "lucide-react";
import { SITE_CATEGORIES } from "@/lib/constants";
import type { FilterState } from "@/lib/types";

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
    <div className="w-96 bg-white/95 backdrop-blur-sm shadow-lg rounded-lg p-4 space-y-3">
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

      {/* 省市县一行 */}
      <div className="space-y-1">
        <label className="text-sm font-medium text-muted-foreground">地区</label>
        <div className="flex gap-1.5">
          <div className="flex-1 min-w-0">
            <SearchableSelect
              options={provinces}
              value={filters.province}
              onChange={(v) => updateFilter("province", v)}
              placeholder="省份"
              allLabel="全部省份"
            />
          </div>
          {cities.length > 0 && (
            <div className="flex-1 min-w-0">
              <SearchableSelect
                options={cities}
                value={filters.city}
                onChange={(v) => updateFilter("city", v)}
                placeholder="城市"
                allLabel="全部城市"
              />
            </div>
          )}
          {districts.length > 0 && (
            <div className="flex-1 min-w-0">
              <SearchableSelect
                options={districts}
                value={filters.district}
                onChange={(v) => updateFilter("district", v)}
                placeholder="区县"
                allLabel="全部区县"
              />
            </div>
          )}
        </div>
      </div>

      <div className="space-y-1">
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
