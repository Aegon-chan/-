# Research Agent -- 自我成长型科研数据分析助手

A self-evolving AI data analysis assistant for geological deformation monitoring, hydrological monitoring, and general scientific research scenarios. Built with FastAPI + NiceGUI + LangChain.

The agent learns from user feedback, optimises its prompts, builds a long-term memory network, and can auto-trigger LoRA fine-tuning -- growing better with every interaction.

---

## Core Capabilities

| Capability | Description |
|------------|-------------|
| Multi-model LLM | DeepSeek, Kimi, OpenAI-compatible API, hot-swappable via registry |
| Domain Analysis | NL-driven GNSS displacement, InSAR deformation, rainfall, groundwater, pore-pressure analysis |
| RAG Knowledge Base | Semantic search over standards, literature, and cases via ChromaDB + BGE embeddings |
| Auto Reporting | One-click monitoring reports in HTML / DOCX / PDF with built-in chart engine |
| Code Sandbox | Isolated subprocess execution with resource limits, figure capture, and safe-package allowlist |
| Self-Growth | Memory network, feedback-driven prompt optimisation, APE, and auto-triggered LoRA fine-tuning |
| ReAct Reasoning | Think-Act-Observe loop with tool use (analysis, search, report generation) |
| Desktop App | PyInstaller-packaged standalone exe with built-in backend |

---

## Tech Stack

| Layer | Technology |
|--------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy, Alembic |
| Frontend | NiceGUI (desktop), API-driven (mobile) |
| AI | LangChain, multi-model Router, ReAct pattern |
| Vector Store | ChromaDB + BAAI/bge-small-zh-v1.5 |
| Self-Growth | SQLite memory network, APE, LoRA (PEFT) |
| Sandbox | Subprocess isolation, resource limits, whitelist |
| Packaging | PyInstaller, Docker Compose |
| CI/CD | GitHub Actions (pytest + ruff) |

---

## Project Structure

```
research-agent/
├── backend/                    # FastAPI 后端服务
│   ├── main.py                 # 应用入口，路由注册，中间件
│   ├── config.py               # pydantic-settings 配置（.env）
│   ├── uploads.py              # 文件上传与文本提取
│   ├── api/                    # REST API 路由
│   │   ├── chat.py             #   对话接口
│   │   ├── models.py           #   模型管理与切换
│   │   ├── sessions.py         #   会话 CRUD
│   │   ├── analysis.py         #   数据分析执行
│   │   ├── knowledge.py        #   知识库管理
│   │   ├── feedback.py         #   反馈收集
│   │   └── self_growth.py      #   自成长状态查询
│   ├── core/                   # 智能体核心引擎
│   │   ├── agent.py            #   ResearchAgent 核心协调器
│   │   ├── memory.py           #   长期记忆存储
│   │   ├── strategy.py         #   策略库
│   │   ├── sandbox.py          #   代码执行沙箱
│   │   └── exceptions.py       #   统一异常处理
│   ├── models/                 # AI 模型适配层
│   │   ├── base.py             #   BaseLLM / BaseEmbedding 抽象接口
│   │   ├── registry.py         #   模型注册表与 fallback
│   │   ├── lora_adapter.py     #   LoRA 微调模型加载
│   │   └── adapters/           #   具体适配器
│   │       ├── deepseek.py     #   DeepSeek API 适配
│   │       ├── kimi.py         #   Kimi API 适配
│   │       └── openai_compat.py#   OpenAI 兼容 API 适配
│   ├── analysis/               # 专业数据分析模块
│   │   ├── gnss.py             #   GNSS 位移分析
│   │   ├── insar.py            #   InSAR 形变分析
│   │   ├── rainfall.py         #   降雨数据分析
│   │   ├── groundwater.py      #   地下水位分析
│   │   ├── pore_pressure.py    #   孔隙水压力分析
│   │   ├── cross_correlation.py#   多源数据互相关分析
│   │   ├── parser.py           #   多格式数据解析
│   │   ├── codegen.py          #   NL-to-Python 代码生成
│   │   └── cache.py            #   查询结果缓存
│   ├── retrieval/              # 知识检索系统
│   │   ├── vector_store.py     #   ChromaDB 向量存储
│   │   ├── literature.py       #   文献检索
│   │   ├── standards.py        #   规范条文检索
│   │   └── cases.py            #   案例检索
│   ├── reporting/              # 报告生成
│   │   ├── report_generator.py #   报告生成引擎（HTML/DOCX/PDF）
│   │   ├── charts.py           #   Plotly 交互式图表
│   │   ├── charts_matplotlib.py#   Matplotlib 出版级静态图表
│   │   └── templates/          #   Jinja2 报告模板
│   ├── self_growth/            # 自我成长模块
│   │   ├── feedback.py         #   显式/隐式反馈收集
│   │   ├── prompt_optimizer.py #   APE Prompt 自动优化
│   │   ├── memory_optimizer.py #   记忆权重优化
│   │   ├── finetune.py         #   LoRA 微调管线
│   │   ├── implicit_feedback.py#   隐式反馈收集
│   │   ├── benchmark.py        #   微调基准评估
│   │   └── progressive.py      #   渐进式学习
│   ├── schemas/                # Pydantic 数据模型
│   └── db/                     # 数据库
│       ├── models.py           #   SQLAlchemy 数据模型
│       ├── session.py          #   数据库会话管理
│       └── migrations/         #   Alembic 迁移脚本
├── frontend/                   # NiceGUI 前端
│   ├── app.py                  #   应用入口
│   └── runtime_hook.py         #   运行环境初始化
├── tests/                      # 测试
│   ├── conftest.py             #   共享 Fixtures
│   ├── unit/                   #   单元测试（覆盖所有模块）
│   └── integration/            #   集成测试
├── scripts/                    # 开发与部署脚本
├── mobile/                     # 移动端（空壳）
├── docs/                       # 文档
├── reports/output/             # 生成的报告
├── data/                       # 运行时数据
└── sandbox/                    # 沙箱策略配置
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- API keys for at least one LLM provider (DeepSeek / Kimi / OpenAI)

```bash
# 1. Clone & enter
git clone https://github.com/your-org/research-agent.git
cd research-agent

# 2. Setup virtual environment
python -m venv .venv
.venv\\Scripts\\activate      # Windows
pip install -r requirements.txt

# 3. Configure API keys
cp .env.example .env
# Edit .env with your API keys

# 4. Run database migrations
alembic upgrade head

# 5. Start servers
powershell -File scripts/dev.ps1
```

Then open http://localhost:8080 for the NiceGUI frontend, or http://localhost:8010/docs for API docs.

### Desktop exe (no Python required)

```powershell
.venv\\Scripts\\Activate.ps1
python scripts/build_exe.ps1
# Output: dist\\ResearchAgent\\ResearchAgent.exe
```

---

## API Overview

All REST endpoints under `GET /api/v1/`:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with component status |
| `GET /metrics` | Prometheus metrics |
| `POST /chat` | Send message (streaming or non-streaming) |
| `GET/POST/DELETE /sessions` | Session CRUD |
| `GET /models` | List registered LLM models |
| `POST /analysis/execute` | Execute NL2Query in sandbox |
| `POST /knowledge/upload` | Upload document to vector store |
| `POST /feedback/collect` | Submit explicit feedback |
| `GET /self-growth/stats` | Get self-growth optimisation stats |

---

## Test Suite

```bash
pytest tests/unit/ --cov=backend -v
```

151+ unit tests covering all core modules (1 skipped for environment-dependent feature). Integration tests cover the RAG analysis pipeline and self-growth loop.

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend framework | FastAPI | Async, auto OpenAPI docs |
| Database | SQLite -> PostgreSQL | Zero-config dev, scalable prod |
| Vector store | ChromaDB | Local, lightweight, no separate service |
| Embedding model | BAAI/bge-small-zh-v1.5 | Top Chinese semantic search |
| Frontend (desktop) | NiceGUI | Python-native, no Node.js |
| Fine-tuning | LoRA (PEFT) | Memory-efficient, hot-swappable |
| Code sandbox | Subprocess + Docker | Dev zero-deps, prod full isolation |

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the four-phase development plan.

---

## License

MIT License.

---

*Research Agent v0.1.0 -- Updated 2026-07-02*
