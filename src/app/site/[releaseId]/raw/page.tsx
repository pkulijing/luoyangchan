import { getSiteByReleaseId } from "@/lib/supabase/queries";
import BackButton from "@/components/site/BackButton";
import Link from "next/link";

export default async function SiteRawPage({
  params,
}: {
  params: Promise<{ releaseId: string }>;
}) {
  const { releaseId } = await params;
  const site = await getSiteByReleaseId(releaseId);

  if (!site) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">未找到该文保单位</h1>
          <BackButton />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-4 mb-4">
          <BackButton />
          <h1 className="text-xl font-bold">{site.name} — Raw Data</h1>
          <Link
            href={`/site/${releaseId}`}
            className="text-blue-600 hover:underline text-sm ml-auto"
          >
            ← 返回详情页
          </Link>
        </div>
        <pre className="bg-white border rounded-lg p-4 overflow-x-auto text-sm leading-relaxed">
          {JSON.stringify(site, null, 2)}
        </pre>
      </div>
    </div>
  );
}
