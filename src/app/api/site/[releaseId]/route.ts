import { NextResponse } from "next/server";
import { getSiteByReleaseId } from "@/lib/supabase/queries";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ releaseId: string }> },
) {
  const { releaseId } = await params;
  const site = await getSiteByReleaseId(releaseId);

  if (!site) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  return NextResponse.json(site);
}
