# Research Agent 使用说明书

> **版本**: 0.1.0 | **更新日期**: 2026-07-02
>
> Research Agent 是一款具备自我成长能力的科研数据分析助手，专注于地质形变监测（GNSS/InSAR）、水文监测（降雨/地下水/孔隙水压力）等领域的智能分析。系统通过持续学习用户反馈，不断优化自身表现。

---

## 目录

1. [产品概述](#1-产品概述)
2. [快速安装](#2-快速安装)
3. [配置指南](#3-配置指南)
4. [界面导航](#4-界面导航)
5. [核心功能详解](#5-核心功能详解)
6. [REST API 参考](#6-rest-api-参考)
7. [自我成长系统](#7-自我成长系统)
8. [代码沙箱](#8-代码沙箱)
9. [报告生成](#9-报告生成)
10. [Docker 部署](#10-docker-部署)
11. [桌面应用打包](#11-桌面应用打包)
12. [常见问题与故障排除](#12-常见问题与故障排除)
13. [项目结构速览](#13-项目结构速览)

---

## 1. 产品概述

### 1.1 简介

Research Agent 是一个由 AI 驱动的科研数据全流程分析平台。与传统分析工具不同，它不仅能够理解自然语言指令并自动执行数据分析，更重要的是能够**从每次交互中学习**——记住用户的偏好、积累领域知识、根据反馈优化自身策略，必要时还可通过 LoRA 微调提升模型表现。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| **多模型 LLM** | 支持 DeepSeek、Kimi、OpenAI 兼容 API，运行时热切换，自动 Fallback |
| **专业数据分析** | 自然语言驱动的 GNSS 位移、InSAR 形变、降雨、地下水、孔隙水压力分析 |
| **RAG 知识库** | 通过 ChromaDB + BGE 中文语义嵌入实现文档智能检索 |
| **自动报告** | 一键生成 HTML / DOCX / PDF 格式监测报告，内置 Plotly + Matplotlib 双引擎 |
| **代码沙箱** | 隔离的子进程执行环境，带资源限制、白名单安全策略、图表自动捕获 |
| **自我成长** | 记忆网络、反馈驱动 Prompt 优化、APE 自动搜索、LoRA 微调自动触发 |
| **ReAct 推理** | 思考-行动-观察循环，支持工具调用（分析、检索、报告生成） |
| **桌面应用** | PyInstaller 打包的独立 exe，内置完整后端服务 |

### 1.3 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.12+, FastAPI, SQLAlchemy, Alembic |
| 前端界面 | NiceGUI（桌面网页），API 驱动（移动端预留） |
| AI 引擎 | LangChain + 自定义 ReAct Loop、多模型路由 |
| 向量存储 | ChromaDB + BAAI/bge-small-zh-v1.5（384维中文向量） |
| 自我成长 | SQLite 记忆网络、APE Prompt 优化、LoRA (PEFT) 微调 |
| 沙箱安全 | Subprocess 隔离、资源限制（CPU/内存/超时）、函数白名单 |
| 打包部署 | PyInstaller、Docker Compose、GitHub Actions CI |

### 1.4 适用场景

- 地质形变监测数据分析（GNSS 位移、InSAR 形变场）
- 水文监测数据分析（降雨量、地下水位、孔隙水压力）
- 多源监测数据关联分析（降雨-位移-水位相关性）
- 自动化监测报告生成（日报/周报/月报/专题报告）
- 科研文献与规范的知识检索
- 需要持续学习用户偏好的个性化数据分析环境

---

## 2. 快速安装

### 2.1 前置条件

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.11+ | 推荐 3.12 |
| pip | 最新版 | — |
| API Key | 至少一个 | DeepSeek / Kimi / OpenAI 任选其一 |
| Git | 可选 | 用于版本管理 |

### 2.2 一键安装（推荐）

```powershell
# 1. 进入项目目录
cd research-agent

# 2. 运行安装脚本（创建虚拟环境 + 安装依赖 + 初始化配置）
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

# 3. 激活虚拟环境
.venv\Scripts\Activate.ps1

# 4. 编辑 .env 文件，填入 API Key
#    详见下方"配置指南"章节

# 5. 运行数据库迁移
alembic upgrade head

# 6. 启动开发服务器（同时启动后端 + 前端）
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

启动后访问：
- 网页界面：http://localhost:8080
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 2.3 手动安装

```powershell
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活
.venv\Scripts\Activate.ps1

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化配置
copy .env.example .env
# 编辑 .env 填入 API Key

# 5. 数据库迁移
alembic upgrade head

# 6. 启动（分离终端）
# 终端 1 - 后端
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2 - 前端
python -m frontend.app
```

### 2.4 Makefile 快捷命令

```powershell
# 安装环境
make install

# 启动开发服务器
make dev

# 运行测试
make test

# 代码检查
make lint

# 数据库迁移
make db-migrate

# Docker 构建
make docker-build
make docker-run

# 打包桌面 exe
make build-exe
```

---

## 3. 配置指南

### 3.1 环境变量配置

系统通过 `.env` 文件（或环境变量）管理所有配置。复制 `.env.example` 为 `.env` 后编辑：

```ini
# === 应用基础配置 ===
APP_NAME=ResearchAgent
APP_ENV=development            # development / staging / production
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000

# === AI 模型 API（至少配置一个） ===
# DeepSeek（推荐 - 性价比最优）
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_API_BASE=https://api.deepseek.com

# KIMI (Moonshot)
KIMI_API_KEY=sk-your-key-here
KIMI_API_BASE=https://api.moonshot.cn

# OpenAI（备用）
OPENAI_API_KEY=sk-your-key-here
OPENAI_API_BASE=https://api.openai.com/v1
```

### 3.2 Feature Flags（功能开关）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FEATURE_SELF_GROWTH` | true | 自成长系统（记忆、Prompt 优化） |
| `FEATURE_FEEDBACK` | true | 反馈收集系统 |
| `FEATURE_FINETUNE` | false | LoRA 微调（需要 GPU） |
| `FEATURE_REALTIME_REPORTS` | true | 实时报告生成 |

### 3.3 API Key 获取

| 模型 | 获取地址 | 推荐等级 |
|------|---------|---------|
| DeepSeek | https://platform.deepseek.com | 推荐（性价比高） |
| Kimi | https://kimi.moonshot.cn | 备用 |
| OpenAI | https://platform.openai.com | 备用 |

### 3.4 运行时配置修改

在网页界面的 **Settings** 页面可以直接修改 API Key，修改后无需重启服务即时生效。配置保存在 `data/user_config.json` 中。

---

## 4. 界面导航

网页界面（http://localhost:8080）左侧为导航侧边栏，包含以下页面：

### 4.1 Chat（对话分析）

核心交互页面。支持：
- **自然语言输入**：直接输入分析问题
- **文件拖拽上传**：支持图片、PDF、DOCX、TXT、MD 文件
- **流式输出**：文字逐 token 实时显示
- **上下文记忆**：自动关联同一会话的对话历史
- **反馈按钮**：每条回复支持点赞/点踩

支持的对话示例：
```
用户: "分析最近30天 GNSS 监测点的位移趋势"
用户: "对比 InSAR 形变场与降雨数据的相关性"
用户: "生成一份本周的水文监测报告"
用户: "帮我查一下边坡监测的相关规范条文"
```

### 4.2 NL2Query（自然语言查询）

将自然语言直接转换为 Python 分析代码并执行：
- 左侧输入自然语言查询
- 系统自动生成对应的 Python 分析代码
- 在沙箱中安全执行
- 返回分析结果、图表和数据
- 支持结果缓存加速重复查询

支持的数据类型：`gnss`、`insar`、`rainfall`、`groundwater`、`pore_pressure`

### 4.3 Charts（图表工作室）

交互式图表配置面板，支持：
- **图表类型**：时序图、散点图、热力图、剖面图
- **配色方案**：默认、专业蓝、暖色、单色红等
- **坐标轴范围**：自定义 X/Y 轴范围
- **标注**：在图表上添加文本标注
- **尺寸与导出**：可调宽高、DPI（150/200/300）
- **实时预览**：生成即看

### 4.4 Knowledge（知识库管理）

上传和管理 RAG 知识库文档：
- 支持格式：PDF、TXT、Markdown
- 自动分块 + 向量化 + 存储
- 文档列表管理（查看/删除）
- 对话中自动检索相关文档

### 4.5 Memory（长期记忆管理）

查看和管理 Agent 的长期记忆：
- **记忆统计**：按类型（偏好/知识/经验）统计数量和平均权重
- **搜索**：按关键词搜索记忆内容
- **筛选**：按记忆类型过滤
- **删除**：手动移除不需要的记忆
- **开关**：开启/关闭记忆系统

### 4.6 Settings（设置）

系统配置页面：
- **API Key 管理**：输入 DeepSeek / Kimi / OpenAI 的 Key
- **连接测试**：验证 API Key 是否可用
- **模型状态**：显示已注册的模型列表
- **反馈概览**：好评数、差评数、好评率
- **系统信息**：向量数据库路径、Embedding 模型、功能开关状态

---

## 5. 核心功能详解

### 5.1 专业数据分析

#### GNSS 位移分析

支持的分析功能：
- 时间序列分解（趋势项、周期项、噪声分离）
- 突变点检测（STL + 3-sigma 阈值）
- 位移速率估计（线性回归 + 置信区间）
- 多测站对比分析

#### InSAR 形变分析

- 形变场插值（Kriging / IDW）
- 时序累积形变计算
- 形变速率图生成
- 形变等值线提取

#### 水文数据分析

- **降雨分析**：累计降雨量、降雨强度、重现期估算
- **地下水位分析**：水位动态曲线、与降雨相关性分析、趋势分析
- **孔隙水压力分析**：孔压变化趋势、超静孔压消散分析、与水位联动

#### 多源数据关联分析

- 降雨 vs 位移 的相关性
- 水位 vs 位移 的时滞分析
- 多因子综合影响评估
- 互相关函数与交叉谱分析

### 5.2 RAG 知识检索系统

#### 工作流程

```
文档上传 -> 文本提取 -> 智能分块 -> 向量化(BGE) -> 存入ChromaDB -> 语义检索 -> 结果注入对话
```

#### 支持的文档格式

| 格式 | 解析方式 | 说明 |
|------|---------|------|
| PDF | pdfplumber | 提取文本内容 |
| TXT | UTF-8 编码 | 直接读取 |
| Markdown | UTF-8 编码 | 保留基本格式 |
| DOCX | python-docx | 提取段落文本 |

#### 检索方式

- **语义检索**：基于向量相似度（默认 Top-3）
- **关键词匹配**：文本关键词重叠度
- 两种方式混合排序

### 5.3 ReAct 推理循环

系统采用 ReAct（Reasoning + Acting）模式进行复杂问题推理：

```
步骤 1: 思考（Thought）-> 分析用户问题，决定下一步
步骤 2: 行动（Action）-> 调用工具（分析数据/搜索知识/搜索记忆/生成报告）
步骤 3: 观察（Observation）-> 获取工具执行结果
步骤 4: 循环 -> 基于观察继续思考，直至得出最终答案
```

**可用工具**：

| 工具 | 说明 |
|------|------|
| `analyze_data(query, data_type)` | 执行 NL2Query 数据分析 |
| `search_knowledge(query)` | 检索知识库 |
| `search_memory(query)` | 检索长期记忆 |
| `generate_report(report_type, data)` | 生成监测报告 |
| `final_answer(answer)` | 输出最终答案 |

### 5.4 对话流程集成

当用户在对话界面输入问题时，系统自动执行以下流程：

```
用户输入
  |
① 记忆召回 -> 从长期记忆中检索相关偏好和知识
  |
② RAG 检索 -> 从知识库搜索相关文档
  |
③ 意图检测 -> 判断是否需要分析或生成报告（自动检测数据类型）
  |
④ 集成分析 -> [可选] 执行数据分析和报告生成
  |
⑤ LLM 推理 -> 整合所有上下文，生成回答
  |
⑥ 记忆提取 -> 从本次对话中提取新的记忆并存储
  |
输出回答
```

---

## 6. REST API 参考

所有 API 端点位于 `http://localhost:8000/api/v1/`。完整的 OpenAPI 文档可在 http://localhost:8000/docs 查看。

### 6.1 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（含组件状态） |
| GET | `/metrics` | Prometheus 格式指标 |
| GET | `/api/v1/ping` | API 连通性测试 |

### 6.2 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chat/completions` | 创建对话补全（非流式） |
| POST | `/api/v1/chat/stream` | 流式对话（SSE 格式） |

**POST /api/v1/chat/completions** 请求体：
```json
{
  "session_id": "uuid-string",
  "message": "分析最近30天的GNSS位移数据",
  "model_id": "deepseek-chat",
  "attachments": [
    {"url": "/uploads/file.pdf", "filename": "data.pdf", "mime_type": "application/pdf", "size": 1024}
  ]
}
```

### 6.3 会话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/sessions/` | 获取会话列表 |
| POST | `/api/v1/sessions/` | 创建新会话 |
| GET | `/api/v1/sessions/{id}` | 获取会话详情及消息 |
| DELETE | `/api/v1/sessions/{id}` | 删除会话 |
| POST | `/api/v1/sessions/{id}/messages` | 同步消息到后端 |

### 6.4 模型管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/models/` | 获取已注册模型列表 |
| POST | `/api/v1/models/switch` | 切换当前模型 |

### 6.5 数据分析

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/analysis/execute` | 执行 NL2Query 分析 |

### 6.6 知识库

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/knowledge/upload` | 上传文档到知识库 |
| GET | `/api/v1/knowledge/documents` | 获取文档列表 |
| DELETE | `/api/v1/knowledge/documents/{id}` | 删除文档 |
| POST | `/api/v1/knowledge/search` | 检索知识库 |

### 6.7 反馈

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/feedback/collect` | 提交反馈（点赞/点踩） |
| GET | `/api/v1/feedback/stats` | 获取反馈统计 |

### 6.8 自我成长

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/self-growth/stats` | 获取自成长优化统计 |
| POST | `/api/v1/self-growth/optimize` | 触发手动优化 |
| POST | `/api/v1/self-growth/finetune` | 触发 LoRA 微调 |

### 6.9 错误响应格式

所有 API 错误返回统一格式：
```json
{
  "code": "ERROR_CODE",
  "message": "人类可读的错误描述",
  "detail": null
}
```

常见错误码：
- `NOT_FOUND` — 资源不存在
- `VALIDATION_ERROR` — 请求参数校验失败
- `MODEL_ERROR` — 模型调用失败
- `INTERNAL_ERROR` — 服务器内部错误

---

## 7. 自我成长系统

这是本系统区别于普通分析工具的核心特性。系统通过持续学习不断进化。

### 7.1 系统架构

```
用户反馈（显式+隐式）
  |
+ 反馈收集器 (FeedbackCollector) ---------------+
|  点赞/点踩 / 评分 / 文本评价 / 编辑行为 / 重复查询 |
+------------------------+----------------------+
                         |
    +--------------------+--------------------+
    |                    |                    |
记忆优化器           Prompt 优化器          LoRA 微调
(MemoryOptimizer)   (PromptOptimizer)    (FineTuner)
    |                    |                    |
记忆权重更新         APE 自动搜索          PEFT 训练
记忆合并去重        A/B 测试/版本管理      HuggingFace 管线
时效衰减         模板库管理             热部署/回滚
```

### 7.2 显式反馈

用户在对话界面可以通过以下方式提供反馈：

- **点赞/点踩**：每条助手回复下方有反馈按钮
- **评分**：1-5 分制评分
- **文本评价**：提供文字描述
- **标签**：可选的分类标签

### 7.3 隐式反馈

系统自动收集以下行为：

| 事件类型 | 说明 | 数据用途 |
|----------|------|---------|
| `message_edited` | 用户编辑了消息 | 指示原始回复质量不高 |
| `query_repeated` | 用户重复相似查询 | 指示之前的回答不满足需求 |
| `session_continued` | 长时间持续对话 | 正面信号 |
| `feature_used` | 使用了特定功能 | 功能偏好学习 |
| `copy_result` | 复制了分析结果 | 正面信号 |

### 7.4 长期记忆系统

记忆分为三种类型：

| 类型 | 说明 | 示例 |
|------|------|------|
| `preference`（偏好） | 用户的格式/风格偏好 | "用户偏好 Word 格式的报告" |
| `knowledge`（知识） | 领域知识和规范 | "用户提到 GNSS 监测精度需达到 10mm" |
| `experience`（经验） | 成功/失败的分析策略 | "使用时间序列分解+突变检测分析成功" |

**记忆管理机制**：
- **权重叠加**：相同 key 的记忆多次出现时权重叠加（上限 5.0）
- **时效衰减**：每 6 小时权重乘以 0.95，低于 0.1 自动清理
- **自动合并**：每 12 小时对相似记忆（相似度 > 0.7）进行合并
- **反馈驱动**：用户反馈可修正记忆权重

### 7.5 Prompt 自动优化

基于 APE（Automatic Prompt Engineer）方法：

- **版本管理**：每个任务类型维护多个 Prompt 版本
- **A/B 测试**：对比不同 Prompt 版本的效果
- **演化策略**：变异 + 交叉 + 选择
- **触发条件**：每 24 小时自动评估，或收集到 5 条以上新反馈后触发
- **任务分类**：analysis（分析）、retrieval（检索）、report（报告）

### 7.6 LoRA 微调

当高质量反馈数据积累到一定程度时，系统可自动触发 LoRA 微调：

- **自动触发**：20 条以上高质量反馈（评分 >= 3）
- **技术方案**：HuggingFace PEFT + LoRA
- **训练管线**：数据准备 -> 训练 -> 评估 -> 部署
- **热切换**：微调后模型可直接注册到模型池中切换使用
- **回滚支持**：保留历史 checkpoint

### 7.7 后台优化线程

系统在后台自动运行以下周期性任务：

| 任务 | 间隔 | 说明 |
|------|------|------|
| 记忆权重衰减 | 6 小时 | 权重乘以 0.95 |
| 记忆合并 | 12 小时 | 合并相似记忆 |
| Prompt 评估 | 24 小时 | 自动搜索更优 Prompt |
| 微调检查 | 30 分钟 | 判断是否触发 LoRA 微调 |

---

## 8. 代码沙箱

为保障系统安全，所有 AI 生成的代码在隔离的沙箱中执行。

### 8.1 安全机制

| 机制 | 说明 |
|------|------|
| **子进程隔离** | 使用 subprocess 在独立进程中执行 |
| **超时控制** | 默认 30 秒，可配置 |
| **内存限制** | 默认 512 MB |
| **环境净化** | 清除 PYTHONPATH、LD_PRELOAD 等危险环境变量 |
| **白名单** | 仅允许安全的科学计算库 |
| **临时目录** | 每次执行使用临时目录，执行后清理 |

### 8.2 允许的包（白名单）

```python
numpy, pandas, scipy, statsmodels, sklearn,
matplotlib, plotly, seaborn,
math, datetime, json, collections,
itertools, typing, pathlib, re,
random, statistics, decimal, fractions,
dataclasses
```

### 8.3 沙箱执行流程

```
用户查询 -> NL2Code 生成 Python 代码
  |
代码包装（Agg 后端 + stdout 捕获 + 图表自动保存）
  |
subprocess 执行（隔离环境 + 资源限制）
  |
结果解析（stdout / 图表 base64 / 数据字典）
  |
图表保存到磁盘
  |
返回给前端展示
```

### 8.4 执行结果格式

```python
class SandboxResult:
    success: bool          # 是否成功
    stdout: str            # 标准输出
    stderr: str            # 错误信息
    figures: list[dict]    # 图表列表（含 base64 编码）
    data: dict             # 结构化数据
    execution_time_ms: float  # 执行时间（毫秒）
```

---

## 9. 报告生成

### 9.1 支持的格式

| 格式 | 引擎 | 特点 |
|------|------|------|
| HTML | Jinja2 模板 | 交互式图表，浏览器直接打开 |
| DOCX | python-docx | 专业排版，适合提交 |
| PDF | fpdf2 / weasyprint | 正式文档格式 |

### 9.2 报告模板

| 模板 | 适用场景 |
|------|---------|
| `daily` | 日报 -- 当日监测数据摘要 |
| `weekly` | 周报 -- 本周趋势分析与异常汇总 |
| `monthly` | 月报 -- 月度综合分析与统计 |
| `special` | 专题报告 -- 特定问题的深度分析 |
| `default` | 通用报告模板 |

### 9.3 报告数据结构

```python
{
    "title": "2026年6月 GNSS 位移监测月报",
    "date": "2026-07-01",
    "report_type": "monthly",
    "summary": "本月各监测点位移量均在安全范围内...",
    "sections": [
        {
            "title": "GNSS 位移分析",
            "content": "对 12 个监测点的数据分析显示...",
            "charts": ["<plotly-chart-html>", ...],
            "tables": [
                {"headers": ["测站", "X(mm)", "Y(mm)", "Z(mm)"],
                 "rows": [["GNSS01", 2.3, 1.8, 0.5], ...]}
            ]
        }
    ],
    "conclusion": "总体形变趋势稳定，建议关注 GNSS03 测站..."
}
```

### 9.4 图表引擎

系统内置两套图表引擎：

| 引擎 | 用途 | 特点 |
|------|------|------|
| Plotly | 网页交互 | 缩放、悬停、动态筛选 |
| Matplotlib | 纸张出版 | 300 DPI、专业排版、导出 PNG |

图表类型支持：
- 时序图（Timeseries）
- 散点图（Scatter，含趋势线）
- 热力图（Heatmap）
- 剖面图（Profile）

---

## 10. Docker 部署

### 10.1 构建和启动

```bash
# 1. 构建镜像
docker compose build

# 2. 启动服务
docker compose up -d

# 3. 查看日志
docker compose logs -f

# 4. 停止服务
docker compose down
```

### 10.2 服务端口

| 端口 | 服务 | 说明 |
|------|------|------|
| 8000 | FastAPI 后端 | REST API + 文档 |
| 8080 | NiceGUI 前端 | 网页界面 |

### 10.3 数据持久化

Docker Compose 使用命名卷进行数据持久化：

| 卷 | 挂载路径 | 存储内容 |
|----|---------|---------|
| `research_data` | /app/data | 数据库、向量库、日志 |
| `research_reports` | /app/reports | 生成的报告 |
| `research_model_cache` | /app/model_cache | 模型缓存 |

### 10.4 环境变量

通过 `.env` 文件传递配置，Docker 会自动加载：

```yaml
environment:
  - APP_ENV=production
  - APP_DEBUG=false
```

---

## 11. 桌面应用打包

### 11.1 构建 exe

```powershell
.venv\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
```

构建产物位于 `dist\ResearchAgent\ResearchAgent.exe`。

### 11.2 运行桌面应用

1. 双击 `ResearchAgent.exe`
2. 自动启动内置后端服务
3. 浏览器自动打开 http://localhost:8080
4. 前往 **Settings** 页面配置 API Key
5. 返回 Chat 页面开始使用

> **注意**：exe 是单进程应用，无需单独启动 FastAPI 后端。
> API Key 保存在 `data/user_config.json` 中，重启后持久生效。

### 11.3 日志文件

应用日志存储在 `data/logs/` 目录：
- `chat_YYYYMMDD.log` -- 对话日志
- `usage.log` -- 功能使用追踪
- `error.log` -- 错误日志

---

## 12. 常见问题与故障排除

### 12.1 启动问题

**Q: 启动后网页无法访问**

确认步骤：
1. 终端是否显示 `Uvicorn running on http://0.0.0.0:8000`
2. 检查端口是否被占用：`netstat -ano | findstr :8000`
3. 防火墙是否阻止了端口
4. 尝试用 `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` 启动

**Q: "No module named 'backend'" 错误**

```powershell
# 确保在项目根目录执行
cd research-agent
# 确保虚拟环境已激活
.venv\Scripts\Activate.ps1
# 安装开发模式
pip install -e .
```

### 12.2 API Key 问题

**Q: "No AI model available" 错误**

1. 检查 `.env` 中是否已填入 API Key
2. 确认 API Key 格式正确（通常是 `sk-` 开头）
3. 在 Settings 页面点击 **Test Connection** 验证
4. 检查 API 余额：https://platform.deepseek.com/usage

**Q: 模型调用超时**

1. 检查网络连接（可能需要代理）
2. 确保网络稳定
3. 沙箱超时在 `.env` 中配置：`SANDBOX_TIMEOUT=60`

### 12.3 数据分析问题

**Q: 分析结果显示空白**

1. 检查数据文件是否成功上传
2. 确认数据格式是否被支持（CSV / Excel / GeoJSON / HDF5）
3. 查看后端日志 `data/logs/research_agent.log`
4. 尝试在 NL2Query 页面直接执行查看详细错误

**Q: 生成的图表不显示**

1. 确认 Matplotlib Agg 后端已设置（默认已配置）
2. 检查临时目录写入权限
3. 尝试在 Chart Studio 页面生成预览

### 12.4 知识库问题

**Q: 上传文档后对话中没有引用**

1. 确认文档上传成功（页面显示 "上传成功"）
2. 检查文档内容是否为可提取文本（扫描 PDF 需要 OCR）
3. 询问的问题是否与文档内容相关
4. 在 Knowledge 页面点击 **刷新列表** 确认文档存在

**Q: 检索结果不准确**

1. 默认使用 BAAI/bge-small-zh-v1.5 嵌入模型
2. 文档长度过长时会被截断，考虑分段上传
3. 语义检索依赖文档质量，确保文档内容清晰

### 12.5 性能问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 对话响应慢 | 模型 API 延迟 | 切换到 DeepSeek（延迟较低） |
| 分析执行慢 | 数据量过大 | 沙箱内限制 512MB 内存、30 秒超时 |
| 报告生成慢 | 图表过多 | 减少图表数量或降低 DPI |
| 前端卡顿 | 消息历史过多 | 创建新会话 |

### 12.6 其他注意事项

| 注意点 | 说明 |
|--------|------|
| 开发模式下数据库 | 默认使用 SQLite，文件位于 `data/research_agent.db` |
| 向量数据库重置 | 删除 `data/chroma_db` 目录可重置知识库 |
| 记忆系统重置 | 删除 `data/memories.db` 可清空所有记忆 |
| 日志轮转 | 日志按天分割在 `data/logs/` 目录 |
| 并发执行 | 每个用户在独立的数据文件中维护状态 |
| GPU 需求 | 仅 LoRA 微调需要 GPU，日常使用不需要 |

---

## 13. 项目结构速览

```
research-agent/
+-- backend/                       # FastAPI 后端
|   +-- main.py                    # 应用入口、路由、中间件
|   +-- config.py                  # pydantic-settings 配置
|   +-- uploads.py                 # 文件上传与文本提取
|   +-- api/                       # REST API 路由
|   |   +-- chat.py                #   对话接口
|   |   +-- models.py              #   模型管理
|   |   +-- sessions.py            #   会话 CRUD
|   |   +-- analysis.py            #   数据分析执行
|   |   +-- knowledge.py           #   知识库管理
|   |   +-- feedback.py            #   反馈收集
|   |   +-- self_growth.py         #   自成长状态
|   +-- core/                      # 核心引擎
|   |   +-- agent.py               #   ResearchAgent 协调器
|   |   +-- memory.py              #   长期记忆存储
|   |   +-- strategy.py            #   策略库
|   |   +-- sandbox.py             #   代码沙箱
|   |   +-- exceptions.py          #   异常定义
|   +-- models/                    # AI 模型适配层
|   |   +-- base.py                #   BaseLLM / BaseEmbedding 接口
|   |   +-- registry.py            #   模型注册表
|   |   +-- lora_adapter.py        #   LoRA 适配器
|   |   +-- adapters/              #   具体适配器
|   +-- analysis/                  # 专业数据分析
|   |   +-- gnss.py                #   GNSS 位移分析
|   |   +-- insar.py               #   InSAR 形变分析
|   |   +-- rainfall.py            #   降雨分析
|   |   +-- groundwater.py         #   地下水位分析
|   |   +-- pore_pressure.py       #   孔隙水压力分析
|   |   +-- cross_correlation.py   #   多源关联分析
|   |   +-- parser.py              #   数据解析
|   |   +-- codegen.py             #   NL-to-Python 代码生成
|   |   +-- cache.py               #   查询缓存
|   +-- retrieval/                 # 知识检索
|   +-- reporting/                 # 报告生成
|   +-- self_growth/               # 自我成长
|   +-- schemas/                   # Pydantic 模型
|   +-- db/                        # 数据库
+-- frontend/                      # NiceGUI 前端
|   +-- app.py                     # 完整的 Web 界面
+-- tests/                         # 测试
+-- scripts/                       # 开发与部署脚本
+-- data/                          # 运行时数据
+-- docs/                          # 文档
+-- .env                           # 环境配置
+-- docker-compose.yml             # Docker 编排
+-- Makefile                       # 快捷命令
+-- pyproject.toml                 # 项目元数据
```

---

> *Research Agent v0.1.0 -- 让数据分析 Agent 在每一次交互中变得更好*
