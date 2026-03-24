export interface HeritageSite {
  id: string;
  name: string;
  province: string | null;
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
  tags: string[] | null;
  wikipedia_url: string | null;
  baike_url: string | null;
  image_url: string | null;
  is_open: boolean | null;
  release_id: string | null;
  release_address: string | null;
  parent_id: string | null;
  created_at: string;
  updated_at: string;
}

export type SiteListItem = Pick<
  HeritageSite,
  "id" | "name" | "release_id" | "province" | "city" | "category" | "era" | "batch" | "batch_year" | "latitude" | "longitude" | "parent_id"
>;

/** 详情页专用：携带父记录概要和兄弟/子记录列表 */
export interface SiteWithRelations extends HeritageSite {
  parent: Pick<HeritageSite, "id" | "name" | "release_id"> | null;
  siblings: Pick<HeritageSite, "id" | "name" | "release_id" | "latitude" | "longitude">[];
  children: Pick<HeritageSite, "id" | "name" | "release_id" | "latitude" | "longitude">[];
}

export type SiteCategory =
  | "古遗址"
  | "古墓葬"
  | "古建筑"
  | "石窟寺及石刻"
  | "近现代重要史迹及代表性建筑"
  | "其他"
  // 早期批次使用的历史分类名称
  | "革命遗址及革命纪念建筑物"
  | "古建筑及历史纪念建筑物"
  | "石窟寺"
  | "石刻及其他";

export interface SiteMarkerData {
  id: string;
  release_id: string;
  name: string;
  latitude: number;
  longitude: number;
  category: SiteCategory;
  era: string | null;
  province: string | null;
}

export interface FilterState {
  province: string | null;
  category: SiteCategory | null;
  era: string | null;
  search: string;
}
