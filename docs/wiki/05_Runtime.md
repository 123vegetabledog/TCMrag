# 05 - 运行方式与开发流程

## 5.1 环境准备

- Python：建议 3.10+（仓库内未固定版本，可按依赖自行选择）
- 安装依赖：

```bash
pip install -r requirements.txt
```

说明：

- 代码中使用了 OpenAI 兼容 SDK：`from openai import OpenAI`（见 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L395-L400)、[smart_diagnosis.py](file:///workspace/smart_diagnosis.py#L16-L18)、[enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L11-L12)），但 `requirements.txt` 未显式列出 `openai`；若运行报 `ModuleNotFoundError: openai`，需额外安装：

```bash
pip install openai
```

## 5.2 环境变量（.env）

后端依赖以下环境变量（默认通过 `python-dotenv` 从 `.env` 加载，见 [app.py](file:///workspace/app.py#L10-L10) 与 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L23-L23)）：

- `MOONSHOT_API_KEY`：必需；未配置会导致 LLM 调用失败（见 [app.py](file:///workspace/app.py#L57-L61)）
- `TCM_CSV_PATH`：可选；默认 `tcm_enhanced_KG.csv`（见 [app.py](file:///workspace/app.py#L50-L55)）
- 可选（在构建脚本中使用）：`API_CALL_DELAY`、`RETRY_DELAY`（见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L38-L40)）

建议做法：

- 使用 `.env.example`（若你后续要加入）或手动创建 `.env`
- 不要把真实密钥提交到仓库

## 5.3 构建增强版知识图谱（可选但推荐）

1. 准备数据：
   - 经典医籍放入 `data/src/classicals/*.txt`（README 有说明，见 [README.md](file:///workspace/README.md#L82-L90)）
   - 临床数据放入 `data/medical_case/*.txt`（仓库已自带部分样例）
2. 运行构建脚本：

```bash
python data/enhanced_TCMKG.py
```

成功后会生成/更新：

- `tcm_enhanced_KG.csv`
- `processing_status_enhanced_KG.json`

## 5.4 启动 Web 服务

```bash
python app.py
```

- 默认监听：`0.0.0.0:8000`（见 [app.py](file:///workspace/app.py#L220-L222)）
- 访问：
  - `http://localhost:8000/`（欢迎页）
  - `http://localhost:8000/chat_page`（对话页）

## 5.5 本地快速自测（不通过 Web）

增强版模块内置一个测试入口（会尝试读取 `tcm_enhanced_KG.csv` 并走一遍 `process_query`）：

```bash
python enhanced_GraphRAG.py
```

实现见 [test_enhanced_system](file:///workspace/enhanced_GraphRAG.py#L585-L613)。

## 5.6 常见问题排查

- 启动时提示 CSV 不存在：
  - 检查 `TCM_CSV_PATH`，或先运行 `python data/enhanced_TCMKG.py` 生成 `tcm_enhanced_KG.csv`（见 [app.py](file:///workspace/app.py#L62-L65)）
- 启动时提示 API Key 未设置：
  - 在 `.env` 或环境变量中配置 `MOONSHOT_API_KEY`（见 [app.py](file:///workspace/app.py#L57-L61)）
- 运行时报 `ModuleNotFoundError: openai`：
  - 安装 `openai`（见 5.1）
- 运行时报 `ImportError: No module named 'GraphRAG'`：
  - 当前仓库未包含 `GraphRAG.py`，增强版导入失败时回退会报错（见 [app.py](file:///workspace/app.py#L31-L40)）；建议保持增强版可用或补齐原版实现。

