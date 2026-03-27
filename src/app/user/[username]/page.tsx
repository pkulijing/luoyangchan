import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { UserProfileHeader } from "@/components/user/UserProfileHeader";
import { UserStatsGrid } from "@/components/user/UserStatsGrid";
import { UserSiteList } from "@/components/user/UserSiteList";
import { UserAchievements } from "@/components/user/UserAchievements";
import type { Profile } from "@/lib/types";
import Link from "next/link";

interface PageProps {
  params: Promise<{ username: string }>;
}

export default async function UserProfilePage({ params }: PageProps) {
  const { username } = await params;
  const supabase = await createClient();

  // 获取用户 profile
  const { data: profile, error } = await supabase
    .from("profiles")
    .select("*")
    .eq("username", username)
    .single();

  if (error || !profile) {
    notFound();
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 导航 */}
      <nav className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="text-lg font-bold hover:text-primary">
            洛阳铲
          </Link>
        </div>
      </nav>

      {/* 内容 */}
      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        {/* 用户信息头部 */}
        <UserProfileHeader profile={profile as Profile} />

        {/* 统计图表 */}
        <section>
          <h2 className="text-xl font-semibold mb-4">探访统计</h2>
          <UserStatsGrid userId={profile.id} />
        </section>

        {/* 成就 */}
        <section id="achievements">
          <h2 className="text-xl font-semibold mb-4">成就</h2>
          <UserAchievements userId={profile.id} />
        </section>

        {/* 去过的文保单位 */}
        <section>
          <h2 className="text-xl font-semibold mb-4">去过的文保单位</h2>
          <UserSiteList userId={profile.id} markType="visited" />
        </section>

        {/* 想去的文保单位 */}
        <section>
          <h2 className="text-xl font-semibold mb-4">想去的文保单位</h2>
          <UserSiteList userId={profile.id} markType="wishlist" />
        </section>
      </main>
    </div>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const { username } = await params;
  const supabase = await createClient();

  const { data: profile } = await supabase
    .from("profiles")
    .select("display_name, username")
    .eq("username", username)
    .single();

  const displayName = profile?.display_name || profile?.username || username;

  return {
    title: `${displayName} 的主页 - 洛阳铲`,
    description: `${displayName} 在洛阳铲上的探访记录`,
  };
}
