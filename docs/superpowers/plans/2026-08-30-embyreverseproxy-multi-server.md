# Emby 302 反向代理多服务器配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 V2/V3 Emby 302 反向代理通过多行文本配置多个 Emby 服务器及监听端口。

**Architecture:** 在各版本 `__init__.py` 内解析 `servers` 行为 `(emby_host, host, port)`，为每项创建独立 Uvicorn Server/线程。旧字段转换为单行配置，代理业务代码保持不变。

**Tech Stack:** Python、FastAPI、Uvicorn、MoviePilot plugin form schema。

## Global Constraints

- V2 与 V3 保持独立实现，不复制版本专属导入。
- 不新增第三方依赖。
- 仅有效配置启动服务；非法配置记录警告并跳过。
- V2/V3 manifest、源码版本与最新 history 键保持一致。

---

### Task 1: 添加多服务器解析与服务生命周期

**Files:**
- Modify: `plugins.v2/embyreverseproxy/__init__.py`
- Modify: `plugins.v3/embyreverseproxy/__init__.py`

**Interfaces:**
- Produce `_parse_servers(raw: str) -> List[Tuple[str, str, int]]`
- Consume parsed tuples in `init_plugin()` and `stop_service()`

- [ ] **Step 1: Add parser and backward-compatible fields**

解析 `Emby地址 => [监听地址:]端口`，规范化协议、监听地址和端口；保留旧字段作为 fallback。

- [ ] **Step 2: Start one Uvicorn server/thread per valid tuple**

为每个 tuple 调用现有 `create_app()`，保存 server/thread 列表并记录启动日志。

- [ ] **Step 3: Stop all servers and threads**

遍历设置 `should_exit`，等待线程结束，清空列表；保留单实例属性兼容外部调用。

### Task 2: 更新配置表单、默认值与版本元数据

**Files:**
- Modify: `plugins.v2/embyreverseproxy/__init__.py`
- Modify: `plugins.v3/embyreverseproxy/__init__.py`
- Modify: `package.v2.json`
- Modify: `package.v3.json`

- [ ] **Step 1: Replace single-host fields with `servers` textarea**

表单显示多行格式示例和默认监听地址说明；保留旧字段默认值以读取历史配置。

- [ ] **Step 2: Bump versions and history**

V2 升至 `0.2.7`，V3 升至 `3.0.1`，两份 history 添加对应条目。

### Task 3: Verification

**Files:**
- Test: `plugins.v2/embyreverseproxy/__init__.py` parser self-check via Python snippet

- [ ] **Step 1: Run parser assertions**

断言默认监听地址、显式监听地址、空行及非法行行为。

- [ ] **Step 2: Run compile and metadata checks**

运行 `python -m py_compile` 检查两份入口文件，并用脚本比对 manifest/source 版本。
