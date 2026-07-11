# Research Agent 项目介绍 - Design Spec

## I. 项目信息

| 项目 | 值 |
| ---- | --- |
| **项目名称** | research-agent-intro |
| **画布格式** | PPT 16:9 (1280x720) |
| **页面数量** | 12 |
| **设计风格** | 通用咨询风 + 信息型科技感 |
| **目标受众** | 技术管理者、研究员、团队成员、合作方 |
| **使用场景** | 项目介绍 / 内部分享 / 立项汇报 |
| **创建日期** | 2026-07-05 |

## II. 画布规格

| 属性 | 值 |
| ----- | --- |
| **格式** | PPT 16:9 |
| **尺寸** | 1280x720 |
| **viewBox** | 0 0 1280 720 |
| **安全边距** | 左/右 60px, 上/下 50px |

## III. 视觉主题

### 主题风格
- **风格**: 信息型科技感 (Information-dense + Tech)
- **主题**: 浅色主题
- **调性**: 专业、现代、创新、科技

### 配色方案

| 角色 | HEX | 用途 |
| ---- | --- | ------- |
| **背景** | #FFFFFF | 页面底色 |
| **次要背景** | #F5F7FA | 卡片/区块背景 |
| **主色** | #1565C0 | 标题装饰、关键区域、图标主色 |
| **强调色** | #00BFA5 | 数据亮点、进阶能力、成长标记 |
| **辅助强调色** | #7C4DFF | 次要强调、渐变过渡 |
| **正文色** | #1E293B | 主要文字 |
| **次要文字** | #64748B | 标注、说明文字 |
| **边框/分割线** | #E2E8F0 | 卡片边框、分割线 |
| **成功色** | #10B981 | 正面指标 |
| **警告色** | #EF4444 | 问题标记 |

### AI 图片渲染策略
- 图片渲染风格: vector-illustration
- 图片调色板: cool-corporate

## IV. 字体系统

### 字体方案
**字体方向**: 现代 CJK 无衬线 + 拉丁无衬线 (科技专业感)

| 角色 | 中文 | 英文 | 回退 |
| ---- | ------- | ------- | ------------- |
| **标题** | Microsoft YaHei, PingFang SC | Arial | sans-serif |
| **正文** | Microsoft YaHei, PingFang SC | Arial | sans-serif |
| **强调** | Microsoft YaHei | Arial | sans-serif |
| **代码** | Microsoft YaHei | Consolas, Courier New | monospace |

**各角色字体栈**:
- 标题: Arial, "Microsoft YaHei", "PingFang SC", sans-serif
- 正文: "Microsoft YaHei", "PingFang SC", Arial, sans-serif
- 强调: Arial, "Microsoft YaHei", sans-serif
- 代码: Consolas, "Courier New", "Microsoft YaHei", monospace

### 字号层级
**基准**: 正文基准字号 = 20px (中等密度)

| 用途 | 比例 | 值 | 字重 |
| ------- | ---- | ------ | ------ |
| 封面标题 | 3-4x | 60-80px | Bold |
| 章节/区隔标题 | 2-2.5x | 40-50px | Bold |
| 页面标题 | 1.5-2x | 30-40px | Bold |
| 副标题 | 1.2-1.4x | 24-28px | SemiBold |
| **正文** | **1x** | **20px** | Regular |
| 标注/说明 | 0.7-0.85x | 14-17px | Regular |
| 页码/页脚 | 0.5-0.6x | 10-12px | Regular |

## V. 布局原则

### 页面结构
- **页头区域**: 高 60px, 含页面标题、装饰线
- **内容区域**: 高 560px (含间距)
- **页脚区域**: 高 40px, 含页码、项目名称

### 间距规范
- 画布安全边距: 60px
- 内容块间距: 28px
- 图标-文字间距: 10px
- 卡片间距: 24px
- 卡片内边距: 24px
- 卡片圆角: 12px
- 三列卡片宽度: 350px

## VI. 图标使用规范

### 来源
- **内置图标库**: tabler-outline
- **描边宽度**: 2

### 图标清单

| 用途 | 图标路径 | 页面 |
| ------- | --------- | ---- |
| AI/智能 | tabler-outline/brain | P01, P03, P08 |
| 智能体 | tabler-outline/robot | P02, P03 |
| 计算引擎 | tabler-outline/cpu | P03, P04 |
| 数据库 | tabler-outline/database | P04, P06 |
| 数据分析 | tabler-outline/chart-bar | P05, P07 |
| 报告 | tabler-outline/file-report | P07 |
| 搜索 | tabler-outline/search | P06 |
| AI 设置 | tabler-outline/settings-ai | P08 |
| 层次架构 | tabler-outline/layers-union | P04 |
| 代码 | tabler-outline/code | P09 |
| 安全 | tabler-outline/shield | P09 |
| 目标 | tabler-outline/target | P11 |
| 里程碑 | tabler-outline/flag-3 | P10 |
| 分支路线 | tabler-outline/git-branch | P10 |
| 想法 | tabler-outline/bulb | P02, P11 |
| 对话 | tabler-outline/message-2 | P03 |
| 迭代 | tabler-outline/arrow-iteration | P08 |
| 自动化 | tabler-outline/settings-automation | P08 |
| 技术栈 | tabler-outline/stack-3 | P04 |
| 集成 | tabler-outline/puzzle | P11 |
| 数据 | tabler-outline/clipboard-data | P05 |
| 网络 | tabler-outline/network | P04 |
| 完成 | tabler-outline/circle-check | P11 |
| 亮点 | tabler-outline/star | P11 |
| 成长 | tabler-outline/trending-up | P08 |
| 文档 | tabler-outline/file-text | P06 |

## VII. 图片资源列表

| 文件名 | 尺寸 | 比例 | 用途 | 类型 | 获取方式 | 状态 |
| -------- | --------- | ---- | ------- | ---- | ----------- | ------ |
| cover_bg.jpg | 1280x720 | 16:9 | 封面背景: 科技感抽象图 | Background | ai | Pending |
| architecture.png | 800x600 | 4:3 | 系统四层架构示意图 | Diagram | ai | Pending |
| roadmap.png | 900x500 | 16:9 | 四阶段时间线路线图 | Diagram | ai | Pending |

## VIII. 内容大纲

### P01 - 封面
- **布局**: 全屏背景 + 居中标题
- **标题**: Research Agent
- **副标题**: 自我成长型科研数据分析助手
- **信息**: 2026.07 | v0.1.0

### P02 - 项目定位与背景
- **布局**: 不对称分割 (3:7)
- **标题**: 项目定位
- **核心信息**: 面向地质变形/水文监测的 AI 数据分析平台
- **内容**: 背景痛点 -> 解决方案 -> 目标用户

### P03 - 核心能力全景
- **布局**: 三列卡片网格 (2行)
- **标题**: 核心能力全景
- **核心信息**: 七大核心能力覆盖从数据接入到智能决策的全链路
- **内容**: Multi-model LLM, Domain Analysis, RAG, Auto Reporting, Self-Growth, ReAct, Code Sandbox

### P04 - 系统技术架构
- **布局**: 分层架构图
- **标题**: 系统架构
- **核心信息**: 四层松耦合架构, 各层职责清晰
- **内容**: Client -> API -> Core Engine -> Services -> Data Storage

### P05 - 专业数据分析引擎
- **布局**: 不对称分割 + 图标列表
- **标题**: 专业数据分析
- **核心信息**: 面向地质监测领域的全方位分析能力
- **内容**: GNSS, InSAR, 降雨, 地下水位, 孔隙水压力

### P06 - RAG 知识检索系统
- **布局**: 不对称分割
- **标题**: RAG 知识检索
- **核心信息**: 基于 ChromaDB + BGE 的专业知识库
- **内容**: 语义检索, 向量存储, 知识类型, 处理流程

### P07 - 自动化报告生成
- **布局**: 三列卡片
- **标题**: 自动报告生成
- **核心信息**: 一键生成多格式专业监测报告
- **内容**: 多格式输出, 图表引擎, 模板系统, 一键闭环

### P08 - 自我成长体系
- **布局**: 中心辐射式
- **标题**: 自我成长体系
- **核心信息**: 每一次使用都在让 Agent 变得更好 -- 核心差异化能力
- **内容**: 记忆网络, 反馈系统, APE Prompt优化, LoRA微调

### P09 - ReAct 推理与代码沙箱
- **布局**: 左右分割
- **标题**: 智能推理 & 沙箱执行
- **核心信息**: Think-Act-Observe 推理循环 + 沙箱隔离
- **内容**: ReAct循环, 工具集, 代码沙箱, NL2Code

### P10 - 项目路线图
- **布局**: 全幅时间线
- **标题**: 项目路线图
- **核心信息**: 四阶段渐进式开发
- **内容**: Phase 1 骨架搭建 -> Phase 2 专业能力 -> Phase 3 自我成长 -> Phase 4 App封装

### P11 - 技术亮点总结
- **布局**: 2x2 矩阵网格
- **标题**: 技术亮点
- **核心信息**: 架构先进, 自我进化, 安全可靠, 开箱即用
- **内容**: 四大亮点象限

### P12 - 感谢页
- **布局**: 单栏居中
- **标题**: 感谢
- **副标题**: Thank You
- **内容**: Research Agent Team | 2026

## IX. 演讲备注要求

每页对应一个备注文件, 保存到 notes/: 与 SVG 名称对应 (如 01_cover.md)

## X. 技术约束提醒

1. viewBox: 0 0 1280 720
2. 背景使用 rect 元素
3. 文本换行使用 tspan (foreignObject 禁止)
4. 透明度使用 fill-opacity / stroke-opacity
5. 禁止: mask, style, class, foreignObject, textPath, animate*, script
6. g opacity 禁止; 在每个子元素上单独设置
7. 图片透明度使用叠加遮罩层
8. 仅使用内联样式