"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import { ProfileForm } from "@/components/settings/ProfileForm";
import { LoginDialog } from "@/components/auth/LoginDialog";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function SettingsProfilePage() {
  const { user, loading } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 导航 */}
      <nav className="bg-white border-b">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="text-lg font-bold hover:text-primary">
            洛阳铲
          </Link>
          {user && (
            <Link
              href={`/settings/profile`}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              设置
            </Link>
          )}
        </div>
      </nav>

      {/* 内容 */}
      <main className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">个人设置</h1>

        {loading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-24 rounded-xl bg-muted" />
            <div className="h-12 rounded-lg bg-muted" />
            <div className="h-12 rounded-lg bg-muted" />
          </div>
        ) : user ? (
          <ProfileForm />
        ) : (
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">请先登录</p>
            <LoginDialog>
              <Button>登录</Button>
            </LoginDialog>
          </div>
        )}
      </main>
    </div>
  );
}
