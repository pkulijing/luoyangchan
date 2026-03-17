export interface HeritageSite {
  id: string;
  name: string;
  province: string;
  city: string | null;
  district: string | null;
  address: string | null;
  category: SiteCategory;
  era: string | null;
  batch: number | null;
  batch_year: number | null;
  latitude: number | null;
  longitude: number | null;
  description: string | null;
  wikipedia_url: string | null;
  image_url: string | null;
  is_open: boolean | null;
  created_at: string;
  updated_at: string;
}

export type SiteListItem = Pick<
  HeritageSite,
  "id" | "name" | "province" | "city" | "category" | "era" | "batch" | "batch_year" | "latitude" | "longitude"
>;

export type SiteCategory =
  | "古遗址"
  | "古墓葬"
  | "古建筑"
  | "石窟寺及石刻"
  | "近现代重要史迹及代表性建筑"
  | "其他";

export interface SiteMarkerData {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  category: SiteCategory;
  era: string | null;
  province: string;
}

export interface FilterState {
  province: string | null;
  category: SiteCategory | null;
  era: string | null;
  search: string;
}
