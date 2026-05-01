# 性能调优与故障排除

## classify.py 速度优化

### 问题：每条新闻耗时数分钟

本地模型（尤其是量化模型在 CPU 上推理时）每条新闻可能耗时 5–15 分钟，2853 条新闻需要数百小时。

### 优化策略（按优先级排序）

#### 1. 启用并发（最重要）

```bash
# 4 个并发 worker，理论 4x 提速
python scripts/classify.py --workers 4

# 8 个并发（服务器端足够时）
python scripts/classify.py --workers 8
```

或永久配置到 `config/settings.yaml`：
```yaml
llm_limits:
  classify_workers: 4
```

原理：API 调用是 I/O 密集型（等待推理），ThreadPoolExecutor 可以并发等待，充分利用服务器多请求处理能力。

#### 2. 降低 max_tokens

```yaml
llm_limits:
  classify_max_tokens: 1024  # 分类 JSON 通常 < 500 tokens，2048 浪费
```

输出 token 数直接影响推理时间（每个 output token 都要逐字生成）。

#### 3. 减少正文截断长度

```yaml
llm_limits:
  classify_body_chars: 2000  # 从 3000 降到 2000
```

输入 token 数影响 prefill 时间。2000 字对分类判断通常足够。

#### 4. 关闭调用间隔

```yaml
llm_limits:
  classify_interval_seconds: 0  # 本地模型无需限流，云端 API 建议 ≥ 0.5
```

#### 5. 降低温度

```yaml
model:
  - name: "Local-Fast"
    role: "fast"
    temperature: 0   # 分类任务确定性输出，减少采样开销
```

### 综合推荐配置

```yaml
llm_limits:
  classify_max_tokens: 1024
  classify_batch_size: 30
  classify_interval_seconds: 0
  classify_body_chars: 2000
  classify_workers: 4
```

预估效果：4 并发 + token 减半 + 正文减少 → 理论 8–10x 提速。

---

## Pydantic 校验失败

### 症状

```
Structured output failed: 2 validation errors for NewsClassification
domain
  Input should be a valid array [type=list_type, input_value='社会/民生', input_type=str]
entities
  Input should be a valid array [type=list_type, input_value={'company': [...]}, input_type=dict]
```

### 原因

本地模型（Gemma、Llama 等）可能不遵循严格的 JSON Schema：
- `domain` 返回字符串 `"社会/民生"` 而非数组 `["社会/民生"]`
- `entities` 返回 `{"company": ["名称"], "person": []}` 而非 `[{"name": "名称", "type": "company"}]`

### 解决方案

已内置修复。`classify.py` 中的 `normalize_classification_json()` 函数在 Pydantic 校验前自动修复：

1. `domain`、`cities`、`tags`：字符串 → 数组
2. `entities`：dict-of-lists → list-of-objects
3. 单个 entity 字符串 → 补充 `type: "unknown"`

此修复通过 `chat_structured(normalizer=...)` 参数传递，不影响其他调用方。

### 如果仍有问题

1. 检查日志中的原始 LLM 返回 JSON，手动添加新的修复规则到 `normalize_classification_json()`
2. 检查 system prompt 中是否强调 JSON 格式要求
3. 考虑在 prompt 末尾添加格式示例

---

## MySQL 连接断开

### 症状

```
MySQL server has gone away
```

### 原因

长时间空闲后 MySQL 连接超时断开。

### 解决方案

已内置修复。`db.py` 的 `_DB.execute()` 在每次执行 SQL 前调用 `_ping()`：
- MySQL 连接断开时自动 `reconnect=True`
- 连接参数已配置 `connect_timeout=10, read_timeout=30`

---

## API 调用超时

### 症状

```
API call failed: ReadTimeout
```

### 配置

```yaml
model:
  - name: "Local-Fast"
    timeout: 15000   # 15 秒 → 本地模型不够用?
    max_retries: 1   # 失败仅重试 1 次
```

建议：
- 本地模型：`timeout: 60000`（60秒，慢模型需要更多时间）
- 云端 API：`timeout: 120`（120秒）
- 重试次数：`max_retries: 3`（指数退避，最多等 2+4+8=14秒后最终失败）

---

## 断点续跑

### 如何使用

classify.py 天然支持断点续跑：

```bash
# 处理到一半 Ctrl+C 中断
# 重新运行即可，已处理的文件自动跳过
python scripts/classify.py --workers 4
```

日志会显示：
```
Checkpoint resume: 156 files already processed, skipping
Total 2853 files, 2697 pending
```

### 机制

- 每处理完一条（无论通过还是跳过），立即写入 `processed_files` 表
- 处理失败的条目不写入 `processed_files`，下次重试
- 不需要任何额外配置
