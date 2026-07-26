# Research Agent -- ҳɳͿݷ

A self-evolving AI data analysis assistant for geological deformation monitoring, hydrological monitoring, and general scientific research scenarios. Built with FastAPI + Vue 3 + LangChain.

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
| Frontend | Vue 3 + Vite (desktop), API-driven (mobile) |
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
 backend/                    # FastAPI ˷
    main.py                 # Ӧڣ·עᣬм
    config.py               # pydantic-settings ã.env
    uploads.py              # ļϴıȡ
    api/                    # REST API ·
       chat.py             #   Իӿ
       models.py           #   ģ͹л
       sessions.py         #   Ự CRUD
       analysis.py         #   ݷִ
       knowledge.py        #   ֪ʶ
       feedback.py         #   ռ
       self_growth.py      #   Գɳ״̬ѯ
    core/                   # 
       agent.py            #   ResearchAgent Э
       memory.py           #   ڼ洢
       strategy.py         #   Կ
       sandbox.py          #   ִɳ
       exceptions.py       #   ͳһ쳣
    models/                 # AI ģ
       base.py             #   BaseLLM / BaseEmbedding ӿ
       registry.py         #   ģע fallback
       lora_adapter.py     #   LoRA ΢ģͼ
       adapters/           #   
           deepseek.py     #   DeepSeek API 
           kimi.py         #   Kimi API 
           openai_compat.py#   OpenAI  API 
    analysis/               # רҵݷģ
       gnss.py             #   GNSS λƷ
       insar.py            #   InSAR α
       rainfall.py         #   ݷ
       groundwater.py      #   ˮλ
       pore_pressure.py    #   ϶ˮѹ
       cross_correlation.py#   Դݻط
       parser.py           #   ʽݽ
       codegen.py          #   NL-to-Python 
       cache.py            #   ѯ
    retrieval/              # ֪ʶϵͳ
       vector_store.py     #   ChromaDB 洢
       literature.py       #   ׼
       standards.py        #   淶ļ
       cases.py            #   
    reporting/              # 
       report_generator.py #   棨HTML/DOCX/PDF
       charts.py           #   Plotly ʽͼ
       charts_matplotlib.py#   Matplotlib 漶̬ͼ
       templates/          #   Jinja2 ģ
    self_growth/            # ҳɳģ
       feedback.py         #   ʽ/ʽռ
       prompt_optimizer.py #   APE Prompt ԶŻ
       memory_optimizer.py #   ȨŻ
       finetune.py         #   LoRA ΢
       implicit_feedback.py#   ʽռ
       benchmark.py        #   ΢׼
       progressive.py      #   ʽѧϰ
    schemas/                # Pydantic ģ
    db/                     # ݿ
        models.py           #   SQLAlchemy ģ
        session.py          #   ݿỰ
        migrations/         #   Alembic Ǩƽű
 frontend/                   # NiceGUI ǰ
    app.py                  #   Ӧ
    runtime_hook.py         #   лʼ
 tests/                      # 
    conftest.py             #    Fixtures
    unit/                   #   Ԫԣģ飩
    integration/            #   ɲ
 scripts/                    # 벿ű
 mobile/                     # ƶˣտǣ
 docs/                       # ĵ
 reports/output/             # ɵı
 data/                       # ʱ
 sandbox/                    # ɳ
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

Then open http://localhost:5173 for the Vue 3 frontend, or http://localhost:8010/docs for API docs.

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
| Frontend (desktop) | Vue 3 + Vite | Node.js required for dev, static build for prod |
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
