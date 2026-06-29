# Research Agent 贡献指南

## 分支策略

| 分支 | 来源 | 用途 |
|------|------|------|
| main | — | 生产就绪代码，仅通过 PR 合并 |
| develop | main | 日常开发集成分支 |
| feature/* | develop | 新功能分支 |
| fix/* | develop | Bug 修复分支 |
| docs/* | develop | 文档更新 |

## 开发流程

1. 从 develop 创建功能分支：
   git checkout develop
   git checkout -b feature/your-feature-name
2. 开发和测试
3. 提交前确保通过检查和测试：
   ruff check backend/ tests/
   pytest tests/ -v
4. 提交到远程并创建 Pull Request
5. PR 合并到 develop（Code Review + CI 通过后）
6. 稳定版本从 develop 合并到 main

## 数据库迁移

alembic revision --autogenerate -m "描述变更"
alembic upgrade head

## 代码规范

- 遵循 PEP 8，行宽 100 字符
- 使用 ruff check 进行格式检查
- 提交前运行 pytest tests/ -v
- 新功能需包含对应的单元测试
