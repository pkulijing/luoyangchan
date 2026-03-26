---
name: fix-heritage-info
description: 修复/富化单个文保单位的描述和标签。自动获取 Wikipedia 和百度百科内容，通过 DeepSeek 生成结构化描述和关键词标签，写入 JSON 并同步 Supabase。
metadata: { "openclaw": { "emoji": "📝", "requires": { "bins": ["python3", "uv"] } } }
---

# 文保单位信息富化 Skill

为单个文保单位生成 description（描述）和 tags（标签），补全百科链接。

## 使用场景

1. **批量富化后的遗漏修复**: DeepSeek 批量处理中 missing 的记录
2. **质量不满意的重新生成**: 描述过短、标签不准确的记录
3. **新增记录的信息补全**: 手动添加的记录需要生成描述

## 工作流程

### 步骤 1: 确定待处理条目

复用 `fix-heritage-site` 的搜索工具：

```bash
cd /home/jing/Developer/luoyangchan/skills/fix-heritage-site/scripts
uv run python search.py --id 1-29
uv run python search.py --name "冉庄地道战"
```

### 步骤 2: 执行富化

```bash
cd /home/jing/Developer/luoyangchan/skills/fix-heritage-info/scripts

# 自动模式：获取百科 + DeepSeek 生成 + 写入 JSON + 同步 Supabase
python enrich.py 1-29

# 附加用户上下文
python enrich.py 1-29 --context "冉庄地道战遗址是抗日战争时期冀中军民..."

# 只看结果不写入
python enrich.py 1-29 --dry-run

# 批量处理
python enrich.py 1-29 1-164 3-32
```

### 内部流程

1. **获取 Wikipedia**: 已有 URL 直接取 → 构造 URL → 搜索 API 兜底（相似度 ≥ 0.85）
2. **获取百度百科**: 直接构造 `baike.baidu.com/item/{名称}` → 去括号重试 → BeautifulSoup 提取摘要
3. **DeepSeek 生成**: 结构化字段 + 百科内容 → 生成 description（150-300字）+ tags（10-20个）
4. **写入**: 更新 JSON 文件 + 增量同步 Supabase（description, tags, wikipedia_url, baike_url）

## 输出字段

| 字段 | 说明 |
|------|------|
| `description` | 150-300 字的结构化描述 |
| `tags` | 10-20 个关键词（人物、事件、朝代、风格等） |
| `wikipedia_url` | Wikipedia 页面链接（如果新发现） |
| `baike_url` | 百度百科页面链接 |

## 环境变量

需要在 `.env.local` 中配置:
- `DEEPSEEK_API_KEY` - DeepSeek API
- `NEXT_PUBLIC_SUPABASE_URL` - Supabase 地址（同步用）
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase 密钥（同步用）

**不需要百度 API Key** — 百度百科通过直接爬取页面获取，不依赖百度 API。

## 文件结构

```
skills/fix-heritage-info/
├── _meta.json
├── SKILL.md
└── scripts/
    └── enrich.py    # 主脚本（百科获取 + DeepSeek + 写入 + 同步）
```
