# 🌙 月読 (Tsukuyomi) — AI 智能助手

基于 **LangChain ReAct Agent + RAG 检索增强** 的智能对话系统，支持多用户知识库、联网搜索、工具调用，提供类 ChatGPT 的流式对话体验。

---

## ✨ 核心特性

- 🤖 **ReAct Agent** — 自主思考 → 工具调用 → 观察结果 → 生成回答
- 📚 **RAG 知识库** — HyDE + BM25 + RRF 融合 + DashScope 云端精排 + PDF 全文 OCR
- 🔍 **联网搜索** — Bing 实时搜索（`curl_cffi` TLS 指纹模拟）+ 中文关键词提取
- 📄 **多格式文档** — txt / pdf / csv / docx / xlsx，PDF 支持 PyMuPDF + RapidOCR（含图文混排）
- 👤 **多用户隔离** — ContextVar 透明注入 user_id，Agent 层无感知
- 💬 **流式对话** — SSE 实时流式输出
- 📝 **Markdown 渲染** — 回复支持标题、列表、引用、链接，可选择复制
- 🗄️ **四层存储** — MySQL（元数据）+ 磁盘（原文件备份）+ Redis（滑动窗口 20 条）+ ChromaDB（向量）
- 🔐 **JWT 双 Token + Rotation** — Access Token + Refresh Token 轮换 + Redis 三态标记重用检测
- 📋 **文档在线预览** — 文本类文档直接预览，二进制文件提示下载

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────┐
│  UniApp (Vue 3) 前端                         │
│  chat / 知识库 / 个人中心 / 导航布局            │
│  ├─ 流式对话 (SSE) + 思考动画                  │
│  ├─ 文档在线预览 + 上传/删除/重命名              │
│  └─ Markdown 渲染                            │
└──────────────┬──────────────────────────────┘
               │ HTTP / SSE
┌──────────────▼──────────────────────────────┐
│  FastAPI 后端                                │
│  /user/*  /agent/*  /kb/*                    │
│  ├─ JWT 双 Token + Refresh Rotation          │
│  ├─ ContextVar 用户上下文透明注入             │
│  └─ run_in_executor 线程池并发               │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  LangChain ReAct Agent (全局单例)            │
│  ChatTongyi (qwen3-max) · 120s 超时         │
│  ├─ rag_summarize     知识库检索             │
│  ├─ web_search         Bing 联网搜索         │
│  ├─ get_weather        wttr.in 天气 API      │
│  ├─ get_user_location  ip-api.com IP 定位    │
│  ├─ get_user_id        ContextVar 上下文      │
│  ├─ get_current_month  datetime 时间          │
│  ├─ fetch_external_data MySQL 使用统计        │
│  └─ fill_context_for_report 报告模式切换      │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  RAG 检索管线                                │
│  HyDE → BM25+ jieba → RRF → gte-rerank-v2   │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  数据层                                      │
│  MySQL ── 用户/会话/消息/文档元数据+路径        │
│  磁盘 ─── 原文件备份 (uploads/{uid}/{hash}_{name})│
│  Redis ── 会话缓存/验证码/Refresh Token 状态   │
│  ChromaDB ─ 向量存储 (kb_user_{id})          │
└─────────────────────────────────────────────┘
```

---

## 🚀 快速启动

### 环境要求

| 依赖 | 版本 |
|------|------|
| Python | ≥ 3.10 |
| MySQL | ≥ 5.7 |
| Redis | ≥ 5.0 |
| Node.js | ≥ 18 |

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
# 设置 DashScope API Key
export DASHSCOPE_API_KEY="your-api-key"
# 修改 settings/__init__.py 中的 DB_URI
# 创建上传目录
mkdir uploads
# 数据库迁移
alembic upgrade head
# 启动 Redis
redis-server
# 启动后端
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev:h5
```

---

## 📡 API 接口

### 用户 /user

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /user/register | 注册 |
| POST | /user/login | 登录（返回 access_token + refresh_token） |
| POST | /user/refresh | 刷新 Token（Rotation 轮换 + 重用检测） |
| GET | /user/code | 邮箱验证码 |
| PUT | /user/reset | 重置密码 |
| GET | /user/profile | 个人信息 |
| PUT | /user/profile | 修改信息/头像 |
| PUT | /user/password | 修改密码 |
| DELETE | /user/account | 注销账号（级联清理全部数据） |

### Agent /agent

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /agent/chat | SSE 流式对话（思考过程已过滤，仅输出回答） |
| GET | /agent/sessions | 会话列表 |
| GET | /agent/sessions/{id} | 会话消息 |
| PUT | /agent/sessions/{id}/rename | 重命名 |
| DELETE | /agent/sessions/{id} | 删除 |

### 知识库 /kb

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /kb/documents | 文档列表 |
| POST | /kb/upload | 上传文档（≤20MB，磁盘备份） |
| GET | /kb/documents/{id}/preview | 在线预览（文本类直接显示） |
| PUT | /kb/documents/{id}/rename | 重命名 |
| DELETE | /kb/documents/{id} | 删除（数据库+向量库+磁盘） |

---

## 📂 项目结构

```
backend/
├── main.py                     # FastAPI 入口
├── settings/                   # 全局配置 (DB_URI, JWT, UPLOAD_DIR)
├── core/                       # JWT 双 Token + Rotation 认证 / 邮件服务
├── models/                     # ORM 模型 (用户、会话、消息、文档)
├── schemas/                    # Pydantic 请求/响应模型
├── respository/                # 数据库仓储层
├── routers/                    # API 路由 (用户 / Agent / 知识库)
├── agent/                      # ReAct Agent + 工具 + 中间件
├── rag/                        # RAG 检索管线 + 向量存储
├── utils/                      # 工具函数 (Redis 缓存、ContextVar、文档加载器、OCR)
├── config/                     # YAML 配置文件
├── prompts/                    # 提示词模板
├── alembic/                    # 数据库迁移
└── uploads/                    # 用户上传原文件

frontend/
└── pages/                      # Vue 页面 (聊天、知识库、个人中心、登录)
```

---

## 🔒 安全机制

### JWT 双 Token + Refresh Rotation

```
登录 → access_token (15d) + refresh_token (30d)
         │
         ├─ 每次 API 请求携带 access_token
         │    └─ 过期 → 用 refresh_token 换取新的一对
         │         └─ 旧 refresh_token 标记 "used"（Redis 三态: valid/used/不存在）
         │
         ├─ 重用检测: 已标记 "used" 的 token 再次出现 → 撤销全部
         └─ 注销/删号: 全部 refresh_token 标记 "used"
```

- **Access Token**: 无状态 JWT，每次请求暴露，15 天有效
- **Refresh Token**: 有状态（Redis），仅刷新接口暴露，Rotation 轮换
- **降级策略**: Redis 不可用时退化为纯 JWT 无状态模式，保证可用性

---

## 🙏 致谢

前端 UI 参考 [magic_conch_frontend](https://github.com/huangyf2013320506/magic_conch_frontend)，在此感谢。

## 📄 License

MIT
