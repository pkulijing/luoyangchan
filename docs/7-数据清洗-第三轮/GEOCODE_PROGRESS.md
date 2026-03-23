# 第三轮 Geocoding 进度记录

## 背景

Phase 2 的核心任务是为 1712 条问题记录提供精确地址，用于后续腾讯地图 API geocoding。原计划由 Gemini Deep Research 一次性处理，但因数据量过大放弃，改为在 Claude Code 内用 Agent 批量处理。

## 当前进度

### Phase 2.1：LLM 生成精确地址

| 批次 | 记录数 | LLM处理 | 备注 |
|------|--------|---------|------|
| batch_001 | 100 | 完成 ✓ | |
| batch_002 | 100 | 完成 ✓ | |
| batch_003 | 100 | 完成 ✓ | |
| batch_004 | 100 | 完成 ✓ | tool_uses 撞上限，质量存疑 |
| batch_005 | 100 | 完成 ✓ | tool_uses 撞上限，质量存疑 |
| batch_006 | 100 | 完成 ✓ | |
| batch_007 | 100 | 完成 ✓ | |
| batch_008 | 100 | 完成 ✓ | tool_uses 撞上限，质量存疑 |
| batch_009 | 100 | 完成 ✓ | tool_uses 撞上限，质量存疑 |
| batch_010 | 100 | 完成 ✓ | 曾用 Haiku 跑过，已删除重跑 |
| batch_011 | 100 | 完成 ✓ | 曾用 Haiku 跑过，已删除重跑 |
| batch_012 | 100 | **损坏 ✗** | 59 条幻觉记录，58 条缺失，需重跑 |
| batch_013–018 | 512 | 待处理 | |

### Phase 2.2：腾讯地图 Geocoding

| 批次 | 记录数 | Geocoding | 成功率 | 备注 |
|------|--------|-----------|--------|------|
| batch_001 | 100 | 完成 ✓ | 100/100 | 试点验证通过 |
| batch_002 | 100 | 完成 ✓ | 99/100 | |
| batch_003 | 100 | 完成 ✓ | 99/100 | |
| batch_006 | 100 | 完成 ✓ | 100/100 | |
| batch_007 | 100 | 完成 ✓ | 98/100 | |
| batch_004,005,008–011 | 800 | 待处理 | - | LLM质量存疑，需先评估 |
| batch_012–018 | 612 | 待处理 | - | LLM地址尚未生成 |

**Geocoding 已完成：batch_001–003、006–007，共 496 条更新写入主数据文件**

## 关键发现：Subagent Tool Use 上限问题

通过对比各批次的 token 和 tool_uses 数据，发现一个系统性问题：

| 批次 | total_tokens | tool_uses | 状态 |
|------|-------------|-----------|------|
| 001 | 86,697 | 39 | 正常 |
| 002 | 101,472 | 43 | 正常 |
| 003 | 108,079 | 53 | 正常 |
| 004 | 12,600 | 107 | 可疑 |
| 005 | 20,228 | 100 | 可疑 |
| 006 | 128,236 | 65 | 正常 |
| 007 | 150,932 | 79 | 正常 |
| 008 | 22,236 | 100 | 可疑 |
| 009 | 41,331 | 105 | 可疑 |
| 010 | 13,471 | 105 | 可疑 |
| 011 | 24,196 | 107 | 可疑 |
| 012 | 24,037 | 105 | 损坏 |

**结论**：Claude Code subagent 存在约 100-107 次的 tool_use 硬上限。触及上限后 agent 被强制截断。
- batch 004-011：触及上限但侥幸在截断前完成了文件写入，release_id 完整性通过，但可能有部分记录未经 WebSearch 直接给了粗糙地址
- batch 012：触及上限时只处理了约 42 条，被迫"补全"剩余 58 条时产生了幻觉（凭空捏造 release_id）

## 方案问题回顾

### 尝试过的方案

1. **Gemini Deep Research**（原计划）：因数据量过大（1712 条）放弃
2. **OpenRouter 调 LLM 逐条处理**：限流严重，放弃
3. **Claude Code Subagent，每批 100 条**：受 tool_use 上限限制，后期批次质量不稳定；另外使用 Haiku 时精度明显下降（大量县级地址）

### 待解决的问题

- batch_012-018（612 条）尚未处理
- 已完成的 batch_004-005、008-011 中，部分记录可能因 tool_use 被截断而未经充分搜索

## 当前计划

优先用 batch_001-011 的 1100 条结果跑后续流程（腾讯地图 geocoding），验证整个 pipeline 的可行性，再回头解决剩余批次的 geocoding 问题。

后续 batch_012-018 的处理方向：考虑改用外部 API 脚本（Deepseek / Qwen）调用，每次固定处理 5-10 条，避免 context 积累和 tool_use 上限问题。

## 相关文件

- 输入：`data/round3/gemini_geocode_input.json`（1712 条）
- 分批文件：`data/round3/geocode_batches/batch_001.json` ~ `batch_018.json`
- 已完成结果：`data/round3/geocode_batches/result_001.json` ~ `result_011.json`
- 辅助脚本：`scripts/round3/batch_geocode_helper.py`（split / merge / status）
