"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "./AuthProvider";
import { LoginDialog } from "./LoginDialog";
import { Button } from "@/components/ui/button";
import { User, LogOut, Settings, MapPin, Trophy } from "lucide-react";
import Link from "next/link";
import { getAvatarUrl } from "@/lib/avatar";

export function UserMenu() {
  const { user, profile, loading, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [menuOpen]);

  // 加载中状态
  if (loading) {
    return (
      <div className="size-8 animate-pulse rounded-full bg-muted" />
    );
  }

  // 未登录状态
  if (!user) {
    return (
      <LoginDialog>
        <Button variant="outline" size="sm">
          <User className="size-4" />
          登录
        </Button>
      </LoginDialog>
    );
  }

  // 已登录状态
  const displayName = profile?.display_name || user.email?.split("@")[0] || "用户";
  const avatarSrc = getAvatarUrl(profile?.avatar_url, user.id);

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setMenuOpen(!menuOpen)}
        className="flex size-8 items-center justify-center rounded-full overflow-hidden transition-transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        aria-label="用户菜单"
      >
        <img
          src={avatarSrc}
          alt={displayName}
          className="size-full object-cover"
        />
      </button>

      {menuOpen && (
        <div className="absolute right-0 top-full z-50 mt-2 w-56 rounded-lg border bg-background p-1 shadow-lg">
          {/* 用户信息 */}
          <div className="border-b px-3 py-2">
            <p className="font-medium">{displayName}</p>
            <p className="text-xs text-muted-foreground">{user.email}</p>
          </div>

          {/* 统计信息 */}
          {profile && (
            <div className="flex gap-4 border-b px-3 py-2 text-sm">
              <div className="flex items-center gap-1">
                <MapPin className="size-3.5 text-green-600" />
                <span>{profile.visited_count} 去过</span>
              </div>
              <div className="flex items-center gap-1">
                <MapPin className="size-3.5 text-amber-500" />
                <span>{profile.wishlist_count} 想去</span>
              </div>
            </div>
          )}

          {/* 菜单项 */}
          <div className="py-1">
            <Link
              href={profile?.username ? `/user/${profile.username}` : "/settings/profile?setup=username"}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
              onClick={() => setMenuOpen(false)}
            >
              <User className="size-4" />
              个人主页
            </Link>
            <Link
              href={profile?.username ? `/user/${profile.username}#achievements` : "/settings/profile?setup=username"}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
              onClick={() => setMenuOpen(false)}
            >
              <Trophy className="size-4" />
              成就
            </Link>
            <Link
              href="/settings/profile"
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted"
              onClick={() => setMenuOpen(false)}
            >
              <Settings className="size-4" />
              设置
            </Link>
          </div>

          {/* 登出 */}
          <div className="border-t py-1">
            <button
              onClick={() => {
                signOut();
                setMenuOpen(false);
              }}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-muted"
            >
              <LogOut className="size-4" />
              退出登录
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
