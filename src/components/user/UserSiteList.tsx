"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CATEGORY_COLORS } from "@/lib/constants";
import Link from "next/link";
import type { MarkType, SiteCategory } from "@/lib/types";

interface UserSiteListProps {
  userId: string;
  markType: MarkType;
}

interface MarkedSite {
  id: string;
  mark_type: MarkType;
  visited_at: string | null;
  created_at: string;
  site: {
    id: string;
    name: string;
    release_id: string;
    category: SiteCategory;
    province: string | null;
    city: string | null;
  };
}

const PAGE_SIZE = 20;

export function UserSiteList({ userId, markType }: UserSiteListProps) {
  const [sites, setSites] = useState<MarkedSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(0);

  const supabase = createClient();

  useEffect(() => {
    const fetchSites = async () => {
      setLoading(true);

      const { data, error } = await supabase
        .from("user_site_marks")
        .select(
          `
          id,
          mark_type,
          visited_at,
          created_at,
          site:heritage_sites (
            id,
            name,
            release_id,
            category,
            province,
            city
          )
        `
        )
        .eq("user_id", userId)
        .eq("mark_type", markType)
        .order("created_at", { ascending: false })
        .range(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

      if (error) {
        console.error("Error fetching sites:", error);
        setLoading(false);
        return;
      }

      const typedData = data as unknown as MarkedSite[];

      if (page === 0) {
        setSites(typedData);
      } else {
        setSites((prev) => [...prev, ...typedData]);
      }

      setHasMore(typedData.length === PAGE_SIZE + 1);
      setLoading(false);
    };

    fetchSites();
  }, [userId, markType, page, supabase]);

  // 重置分页当类型变化
  useEffect(() => {
    setPage(0);
    setSites([]);
  }, [markType]);

  if (loading && page === 0) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    );
  }

  if (sites.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        {markType === "visited" ? "还没有标记去过的文保单位" : "还没有标记想去的文保单位"}
      </div>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {sites.map((item) => (
          <Link
            key={item.id}
            href={`/site/${item.site.release_id}`}
            className="block"
          >
            <Card className="p-4 hover:shadow-md transition-shadow">
              <h4 className="font-medium truncate">{item.site.name}</h4>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge
                  style={{
                    backgroundColor: CATEGORY_COLORS[item.site.category] || "#95a5a6",
                    color: "white",
                  }}
                  className="text-xs"
                >
                  {item.site.category}
                </Badge>
                {item.site.province && (
                  <Badge variant="outline" className="text-xs">
                    {item.site.province}
                    {item.site.city ? ` · ${item.site.city}` : ""}
                  </Badge>
                )}
              </div>
              {item.visited_at && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {new Date(item.visited_at).toLocaleDateString("zh-CN")} 去过
                </p>
              )}
            </Card>
          </Link>
        ))}
      </div>

      {hasMore && (
        <div className="mt-6 text-center">
          <Button
            variant="outline"
            onClick={() => setPage((p) => p + 1)}
            disabled={loading}
          >
            {loading ? "加载中..." : "加载更多"}
          </Button>
        </div>
      )}
    </div>
  );
}
