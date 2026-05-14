# OpenTCM 增强版 - Code Wiki

本 Wiki 面向“读代码/改代码/部署运行”的场景，对仓库的整体架构、主要模块职责、关键类与函数、依赖关系与运行方式做结构化说明。

## 快速导航

- [01_Architecture.md](./01_Architecture.md)：整体架构与请求/数据流
- [02_Modules.md](./02_Modules.md)：主要模块职责与内部依赖
- [03_API_And_Frontend.md](./03_API_And_Frontend.md)：Web 路由、SSE 协议与前端交互
- [04_Data_Pipeline.md](./04_Data_Pipeline.md)：离线知识图谱构建流程与数据规范
- [05_Runtime.md](./05_Runtime.md)：本地运行、开发调试、常见问题
- [06_Dependencies.md](./06_Dependencies.md)：外部依赖、环境变量与安全注意事项

## 仓库概览

- 形态：Python 单体应用（Flask）+ 本地知识图谱（CSV → NetworkX）+ 远程 LLM API（Moonshot/Kimi 等）+ HTML/CSS/原生 JS 前端
- 核心入口：后端 [app.py](file:///workspace/app.py)，增强版问答/编排 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py)，智能辨证 [smart_diagnosis.py](file:///workspace/smart_diagnosis.py)，图谱构建脚本 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py)
- 运行端口：默认 8000（见 [app.py](file:///workspace/app.py#L220-L222)）

