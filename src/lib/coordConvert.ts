import { gcj02towgs84, gcj02tobd09 } from "coordtransform";

/**
 * 将 GCJ-02（高德/国测局坐标系）转换为 WGS-84（GPS/天地图坐标系）
 * 数据库中存储的是高德地理编码产出的 GCJ-02 坐标，Leaflet + 天地图需要 WGS-84
 */
export function gcj02ToWgs84(lng: number, lat: number): [number, number] {
  return gcj02towgs84(lng, lat);
}

/**
 * 将 GCJ-02 转换为 BD-09（百度坐标系）
 * 百度地图 API 使用 BD-09，传入 GCJ-02 坐标前需转换
 */
export function gcj02ToBd09(lng: number, lat: number): [number, number] {
  return gcj02tobd09(lng, lat);
}
