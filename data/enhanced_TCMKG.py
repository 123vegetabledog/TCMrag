# -*- coding: utf-8 -*-
"""
增强版中医知识图谱构建系统
针对《黄帝内经》《伤寒杂病论》《金匮要略》等经典医籍
结合现代临床数据，专注于舌象、脉象、症状的智能辨证分析
"""

import time
import re
import json
from openai import OpenAI
import os
import csv
import traceback
from dotenv import load_dotenv
load_dotenv()

# --- API 配置 ---
KIMI_API_KEY = os.getenv("MOONSHOT_API_KEY", "sk-your-kimi-api-key")
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-your-deepseek-api-key")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
GLM_API_KEY = os.getenv("GLM_API_KEY", "your-glm-api-key")
GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

# --- 选择模型 ---
CURRENT_API_KEY = KIMI_API_KEY
CURRENT_BASE_URL = KIMI_BASE_URL
CURRENT_MODEL_NAME = "moonshot-v1-32k"

# --- 文件路径配置 ---
BASE_BOOKS_DIR = "data/src/classicals"  # 经典医籍
MEDICAL_CASES_DIR = "data/medical_case"  # 现代临床数据
OUTPUT_CSV_FILE = "tcm_enhanced_KG.csv"  # 增强版知识图谱输出
STATUS_FILE = "processing_status_enhanced_KG.json"  # 状态文件
CHUNK_SIZE_THRESHOLD = 3000  # 减小块大小以提高精度
CHUNK_OVERLAP = 400          # 块重叠
API_CALL_DELAY = int(os.getenv("API_CALL_DELAY", "25"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "15"))

# --- 初始化API客户端 ---
def get_llm_client():
    global CURRENT_API_KEY
    if not CURRENT_API_KEY or "your-" in CURRENT_API_KEY:
        print("Attempting to load API key from environment variables...")
        if "moonshot" in CURRENT_MODEL_NAME.lower() or "kimi" in CURRENT_MODEL_NAME.lower():
            CURRENT_API_KEY = os.getenv("MOONSHOT_API_KEY")
        elif "deepseek" in CURRENT_MODEL_NAME.lower():
            CURRENT_API_KEY = os.getenv("DEEPSEEK_API_KEY")
        elif "glm" in CURRENT_MODEL_NAME.lower():
            CURRENT_API_KEY = os.getenv("GLM_API_KEY")

    if not CURRENT_API_KEY or "your-" in CURRENT_API_KEY or CURRENT_API_KEY is None:
         raise ValueError(f"请为 {CURRENT_MODEL_NAME} 设置有效的API Key")
    client = OpenAI(
        api_key=CURRENT_API_KEY, 
        base_url=CURRENT_BASE_URL,
 
    )
    return client

# --- 文本清理 ---
def clean_text_for_llm(text):
    text = text.strip()

    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+', '', text)
    text = re.sub(r'\s*\n\s*', '\n', text)
    text = re.sub(r'[ 　]+', ' ', text)
    text = re.sub(r'【|】', '', text)
    text = re.sub(r'<|>', '', text)
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9,.?!;，。？！；、():：（）：]', ' ', text)
    return text

# --- 增强版三元关系提取Prompt ---
def create_enhanced_triple_extraction_prompt(text_chunk, source_name, chapter_name, source_type, chunk_idx):
    """
    针对中医智能辨证分析的三元关系提取
    重点关注的实体类型：疾病、症状、舌象、脉象、证候、治法、方剂、药材
    """
    
    # 核心关系类型设计
    target_relations = {
        # 疾病与症状关系
        "疾病表现症状": "疾病 → 表现症状 → 具体症状（如：感冒 表现症状 发热）",
        "症状伴随症状": "主要症状 → 伴随症状 → 次要症状（如：发热 伴随症状 头痛）",
        
        # 舌象关系
        "疾病导致舌象": "疾病 → 导致舌象 → 舌象描述（如：湿热病 导致舌象 舌红苔黄腻）",
        "证候导致舌象": "证候 → 导致舌象 → 舌象描述（如：胃热证 导致舌象 舌红苔黄）",
        "舌象表现特征": "舌象 → 表现特征 → 具体特征（如：舌红苔黄腻 表现特征 舌质红绛）",
        
        # 脉象关系
        "疾病导致脉象": "疾病 → 导致脉象 → 脉象描述（如：寒证 导致脉象 脉浮紧）",
        "证候导致脉象": "证候 → 导致脉象 → 脉象描述（如：表寒证 导致脉象 脉浮紧）",
        "脉象表现特征": "脉象 → 表现特征 → 具体特征（如：脉浮紧 表现特征 轻取即得）",
        
        # 证候辨证关系
        "症状辨证证候": "症状组合 → 辨证证候 → 证候名称（如：发热恶寒头痛 辨证证候 表寒证）",
        "舌象辨证证候": "舌象特征 → 辨证证候 → 证候名称（如：舌红苔黄腻 辨证证候 湿热证）",
        "脉象辨证证候": "脉象特征 → 辨证证候 → 证候名称（如：脉浮紧 辨证证候 表寒证）",
        "综合辨证证候": "症状舌象脉象 → 综合辨证 → 证候名称（如：发热恶寒头痛舌淡红脉浮紧 综合辨证 风寒表证）",
        
        # 治法方药关系

        "证候采用方剂": "证候 → 采用方剂 → 方剂名称（如：风寒表证 采用方剂 麻黄汤）",
        "方剂组成药材": "方剂 → 组成药材 → 药材名称（如：麻黄汤 组成药材 麻黄）",
        "药材具有功效": "药材 → 具有功效 → 功效描述（如：麻黄 具有功效 发汗解表）",
        
        # 经典理论关系
        "归属于经典": "理论 → 归属于经典 → 经典名称（如：六经辨证 归属于经典 伤寒论）",
        "理论指导实践": "经典理论 → 指导实践 → 实践应用（如：六经辨证 指导实践 外感病诊治）",
        
        # 现代临床验证

        "名医经验总结": "名医 → 经验总结 → 经验内容（如：丁光迪 经验总结 感冒辨证论治）"
    }
    
    desired_relations = list(target_relations.keys())
    
    # 根据来源类型添加特殊规则
    special_rules = ""
    if source_type == "现代临床":
        special_rules = """
重要规则（现代临床病例）：
- 患者姓名（如"范某"、"张某"、"李某"等）不能作为疾病、症状或证候的subject
- 患者姓名只能用于"临床验证理论"关系中作为验证案例
- 医生姓名（如"万友生"等）只能用于"名医经验总结"关系
- 对于疾病表现症状关系，subject应该是具体的疾病名称或证候名称，而不是患者姓名
- 如果遇到患者姓名作为疾病主体的情况，请将其转换为实际的疾病或证候名称
"""

    system_prompt = f"""
你是一位高级中医智能辨证分析专家，专门从中医经典文献和现代临床资料中提取结构化知识。

任务：从以下文本中提取三元组关系，严格按照指定的关系类型。

重点关注：
1. 舌象特征：舌质（红、淡、绛、紫等）、舌苔（白、黄、腻、燥等）、舌形（胖、瘦、齿痕等）
2. 脉象特征：浮、沉、迟、数、滑、涩、弦、紧等脉象及其临床意义
3. 症状特征：寒热、汗出、头痛、咳嗽等具体症状
4. 证候辨证：如何根据症状、舌象、脉象综合辨证
5. 方剂应用：具体方剂的应用指征和组成
6. 药材功效：单味药材的功效特性

关系类型列表：{', '.join(desired_relations)}

{special_rules}
输出格式：严格JSON数组格式：[{{"subject":..., "predicate":..., "object":...}}]

要求：
- 仅从文本中提取明确提及的关系
- 主语和宾语必须来自原文或基于原文的合理概括
- 同一个内容不要重复提取
- 如果文本中没有相关关系，返回空数组[]
- 输出必须是有效的JSON格式，不要包含其他文字
"""
    
    return system_prompt

# --- 临床病例三元组验证函数 ---
def is_valid_clinical_triple(subject, predicate, object_entity):
    """
    验证临床病例中的三元组是否有效，主要过滤人名被错误识别为疾病的情况
    """
    # 患者姓名模式（如：范某、张某、李某、患者甲等）
    patient_name_patterns = [
        r'^[一二三四五六七八九十\d]*[甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]某$',
        r'^(?:张|王|李|赵|刘|陈|杨|黄|周|吴|徐|孙|朱|马|胡|郭|林|何|高|梁|郑|罗|宋|谢|唐|韩|曹|许|邓|萧|冯|曾|程|蔡|彭|潘|袁|于|董|余|苏|叶|吕|魏|蒋|田|杜|丁|沈|姜|范|江|傅|钟|卢|汪|戴|崔|任|陆|廖|姚|方|金|邱|夏|谭|韦|贾|邹|石|熊|孟|秦|阎|薛|侯|雷|白|龙|段|郝|孔|邵|史|毛|常|万|顾|赖|武|康|贺|严|尹|钱|施|牛|洪|龚)[某君先生女士]$',
        r'^患者[甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]$',
        r'^(?:病|患)者?$'
    ]
    
    # 医生姓名模式（常见中医姓氏）
    doctor_name_patterns = [
        r'^万友生$',  # 特定医生姓名
        r'^[名医专家]$',  # 通用名医标识
    ]
    
    # 需要过滤的关系类型
    restricted_predicates = [
        "疾病表现症状", "症状伴随症状", "疾病导致舌象", "疾病导致脉象", 
        "症状辨证证候", "舌象辨证证候", "脉象辨证证候", "综合辨证证候"
    ]
    
    # 检查是否是患者姓名且在受限关系中
    for pattern in patient_name_patterns:
        if re.match(pattern, subject):
            if predicate in restricted_predicates:
                return False

    
    # 检查是否是医生姓名且用在了错误的关系中
    for pattern in doctor_name_patterns:
        if re.match(pattern, subject):
            if predicate not in ["名医经验总结"]:
                return False
    
    return True

# --- 增强版三元组提取 ---
def extract_enhanced_triples_with_llm(client, text_chunk, source_name, chapter_name, source_type, chunk_idx):
    system_prompt_content = create_enhanced_triple_extraction_prompt(
        text_chunk, source_name, chapter_name, source_type, chunk_idx
    )
    
    max_retries = 2
    response_content = ""

    for attempt in range(max_retries):
        try:
            print(f"      LLM API call for {source_type} chunk (attempt {attempt + 1}/{max_retries})...")
            
            completion = client.chat.completions.create(
                model=CURRENT_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt_content},
                    {"role": "user", "content": f"请从以下{source_type}中提取三元组：\n\n来源：{source_name}\n章节：{chapter_name}\n\n文本内容：\n{text_chunk}"}
                ],
                stream=False,
                temperature=0.1,  # 降低温度以提高准确性
                max_tokens=min(int(CHUNK_SIZE_THRESHOLD * 2.5), 8000),
                response_format={"type": "json_object"},
            )
            
            response_content = completion.choices[0].message.content
            clean_response = re.sub(r"^```json\s*|\s*```$", "", response_content, flags=re.MULTILINE).strip()
            
            try:
                extracted_data = json.loads(clean_response)
            except json.JSONDecodeError:
                # 尝试修复常见的JSON格式问题
                clean_response = clean_response.replace('\n', '\\n').replace('\r', '\\r')
                clean_response = re.sub(r',\s*]', ']', clean_response)  # 移除末尾多余的逗号
                extracted_data = json.loads(clean_response)

            valid_triples = []
            data_list_to_process = []
            
            if isinstance(extracted_data, list):
                data_list_to_process = extracted_data
            elif isinstance(extracted_data, dict) and "triples" in extracted_data:
                data_list_to_process = extracted_data["triples"]
            elif isinstance(extracted_data, dict) and isinstance(list(extracted_data.values())[0], list):
                 data_list_to_process = list(extracted_data.values())[0]
            else:
                print(f"      Warning: Unexpected LLM response format. Type: {type(extracted_data)}")
                print(f"      LLM raw response (cleaned): {clean_response[:500]}")
                return []

            for item in data_list_to_process:
                if isinstance(item, dict) and "subject" in item and "predicate" in item and "object" in item:
                    s = str(item["subject"]).strip()
                    p = str(item["predicate"]).strip()
                    o = str(item["object"]).strip()
                    
                    if s and p and o and len(s) > 1 and len(o) > 1:
                         # 后处理过滤：针对现代临床病例的特殊规则
                         if source_type == "现代临床":
                            if not is_valid_clinical_triple(s, p, o):
                                print(f"        Filtering invalid clinical triple: ({s}, {p}, {o})")
                                continue
                         valid_triples.append((s, p, o))
                else:
                    print(f"        Warning: Invalid item in LLM response list: {item}")
            
            print(f"      Successfully extracted {len(valid_triples)} triples.")
            return valid_triples
            
        except json.JSONDecodeError as e:
            print(f"      Error: LLM response JSON decode error (attempt {attempt + 1}): {e}")
            print(f"      LLM raw response content: {response_content[:1000]}")
        except Exception as e:
            print(f"      Error: Unknown error during LLM API call (attempt {attempt + 1}): {e}")
            traceback.print_exc()
            
        if attempt < max_retries - 1:
            print(f"      Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
        else:
            print(f"      Max retries reached. Failed to extract for this chunk.")
    return []

# --- 状态管理 ---
def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                status = json.load(f)
                print(f"Resuming from status: {status.get('current_file_path', 'None')}")
                return status
        except Exception as e:
            print(f"Warning: Error loading status file '{STATUS_FILE}': {e}. Starting fresh.")
    return {
        "processed_files_map": {}, 
        "current_file_path": None, 
        "current_chapter_name_being_processed": None, 
        "current_chunk_idx": 0
    }

def save_status(status):
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving status file '{STATUS_FILE}': {e}")

# --- 处理经典医籍文件 ---
def process_classical_book_file(filepath, book_name, client, status, writer, csv_file_needs_header):
    print(f"\n======================================================")
    print(f"Processing Classical Book: {book_name}")
    print(f"======================================================")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            book_content_full = f.read()
    except Exception as e:
        print(f"  Error reading file {filepath}: {e}")
        status["processed_files_map"][filepath] = f"error_reading: {e}"
        save_status(status)
        return False

    if not book_content_full.strip():
        print(f"  Book {book_name} is empty. Skipping.")
        status["processed_files_map"][filepath] = "empty"
        save_status(status)
        return True

    current_book_triples_count = 0
    
    # 章节划分 - 适配经典医籍的章节格式
    chapters = re.split(r'(<[^>]+>)', book_content_full)
    
    parsed_chapters = []
    current_chapter_title = f"{book_name}_引言"
    current_chapter_content = ""

    if not chapters[0].strip() and len(chapters) > 1:
        chapters = chapters[1:]

    for i in range(0, len(chapters)):
        part = chapters[i].strip()
        if not part:
            continue
        if part.startswith("<") and part.endswith(">"):
            if current_chapter_content.strip():
                parsed_chapters.append({"title": current_chapter_title, "content": current_chapter_content.strip()})
            current_chapter_title = part[1:-1].strip()
            current_chapter_content = ""
        else:
            current_chapter_content += part + "\n"
    
    if current_chapter_content.strip():
        parsed_chapters.append({"title": current_chapter_title, "content": current_chapter_content.strip()})

    if not parsed_chapters and book_content_full.strip():
        parsed_chapters.append({"title": f"{book_name}_全文", "content": book_content_full.strip()})

    total_chapters_in_book = len(parsed_chapters)
    print(f"  Book '{book_name}' parsed into {total_chapters_in_book} chapters.")

    # 断点续传逻辑
    start_processing_chapter_name = None
    start_chunk_idx_for_chapter = 0

    if status.get("current_file_path") == filepath:
        start_processing_chapter_name = status.get("current_chapter_name_being_processed")
        start_chunk_idx_for_chapter = status.get("current_chunk_idx", 0)
        if start_processing_chapter_name:
             print(f"  Resuming '{book_name}' from chapter '{start_processing_chapter_name}', chunk index {start_chunk_idx_for_chapter}")

    for chapter_idx, chapter_data in enumerate(parsed_chapters):
        chapter_name = chapter_data["title"]
        chapter_content_full = chapter_data["content"]

        if start_processing_chapter_name:
            if chapter_name != start_processing_chapter_name:
                try:
                    current_parsed_chapter_idx = parsed_chapters.index(chapter_data)
                    start_status_chapter_idx = -1
                    for idx, c_data in enumerate(parsed_chapters):
                        if c_data["title"] == start_processing_chapter_name:
                            start_status_chapter_idx = idx
                            break
                    if start_status_chapter_idx != -1 and current_parsed_chapter_idx < start_status_chapter_idx:
                        print(f"    Skipping chapter '{chapter_name}' (before resume point)")
                        continue
                except ValueError:
                    pass

        print(f"    Processing Chapter {chapter_idx + 1}/{total_chapters_in_book}: '{chapter_name}'")
        status["current_file_path"] = filepath
        status["current_chapter_name_being_processed"] = chapter_name

        text_chunks = []
        cleaned_chapter_content = clean_text_for_llm(chapter_content_full)
        
        # 分块逻辑
        if len(cleaned_chapter_content) > CHUNK_SIZE_THRESHOLD:
            start = 0
            while start < len(cleaned_chapter_content):
                end = min(start + CHUNK_SIZE_THRESHOLD, len(cleaned_chapter_content))
                text_chunks.append(cleaned_chapter_content[start:end])
                if end == len(cleaned_chapter_content):
                    break
                start += (CHUNK_SIZE_THRESHOLD - CHUNK_OVERLAP)
                if start >= len(cleaned_chapter_content):
                    break
        elif cleaned_chapter_content:
            text_chunks.append(cleaned_chapter_content)

        if not text_chunks:
            print(f"      No text chunks for chapter '{chapter_name}'. Skipping chapter.")
            continue
        
        print(f"      Chapter '{chapter_name}' split into {len(text_chunks)} text chunks.")

        actual_start_chunk_this_chapter = 0
        if chapter_name == start_processing_chapter_name:
            actual_start_chunk_this_chapter = start_chunk_idx_for_chapter

        for chunk_idx, text_chunk in enumerate(text_chunks):
            if chunk_idx < actual_start_chunk_this_chapter:
                continue

            status["current_chunk_idx"] = chunk_idx
            save_status(status)

            print(f"        Processing chunk {chunk_idx + 1}/{len(text_chunks)} for chapter '{chapter_name}'...")
            
            triples_from_chunk = extract_enhanced_triples_with_llm(
                client, text_chunk, book_name, chapter_name, "经典医籍", chunk_idx + 1
            )
            
            if triples_from_chunk:
                # CSV: Subject, Predicate, Object, SourceName, SourceChapter, SourceType
                rows_to_write = [(s, p, o, book_name, chapter_name, "经典医籍") for s, p, o in triples_from_chunk]
                
                if csv_file_needs_header[0]:
                    writer.writerow(['Subject', 'Predicate', 'Object', 'SourceName', 'SourceChapter', 'SourceType'])
                    csv_file_needs_header[0] = False
                writer.writerows(rows_to_write)
                current_book_triples_count += len(rows_to_write)
                print(f"          Chunk {chunk_idx + 1} processed. {len(rows_to_write)} triples extracted.")
            else:
                print(f"          No triples extracted from chunk {chunk_idx + 1}.")

            time.sleep(API_CALL_DELAY)
        
        start_processing_chapter_name = None 
        start_chunk_idx_for_chapter = 0
        status["current_chapter_name_being_processed"] = chapter_name
        status["current_chunk_idx"] = 0
        save_status(status)

    status["processed_files_map"][filepath] = "completed"
    status["current_chapter_name_being_processed"] = None 
    save_status(status)
    print(f"  Finished processing book: {book_name}. Total triples: {current_book_triples_count}")
    return True

# --- 处理现代临床病例文件 ---
def process_medical_case_file(filepath, doctor_name, client, status, writer, csv_file_needs_header):
    print(f"\n======================================================")
    print(f"Processing Medical Cases: {doctor_name}")
    print(f"======================================================")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  Error reading file {filepath}: {e}")
        status["processed_files_map"][filepath] = f"error_reading: {e}"
        save_status(status)
        return False

    if not content.strip():
        print(f"  Medical case file {doctor_name} is empty. Skipping.")
        status["processed_files_map"][filepath] = "empty"
        save_status(status)
        return True

    current_case_triples_count = 0
    
    # 病例分割 - 按例X或病例X分割
    case_pattern = r'(?:例[一二三四五六七八九十\d]+|病例[一二三四五六七八九十\d]+)'
    cases = re.split(case_pattern, content)
    
    parsed_cases = []
    case_titles = re.findall(case_pattern, content)
    
    for i, case_content in enumerate(cases):
        if not case_content.strip():
            continue
            
        case_title = case_titles[i-1] if i > 0 and i-1 < len(case_titles) else f"{doctor_name}_病例{i+1}"
        parsed_cases.append({"title": case_title, "content": case_content.strip()})
    
    if not parsed_cases and content.strip():
        parsed_cases.append({"title": f"{doctor_name}_病例集", "content": content.strip()})

    total_cases = len(parsed_cases)
    print(f"  Doctor '{doctor_name}' has {total_cases} cases.")

    # 断点续传逻辑
    start_processing_case_name = None
    start_chunk_idx_for_case = 0

    if status.get("current_file_path") == filepath:
        start_processing_case_name = status.get("current_chapter_name_being_processed")
        start_chunk_idx_for_case = status.get("current_chunk_idx", 0)
        if start_processing_case_name:
             print(f"  Resuming '{doctor_name}' from case '{start_processing_case_name}', chunk index {start_chunk_idx_for_case}")

    for case_idx, case_data in enumerate(parsed_cases):
        case_title = case_data["title"]
        case_content_full = case_data["content"]

        if start_processing_case_name:
            if case_title != start_processing_case_name:
                try:
                    current_parsed_case_idx = parsed_cases.index(case_data)
                    start_status_case_idx = -1
                    for idx, c_data in enumerate(parsed_cases):
                        if c_data["title"] == start_processing_case_name:
                            start_status_case_idx = idx
                            break
                    if start_status_case_idx != -1 and current_parsed_case_idx < start_status_case_idx:
                        print(f"    Skipping case '{case_title}' (before resume point)")
                        continue
                except ValueError:
                    pass

        print(f"    Processing Case {case_idx + 1}/{total_cases}: '{case_title}'")
        status["current_file_path"] = filepath
        status["current_chapter_name_being_processed"] = case_title

        text_chunks = []
        cleaned_case_content = clean_text_for_llm(case_content_full)
        
        # 分块逻辑
        if len(cleaned_case_content) > CHUNK_SIZE_THRESHOLD:
            start = 0
            while start < len(cleaned_case_content):
                end = min(start + CHUNK_SIZE_THRESHOLD, len(cleaned_case_content))
                text_chunks.append(cleaned_case_content[start:end])
                if end == len(cleaned_case_content):
                    break
                start += (CHUNK_SIZE_THRESHOLD - CHUNK_OVERLAP)
                if start >= len(cleaned_case_content):
                    break
        elif cleaned_case_content:
            text_chunks.append(cleaned_case_content)

        if not text_chunks:
            print(f"      No text chunks for case '{case_title}'. Skipping case.")
            continue
        
        print(f"      Case '{case_title}' split into {len(text_chunks)} text chunks.")

        actual_start_chunk_this_case = 0
        if case_title == start_processing_case_name:
            actual_start_chunk_this_case = start_chunk_idx_for_case

        for chunk_idx, text_chunk in enumerate(text_chunks):
            if chunk_idx < actual_start_chunk_this_case:
                continue

            status["current_chunk_idx"] = chunk_idx
            save_status(status)

            print(f"        Processing chunk {chunk_idx + 1}/{len(text_chunks)} for case '{case_title}'...")
            
            triples_from_chunk = extract_enhanced_triples_with_llm(
                client, text_chunk, doctor_name, case_title, "现代临床", chunk_idx + 1
            )
            
            if triples_from_chunk:
                # CSV: Subject, Predicate, Object, SourceName, SourceChapter, SourceType
                rows_to_write = [(s, p, o, doctor_name, case_title, "现代临床") for s, p, o in triples_from_chunk]
                
                if csv_file_needs_header[0]:
                    writer.writerow(['Subject', 'Predicate', 'Object', 'SourceName', 'SourceChapter', 'SourceType'])
                    csv_file_needs_header[0] = False
                writer.writerows(rows_to_write)
                current_case_triples_count += len(rows_to_write)
                print(f"          Chunk {chunk_idx + 1} processed. {len(rows_to_write)} triples extracted.")
            else:
                print(f"          No triples extracted from chunk {chunk_idx + 1}.")

            time.sleep(API_CALL_DELAY)
        
        start_processing_case_name = None 
        start_chunk_idx_for_case = 0
        status["current_chapter_name_being_processed"] = case_title
        status["current_chunk_idx"] = 0
        save_status(status)

    status["processed_files_map"][filepath] = "completed"
    status["current_chapter_name_being_processed"] = None 
    save_status(status)
    print(f"  Finished processing medical cases: {doctor_name}. Total triples: {current_case_triples_count}")
    return True

# --- 主函数 ---
def main():
    print("=== 增强版中医知识图谱构建系统 ===")
    print("特点：")
    print("1. 专注于舌象、脉象、症状的智能辨证分析")
    print("2. 整合经典医籍与现代临床数据")
    print("3. 支持断点续传和错误恢复")
    print("4. 优化的三元关系提取策略")
    print("=" * 50)
    
    client = get_llm_client()
    status = load_status()
    
    csv_file_needs_header = [not os.path.exists(OUTPUT_CSV_FILE) or os.path.getsize(OUTPUT_CSV_FILE) == 0]

    output_dir = os.path.dirname(OUTPUT_CSV_FILE)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    processed_in_this_run_count = 0
    
    # 收集所有要处理的文件
    files_to_process = []
    
    # 1. 经典医籍文件
    if os.path.isdir(BASE_BOOKS_DIR):
        for filename in os.listdir(BASE_BOOKS_DIR):
            if filename.endswith(".txt"):
                files_to_process.append({
                    "path": os.path.join(BASE_BOOKS_DIR, filename),
                    "name": os.path.splitext(filename)[0],
                    "type": "classical"
                })
    
    # 2. 现代临床文件
    if os.path.isdir(MEDICAL_CASES_DIR):
        for filename in os.listdir(MEDICAL_CASES_DIR):
            if filename.endswith(".txt"):
                files_to_process.append({
                    "path": os.path.join(MEDICAL_CASES_DIR, filename),
                    "name": os.path.splitext(filename)[0],
                    "type": "medical"
                })
    
    files_to_process.sort(key=lambda x: x["path"])
    total_files = len(files_to_process)
    print(f"Found {total_files} files to process.")

    start_processing_from_file_idx = 0
    if status.get("current_file_path") and status["processed_files_map"].get(status["current_file_path"]) != "completed":
        try:
            start_processing_from_file_idx = [f["path"] for f in files_to_process].index(status["current_file_path"])
            print(f"Attempting to resume from file: {status['current_file_path']}")
        except ValueError:
            print(f"Warning: Status file's current_file_path not found. Starting fresh.")
            status["current_file_path"] = None
            status["current_chapter_name_being_processed"] = None
            status["current_chunk_idx"] = 0
            start_processing_from_file_idx = 0

    try:
        with open(OUTPUT_CSV_FILE, 'a+', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            if csv_file_needs_header[0] and csvfile.tell() == 0:
                writer.writerow(['Subject', 'Predicate', 'Object', 'SourceName', 'SourceChapter', 'SourceType'])
                csv_file_needs_header[0] = False

            for file_idx, file_info in enumerate(files_to_process):
                filepath = file_info["path"]
                file_name = file_info["name"]
                file_type = file_info["type"]
                
                if status["processed_files_map"].get(filepath) == "completed":
                    print(f"Skipping already completed file: {file_name}")
                    continue
                
                if status.get("current_file_path") and filepath != status.get("current_file_path") and file_idx < start_processing_from_file_idx:
                    print(f"Skipping file {file_name} as it's before the resume point.")
                    continue
                
                if status.get("current_file_path") and status.get("current_file_path") != filepath and status["processed_files_map"].get(status["current_file_path"]) == "completed":
                    print(f"Previous resume file was completed. Moving to next file.")
                    status["current_file_path"] = filepath
                    status["current_chapter_name_being_processed"] = None
                    status["current_chunk_idx"] = 0

                if file_type == "classical":
                    success = process_classical_book_file(filepath, file_name, client, status, writer, csv_file_needs_header)
                elif file_type == "medical":
                    success = process_medical_case_file(filepath, file_name, client, status, writer, csv_file_needs_header)
                else:
                    success = False
                
                if success:
                    processed_in_this_run_count += 1
                else:
                    print(f"Processing may have failed for: {file_name}. Check logs.")
            
            status["current_file_path"] = None
            status["current_chapter_name_being_processed"] = None
            status["current_chunk_idx"] = 0
            save_status(status)

    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Saving current status...")
        save_status(status)
        print("Status saved. Exiting.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        traceback.print_exc()
        save_status(status)
        print("Status saved due to error. Exiting.")
    finally:
        print(f"\n\nProcessing session finished.")
        print(f"Total files processed in this run: {processed_in_this_run_count}")
        print(f"All extracted triples are in '{OUTPUT_CSV_FILE}'.")
        print(f"Final processing status saved in '{STATUS_FILE}'.")

if __name__ == '__main__':
    main()
