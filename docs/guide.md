# Research Agent User Guide

## Overview

Research Agent is an AI data analysis assistant for geological
deformation monitoring (GNSS/InSAR) and hydrological monitoring,
with self-growth capabilities through user feedback.

## Quick Start

### 1. Environment Setup

```bash
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

# Activate virtual environment
.venv\Scripts\Activate.ps1
```

### 2. Configure API Key

Edit `.env` and set at least one API key:

| Model | Variable | Get it at |
|-------|----------|-----------|
| DeepSeek | DEEPSEEK_API_KEY | https://platform.deepseek.com |
| KIMI | KIMI_API_KEY | https://kimi.moonshot.cn |
| OpenAI | OPENAI_API_KEY | https://platform.openai.com |

### 3. Start Server

```bash
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

Then open:
- Web UI: http://localhost:8080
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Features

### Conversational Analysis

Type natural language questions in the chat box. The Agent will:

1. **Search Knowledge** -- Find relevant info from uploaded documents
2. **Analyze Data** -- Generate and execute Python code in sandbox
3. **Generate Reports** -- Output professional reports with charts
4. **Recall Memory** -- Reference user preferences and history

### Knowledge Management

1. Go to "Knowledge Base" page in Web UI
2. Upload PDF/TXT/Markdown documents
3. System auto-chunks and vectorizes them
4. Agent retrieves relevant docs during conversations

### Feedback & Self-Growth

- **Explicit Feedback**: Like/dislike each response, add comments
- **Implicit Feedback**: System tracks edits, repeated queries, etc.
- **Memory Optimization**: Remembers preferences and domain knowledge
- **Prompt Optimization**: Auto-searches better prompts by task results
- **Model Fine-Tuning**: LoRA fine-tuning from accumulated feedback

### Report Generation

Four report types: daily, weekly, monthly, special.
Output formats: HTML, PDF, DOCX.

## Advanced Configuration

### Feature Flags (in .env)

```
FEATURE_SELF_GROWTH=true   # Enable self-growth system
FEATURE_FEEDBACK=true      # Enable feedback collection
FEATURE_FINETUNE=false     # Enable model fine-tuning (needs GPU)
FEATURE_REALTIME_REPORTS=true
```

### Docker Deployment

```bash
docker compose build
docker compose up -d
```
