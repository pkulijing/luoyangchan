import type { SiteCategory } from "./types";

export const SITE_CATEGORIES: SiteCategory[] = [
  "古遗址",
  "古墓葬",
  "古建筑",
  "石窟寺及石刻",
  "近现代重要史迹及代表性建筑",
  "其他",
  // 早期批次历史分类名称
  "革命遗址及革命纪念建筑物",
  "古建筑及历史纪念建筑物",
  "石窟寺",
  "石刻及其他",
];

export const CATEGORY_COLORS: Record<SiteCategory, string> = {
  古遗址: "#e74c3c",
  古墓葬: "#9b59b6",
  古建筑: "#f39c12",
  石窟寺及石刻: "#2ecc71",
  近现代重要史迹及代表性建筑: "#3498db",
  其他: "#95a5a6",
  // 早期批次历史分类，沿用相近的现代分类颜色
  革命遗址及革命纪念建筑物: "#3498db",
  古建筑及历史纪念建筑物: "#f39c12",
  石窟寺: "#2ecc71",
  石刻及其他: "#95a5a6",
};

export const PROVINCES = [
  "北京市",
  "天津市",
  "河北省",
  "山西省",
  "内蒙古自治区",
  "辽宁省",
  "吉林省",
  "黑龙江省",
  "上海市",
  "江苏省",
  "浙江省",
  "安徽省",
  "福建省",
  "江西省",
  "山东省",
  "河南省",
  "湖北省",
  "湖南省",
  "广东省",
  "广西壮族自治区",
  "海南省",
  "重庆市",
  "四川省",
  "贵州省",
  "云南省",
  "西藏自治区",
  "陕西省",
  "甘肃省",
  "青海省",
  "宁夏回族自治区",
  "新疆维吾尔自治区",
];

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
