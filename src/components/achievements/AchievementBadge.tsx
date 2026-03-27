"use client";

import { Card } from "@/components/ui/card";
import type { AchievementDefinition, AchievementRarity } from "@/lib/types";

interface AchievementBadgeProps {
  achievement: AchievementDefinition;
  unlockedAt?: string;
  showDetails?: boolean;
}

const RARITY_COLORS: Record<AchievementRarity, { bg: string; border: string; text: string }> = {
  common: {
    bg: "bg-gray-100",
    border: "border-gray-300",
    text: "text-gray-700",
  },
  rare: {
    bg: "bg-blue-50",
    border: "border-blue-300",
    text: "text-blue-700",
  },
  epic: {
    bg: "bg-purple-50",
    border: "border-purple-300",
    text: "text-purple-700",
  },
  legendary: {
    bg: "bg-amber-50",
    border: "border-amber-400",
    text: "text-amber-700",
  },
};

const RARITY_LABELS: Record<AchievementRarity, string> = {
  common: "普通",
  rare: "稀有",
  epic: "史诗",
  legendary: "传说",
};

export function AchievementBadge({
  achievement,
  unlockedAt,
  showDetails = false,
}: AchievementBadgeProps) {
  const colors = RARITY_COLORS[achievement.rarity];

  return (
    <Card
      className={`p-4 border-2 ${colors.bg} ${colors.border} transition-transform hover:scale-105`}
    >
      <div className="text-center">
        {/* 图标 */}
        <div className="text-4xl mb-2">{achievement.icon || "🏆"}</div>

        {/* 名称 */}
        <h4 className={`font-semibold text-sm ${colors.text}`}>
          {achievement.name}
        </h4>

        {/* 稀有度标签 */}
        <span
          className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}
        >
          {RARITY_LABELS[achievement.rarity]}
        </span>

        {/* 描述 */}
        {showDetails && (
          <p className="mt-2 text-xs text-muted-foreground">
            {achievement.description}
          </p>
        )}

        {/* 解锁时间 */}
        {unlockedAt && (
          <p className="mt-2 text-xs text-muted-foreground">
            {new Date(unlockedAt).toLocaleDateString("zh-CN")} 解锁
          </p>
        )}

        {/* 积分 */}
        {showDetails && (
          <p className="mt-1 text-xs font-medium text-primary">
            +{achievement.points} 积分
          </p>
        )}
      </div>
    </Card>
  );
}

// 成就解锁 Toast 组件
export function AchievementUnlockToast({
  achievement,
  onClose,
}: {
  achievement: AchievementDefinition;
  onClose: () => void;
}) {
  const colors = RARITY_COLORS[achievement.rarity];

  return (
    <div
      className={`fixed bottom-4 right-4 z-50 animate-in slide-in-from-right-full duration-300 max-w-sm`}
    >
      <Card
        className={`p-4 border-2 ${colors.bg} ${colors.border} shadow-lg`}
      >
        <div className="flex items-center gap-4">
          <div className="text-4xl">{achievement.icon || "🏆"}</div>
          <div className="flex-1">
            <p className="text-xs text-muted-foreground">成就解锁！</p>
            <h4 className={`font-semibold ${colors.text}`}>
              {achievement.name}
            </h4>
            <p className="text-xs text-muted-foreground mt-1">
              {achievement.description}
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 text-muted-foreground hover:text-foreground"
          >
            ×
          </button>
        </div>
      </Card>
    </div>
  );
}
