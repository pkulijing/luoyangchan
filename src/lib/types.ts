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
  baike_image_url: string | null;
  is_open: boolean | null;
  release_id: string | null;
  release_address: string | null;
  parent_id: string | null;
  created_at: string;
  updated_at: string;
}

export type SiteListItem = Pick<
  HeritageSite,
  "id" | "name" | "release_id" | "province" | "city" | "district" | "category" | "era" | "batch" | "batch_year" | "latitude" | "longitude" | "parent_id"
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
  | "其他";

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
  search: string;
  category: SiteCategory | null;
  province: string | null;
  city: string | null;
  district: string | null;
}

// ===========================
// 用户相关类型
// ===========================

export interface Profile {
  id: string;
  username: string | null;
  display_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  visited_count: number;
  wishlist_count: number;
  created_at: string;
  updated_at: string;
}

export type MarkType = "visited" | "wishlist";

export interface UserSiteMark {
  id: string;
  user_id: string;
  site_id: string;
  mark_type: MarkType;
  visited_at: string | null;
  visited_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface SiteMarkStats {
  site_id: string;
  visited_count: number;
  wishlist_count: number;
}

// ===========================
// 成就相关类型
// ===========================

export type AchievementRarity = "common" | "rare" | "epic" | "legendary";

export type AchievementConditionType =
  | "province_count"
  | "province_complete"
  | "city_complete"
  | "district_complete"
  | "category_count"
  | "total_count";

export interface AchievementDefinition {
  id: string;
  code: string;
  name: string;
  description: string;
  icon: string | null;
  rarity: AchievementRarity;
  condition_type: AchievementConditionType;
  condition_value: Record<string, unknown>;
  points: number;
  created_at: string;
}

export interface UserAchievement {
  id: string;
  user_id: string;
  achievement_id: string;
  unlocked_at: string;
  achievement?: AchievementDefinition;
}
