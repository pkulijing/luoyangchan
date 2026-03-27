"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";
import { Loader2, Mail } from "lucide-react";

interface LoginDialogProps {
  children: React.ReactNode;
  onSuccess?: () => void;
}

type LoginStep = "initial" | "otp_sent" | "verifying";

export function LoginDialog({ children, onSuccess }: LoginDialogProps) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<LoginStep>("initial");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const supabase = createClient();

  // 发送邮箱验证码
  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    setLoading(true);
    setError(null);

    try {
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          shouldCreateUser: true,
        },
      });

      if (error) {
        setError(error.message);
      } else {
        setStep("otp_sent");
      }
    } catch {
      setError("发送验证码失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  // 验证 OTP
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otp) return;

    setLoading(true);
    setError(null);
    setStep("verifying");

    try {
      const { error } = await supabase.auth.verifyOtp({
        email,
        token: otp,
        type: "email",
      });

      if (error) {
        setError(error.message);
        setStep("otp_sent");
      } else {
        setOpen(false);
        resetForm();
        onSuccess?.();
      }
    } catch {
      setError("验证失败，请检查验证码是否正确");
      setStep("otp_sent");
    } finally {
      setLoading(false);
    }
  };

  // Google OAuth 登录
  const handleGoogleLogin = async () => {
    setLoading(true);
    setError(null);

    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      });

      if (error) {
        setError(error.message);
      }
    } catch {
      setError("Google 登录失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  // 重置表单
  const resetForm = () => {
    setStep("initial");
    setEmail("");
    setOtp("");
    setError(null);
  };

  // 关闭对话框时重置
  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen) {
      resetForm();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={children as React.ReactElement}></DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>登录洛阳铲</DialogTitle>
          <DialogDescription>
            登录后可标记去过/想去的文保单位，解锁成就
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {step === "initial" && (
          <div className="flex flex-col gap-4">
            {/* 邮箱验证码登录 */}
            <form onSubmit={handleSendOtp} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="email" className="text-sm font-medium">
                  邮箱地址
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="your@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>
              <Button type="submit" disabled={loading || !email}>
                {loading ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Mail className="size-4" />
                )}
                发送验证码
              </Button>
            </form>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">
                  或
                </span>
              </div>
            </div>

            {/* Google OAuth 登录 */}
            <Button
              variant="outline"
              onClick={handleGoogleLogin}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <svg className="size-4" viewBox="0 0 24 24">
                  <path
                    fill="currentColor"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="currentColor"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
              )}
              使用 Google 账号登录
            </Button>

            <p className="text-center text-xs text-muted-foreground">
              Google 登录需要科学上网，国内用户推荐使用邮箱登录
            </p>
          </div>
        )}

        {(step === "otp_sent" || step === "verifying") && (
          <form onSubmit={handleVerifyOtp} className="flex flex-col gap-4">
            <div className="text-sm text-muted-foreground">
              验证码已发送至 <span className="font-medium">{email}</span>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="otp" className="text-sm font-medium">
                验证码
              </label>
              <Input
                id="otp"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                placeholder="输入 6 位验证码"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                disabled={loading}
                autoFocus
                required
              />
            </div>
            <Button type="submit" disabled={loading || otp.length !== 6}>
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                "验证并登录"
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setStep("initial")}
              disabled={loading}
            >
              返回
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
