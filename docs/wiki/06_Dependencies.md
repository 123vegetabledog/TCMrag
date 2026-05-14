# 06 - 依赖、配置与安全

## 6.1 Python 依赖

依赖清单来自 [requirements.txt](file:///workspace/requirements.txt)。

- `Flask`：Web 服务与路由（见 [app.py](file:///workspace/app.py#L3-L4)）
- `Flask-CORS`：跨域（见 [app.py](file:///workspace/app.py#L4-L4)）
- `python-dotenv`：从 `.env` 加载环境变量（见 [app.py](file:///workspace/app.py#L5-L10)）
- `requests`：HTTP 调用（在增强版 GraphRAG 中引入，见 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L12-L13)）
- `networkx`：知识图谱内存结构（见 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L10-L10)、[smart_diagnosis.py](file:///workspace/smart_diagnosis.py#L11-L11)）
- `pandas` / `numpy`：CSV 读取与基础处理（见 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L8-L9)、[smart_diagnosis.py](file:///workspace/smart_diagnosis.py#L9-L10)）
- `matplotlib`：图形相关（当前主要为潜在分析/调试用途，见 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L18-L18)）
- `tqdm`：构建图谱时进度条（见 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L19-L19)、[enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L74-L74)）

额外注意：

- 代码中直接使用 `openai` SDK（`from openai import OpenAI`），但未写入 requirements（见 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L395-L400) 等）；如果你的环境中没有该包，需要手动安装。

## 6.2 外部服务依赖（LLM API）

系统通过 OpenAI 兼容接口调用第三方 LLM：

- Moonshot/Kimi（默认）：`https://api.moonshot.cn/v1`（见 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L27-L35)）
- DeepSeek、GLM：代码中有预留配置（见 [smart_diagnosis.py](file:///workspace/smart_diagnosis.py#L21-L33)，[enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L18-L30)）

## 6.3 配置项与默认值

- `TCM_CSV_PATH`
  - 默认：`tcm_enhanced_KG.csv`（增强版）或 `tcm_KG.csv`（原版）
  - 使用处：[app.py](file:///workspace/app.py#L48-L55)
- `MOONSHOT_API_KEY`
  - 使用处：Web 服务初始化与 LLM 调用（见 [app.py](file:///workspace/app.py#L57-L61)，[enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L26-L35)）
- 构建脚本节流：
  - `API_CALL_DELAY` 默认 25 秒
  - `RETRY_DELAY` 默认 15 秒
  - 使用处：[enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L38-L40)

## 6.4 安全注意事项（重要）

- 不要在 Wiki、日志、issue 或截图中粘贴真实 API Key。
- 建议把 `.env` 加入 `.gitignore`，并使用 `.env.example`（只保留变量名，不含真实值）用于分发配置模板。

