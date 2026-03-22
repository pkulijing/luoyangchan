# 数据清洗方案：从维基文库通知文本补全文保单位列表

## 背景

Wikipedia 数据覆盖第 1-8 批但不完整（约 4303 条），官方数据共 5294 条。通过解析维基文库收录的国务院原始通知，补全完整列表并与 Wikipedia 坐标/链接数据合并。

---

## 步骤 1：数据库 Schema

**文件**: `supabase/migrations/20240102000000_add_release_columns.sql`

在 `heritage_sites` 表新增两列：

```sql
ALTER TABLE heritage_sites ADD COLUMN release_id TEXT;
ALTER TABLE heritage_sites ADD COLUMN release_address TEXT;
CREATE INDEX idx_heritage_sites_release_id ON heritage_sites (release_id);
```

---

## 步骤 2：维基文库文本解析

**文件**: `scripts/scrape_wikisource.py`

解析 8 批国务院通知的 HTML 表格，提取每条记录。

### 数据源

| 批次 | 年份 |
| ---- | ---- |
| 1    | 1961 |
| 2    | 1982 |
| 3    | 1988 |
| 4    | 1996 |
| 5    | 2001 |
| 6    | 2006 |
| 7    | 2013 |
| 8    | 2019 |

### 设计要点

- 8 批通知结构一致：每页最大的 table 为主数据表，末尾小表为合并项目（跳过）
- 分类信息以 `colspan>=3` 单格行出现在表格内，需从上下文推断
- 有子行的条目（如长城各段）展开为独立条目：`name = "长城-齐长城遗址"`，`release_id = "5-442-1"`
- 合并项目一律忽略，只记录原始新增条目
- 所有文本字段统一转为简体中文（`zhconv`）

### 输出字段

```json
{
  "release_id": "8-123",
  "name": "上宅遗址",
  "era": "新石器时代",
  "release_address": "北京市平谷区",
  "category": "古遗址",
  "batch": 8,
  "batch_year": 2019
}
```

**输出**: `data/heritage_sites_gov.json`（共 5060 条）

---

## 步骤 3：数据合并

**文件**: `scripts/reconcile_data.py`

将维基文库数据（权威名称/编号/地址/分类）与 Wikipedia 数据（wikipedia_url/坐标）合并。

### 匹配策略（多轮）

| 轮次 | 匹配方式                                                          |
| ---- | ----------------------------------------------------------------- |
| 1    | `(normalized_name, batch)` 精确匹配                               |
| 2    | 去括号/注释后的 name + batch 精确匹配                             |
| 3    | 同 batch+province 下 difflib 相似度 > 0.85                        |
| 4    | 反向匹配：对未命中的 Wikipedia 记录，找最近的政府记录补充坐标/URL |

### 合并规则

- `name`, `era`, `category`, `batch`, `release_id`, `release_address`：以维基文库数据为准
- `wikipedia_url`, `latitude`, `longitude`, `province`, `city`, `address`, `description`, `image_url`：保留 Wikipedia 数据
- 仍无法匹配的 Wikipedia 独有记录直接丢弃（数量极少）

**输出**: `data/heritage_sites_merged.json` + `data/reconciliation_report.txt`

---

## 步骤 4：地理编码

**文件**: `scripts/geocode_amap.py`

通过高德 Web 服务 API 补全缺失的坐标和地址信息（约 823 条无坐标记录，主要为第 8 批）。

- 使用 `AMAP_GEOCODING_KEY`（Web 服务类型，非 JS API Key）
- 以 lat/lon 是否存在判断是否需要处理，可多次运行
- 地理编码失败时自动 fallback 到 POI 关键词搜索，用 difflib 做名称相似度校验

**输出**: `data/heritage_sites_geocoded.json`

---

## 步骤 5：数据导入

**文件**: `scripts/seed_supabase.py`

- `--clear` 参数，导入前执行 `DELETE FROM heritage_sites`
- 读取 `data/heritage_sites_geocoded.json`，字段映射含 `release_id`, `release_address`

---

## 执行顺序

```bash
# 1. 应用 Schema Migration
supabase db reset

# 2. 解析维基文库
cd scripts
uv run python scrape_wikisource.py

# 3. 与 Wikipedia 数据合并
uv run python reconcile_data.py

# 4. 地理编码（首次：从 merged 复制；后续重跑直接运行即可）
cp ../data/heritage_sites_merged.json ../data/heritage_sites_geocoded.json
uv run python geocode_amap.py

# 5. 导入数据库
uv run python seed_supabase.py --clear
```

## TODO

- [ ] **补全 53 条缺坐标记录**：运行 `list_missing_coords.py` 可查看完整列表（输出至 `data/missing_coords.json`）。这些记录高德地理编码和 POI 搜索均未命中，需人工核查地址或通过其他方式补充坐标。

- [ ] **补全几个增补的条目**：当前只处理了批量公布的，几个增补的仍然缺失：
  - [第5批] 里耶古城遗址 (湖南省)
  - [第5批] 阿尔寨石窟 (内蒙古自治区)
  - [第5批] 焦裕禄烈士墓 (河南省)
  - [第6批] 安江农校纪念园 (湖南省)
  - [第7批] 北京市八宝山革命公墓 (北京市)

---

## 关键文件

| 文件                                                         | 说明                                                |
| ------------------------------------------------------------ | --------------------------------------------------- |
| `supabase/migrations/20240102000000_add_release_columns.sql` | 新增 release_id / release_address 列                |
| `scripts/scrape_wikisource.py`                               | 维基文库解析，输出 heritage_sites_gov.json          |
| `scripts/reconcile_data.py`                                  | 多轮匹配合并，输出 heritage_sites_merged.json       |
| `scripts/geocode_amap.py`                                    | 高德地理编码，输出 heritage_sites_geocoded.json     |
| `scripts/seed_supabase.py`                                   | 导入 Supabase                                       |
| `src/lib/types.ts`                                           | 添加 release_id, release_address，扩展 SiteCategory |
| `src/lib/constants.ts`                                       | 添加历史分类及其颜色                                |
