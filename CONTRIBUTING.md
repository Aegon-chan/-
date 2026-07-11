# Research Agent — 开发贡献指南

## Git 分支策略

项目采用 **Git Flow** 简化版分支模型：

```
main ──┬────────────────── merge ──► release
        │                      ▲
  develop ──┬──────── merge ───┘
            │               ▲
    feature/* ───── PR ────┘
```

### 分支类型

| 分支 | 用途 | 基础分支 | 合并目标 | 保护规则 |
|------|------|---------|---------|---------|
| `main` | 生产就绪代码 | — | — | 需 PR 审查 + CI 通过，禁止直接推送 |
| `develop` | 功能集成分支 | `main` | `main` | 需 CI 通过 |
| `codex/*` | 功能/特性分支 | `develop` | `develop` | 无限制，鼓励频繁推送 |
| `fix/*` | 紧急修复分支 | `main` | `main` + `develop` | 需 PR 审查 |

### 开发流程

1. **从 `develop` 创建功能分支**：
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b codex/your-feature-name
   ```

2. **在功能分支上工作并提交**：
   - 保持提交粒度合理，每个提交完成一个逻辑变更
   - 提交信息格式：`type: description`（如 `feat: add GNSS time series decomposition`）
   - 类型前缀：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`

3. **推送并创建 Pull Request**：
   ```bash
   git push origin codex/your-feature-name
   ```
   然后在 GitHub 上创建 PR → `develop`，等待 CI 通过。

4. **合并到 `develop`**：
   - 由另一位开发者审查后合并（Squash merge 或普通 merge）
   - 合并后删除远程功能分支

5. **发布到 `main`**：
   - 从 `develop` 创建 PR → `main`
   - 通过审查和 CI 后合并
   - 在 `main` 上打版本 tag：`git tag v0.2.0`

## 代码规范

- **Python**: 遵循 PEP 8，行长度 100 字符
- **类型注解**: 所有函数必须包含类型注解
- **导入顺序**: 标准库 → 第三方 → 本地（每组空行分隔）
- **文档字符串**: 使用三重引号 `"""doc"""`，复杂模块需写模块文档

## 环境配置

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/Mac
pip install -e ".[dev,analysis,visualization,ai,retrieval,reporting,frontend]"
```

## 测试

```bash
# 运行全部单元测试
pytest tests/unit/ -v

# 带覆盖率
pytest tests/unit/ --cov=backend -v

# 运行集成测试（需要数据库和运行中的服务）
pytest tests/integration/ -v

# 代码检查
ruff check backend/
```

> 提 PR 前请确保 `pytest tests/unit/ --tb=short -q` 全部通过。
