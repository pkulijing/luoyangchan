"use client";

import { MapPin, Star, Calendar } from "lucide-react";
import type { Profile } from "@/lib/types";
import { getAvatarUrl } from "@/lib/avatar";

interface UserProfileHeaderProps {
  profile: Profile;
}

export function UserProfileHeader({ profile }: UserProfileHeaderProps) {
  const displayName = profile.display_name || profile.username || "用户";
  const avatarSrc = getAvatarUrl(profile.avatar_url, profile.id);

  const joinDate = new Date(profile.created_at).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
  });

  return (
    <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6 p-6 bg-white rounded-xl shadow-sm">
      {/* 头像 */}
      <div className="size-24 rounded-full overflow-hidden shrink-0">
        <img
          src={avatarSrc}
          alt={displayName}
          className="size-full object-cover"
        />
      </div>

      {/* 信息 */}
      <div className="flex-1 text-center sm:text-left">
        <h1 className="text-2xl font-bold">{displayName}</h1>
        {profile.username && (
          <p className="text-sm text-muted-foreground">@{profile.username}</p>
        )}
        {profile.bio && (
          <p className="mt-2 text-sm text-gray-700">{profile.bio}</p>
        )}

        {/* 统计 */}
        <div className="mt-4 flex flex-wrap justify-center sm:justify-start gap-6">
          <div className="flex items-center gap-1.5 text-sm">
            <MapPin className="size-4 text-green-600" />
            <span className="font-semibold">{profile.visited_count}</span>
            <span className="text-muted-foreground">去过</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm">
            <Star className="size-4 text-amber-500" />
            <span className="font-semibold">{profile.wishlist_count}</span>
            <span className="text-muted-foreground">想去</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Calendar className="size-4" />
            <span>{joinDate} 加入</span>
          </div>
        </div>
      </div>
    </div>
  );
}
