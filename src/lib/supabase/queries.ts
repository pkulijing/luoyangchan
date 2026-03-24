import { createClient } from "./server";
import type { HeritageSite, SiteListItem, SiteWithRelations } from "../types";

export async function getAllSites(): Promise<SiteListItem[]> {
  const supabase = await createClient();

  const pageSize = 1000;
  let from = 0;
  const allSites: SiteListItem[] = [];

  while (true) {
    const { data, error } = await supabase
      .from("heritage_sites")
      .select(
        "id, name, release_id, province, city, category, era, batch, batch_year, latitude, longitude, parent_id",
      )
      .not("latitude", "is", null)  // 排除父记录（无坐标）
      .order("id", { ascending: true })
      .range(from, from + pageSize - 1);

    if (error) throw error;
    if (!data || data.length === 0) break;

    allSites.push(...(data as SiteListItem[]));

    if (data.length < pageSize) break;
    from += pageSize;
  }

  return allSites;
}

export async function getSiteByReleaseId(releaseId: string): Promise<SiteWithRelations | null> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("heritage_sites")
    .select("*")
    .eq("release_id", releaseId)
    .single();
  if (error) return null;
  const site = data as HeritageSite;

  // 并行查父记录、子记录
  const [parentResult, childrenResult] = await Promise.all([
    site.parent_id
      ? supabase
          .from("heritage_sites")
          .select("id, name, release_id")
          .eq("id", site.parent_id)
          .single()
      : Promise.resolve({ data: null, error: null }),
    supabase
      .from("heritage_sites")
      .select("id, name, release_id, latitude, longitude")
      .eq("parent_id", site.id),
  ]);

  const parent = parentResult.data as Pick<HeritageSite, "id" | "name" | "release_id"> | null;

  // 兄弟：同父、非自身（仅有父记录时才查）
  let siblings: Pick<HeritageSite, "id" | "name" | "release_id" | "latitude" | "longitude">[] = [];
  if (site.parent_id) {
    const { data: sibData } = await supabase
      .from("heritage_sites")
      .select("id, name, release_id, latitude, longitude")
      .eq("parent_id", site.parent_id)
      .neq("id", site.id);
    siblings = (sibData ?? []) as typeof siblings;
  }

  return {
    ...site,
    parent,
    siblings,
    children: (childrenResult.data ?? []) as Pick<HeritageSite, "id" | "name" | "release_id" | "latitude" | "longitude">[],
  };
}
