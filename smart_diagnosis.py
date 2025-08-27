# -*- coding: utf-8 -*-
"""
智能辨证分析系统
基于知识图谱实现舌象、脉象、症状的智能辨证分析
支持中医诊断逻辑的可解释性推导
"""

import os
import pandas as pd
import numpy as np
import networkx as nx
from typing import List, Dict, Any, Tuple, Optional, Set
import json
import re
from collections import defaultdict, Counter
from openai import OpenAI
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

class SmartDiagnosisSystem:
    """智能辨证分析系统"""

    def __init__(self, kg_csv_path: str = None):
        """
        初始化智能辨证系统

        Args:
            kg_csv_path: 知识图谱CSV文件路径
        """
        self.graph = nx.MultiDiGraph()
        self.triples_with_source = []
        self.relation_types = set()

        # 辨证分析专用数据结构
        self.symptom_disease_map = defaultdict(set)  # 症状->疾病
        self.tongue_disease_map = defaultdict(set)  # 舌象->疾病
        self.pulse_disease_map = defaultdict(set)  # 脉象->疾病
        self.syndrome_disease_map = defaultdict(set)  # 证候->疾病
        self.disease_syndrome_map = defaultdict(set)  # 疾病->证候
        self.syndrome_formula_map = defaultdict(set)  # 证候->方剂（新增映射）
        self.formula_herb_map = defaultdict(set)  # 方剂->药材

        # 舌象、脉象、症状标准化映射
        self.tongue_patterns = self._init_tongue_patterns()
        self.pulse_patterns = self._init_pulse_patterns()
        self.symptom_patterns = self._init_symptom_patterns()

        if kg_csv_path:
            self.load_knowledge_graph(kg_csv_path)

    def _init_tongue_patterns(self):
        """初始化舌象模式"""
        return {
            '舌质': ['淡', '红', '绛', '紫', '淡白', '红绛', '青紫'],
            '舌苔': ['薄白', '薄黄', '白腻', '黄腻', '灰黑', '少苔', '无苔', '苔燥', '苔滑'],
            '舌形': ['胖大', '瘦薄', '齿痕', '裂纹', '芒刺', '光滑']
        }

    def _init_pulse_patterns(self):
        """初始化脉象模式"""
        return {
            '浮脉类': ['浮', '洪', '芤', '革', '散'],
            '沉脉类': ['沉', '伏', '牢', '弱'],
            '迟脉类': ['迟', '缓', '涩', '结'],
            '数脉类': ['数', '疾', '促', '动'],
            '虚脉类': ['虚', '微', '细', '代', '短'],
            '实脉类': ['实', '滑', '紧', '长', '弦']
        }

    def _init_symptom_patterns(self):
        """初始化症状模式"""
        return {
            '寒热': ['恶寒', '发热', '寒战', '壮热', '潮热', '五心烦热'],
            '汗出': ['无汗', '有汗', '自汗', '盗汗', '大汗', '冷汗'],
            '头身': ['头痛', '头晕', '身痛', '肢体酸痛', '项强', '背痛'],
            '二便': ['便秘', '腹泻', '尿频', '尿急', '尿痛', '小便不利'],
            '饮食': ['食欲不振', '恶心', '呕吐', '口渴', '口苦', '口淡']
        }

    def load_knowledge_graph(self, csv_path: str):
        try:
            df = pd.read_csv(csv_path)
            print(f"加载知识图谱：{len(df)}条三元组")

            for _, row in df.iterrows():
                subject = str(row['Subject']).strip()
                predicate = str(row['Predicate']).strip()
                obj = str(row['Object']).strip()
                # 1. 补全溯源字段读取（关键新增）
                source_name = str(row.get('SourceName', '')).strip()  # 来源名称（如《伤寒论》）
                source_chapter = str(row.get('SourceChapter', '')).strip()  # 来源章节（如辨太阳病脉证并治上第五）
                source_type = str(row.get('SourceType', '')).strip()  # 来源类型（如经典医籍）

                if subject and predicate and obj:
                    # 2. 将溯源信息打包为元组，传入映射（关键修改）
                    source_info = (source_name, source_chapter, source_type)
                    self._add_triple_to_mappings(subject, predicate, obj, source_info)

                    # 3. 边属性中存储完整溯源信息（关键修改）
                    self.graph.add_edge(
                        subject, obj,
                        relation=predicate,
                        source_name=source_name,
                        source_chapter=source_chapter,
                        source_type=source_type
                    )
                    self.relation_types.add(predicate)

            print(f"知识图谱构建完成：{len(self.graph.nodes)}个节点，{len(self.graph.edges)}条边")
            self._print_mapping_stats()
        except Exception as e:
            print(f"加载知识图谱失败：{e}")

    def _add_triple_to_mappings(self, subject: str, predicate: str, obj: str, source_info: Tuple[str, str, str]):
        """
        source_info: (source_name, source_chapter, source_type)
        """
        source_name, source_chapter, source_type = source_info

        # 1. 现代临床病例：仅显示病例文件名称
        if source_type == "现代临床":
            source_label = f"<<{source_name}>>" if source_name else "未知病例"
        # 2. 书籍类来源：显示书籍名称和章节
        elif source_type == "经典医籍":
            if source_name and source_chapter:
                source_label = f"《{source_name}》（{source_chapter}）"
            elif source_name:
                source_label = f"《{source_name}》"
            else:
                source_label = "未知书籍来源"
        # 3. 其他类型来源
        else:
            source_label = f"{source_name}" if source_name else "未知来源"

        # 1. 症状→(疾病, 溯源)
        if predicate == "疾病表现症状":
            self.symptom_disease_map[obj].add((subject, source_label))

        # 2. 舌象→(疾病, 溯源)
        elif predicate == "疾病导致舌象":
            self.tongue_disease_map[obj].add((subject, source_label))

        # 3. 脉象→(疾病, 溯源)
        elif predicate == "疾病导致脉象":
            self.pulse_disease_map[obj].add((subject, source_label))

        # 4. 症状/舌象/脉象→(证候, 溯源)
        elif predicate in ["症状辨证证候", "舌象辨证证候", "脉象辨证证候"]:
            self.syndrome_disease_map[obj].add((subject, source_label))

        # 证候→方剂映射
        elif predicate == "证候采用方剂":
            self.syndrome_formula_map[subject].add(obj)

        # 方剂→药材映射
        elif predicate == "方剂组成药材":
            self.formula_herb_map[subject].add(obj)



    def _print_mapping_stats(self):
        """打印映射统计信息"""
        print("\n=== 知识图谱映射统计 ===")
        print(f"症状-疾病映射：{len(self.symptom_disease_map)} 种症状")
        print(f"舌象-疾病映射：{len(self.tongue_disease_map)} 种舌象")
        print(f"脉象-疾病映射：{len(self.pulse_disease_map)} 种脉象")
        print(f"证候-疾病映射：{len(self.syndrome_disease_map)} 种证候")
        print(f"证候-方剂映射：{len(self.syndrome_formula_map)} 种证候")  # 更新统计信息
        print(f"方剂-药材映射：{len(self.formula_herb_map)} 种方剂")

    def _call_llm_for_extraction(self, text: str) -> Dict[str, List[str]]:
        """调用大模型提取中医信息"""
        # 构建专业中医信息提取提示词
        prompt = f"""你是一位经验丰富的中医医师，擅长从患者描述中提取关键临床信息。
请仔细分析以下患者描述，提取其中的症状、舌象和脉象信息。

【提取要求】
1. 症状：包括寒热、汗出、头身、二便、饮食等全身及局部不适表现
2. 舌象：包括舌质（淡/红/绛等）、舌苔（薄白/黄腻等）、舌形（胖大/齿痕等）相关描述
3. 脉象：包括浮/沉/迟/数/虚/实等各类脉象描述

【患者描述】
{text}

【输出格式】
请以JSON格式返回结果，包含"symptoms"、"tongue_findings"、"pulse_findings"三个键，值为提取到的对应信息列表。
如果未提及某类信息，请返回空列表。
仅返回JSON内容，不要添加额外解释。
"""

        try:
            # 调用大模型
            response = self.llm_client.chat.completions.create(
                model=CURRENT_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "你是专业的中医信息提取助手，精准提取临床信息。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 低温度保证提取稳定性
                response_format={"type": "json_object"}
            )

            # 解析结果
            result = json.loads(response.choices[0].message.content)

            # 验证结果格式
            if not isinstance(result, dict):
                raise ValueError("大模型返回格式不是JSON对象")

            # 确保返回必要的键
            return {
                "symptoms": result.get("symptoms", []),
                "tongue_findings": result.get("tongue_findings", []),
                "pulse_findings": result.get("pulse_findings", [])
            }

        except Exception as e:
            print(f"大模型提取失败: {str(e)}")
            # 失败时使用原有提取方法作为降级方案
            return {
                "symptoms": self._fallback_extract_symptoms(text),
                "tongue_findings": self._fallback_extract_tongue(text),
                "pulse_findings": self._fallback_extract_pulse(text)
            }

    def _fallback_extract_symptoms(self, text: str) -> List[str]:
        """降级方案：原有症状提取"""
        extracted_symptoms = []
        for category, symptoms in self.symptom_patterns.items():
            for symptom in symptoms:
                if symptom in text:
                    extracted_symptoms.append(symptom)

        symptom_patterns = [
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)痛(?!\w)',
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)胀(?!\w)',
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)痒(?!\w)',
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)红(?!\w)',
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)肿(?!\w)',
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)热(?!\w)',
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)寒(?!\w)',
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)汗(?!\w)',
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)咳(?!\w)',
            r'(?!患者)([^，。！？\s痛胀痒红肿胀热寒汗咳喘]{2,6}?)喘(?!\w)',
        ]

        for pattern in symptom_patterns:
            matches = re.findall(pattern, text)
            extracted_symptoms.extend(matches)

        return list(set(extracted_symptoms))

    def _fallback_extract_tongue(self, text: str) -> List[str]:
        """降级方案：原有舌象提取"""
        extracted_tongue = []
        tongue_keywords = ['舌', '苔']
        for keyword in tongue_keywords:
            if keyword in text:
                sentences = re.split(r'[，。！？]', text)
                for sentence in sentences:
                    if keyword in sentence:
                        words = sentence.split()
                        for i, word in enumerate(words):
                            if keyword in word:
                                context_words = words[max(0, i - 2):i + 3]
                                extracted_tongue.append(''.join(context_words))
        return list(set(extracted_tongue))

    def _fallback_extract_pulse(self, text: str) -> List[str]:
        """降级方案：原有脉象提取"""
        extracted_pulse = []
        pulse_keywords = ['脉', '搏']
        for keyword in pulse_keywords:
            if keyword in text:
                sentences = re.split(r'[，。！？]', text)
                for sentence in sentences:
                    if keyword in sentence:
                        words = sentence.split()
                        for i, word in enumerate(words):
                            if keyword in word:
                                context_words = words[max(0, i - 2):i + 3]
                                extracted_pulse.append(''.join(context_words))
        return list(set(extracted_pulse))

    def extract_symptoms_from_text(self, text: str) -> List[str]:
        """从文本中提取症状（基于大模型）"""
        extraction_result = self._call_llm_for_extraction(text)
        return extraction_result["symptoms"]

    def extract_tongue_from_text(self, text: str) -> List[str]:
        """从文本中提取舌象（基于大模型）"""
        extraction_result = self._call_llm_for_extraction(text)
        return extraction_result["tongue_findings"]

    def extract_pulse_from_text(self, text: str) -> List[str]:
        """从文本中提取脉象（基于大模型）"""
        extraction_result = self._call_llm_for_extraction(text)
        return extraction_result["pulse_findings"]

    def analyze_syndrome_from_symptoms(self, symptoms: List[str]) -> List[Dict]:
        """根据症状分析可能的证候"""
        syndrome_candidates = []

        for symptom in symptoms:
            # 查找与症状相关的证候
            related_syndromes = set()
            for syndrome, disease_set in self.syndrome_disease_map.items():
                if symptom in syndrome:
                    related_syndromes.add(syndrome)

            for syndrome in related_syndromes:
                syndrome_candidates.append({
                    'syndrome': syndrome,
                    'evidence': symptom,
                    'confidence': 0.7
                })

        return syndrome_candidates

    def analyze_disease_from_manifestations(self, symptoms: List[str],
                                            tongue_findings: List[str],
                                            pulse_findings: List[str]) -> List[Dict]:
        """根据症状、舌象、脉象分析可能的疾病"""
        disease_candidates = []

        # 基于症状的疾病分析
        for symptom in symptoms:
            if symptom in self.symptom_disease_map:
                for disease in self.symptom_disease_map[symptom]:
                    disease_candidates.append({
                        'disease': disease,
                        'evidence_type': '症状',
                        'evidence': symptom,
                        'confidence': 0.8
                    })

        # 基于舌象的疾病分析
        for tongue in tongue_findings:
            if tongue in self.tongue_disease_map:
                for disease in self.tongue_disease_map[tongue]:
                    disease_candidates.append({
                        'disease': disease,
                        'evidence_type': '舌象',
                        'evidence': tongue,
                        'confidence': 0.7
                    })

        # 基于脉象的疾病分析
        for pulse in pulse_findings:
            if pulse in self.pulse_disease_map:
                for disease in self.pulse_disease_map[pulse]:
                    disease_candidates.append({
                        'disease': disease,
                        'evidence_type': '脉象',
                        'evidence': pulse,
                        'confidence': 0.7
                    })

        return disease_candidates

    def get_treatment_recommendations(self, syndrome: str) -> Dict:
        """根据证候获取治疗建议"""
        recommendations = {
            'syndrome': syndrome,
            'formulas': [],  # 直接从证候获取方剂
            'herbs': []
        }

        # 直接从证候获取方剂（新增逻辑）
        if syndrome in self.syndrome_formula_map:
            recommendations['formulas'] = list(self.syndrome_formula_map[syndrome])

        # 获取药材
        for formula in recommendations['formulas']:
            if formula in self.formula_herb_map:
                recommendations['herbs'].extend(list(self.formula_herb_map[formula]))

        # 去重
        recommendations['formulas'] = list(set(recommendations['formulas']))
        recommendations['herbs'] = list(set(recommendations['herbs']))

        return recommendations

    def smart_diagnosis_analysis(self, patient_description: str) -> Dict:
        """
        智能辨证分析主函数

        Args:
            patient_description: 患者描述文本

        Returns:
            辨证分析结果
        """
        print(f"开始智能辨证分析...")
        print(f"患者描述：{patient_description[:100]}...")

        # 1. 提取临床表现
        symptoms = self.extract_symptoms_from_text(patient_description)
        tongue_findings = self.extract_tongue_from_text(patient_description)
        pulse_findings = self.extract_pulse_from_text(patient_description)

        print(f"提取到症状：{symptoms}")
        print(f"提取到舌象：{tongue_findings}")
        print(f"提取到脉象：{pulse_findings}")

        # 2. 证候分析
        syndrome_candidates = self.analyze_syndrome_from_symptoms(symptoms)

        # 3. 疾病分析
        disease_candidates = self.analyze_disease_from_manifestations(
            symptoms, tongue_findings, pulse_findings
        )

        # 4. 生成诊断结果
        diagnosis_result = {
            'patient_description': patient_description,
            'extracted_findings': {
                'symptoms': symptoms,
                'tongue_findings': tongue_findings,
                'pulse_findings': pulse_findings
            },
            'syndrome_analysis': syndrome_candidates,
            'differential_diagnosis': disease_candidates,
            'treatment_recommendations': []
        }

        # 5. 为主要证候推荐治疗方案
        if syndrome_candidates:
            top_syndrome = syndrome_candidates[0]['syndrome']
            treatment = self.get_treatment_recommendations(top_syndrome)
            diagnosis_result['treatment_recommendations'].append(treatment)

        # 6. 生成解释性推理
        diagnosis_result['reasoning'] = self._generate_reasoning_text(diagnosis_result)

        return diagnosis_result

    def _generate_reasoning_text(self, diagnosis_result: Dict) -> str:
        """生成解释性推理文本"""
        reasoning = []

        findings = diagnosis_result['extracted_findings']

        reasoning.append("【辨证分析过程】")

        if findings['symptoms']:
            reasoning.append(f"1. 症状分析：患者出现{', '.join(findings['symptoms'])}等症状")

        if findings['tongue_findings']:
            reasoning.append(f"2. 舌象分析：舌象表现为{', '.join(findings['tongue_findings'])}")

        if findings['pulse_findings']:
            reasoning.append(f"3. 脉象分析：脉象表现为{', '.join(findings['pulse_findings'])}")

        if diagnosis_result['syndrome_analysis']:
            top_syndrome = diagnosis_result['syndrome_analysis'][0]['syndrome']
            reasoning.append(f"4. 证候诊断：综合分析，辨证为{top_syndrome}")

        if diagnosis_result['differential_diagnosis']:
            reasoning.append("5. 鉴别诊断：需要与以下疾病进行鉴别")
            for disease in diagnosis_result['differential_diagnosis'][:3]:
                disease_name, source_label = disease['disease']
                reasoning.append(f"   - {disease_name}（{source_label}）（{disease['evidence_type']}：{disease['evidence']}）")

        return '\n'.join(reasoning)

    def explain_diagnosis_logic(self, diagnosis_result: Dict) -> str:
        """解释诊断逻辑（用于用户界面展示）"""
        explanation = []

        explanation.append("🔍 **智能辨证分析报告**")
        explanation.append("=" * 50)

        # 临床表现
        findings = diagnosis_result['extracted_findings']
        explanation.append("\n📋 **临床表现**")
        if findings['symptoms']:
            explanation.append(f"• 症状：{', '.join(findings['symptoms'])}")
        if findings['tongue_findings']:
            explanation.append(f"• 舌象：{', '.join(findings['tongue_findings'])}")
        if findings['pulse_findings']:
            explanation.append(f"• 脉象：{', '.join(findings['pulse_findings'])}")

        # 证候分析
        if diagnosis_result['syndrome_analysis']:
            explanation.append("\n🎯 **证候分析**")
            for i, syndrome in enumerate(diagnosis_result['syndrome_analysis'][:3]):
                explanation.append(f"{i + 1}. {syndrome['syndrome']} (可信度: {syndrome['confidence']:.1f})")

        # 鉴别诊断
        if diagnosis_result['differential_diagnosis']:
            explanation.append("\n🔬 **鉴别诊断**")
            disease_confidence = defaultdict(float)
            for disease in diagnosis_result['differential_diagnosis']:
                disease_confidence[disease['disease']] += disease['confidence']

            sorted_diseases = sorted(disease_confidence.items(), key=lambda x: x[1], reverse=True)
            for i, (disease, confidence) in enumerate(sorted_diseases[:5]):
                disease_name, source_label = disease
                explanation.append(f"{i + 1}. {disease_name} （{source_label}）(综合可信度: {confidence:.1f})")

        # 治疗建议
        if diagnosis_result['treatment_recommendations']:
            treatment = diagnosis_result['treatment_recommendations'][0]
            explanation.append(f"\n💊 **治疗建议**")
            explanation.append(f"• 证候：{treatment['syndrome']}")
            if treatment['formulas']:
                explanation.append(f"• 方剂：{', '.join(treatment['formulas'])}")
            if treatment['herbs']:
                explanation.append(f"• 药材：{', '.join(treatment['herbs'][:10])}")  # 限制显示数量

        # 推理过程
        explanation.append(f"\n🧠 **推理过程**")
        explanation.append(diagnosis_result['reasoning'])

        return '\n'.join(explanation)


# 测试函数
def test_smart_diagnosis():
    """测试智能辨证分析系统"""
    # 创建测试用例
    test_cases = [
        {
            'name': '风寒感冒',
            'description': '患者恶寒发热，头痛身痛，无汗，鼻塞流清涕，舌苔薄白，脉浮紧'
        },
        {
            'name': '风热感冒',
            'description': '患者发热重，微恶风，头痛咽痛，有汗，舌尖红，苔薄黄，脉浮数'
        },
        {
            'name': '脾胃湿热',
            'description': '患者脘腹胀满，食欲不振，恶心呕吐，大便溏薄，舌红苔黄腻，脉濡数'
        }
    ]

    # 初始化系统
    kg_path = "tcm_enhanced_KG.csv"  # 假设这是增强版知识图谱
    if os.path.exists(kg_path):
        diagnosis_system = SmartDiagnosisSystem(kg_path)

        for case in test_cases:
            print(f"\n{'=' * 60}")
            print(f"测试用例：{case['name']}")
            print(f"{'=' * 60}")

            result = diagnosis_system.smart_diagnosis_analysis(case['description'])
            print(diagnosis_system.explain_diagnosis_logic(result))
    else:
        print(f"知识图谱文件 {kg_path} 不存在，请先运行 enhanced_TCMKG.py 构建知识图谱")


if __name__ == '__main__':
    test_smart_diagnosis()