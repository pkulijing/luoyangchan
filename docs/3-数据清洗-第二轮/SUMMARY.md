# 数据清洗第二轮 - 总结

## 背景

### 希望解决的问题

1. **中文乱码**：数据中部分条目名称含生僻字（部分在原始通知里就已是乱码），需要找出可疑条目供人工修复。
2. **经纬度精度低**：原有地理编码使用 `release_address` 字段（行政区地址，仅精确到县市），导致大量坐标落在当地政府大楼而非文保单位实际位置。应改用 `name` 字段进行 POI 模糊搜索。

---

## 实现方案

### 关键设计

**问题一：乱码扫描**

- 遍历所有记录名称，按 Unicode 代码点范围（CJK Extension A/B/C/F 等）识别生僻字
- 同时检测名称中是否含空格（中文名称正常不含空格，有空格强烈暗示提取时编码错误）
- 按严重程度分级输出，优先呈现最可疑的条目

**问题二：按名称重新地理编码**

- 以高德 **POI 关键词搜索**（`/v3/place/text`）为主，`name` 字段为搜索词，`release_address` 提供城市 hint
- 用 difflib 相似度（≥0.5）校验匹配质量，避免错位
- POI 搜索失败时 fallback 到地址编码（`/v3/geocode/geo`）
- **全量刷新**所有 5060 条，不跳过已有坐标的记录（旧坐标普遍不准）
- 每条记录写入 `_geocode_method` 字段（`poi_search` / `geocode` / `kept_original`），便于后续追踪

### 开发内容概括

- `scripts/find_encoding_issues.py`：扫描乱码，输出 `data/encoding_issues.json`（12 条可疑记录）
- `scripts/apply_name_corrections.py`：读取用户在 `encoding_issues.json` 填写的修正名称，一键写回主数据文件
- `scripts/regeocode_by_name.py`：全量按名称重新地理编码，支持断点续传（`--resume`）
- 执行结果：
  - POI 搜索成功 **4042 条**（精确到具体地址/门牌）
  - 地址编码 fallback **1015 条**（精度仅到区县，详见 `data/geocode_fallback_list.json`）
  - 完全失败保留原坐标 **3 条**（唐代帝陵、茶马古道——跨地区线性遗址；商洛崖墓群——原本也无坐标）

### 额外产物

- `data/encoding_issues.json`：12 条乱码可疑记录清单，含严重度分级，`corrected_name` 字段留空供用户填写
- `data/geocode_fallback_list.json`：1015 条 fallback 到地址编码的记录清单（精度较低，待后续改善）
- `data/regeocode_checkpoint.json`：断点记录，中断后可续跑

---

## 局限性

1. **1015 条坐标精度仍低**：这些记录在高德 POI 库中无命中（或名称相似度低于阈值），fallback 到地址编码后坐标落在区县中心。其中包括应县木塔、嘉峪关、八达岭等知名遗址，原因是其 POI 名称与通知里的名称差异较大。

2. **高德 API 月度配额耗尽**：本轮共消耗约 6000+ 次 API 调用（POI 搜索 + 地址编码各一次），触达免费 5000 次/月上限。后续开发前需解决 API 替代问题。

---

## 后续 TODO

- [x] **寻找高德地图 SDK/API 的合理替代**：高德商业化门槛（50000 元）不合理，考虑替代方案：
  - 地图渲染：Leaflet.js（开源）+ OpenStreetMap 瓦片，或 MapLibre GL JS
  - 地理编码/POI 搜索：Nominatim（OpenStreetMap 免费服务）、腾讯地图 API（国内坐标系，免费额度更高）、百度地图 API
  - 坐标系注意：高德/腾讯使用 GCJ-02，百度使用 BD-09，OSM 使用 WGS-84，切换时需调整 `coordtransform` 逻辑
- [ ] **修复 1015 条低精度坐标**：等 API 额度恢复（或切换新 API）后，针对 `data/geocode_fallback_list.json` 中的记录，放宽 POI 相似度阈值或人工辅助校正
