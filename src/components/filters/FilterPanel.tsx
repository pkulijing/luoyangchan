"use client";

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
import { PROVINCES, SITE_CATEGORIES } from "@/lib/constants";
import type { FilterState, SiteCategory } from "@/lib/types";

interface FilterPanelProps {
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  totalCount: number;
  filteredCount: number;
}

export default function FilterPanel({
  filters,
  onFiltersChange,
  totalCount,
  filteredCount,
}: FilterPanelProps) {
  const updateFilter = (key: keyof FilterState, value: string | null) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  const clearFilters = () => {
    onFiltersChange({ province: null, category: null, era: null, search: "" });
  };

  const hasActiveFilters =
    filters.province || filters.category || filters.era || filters.search;

  return (
    <div className="w-80 bg-white/95 backdrop-blur-sm shadow-lg rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">筛选</h2>
        <Badge variant="secondary">
          {filteredCount} / {totalCount}
        </Badge>
      </div>

      <Input
        placeholder="搜索文保单位名称..."
        value={filters.search}
        onChange={(e) => updateFilter("search", e.target.value)}
      />

      <div className="space-y-2">
        <label className="text-sm font-medium text-muted-foreground">省份</label>
        <Select
          value={filters.province || ""}
          onValueChange={(v) => updateFilter("province", v || null)}
        >
          <SelectTrigger>
            <SelectValue placeholder="全部省份" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部省份</SelectItem>
            {PROVINCES.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium text-muted-foreground">类型</label>
        <Select
          value={filters.category || ""}
          onValueChange={(v) => updateFilter("category", v || null)}
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

      <div className="space-y-2">
        <label className="text-sm font-medium text-muted-foreground">时代</label>
        <Input
          placeholder="如：唐、明清、商..."
          value={filters.era || ""}
          onChange={(e) => updateFilter("era", e.target.value || null)}
        />
      </div>

      {hasActiveFilters && (
        <Button variant="outline" size="sm" onClick={clearFilters} className="w-full">
          清除筛选
        </Button>
      )}
    </div>
  );
}
