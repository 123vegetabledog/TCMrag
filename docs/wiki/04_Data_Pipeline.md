# 04 - 知识图谱构建（离线数据管道）

构建脚本：[data/enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py)

## 4.1 输入与输出

### 输入目录

- 经典医籍：`data/src/classicals/`（脚本常量 `BASE_BOOKS_DIR`，见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L31-L35)）
  - 仓库 README 提示需自行补充医籍 txt（见 [README.md](file:///workspace/README.md#L82-L90)）
- 现代临床：`data/medical_case/`（脚本常量 `MEDICAL_CASES_DIR`，见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L31-L35)）

### 输出文件

- 知识图谱 CSV：`tcm_enhanced_KG.csv`（`OUTPUT_CSV_FILE`，见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L31-L35)）
- 断点状态：`processing_status_enhanced_KG.json`（`STATUS_FILE`，见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L31-L35)）

## 4.2 CSV 数据规范

输出 CSV 统一写入以下列（见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L578-L584) 与 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L665-L669)）：

- `Subject`：主语实体（疾病/证候/方剂/药材/症状等）
- `Predicate`：关系类型（受控集合）
- `Object`：宾语实体
- `SourceName`：来源名称（如书名/医生名）
- `SourceChapter`：来源章节（如医籍章节名/病例标题）
- `SourceType`：来源类型（如“经典医籍”“现代临床”）

## 4.3 抽取策略与关系类型

Prompt 构建函数：[create_enhanced_triple_extraction_prompt](file:///workspace/data/enhanced_TCMKG.py#L75-L159)

关系类型围绕“辨证分析”设计，核心包括：

- 疾病与症状：`疾病表现症状`、`症状伴随症状`
- 舌象/脉象：`疾病导致舌象`、`证候导致舌象`、`疾病导致脉象`、`证候导致脉象`
- 辨证：`症状辨证证候`、`舌象辨证证候`、`脉象辨证证候`、`综合辨证证候`
- 方药：`证候采用方剂`、`方剂组成药材`、`药材具有功效`
- 现代临床：`名医经验总结`（以及 Prompt 中提到的现代临床规则约束）

如需扩展关系类型：

1. 在 `create_enhanced_triple_extraction_prompt` 的 `target_relations` 增加关系定义（见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L82-L116)）
2. 同步更新下游消费：
   - 图谱加载与过滤：`EnhancedTCMKnowledgeGraph.get_diagnosis_related_triples`（见 [enhanced_GraphRAG.py](file:///workspace/enhanced_GraphRAG.py#L121-L137)）
   - 辨证映射：`SmartDiagnosisSystem._add_triple_to_mappings`（见 [smart_diagnosis.py](file:///workspace/smart_diagnosis.py#L128-L173)）

## 4.4 分块、限速与重试

- 分块策略相关常量：
  - `CHUNK_SIZE_THRESHOLD = 3000`
  - `CHUNK_OVERLAP = 400`
  - 见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L36-L40)
- API 调用限速（默认）：
  - `API_CALL_DELAY` 默认 25 秒
  - `RETRY_DELAY` 默认 15 秒
  - 可通过环境变量覆盖（见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L38-L40)）
- 抽取函数带重试：`extract_enhanced_triples_with_llm(..., max_retries=2)`（见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L201-L220)）

## 4.5 断点续跑机制

主流程会扫描“经典医籍 txt + 临床 txt”，按文件顺序处理（见 [main](file:///workspace/data/enhanced_TCMKG.py#L625-L705)）。

断点状态包含：

- 当前文件：`current_file_path`
- 当前章节/病例：`current_chapter_name_being_processed`
- 当前 chunk：`current_chunk_idx`
- 已完成文件表：`processed_files_map`

当构建中断（如网络/API 失败或手动终止）：

- 直接重新运行 `python data/enhanced_TCMKG.py` 即可尝试从状态文件恢复（恢复逻辑见 [enhanced_TCMKG.py](file:///workspace/data/enhanced_TCMKG.py#L652-L663)）。

