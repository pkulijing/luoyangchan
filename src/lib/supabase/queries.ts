import { createClient } from "./server";
import type { HeritageSite, SiteListItem } from "../types";

export async function getAllSites(): Promise<SiteListItem[]> {
  const supabase = await createClient();

  const pageSize = 1000;
  let from = 0;
  const allSites: SiteListItem[] = [];

  while (true) {
    const { data, error } = await supabase
      .from("heritage_sites")
      .select(
        "id, name, province, city, category, era, batch, batch_year, latitude, longitude",
      )
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

export async function getSiteById(id: string): Promise<HeritageSite | null> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("heritage_sites")
    .select("*")
    .eq("id", id)
    .single();
  if (error) return null;
  return data as HeritageSite;
}
