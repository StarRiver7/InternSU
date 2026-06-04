# Milvus Lite 文件锁残留导致 RAG 检索偶发失效

> 问题编号: Q-001 | 严重级别: P1（核心功能中断） | 修复日期: 2026-06-04 | 状态: ✅ 已解决

---

## 一、现象

### 用户视角

用户在知识库对话中提问，问题和文档内容**字面高度重合**，但系统返回「知识库中没有找到相关信息」。

| 用户问题 | 文档原文 | 预期 | 实际 |
|----------|---------|------|------|
| "连续旷工会怎么样？" | "连续旷工 3 天或全年累计旷工 5 天的，视为严重违纪，公司可予以辞退" | 命中并引用 | ❌ "未找到" |
| "年假怎么算？" | "工龄满 1 年不满 10 年的，年假为 5 天" | 命中并引用 | ❌ "未找到" |

### 关键特征

1. **偶发性** —— 不是所有查询都失败，同一查询在不同时段结果不同
2. **字面重合但检索不到** —— 排除语义匹配问题，指向检索管道本身故障
3. **无声失败** —— 不报 HTTP 500，返回正常的「找不到」降级回答，问题隐藏极深

---

## 二、排查过程

### 排除链

```
意图识别 ✅ → 路由分发 ✅ → Embedding ✅ → 向量数据库连接 ⚠️
```

1. **意图识别** —— 日志显示 `IntentNode: '连续旷工会怎么样...' → rag`，分类正确
2. **路由分发** —— `RouterNode: intent=rag → rag_retrieval_node`，路由正确
3. **Embedding 模型** —— BGE-M3 加载正常，无维度异常日志
4. **向量数据库连接** —— 日志中发现关键异常：

```
[RAGRetrieval] 检索失败: <ConnectionConfigException: (code=1, message=Open local milvus failed)>
```

### 堆栈追踪

```
pymilvus.exceptions.ConnectionConfigException: Open local milvus failed
  └── milvus_lite.exceptions.DataDirLockedError: 
      another process holds the lock on 'data/milvus_lite.db':
      [Errno 13] Permission denied
        └── msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            └── PermissionError
```

**关键发现**：底层系统调用 `msvcrt.locking` 返回 `PermissionError`，说明文件锁被其他进程持有。

---

## 三、根因分析

### 直接原因

uvicorn 的 `--reload` 模式与 Milvus Lite 的文件锁机制存在冲突。

### 时间线还原

```
T1  09:09   uvicorn 启动（带 --reload）
            ├─ 进程 A 获取 Milvus LOCK → 正常服务
            │
T2  10:03   修改代码文件（chat_node.py 等）
            ├─ watchfiles 检测到变更 → 触发 reload
            │
T3  10:03   uvicorn reload 执行：
            ├─ 进程 A 被 SIGTERM/SIGKILL
            ├─ Milvus LOCK 未被释放（非优雅退出）
            │
T4  10:03   进程 B 启动：
            ├─ 尝试 MilvusClient(db_path)
            ├─ _acquire_lock() → msvcrt.locking() → PermissionError
            ├─ 抛出 DataDirLockedError
            ├─ pymilvus 包装为 ConnectionConfigException
            │
T5  10:04   用户发起 RAG 查询：
            ├─ hybrid_retriever.search() → milvus_store.search()
            ├─ _ensure_client() 失败 → 异常被 try-catch 吞掉
            ├─ 返回 retrieval_results = []
            └─ 走「找不到」降级回答 → 用户看到"未找到"
```

### 底层原理

Milvus Lite 是一个**嵌入式文件数据库**（架构类比 SQLite，而非 Redis）：

```
┌──────────────────────────────────────────────┐
│                  Milvus Lite                  │
│                                              │
│  进程内运行，数据持久化到磁盘文件               │
│  使用文件系统锁保证单进程写入                   │
│                                              │
│  data/milvus_lite.db/                        │
│  ├── LOCK          ← 排他锁文件               │
│  ├── collections/                            │
│  │   └── internsu_rag_v2/                    │
│  │       ├── wal/     ← 写入前日志 (WAL)      │
│  │       └── partitions/  ← 实际数据          │
│  └── manifest.json                           │
└──────────────────────────────────────────────┘
```

关键点：

- **不是内存数据库** —— 数据在磁盘上，WAL 文件持久化
- **锁的是文件系统写权限** —— Windows 用 `msvcrt.locking`，Linux 用 `flock`
- **进程退出 = 锁释放** —— 正常退出时 OS 回收文件描述符 → 锁自动释放。但 `--reload` 的快速重启可能导致旧进程未完全退出就启动了新进程

### 为什么问题隐藏得深

```python
# rag_retrieval_node.py —— 异常被静默捕获
try:
    chunks = await hybrid_retriever.search(...)
except Exception as e:
    logger.warning(f"检索失败: {e}")
    state["retrieval_results"] = []   # ← 静默设为空
    state["retrieval_count"] = 0
```

对外表现：
- 不报 500 ✅（看起来系统正常）
- 检索到 0 条 ✅（像真的没找到）
- 走降级回答 ✅（"建议换个说法试试"）

实际是数据库根本没连上。

---

## 四、解决方案

### 设计思路

覆盖两种退出场景：

| 场景 | 触发 | LOCK 状态 | 处理 |
|------|------|-----------|------|
| 正常关闭 (Ctrl+C / SIGTERM) | FastAPI lifespan shutdown | 优雅释放 | `milvus_store.close()` |
| 崩溃退出 (kill -9 / OOM) | 进程被强制终止 | 锁文件残留 | 启动时检测 + 清理 + 重试 |

### 实现一：FastAPI lifespan 优雅关闭

**文件**: `app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # === Startup ===
    await llm_gateway.initialize()
    
    yield  # ← 服务运行中
    
    # === Shutdown ===
    try:
        from app.retrieval.milvus_store import milvus_store
        milvus_store.close()          # 释放文件锁
        logger.info("Milvus 连接已关闭")
    except Exception as e:
        logger.warning("Milvus 关闭异常: %s", e)
```

FastAPI 收到 SIGTERM/SIGINT 后自动执行 `yield` 之后的代码，确保 Milvus 连接被正确关闭。

### 实现二：启动时自愈——检测残留锁并清理

**文件**: `app/retrieval/milvus_store.py`

```python
def _ensure_client(self) -> MilvusClient:
    if self._client is not None:
        return self._client

    for attempt in (1, 2):
        try:
            self._client = MilvusClient(self._db_path)
            self._ensure_collection()
            return self._client
        except Exception as e:
            lock_file = self._db_path / "LOCK"
            if attempt == 1 and lock_file.exists():
                logger.warning(
                    "Milvus 连接失败 (attempt 1): %s。"
                    "尝试清理残留 LOCK 文件后重试...", e
                )
                try:
                    lock_file.unlink()       # ← 删除上一个进程的残留锁
                    logger.info("已删除残留 LOCK 文件")
                except Exception:
                    pass
                continue                     # ← 重试
            raise
```

设计要点：

- **两次重试**，不是无限循环 —— 防止真正的死锁场景
- **仅清理已知的残留场景** —— 只有第一次失败且 LOCK 文件存在时才删除，避免掩盖真实的并发写入问题
- **懒加载触发** —— `_ensure_client()` 在首次查询时才调用，不影响启动速度

### 辅助修复：全局 BM25 缓存失效

**文件**: `app/pipeline/rag_pipeline.py` + `app/retrieval/hybrid_retriever.py`

新增 `invalidate_global_bm25()` 函数，文档入库/删除后自动重建全局 BM25 索引，避免缓存不一致。

---

## 五、验证

### 测试用例

| # | 场景 | 操作 | 结果 |
|---|------|------|------|
| 1 | 正常关闭后重启 | Ctrl+C → 重启 | ✅ sources=5 |
| 2 | 强杀后重启 | kill -9 → 重启 | ✅ sources=5（LOCK 被清理） |
| 3 | 连续多次强杀重启 | kill -9 × 3 → 重启 | ✅ 每次自动恢复 |
| 4 | 所有 RAG 查询 | 年假/迟到/离职/加班费/旷工/报销 | ✅ 5/6 命中（报销文档不存在） |

### 验证脚本

```powershell
# 模拟崩溃恢复
Get-Process -Name "python" | Stop-Process -Force    # 强杀
Start-Sleep 3
# 确认 LOCK 残留
Test-Path "data/milvus_lite.db/LOCK"                # → True
# 启动服务
Start-Process python -ArgumentList "-m uvicorn app.main:app ..."
# 测试查询
Invoke-WebRequest .../ai/chat -Body '{"message":"连续旷工会怎么样"}'
# → sources=5, answer="连续旷工3天...予以辞退" ✅
```

---

## 六、反思与改进方向

### 当前方案的适用边界

| 维度 | 评价 |
|------|------|
| 单机开发/测试 | ✅ 完全适用 |
| 单机生产部署 | ✅ 适用（配合进程管理器如 systemd/supervisor） |
| 多实例部署 | ❌ 不适用 —— Milvus Lite 不支持多进程并发 |
| Kubernetes | ⚠️ 可用但非最优 —— 每个 Pod 一个 Milvus Lite 实例 |

### 生产级演进路径

```
当前：Milvus Lite（嵌入式）
  │
  ├─ 单机生产 → Milvus Standalone（独立进程，无文件锁问题）
  │
  └─ 集群生产 → Milvus Cluster（分布式 + 健康检查 + 连接池）
```

### 通用工程原则

这个问题的解法体现了两个通用的工程原则：

1. **优雅关闭 (Graceful Shutdown)** —— 任何持有资源的进程都应该在退出时释放资源。Kubernetes 的 `preStop` hook 也是同样的思想。

2. **启动时自愈 (Self-healing on Startup)** —— 不能假设上一个进程是优雅退出的。Kubernetes 的 `initContainer` 清理残留数据、数据库的 WAL 恢复，都是这个模式。

---

## 七、面试叙述模板

**如果面试官问「你解决过最有挑战的 Bug 是什么」：**

> 我在开发一个企业级 RAG 知识库系统时，遇到了一个偶发的检索失效问题——用户问的问题和文档原文高度重合，但系统却返回「找不到」。
>
> 排查时我先排除了意图识别和 Embedding 层，定位到向量数据库连接。翻堆栈发现底层是 `msvcrt.locking` 抛的 `PermissionError`——Milvus Lite 的文件锁被残留进程持有。
>
> 根因是 uvicorn 的 reload 模式。每次代码变更触发热重启时，旧进程的 Milvus 连接没有优雅关闭，LOCK 文件残留。新进程打不开数据库，但异常被上层 try-catch 吞掉了，对外表现为「检索到 0 条」。
>
> 解法分两条路径：正常关闭路径在 FastAPI lifespan 里加 `milvus_store.close()`；崩溃路径在 `_ensure_client()` 里加检测——第一次连接失败时如果 LOCK 文件存在，删掉它重试。
>
> 这个解法本质是「优雅关闭 + 启动自愈」模式。如果上生产，我会推荐升级到 Milvus Standalone，但当前的工程约束下这是最优解。

---

## 八、相关文件

| 文件 | 改动 |
|------|------|
| `app/main.py` | lifespan shutdown 阶段增加 `milvus_store.close()` |
| `app/retrieval/milvus_store.py` | `_ensure_client()` 增加残留锁检测 + 重试逻辑 |
| `app/pipeline/rag_pipeline.py` | 文档入库/删除后调用 `invalidate_global_bm25()` |
| `app/retrieval/hybrid_retriever.py` | 新增 `invalidate_global_bm25()` 缓存失效接口 |
| `app/graph/nodes/rag_retrieval_node.py` | v3 重写：LLM 查询扩展 + jieba 分词 |
| `app/core/config.py` | RAG 检索参数调优 |