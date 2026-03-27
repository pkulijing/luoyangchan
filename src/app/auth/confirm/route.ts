import { type EmailOtpType } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * Email OTP/Magic Link 确认处理
 * 处理邮箱验证码登录的确认
 */
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const next = searchParams.get("next") ?? "/";

  if (token_hash && type) {
    const supabase = await createClient();
    const { error } = await supabase.auth.verifyOtp({
      type,
      token_hash,
    });
    if (!error) {
      // 验证成功，重定向到目标页面
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  // 验证失败，重定向到首页并显示错误
  return NextResponse.redirect(`${origin}/?error=email_confirm_error`);
}
