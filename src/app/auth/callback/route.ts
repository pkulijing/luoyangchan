import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * OAuth 回调处理
 * 处理 Google OAuth 等第三方登录的回调
 */
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      // 登录成功，重定向到目标页面
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  // 登录失败，重定向到首页并显示错误
  return NextResponse.redirect(`${origin}/?error=auth_callback_error`);
}
