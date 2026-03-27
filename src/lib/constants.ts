import type { SiteCategory } from "./types";

export const SITE_CATEGORIES: SiteCategory[] = [
  "古遗址",
  "古墓葬",
  "古建筑",
  "石窟寺及石刻",
  "近现代重要史迹及代表性建筑",
  "其他",
];

export const CATEGORY_COLORS: Record<SiteCategory, string> = {
  古遗址: "#3498db",
  古墓葬: "#2ecc71",
  古建筑: "#f39c12",
  石窟寺及石刻: "#95a5a6",
  近现代重要史迹及代表性建筑: "#e74c3c",
  其他: "#9b59b6",
};

export const BATCH_YEARS: Record<number, number> = {
  1: 1961,
  2: 1982,
  3: 1988,
  4: 1996,
  5: 2001,
  6: 2006,
  7: 2013,
  8: 2019,
};

export const MAP_DEFAULT_CENTER: [number, number] = [104.0, 35.0];
export const MAP_DEFAULT_ZOOM = 5;
