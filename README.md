# Research Agent — 自我成长型AI数据分析助手

面向地质形变监测、水文监测等科研场景，一款具备**自我成长能力**的AI数据分析助手。

## 核心能力

| 功能 | 说明 |
|------|------|
| **多模型接入** | 支持 DeepSeek、KIMI 等主流 AI 模型，可动态切换 |
| **专业数据分析** | 自然语言查询分析 GNSS 位移、InSAR 形变、雨量、地下水位、孔隙水压力等数据 |
| **知识检索** | 基于 RAG 的规范条文、历史文献、监测案例语义检索 |
| **自动报告** | 一键生成监测报告与专业分析图表 |
| **沙箱安全** | 隔离的代码执行环境，保障敏感操作安全 |
| **自我成长** | 基于用户反馈和任务结果优化记忆权重、提示词，支持模型微调 |
| **App 封装** | 核心功能打包为桌面/移动端应用 |

## 技术栈

- **后端**: Python FastAPI + SQLAlchemy + Alembic
- **前端**: NiceGUI（快速原型）→ React Native / Flutter（移动端）
- **AI 引擎**: LangChain + 多模型 Router + RAG
- **向量存储**: ChromaDB + BGE Embeddings
- **自我成长**: 记忆网络 + Prompt 优化 + LoRA 微调
- **沙箱**: Subprocess 隔离 + Docker（生产环境）

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url> && cd research-agent

# 2. 安装依赖
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 4. 启动开发服务器
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

## 项目结构

```
├── backend/          # 后端服务
│   ├── api/          # REST API 路由
│   ├── core/         # 智能体核心引擎
│   ├── models/       # AI 模型接入层
│   ├── analysis/     # 专业数据分析
│   ├── retrieval/    # 知识检索系统
│   ├── reporting/    # 报告生成
│   ├── self_growth/  # 自我成长模块
│   └── db/           # 数据持久化
├── frontend/         # 用户界面
├── sandbox/          # 代码执行沙箱
├── tests/            # 测试
├── docs/             # 文档
├── mobile/           # 移动端封装
└── scripts/          # 开发脚本
```

## 开发路线

详见 [ROADMAP.md](ROADMAP.md)

## 许可

MIT License
