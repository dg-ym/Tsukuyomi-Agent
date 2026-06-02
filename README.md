# 🌙 月読 (Tsukuyomi) — AI 智能助手

基于 **LangChain ReAct Agent + RAG 检索增强** 的智能对话系统，支持多用户知识库、联网搜索、工具调用，提供类 ChatGPT 的流式对话体验。

---

## ✨ 核心特性

- 🤖 **ReAct Agent** — 自主思考 → 工具调用 → 观察结果 → 生成回答
- 📚 **RAG 知识库** — HyDE + BM25 + RRF 融合 + DashScope 云端精排 + PDF OCR
- 🔍 **联网搜索** — Bing 实时搜索（`curl_cffi` 反反爬）+ 中文关键词提取
- 📄 **多格式文档** — txt / pdf / csv / docx / xlsx，PDF 支持 PyMuPDF + RapidOCR 扫描件识别
- 👤 **多用户隔离** — 独立知识库、独立会话、独立 ChromaDB 向量集合
- 💬 **流式对话** — SSE 实时流式输出 + 加载动画
- 📝 **Markdown 渲染** — 回复支持标题、列表、引用、链接
- 🗄️ **三层存储** — Redis（滑动窗口 20 条 + 30 天 TTL）+ ChromaDB（长期语义记忆）+ MySQL（永久）
- 🔐 **JWT 认证** — 登录/注册/邮箱验证码（Redis 10 分钟）+ 注销

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────┐
│  UniApp (Vue 3) 前端                        │
│  chat / 知识库 / 个人中心 / 导航布局          │
└──────────────┬──────────────────────────────┘
               │ HTTP / SSE
┌──────────────▼──────────────────────────────┐
│  FastAPI 后端                                │
│  /user/*  /agent/*  /kb/*                    │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│  LangChain ReAct Agent                      │
│  ChatTongyi (qwen3-max)                     │
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
│  MySQL ─── 用户/会话/消息/文档元数据          │
│  Redis ─── 会话缓存/验证码/用户缓存           │
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
| POST | /user/login | 登录 |
| GET | /user/code | 邮箱验证码 |
| PUT | /user/reset | 重置密码 |
| GET | /user/profile | 个人信息 |
| PUT | /user/profile | 修改信息/头像 |
| PUT | /user/password | 修改密码 |
| DELETE | /user/account | 注销账号 |

### Agent /agent

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /agent/chat | SSE 流式对话 |
| POST | /agent/chat/sync | 同步对话 |
| WS | /agent/chat/ws | WebSocket |
| GET | /agent/sessions | 会话列表 |
| GET | /agent/sessions/{id} | 会话消息 |
| PUT | /agent/sessions/{id}/rename | 重命名 |
| DELETE | /agent/sessions/{id} | 删除 |

### 知识库 /kb

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /kb/documents | 文档列表 |
| POST | /kb/upload | 上传文档 |
| PUT | /kb/documents/{id}/rename | 重命名 |
| DELETE | /kb/documents/{id} | 删除 |

---

## 📂 项目结构

```
backend/
├── main.py                     # FastAPI 入口
├── settings/                   # 全局配置
├── core/                       # 认证 + 邮件
├── models/                     # ORM 模型
├── schemas/                    # Pydantic 模型
├── respository/                # 数据库仓库
├── routers/                    # API 路由
├── agent/
│   ├── react_agent.py          # ReAct Agent
│   └── tools/                  # 8 工具 + 3 中间件
├── rag/
│   ├── rag_service.py          # RAG 服务
│   ├── vector_store.py         # 向量存储（单例）
│   └── advanced_retriever.py   # HyDE+BM25+RRF+Rerank
├── utils/
│   ├── cache_service.py        # Redis+ChromaDB 缓存
│   ├── context_vars.py         # ContextVar 上下文
│   ├── file_handler.py         # 文档加载器+OCR
│   └── ...
├── config/                     # YAML 配置
├── prompts/                    # 提示词模板
└── alembic/                    # 数据库迁移

frontend/
└── pages/
    ├── chat.vue                # 聊天（SSE 流式）
    ├── per_database.vue        # 知识库管理
    ├── mine.vue                # 个人中心
    ├── main.vue                # 导航+布局
    ├── login.vue / register.vue
    └── index.vue
```

---

## 🙏 致谢

前端 UI 参考 [magic_conch_frontend](https://github.com/huangyf2013320506/magic_conch_frontend)，在此感谢。

## 📄 License

MIT
