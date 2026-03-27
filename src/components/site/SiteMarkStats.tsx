"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import { MapPin, Star } from "lucide-react";

interface SiteMarkStatsProps {
  siteId: string;
}

interface Stats {
  visited_count: number;
  wishlist_count: number;
}

export function SiteMarkStats({ siteId }: SiteMarkStatsProps) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  const supabase = createClient();

  useEffect(() => {
    if (!siteId) {
      setStats(null);
      setLoading(false);
      return;
    }

    const fetchStats = async () => {
      setLoading(true);

      // 使用视图查询统计
      const { data, error } = await supabase
        .from("site_mark_stats")
        .select("visited_count, wishlist_count")
        .eq("site_id", siteId)
        .maybeSingle();

      if (error) {
        console.error("Error fetching stats:", error);
      }

      setStats(
        data
          ? { visited_count: data.visited_count, wishlist_count: data.wishlist_count }
          : { visited_count: 0, wishlist_count: 0 }
      );
      setLoading(false);
    };

    fetchStats();
  }, [siteId, supabase]);

  if (loading) {
    return (
      <div className="flex gap-3 text-sm text-muted-foreground">
        <span className="animate-pulse">加载中...</span>
      </div>
    );
  }

  if (!stats || (stats.visited_count === 0 && stats.wishlist_count === 0)) {
    return null;
  }

  return (
    <div className="flex gap-4 text-sm text-muted-foreground">
      {stats.visited_count > 0 && (
        <span className="flex items-center gap-1">
          <MapPin className="size-3.5 text-green-600" />
          {stats.visited_count} 人去过
        </span>
      )}
      {stats.wishlist_count > 0 && (
        <span className="flex items-center gap-1">
          <Star className="size-3.5 text-amber-500" />
          {stats.wishlist_count} 人想去
        </span>
      )}
    </div>
  );
}
