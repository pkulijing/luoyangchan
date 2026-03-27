"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { LoginDialog } from "@/components/auth/LoginDialog";
import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/supabase/client";
import { MapPin, Star, Loader2, Check } from "lucide-react";
import type { MarkType, UserSiteMark } from "@/lib/types";

interface SiteMarkButtonProps {
  siteId: string;
  onMarkChange?: () => void;
}

export function SiteMarkButton({ siteId, onMarkChange }: SiteMarkButtonProps) {
  const { user, refreshProfile } = useAuth();
  const [mark, setMark] = useState<UserSiteMark | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [showLoginHint, setShowLoginHint] = useState(false);

  const supabase = createClient();

  // 获取用户对该站点的标记
  useEffect(() => {
    if (!user || !siteId) {
      setMark(null);
      setLoading(false);
      return;
    }

    const fetchMark = async () => {
      setLoading(true);
      const { data, error } = await supabase
        .from("user_site_marks")
        .select("*")
        .eq("user_id", user.id)
        .eq("site_id", siteId)
        .maybeSingle();

      if (error) {
        console.error("Error fetching mark:", error);
      }
      setMark(data as UserSiteMark | null);
      setLoading(false);
    };

    fetchMark();
  }, [user, siteId, supabase]);

  // 更新标记
  const handleMark = async (markType: MarkType) => {
    if (!user) {
      setShowLoginHint(true);
      return;
    }

    setUpdating(true);

    try {
      if (mark?.mark_type === markType) {
        // 取消标记
        const { error } = await supabase
          .from("user_site_marks")
          .delete()
          .eq("id", mark.id);

        if (error) throw error;
        setMark(null);
      } else if (mark) {
        // 切换标记类型
        const { data, error } = await supabase
          .from("user_site_marks")
          .update({
            mark_type: markType,
            visited_at: markType === "visited" ? new Date().toISOString().split("T")[0] : null,
          })
          .eq("id", mark.id)
          .select()
          .single();

        if (error) throw error;
        setMark(data as UserSiteMark);
      } else {
        // 新建标记
        const { data, error } = await supabase
          .from("user_site_marks")
          .insert({
            user_id: user.id,
            site_id: siteId,
            mark_type: markType,
            visited_at: markType === "visited" ? new Date().toISOString().split("T")[0] : null,
          })
          .select()
          .single();

        if (error) throw error;
        setMark(data as UserSiteMark);
      }

      // 刷新 profile 以更新统计
      await refreshProfile();
      onMarkChange?.();
    } catch (error) {
      console.error("Error updating mark:", error);
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex gap-2">
        <div className="h-8 w-20 animate-pulse rounded-lg bg-muted" />
        <div className="h-8 w-20 animate-pulse rounded-lg bg-muted" />
      </div>
    );
  }

  const isVisited = mark?.mark_type === "visited";
  const isWishlist = mark?.mark_type === "wishlist";

  return (
    <div className="flex gap-2">
      {/* 去过按钮 */}
      {user ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleMark("visited")}
          disabled={updating}
          style={isVisited ? { backgroundColor: "#16a34a", color: "white", borderColor: "#16a34a" } : undefined}
        >
          {updating ? (
            <Loader2 className="size-4 animate-spin" />
          ) : isVisited ? (
            <Check className="size-4" />
          ) : (
            <MapPin className="size-4" />
          )}
          {isVisited ? "已去过" : "去过"}
        </Button>
      ) : (
        <LoginDialog onSuccess={() => setShowLoginHint(false)}>
          <Button variant="outline" size="sm">
            <MapPin className="size-4" />
            去过
          </Button>
        </LoginDialog>
      )}

      {/* 想去按钮 */}
      {user ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleMark("wishlist")}
          disabled={updating}
          style={isWishlist ? { backgroundColor: "#f59e0b", color: "white", borderColor: "#f59e0b" } : undefined}
        >
          {updating ? (
            <Loader2 className="size-4 animate-spin" />
          ) : isWishlist ? (
            <Check className="size-4" />
          ) : (
            <Star className="size-4" />
          )}
          {isWishlist ? "已想去" : "想去"}
        </Button>
      ) : (
        <LoginDialog onSuccess={() => setShowLoginHint(false)}>
          <Button variant="outline" size="sm">
            <Star className="size-4" />
            想去
          </Button>
        </LoginDialog>
      )}

      {/* 登录提示 */}
      {showLoginHint && !user && (
        <span className="text-xs text-muted-foreground self-center">
          请先登录
        </span>
      )}
    </div>
  );
}
