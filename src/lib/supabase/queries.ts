import { createClient } from "./server";
import type { HeritageSite, SiteListItem } from "../types";

export async function getAllSites(): Promise<SiteListItem[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("heritage_sites")
    .select("id, name, province, city, category, era, batch, batch_year, latitude, longitude");
  if (error) throw error;
  return data as SiteListItem[];
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
