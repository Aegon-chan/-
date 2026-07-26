# Vue 3 前端重构工作量评估

> 日期：2026-07-23  
> 项目：Research Agent（自我成长型科研数据分析助手）  
> 当前前端技术栈：NiceGUI（Python，~2152 行，8 个页面）  
> 目标技术栈：Vue 3 + TypeScript + Vite + Pinia + Element Plus + ECharts + CodeMirror

---

## 一、项目范围

### 后端 API（FastAPI，约 20+ 端点）

| 路由前缀 | 模块 | 端点数 |
|---------|------|--------|
| /api/v1/chat/ | 对话（含 SSE 流式） | 2 |
| /api/v1/sessions/ | 会话 CRUD | 6 |
| /api/v1/models/ | 模型列表/详情 | 2 |
| /api/v1/analysis/ | 数据分析 + NL2Query | 8 |
| /api/v1/knowledge/ | 知识库文档管理 + 语义搜索 | 4 |
| /api/v1/feedback/ | 反馈收集与统计 | 5 |
| /api/v1/self-growth/ | 自成长状态与微调 | 3 |
| /api/v1/config/ | API Key 加密管理 | 2 |
| /api/v1/db/ | 数据库管理（表浏览、SQL、导入） | 9 |
| /api/v1/upload/ | 文件上传 | 若干 |
| /api/v1/monitoring/ | 监测站点与数据 | 12+ |
| /api/v1/mobile/ | 移动端 API | 若干 |

### 当前前端页面（NiceGUI）

| 页面 | 路由 | 行数 | 核心功能 |
|------|------|------|---------|
| 对话 | / | ~1531 | SSE 流式聊天、文件/图片上传、拖拽上传、会话管理、反馈按钮 |
| NL2Query | /nl2query | ~1138 | 自然语言→Python 代码生成与执行、数据文件选择预览、缓存浏览 |
| 图表工作室 | /chart-studio | ~990 | 图表配置面板、多类型图表预览、数据源选择、导出 |
| 知识库 | /knowledge | ~826 | 文档上传（PDF/TXT/MD）、语义搜索、文档管理 |
| 设置 | /settings | ~758 | API Key 加密配置、模型选择、主题切换 |
| 记忆 | /memories | ~640 | 记忆列表浏览、搜索过滤、删除 |
| 数据库管理 | /database | ~524 | 表结构浏览、SQL 查询编辑器、数据导入导出、分页 |
| 数据导入 | /data-import | ~216 | 文件上传、类型选择、导入预览与确认 |

---

## 二、工作量明细

### 2.1 共享基础设施（约 3 人天）

| 任务 | 说明 | 估时（天） |
|------|------|-----------|
| 项目脚手架 | Vite + Vue 3 + TypeScript + ESLint + Prettier 初始化 | 0.5 |
| Router 配置 | 8 条路由 + 布局嵌套 + 导航守卫 | 0.5 |
| HTTP 客户端 | Axios 封装 + 拦截器 + SSE 流式客户端封装 | 0.5 |
| TypeScript 类型定义 | 全部 API DTO（建议用 openapi-typescript 自动生成） | 1 |
| Pinia Store | sessions、models、knowledge、memories、settings、feedback 等 | 0.5 |

### 2.2 功能模块（约 13.5-18 人天）

| 模块 | 核心复杂度 | 估时（天） | 关键挑战 |
|------|-----------|-----------|---------|
| 布局与共享组件 | 中 | 2 | 响应式侧边栏（会话列表+导航）、模型选择器、暗色模式、通用上传组件 |
| 对话页 | 高 | 3-4 | SSE 流式渲染、Markdown 渲染+数学公式+代码高亮、拖拽上传进度、图片下载 |
| NL2Query | 高 | 2-3 | CodeMirror 6 集成、三分栏（输入→代码→结果）、数据文件选择预览、缓存管理 |
| 图表工作室 | 高 | 2-3 | ECharts 配置表单+实时预览双向绑定、导出 |
| 知识库 | 中 | 1.5 | 文档列表、上传进度、语义搜索交互 |
| 设置 | 低 | 1 | API Key 加密表单、模型配置、主题选择 |
| 记忆 | 低 | 1 | 列表搜索/过滤、详情查看、删除确认 |
| 数据库管理 | 高 | 2-3 | 表浏览器分页、SQL 编辑器语法高亮、数据导入预览→确认、跨库切换 |
| 数据导入 | 低 | 0.5 | 文件上传+类型选择+导入预览 |

### 2.3 测试与打磨（约 4-6 人天）

| 任务 | 估时（天） |
|------|-----------|
| 单元测试（Vitest） + e2e 测试（Playwright） | 2-3 |
| 边界情况、加载态、错误处理、响应式适配 | 2-3 |

---

## 三、总计

| 方案 | 人力 | 工期 |
|------|------|------|
| 单人全量 | 1 人 | 22-30 人天（约 4-6 周） |
| 双人并行 | 2 人 | 2-3 周 |
| MVP 优先（先上线对话+NL2Query） | 1 人 | 第 1 周对话页，第 2 周 NL2Query+设置+知识库 |

---

## 四、关键技术风险

1. **SSE 流式对话**：需要 EventSource / fetch ReadableStream 解析，处理断线重连、中止请求、逐词渲染。目前最复杂的部分。
2. **代码编辑器**：NL2Query 和 Database 页需要 CodeMirror 6 或 Monaco Editor，涉及 Web Worker 加载和主题定制。
3. **Markdown 渲染管线**：KaTeX（数学公式）+ Shiki/Prism（代码高亮）+ 自定义图片插件（加下载按钮）。
4. **ECharts 配置表单**：将 ECharts 复杂配置对象映射为可视化表单，双向绑定+实时预览。
5. **动态表结构渲染**：Database 页需要根据后端返回的动态列信息渲染不固定列数的表格。
6. **离线会话逻辑**：当前 NiceGUI 前端有本地消息持久化逻辑，需决定重写为浏览器端存储（IndexedDB）还是纯 API 驱动。

---

## 五、建议

- 后端已有完整的 FastAPI 路由和 Pydantic Schema，建议先导出 OpenAPI 文档，用 openapi-typescript 自动生成 TS 类型，节省 0.5-1 天。
- 组件库建议选择 Element Plus（与当前 NiceGUI 的 Material Design 风格接近）或 Naive UI（TypeScript 友好）。
- 如果团队人力允许，推荐双人并行：一人攻坚对话页（最核心），另一人处理其余模块。
