"use client";

import { useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";
import { Loader2, Check, Upload } from "lucide-react";
import { getAvatarUrl } from "@/lib/avatar";

export function ProfileForm() {
  const { user, profile, refreshProfile } = useAuth();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [username, setUsername] = useState(profile?.username || "");
  const [displayName, setDisplayName] = useState(profile?.display_name || "");
  const [bio, setBio] = useState(profile?.bio || "");
  const [avatarUploading, setAvatarUploading] = useState(false);

  const supabase = createClient();

  // 保存 profile
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;

    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      // 检查用户名是否已被占用
      if (username && username !== profile?.username) {
        const { data: existing } = await supabase
          .from("profiles")
          .select("id")
          .eq("username", username)
          .neq("id", user.id)
          .single();

        if (existing) {
          setError("该用户名已被占用");
          setLoading(false);
          return;
        }
      }

      // 更新 profile
      const { error: updateError } = await supabase
        .from("profiles")
        .update({
          username: username || null,
          display_name: displayName || null,
          bio: bio || null,
        })
        .eq("id", user.id);

      if (updateError) throw updateError;

      await refreshProfile();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error("Error updating profile:", err);
      setError("保存失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  // 上传头像
  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !user) return;

    // 检查文件大小（最大 2MB）
    if (file.size > 2 * 1024 * 1024) {
      setError("图片大小不能超过 2MB");
      return;
    }

    // 检查文件类型
    if (!file.type.startsWith("image/")) {
      setError("请上传图片文件");
      return;
    }

    setAvatarUploading(true);
    setError(null);

    try {
      const fileExt = file.name.split(".").pop();
      const fileName = `${user.id}-${Date.now()}.${fileExt}`;
      const filePath = `avatars/${fileName}`;

      // 上传到 Storage
      const { error: uploadError } = await supabase.storage
        .from("site-images")
        .upload(filePath, file, { upsert: true });

      if (uploadError) throw uploadError;

      // 获取公开 URL
      const { data: urlData } = supabase.storage
        .from("site-images")
        .getPublicUrl(filePath);

      // 更新 profile
      const { error: updateError } = await supabase
        .from("profiles")
        .update({ avatar_url: urlData.publicUrl })
        .eq("id", user.id);

      if (updateError) throw updateError;

      await refreshProfile();
    } catch (err) {
      console.error("Error uploading avatar:", err);
      setError("头像上传失败");
    } finally {
      setAvatarUploading(false);
    }
  };

  if (!user) {
    return (
      <Card className="p-6 text-center text-muted-foreground">
        请先登录
      </Card>
    );
  }

  const avatarSrc = getAvatarUrl(profile?.avatar_url, user.id);

  return (
    <Card className="p-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* 头像 */}
        <div className="flex flex-col items-center gap-3">
          <div className="size-24 rounded-full overflow-hidden border-2 border-muted">
            <img
              src={avatarSrc}
              alt="头像"
              className="size-full object-cover"
            />
          </div>
          <label
            htmlFor="avatar-upload"
            className="inline-flex items-center gap-1.5 text-sm text-primary cursor-pointer hover:underline"
          >
            {avatarUploading ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                上传中...
              </>
            ) : (
              <>
                <Upload className="size-4" />
                更换头像
              </>
            )}
          </label>
          <input
            id="avatar-upload"
            type="file"
            accept="image/*"
            className="sr-only"
            onChange={handleAvatarUpload}
            disabled={avatarUploading}
          />
          <p className="text-xs text-muted-foreground">
            支持 JPG、PNG 格式，最大 2MB
          </p>
        </div>

        {/* 用户名 */}
        <div className="space-y-2">
          <label htmlFor="username" className="text-sm font-medium">
            用户名
          </label>
          <Input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
            placeholder="设置用户名后可访问个人主页"
            maxLength={20}
          />
          <p className="text-xs text-muted-foreground">
            只能包含小写字母、数字和下划线，用于个人主页 URL：/user/{username || "your_username"}
          </p>
        </div>

        {/* 昵称 */}
        <div className="space-y-2">
          <label htmlFor="displayName" className="text-sm font-medium">
            昵称
          </label>
          <Input
            id="displayName"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="显示的昵称"
            maxLength={30}
          />
        </div>

        {/* 简介 */}
        <div className="space-y-2">
          <label htmlFor="bio" className="text-sm font-medium">
            个人简介
          </label>
          <textarea
            id="bio"
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            placeholder="介绍一下自己..."
            maxLength={200}
            rows={3}
            className="w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
          <p className="text-xs text-muted-foreground text-right">
            {bio.length}/200
          </p>
        </div>

        {/* 错误信息 */}
        {error && (
          <div className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* 成功信息 */}
        {success && (
          <div className="rounded-lg bg-green-100 px-3 py-2 text-sm text-green-700 flex items-center gap-2">
            <Check className="size-4" />
            保存成功
          </div>
        )}

        {/* 提交按钮 */}
        <Button type="submit" disabled={loading} className="w-full">
          {loading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            "保存"
          )}
        </Button>
      </form>
    </Card>
  );
}
