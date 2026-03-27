"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import { AchievementBadge } from "@/components/achievements/AchievementBadge";
import type { UserAchievement, AchievementDefinition } from "@/lib/types";

interface UserAchievementsProps {
  userId: string;
}

export function UserAchievements({ userId }: UserAchievementsProps) {
  const [achievements, setAchievements] = useState<UserAchievement[]>([]);
  const [loading, setLoading] = useState(true);

  const supabase = createClient();

  useEffect(() => {
    const fetchAchievements = async () => {
      setLoading(true);

      const { data, error } = await supabase
        .from("user_achievements")
        .select(
          `
          id,
          user_id,
          achievement_id,
          unlocked_at,
          achievement:achievement_definitions (
            id,
            code,
            name,
            description,
            icon,
            rarity,
            condition_type,
            condition_value,
            points,
            created_at
          )
        `
        )
        .eq("user_id", userId)
        .order("unlocked_at", { ascending: false });

      if (error) {
        console.error("Error fetching achievements:", error);
        setLoading(false);
        return;
      }

      // 转换数据类型
      const typedData = data?.map((item) => ({
        ...item,
        achievement: item.achievement as unknown as AchievementDefinition,
      })) as UserAchievement[];

      setAchievements(typedData || []);
      setLoading(false);
    };

    if (userId) {
      fetchAchievements();
    }
  }, [userId, supabase]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    );
  }

  if (achievements.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        还没有解锁任何成就，去探索更多文保单位吧！
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {achievements.map((item) => (
        <AchievementBadge
          key={item.id}
          achievement={item.achievement!}
          unlockedAt={item.unlocked_at}
        />
      ))}
    </div>
  );
}
