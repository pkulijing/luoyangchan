"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card } from "@/components/ui/card";
import Link from "next/link";
import { CATEGORY_COLORS } from "@/lib/constants";
import type { SiteCategory } from "@/lib/types";

interface UserStatsGridProps {
  userId: string;
}

interface ProvinceStats {
  province: string;
  count: number;
}

interface CategoryStats {
  category: string;
  count: number;
}

export function UserStatsGrid({ userId }: UserStatsGridProps) {
  const [provinceStats, setProvinceStats] = useState<ProvinceStats[]>([]);
  const [categoryStats, setCategoryStats] = useState<CategoryStats[]>([]);
  const [loading, setLoading] = useState(true);

  const supabase = createClient();

  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);

      // 获取省份分布
      const { data: provinceData } = await supabase
        .from("user_site_marks")
        .select(
          `
          site_id,
          heritage_sites!inner (
            province
          )
        `
        )
        .eq("user_id", userId)
        .eq("mark_type", "visited");

      // 获取类别分布
      const { data: categoryData } = await supabase
        .from("user_site_marks")
        .select(
          `
          site_id,
          heritage_sites!inner (
            category
          )
        `
        )
        .eq("user_id", userId)
        .eq("mark_type", "visited");

      // 统计省份
      const provinceCounts: Record<string, number> = {};
      provinceData?.forEach((item) => {
        const sites = item.heritage_sites as unknown as { province: string | null };
        const province = sites?.province;
        if (province) {
          provinceCounts[province] = (provinceCounts[province] || 0) + 1;
        }
      });

      // 统计类别
      const categoryCounts: Record<string, number> = {};
      categoryData?.forEach((item) => {
        const sites = item.heritage_sites as unknown as { category: string | null };
        const category = sites?.category;
        if (category) {
          categoryCounts[category] = (categoryCounts[category] || 0) + 1;
        }
      });

      setProvinceStats(
        Object.entries(provinceCounts)
          .map(([province, count]) => ({ province, count }))
          .sort((a, b) => b.count - a.count)
      );

      setCategoryStats(
        Object.entries(categoryCounts)
          .map(([category, count]) => ({ category, count }))
          .sort((a, b) => b.count - a.count)
      );

      setLoading(false);
    };

    if (userId) {
      fetchStats();
    }
  }, [userId, supabase]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="h-48 animate-pulse rounded-xl bg-muted" />
        <div className="h-48 animate-pulse rounded-xl bg-muted" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* 省份分布 */}
      <Card className="p-4">
        <h3 className="text-lg font-semibold mb-4">省份分布</h3>
        {provinceStats.length > 0 ? (
          <div className="space-y-2">
            {provinceStats.slice(0, 10).map((stat) => (
              <div key={stat.province} className="flex items-center gap-2">
                <span className="w-20 text-sm truncate">{stat.province}</span>
                <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full"
                    style={{
                      width: `${Math.min(100, (stat.count / provinceStats[0].count) * 100)}%`,
                    }}
                  />
                </div>
                <span className="w-8 text-sm text-right">{stat.count}</span>
              </div>
            ))}
            {provinceStats.length > 10 && (
              <p className="text-xs text-muted-foreground mt-2">
                还有 {provinceStats.length - 10} 个省份...
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">暂无数据</p>
        )}
      </Card>

      {/* 类别分布 */}
      <Card className="p-4">
        <h3 className="text-lg font-semibold mb-4">类别分布</h3>
        {categoryStats.length > 0 ? (
          <div className="space-y-2">
            {categoryStats.map((stat) => (
              <div key={stat.category} className="flex items-center gap-2">
                <span className="w-32 text-sm truncate">{stat.category}</span>
                <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.min(100, (stat.count / categoryStats[0].count) * 100)}%`,
                      backgroundColor: CATEGORY_COLORS[stat.category as SiteCategory] || "#95a5a6",
                    }}
                  />
                </div>
                <span className="w-8 text-sm text-right">{stat.count}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">暂无数据</p>
        )}
      </Card>
    </div>
  );
}
