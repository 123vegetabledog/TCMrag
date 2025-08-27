# -*- coding: utf-8 -*-
"""
增强版GraphRAG系统
整合智能辨证分析功能，支持舌象、脉象、症状的智能辨证
"""

import os
import pandas as pd
import numpy as np
import networkx as nx
from typing import List, Dict, Any, Tuple, Optional, Set, Iterator
import requests
import json
import re
from dotenv import load_dotenv
import time
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
from tqdm import tqdm

from smart_diagnosis import SmartDiagnosisSystem

load_dotenv()

# API配置
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY")
MOONSHOT_API_URL = "https://api.moonshot.cn/v1"
GLM_API_KEY = os.getenv("GLM_API_KEY")
GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4"

# 当前使用的API配置
CURRENT_API_KEY = MOONSHOT_API_KEY
CURRENT_API_URL = MOONSHOT_API_URL
CURRENT_MODEL_NAME = "moonshot-v1-32k"


class EnhancedTCMKnowledgeGraph:
    """增强版中医知识图谱"""

    def __init__(self, csv_path: str = None):
        self.graph = nx.MultiDiGraph()
        self.triples_with_source = []
        self.relation_types = set()
        self.entity_types = {}
        self.diagnosis_system = None

        if csv_path:
            self.load_from_csv(csv_path)

    def _format_knowledge_for_llm(self, knowledge_items: List[Dict]) -> str:
        """为LLM格式化知识"""
        if not knowledge_items:
            return "未找到相关知识。"

        formatted = "相关知识：\n"
        for item in knowledge_items:
            formatted += f"• {item['subject']} {item['predicate']} {item['object']}"
            if item['source']:
                formatted += f"（来源：{item['source']}）"
            formatted += "\n"
        return formatted

    def load_from_csv(self, csv_path: str):
        """从CSV文件加载知识图谱"""
        try:
            df = pd.read_csv(csv_path)
            print(f"成功加载增强版CSV文件，共有{len(df)}条三元组数据")

            required_columns = ['Subject', 'Predicate', 'Object']
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"CSV文件缺少必要的列：{col}")

            for _, row in tqdm(df.iterrows(), total=len(df), desc="构建增强版知识图谱"):
                subject = str(row['Subject']).strip()
                predicate = str(row['Predicate']).strip()
                obj = str(row['Object']).strip()

                source_name = str(row.get('SourceName', '')).strip()
                source_chapter = str(row.get('SourceChapter', '')).strip()
                source_type = str(row.get('SourceType', '')).strip()

                if source_name.lower() == 'nan': source_name = ''
                if source_chapter.lower() == 'nan': source_chapter = ''
                if source_type.lower() == 'nan': source_type = ''

                source_info_str = f"{source_type}-{source_name}"
                if source_chapter:
                    source_info_str += f"-{source_chapter}"

                self.add_triple(subject, predicate, obj, source_name, source_chapter, source_type, source_info_str)

            print(f"成功构建增强版知识图谱，共有{len(self.graph.nodes)}个节点，{len(self.graph.edges)}条边")
            print(f"关系类型：{sorted(list(self.relation_types))}")

            # 初始化智能辨证系统
            self.diagnosis_system = SmartDiagnosisSystem(csv_path)

        except Exception as e:
            print(f"加载CSV文件失败：{e}")
            raise

    def add_triple(self, subject: str, predicate: str, obj: str,
                   source_name: str = "", source_chapter: str = "",
                   source_type: str = "", source_info_str: str = "未知来源"):
        """添加三元组到知识图谱"""
        if not subject or not predicate or not obj:
            return

        self.graph.add_node(subject)
        self.graph.add_node(obj)
        self.graph.add_edge(subject, obj, relation=predicate,
                            source_name=source_name,
                            source_chapter=source_chapter,
                            source_type=source_type,
                            source_info=source_info_str)

        self.triples_with_source.append((subject, predicate, obj, source_info_str))
        self.relation_types.add(predicate)

    def get_diagnosis_related_triples(self) -> List[Tuple]:
        """获取与辨证分析相关的三元组"""
        # 更新辨证相关关系列表，删除旧关系，添加新关系
        diagnosis_relations = {
            '疾病表现症状', '症状伴随症状', '疾病导致舌象', '证候导致舌象',
            '疾病导致脉象', '证候导致脉象', '症状辨证证候', '舌象辨证证候',
            '脉象辨证证候', '综合辨证证候', '证候采用方剂',  # 新增关系
            '方剂组成药材', '药材具有功效'
        }

        related_triples = []
        for s, p, o, source in self.triples_with_source:
            if p in diagnosis_relations:
                related_triples.append((s, p, o, source))

        return related_triples

    def smart_diagnosis_query(self, patient_description: str) -> Dict:
        """智能辨证查询"""
        if not self.diagnosis_system:
            return {"error": "智能辨证系统未初始化"}

        return self.diagnosis_system.smart_diagnosis_analysis(patient_description)

    def get_knowledge_explanation(self, concept: str) -> Dict:
        """获取概念的知识解释"""
        explanations = {
            'related_concepts': [],
            'relations': [],
            'sources': []
        }

        # 查找相关概念
        for neighbor in self.graph.neighbors(concept):
            edge_data = self.graph.get_edge_data(concept, neighbor)
            if edge_data:
                for edge_key, attr in edge_data.items():
                    explanations['related_concepts'].append(neighbor)
                    explanations['relations'].append({
                        'from': concept,
                        'to': neighbor,
                        'relation': attr.get('relation', ''),
                        'source': attr.get('source_info', '')
                    })

        # 查找指向该概念的关系
        for node in self.graph.nodes():
            if node != concept:
                edge_data = self.graph.get_edge_data(node, concept)
                if edge_data:
                    for edge_key, attr in edge_data.items():
                        explanations['related_concepts'].append(node)
                        explanations['relations'].append({
                            'from': node,
                            'to': concept,
                            'relation': attr.get('relation', ''),
                            'source': attr.get('source_info', '')
                        })

        # 去重
        explanations['related_concepts'] = list(set(explanations['related_concepts']))

        return explanations


class EnhancedGraphRAG:
    """增强版GraphRAG系统"""

    def __init__(self, kg_csv_path: str = None):
        self.knowledge_graph = EnhancedTCMKnowledgeGraph(kg_csv_path)
        self.api_key = CURRENT_API_KEY
        self.api_url = CURRENT_API_URL
        self.model_name = CURRENT_MODEL_NAME

    def extract_keywords_and_intent(self, query: str) -> Dict:
        """提取关键词和意图"""
        # 首先判断是否为辨证分析查询
        diagnosis_keywords = ['辨证', '诊断', '症状', '舌象', '脉象', '治疗', '证候']
        is_diagnosis_query = any(keyword in query for keyword in diagnosis_keywords)

        if is_diagnosis_query:
            return {
                'intent': '智能辨证分析',
                'keywords': self._extract_medical_keywords(query),
                'is_diagnosis': True
            }
        else:
            return {
                'intent': '一般知识查询',
                'keywords': self._extract_general_keywords(query),
                'is_diagnosis': False
            }

    def _extract_medical_keywords(self, text: str) -> List[str]:
        """提取医学关键词"""
        keywords = []

        # 症状相关
        symptoms = ['发热', '头痛', '咳嗽', '恶寒', '无汗', '有汗', '鼻塞', '咽痛']
        for symptom in symptoms:
            if symptom in text:
                keywords.append(symptom)

        # 舌象相关
        tongue_patterns = ['舌红', '舌淡', '苔白', '苔黄', '苔腻', '薄苔', '厚苔']
        for pattern in tongue_patterns:
            if pattern in text:
                keywords.append(pattern)

        # 脉象相关
        pulse_patterns = ['脉浮', '脉沉', '脉数', '脉迟', '脉紧', '脉弦', '脉滑']
        for pattern in pulse_patterns:
            if pattern in text:
                keywords.append(pattern)

        return keywords

    def _extract_general_keywords(self, text: str) -> List[str]:
        """提取一般关键词"""
        # 简单的关键词提取
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        return list(set(words))[:10]  # 返回前10个唯一词

    def _format_knowledge_for_llm(self, knowledge_items: List[Dict]) -> str:
        """为LLM格式化知识"""
        if not knowledge_items:
            return "未找到相关知识。"

        formatted = "相关知识：\n"
        for item in knowledge_items:
            formatted += f"• {item['subject']} {item['predicate']} {item['object']}"
            if item['source']:
                formatted += f"（来源：{item['source']}）"
            formatted += "\n"

        return formatted

    def retrieve_relevant_knowledge(self, query: str, extracted_info: Dict) -> List[Dict]:
        """检索相关知识"""
        if extracted_info.get('is_diagnosis'):
            return self._retrieve_diagnosis_knowledge(query, extracted_info)
        else:
            return self._retrieve_general_knowledge(query, extracted_info)

    def _retrieve_diagnosis_knowledge(self, query: str, extracted_info: Dict) -> List[Dict]:
        """检索辨证相关知识"""
        knowledge_items = []

        # 获取辨证相关的三元组
        diagnosis_triples = self.knowledge_graph.get_diagnosis_related_triples()

        # 根据关键词过滤
        keywords = extracted_info.get('keywords', [])
        for s, p, o, source in diagnosis_triples:
            relevance_score = 0
            for keyword in keywords:
                if keyword in s or keyword in p or keyword in o:
                    relevance_score += 1

            if relevance_score > 0:
                knowledge_items.append({
                    'subject': s,
                    'predicate': p,
                    'object': o,
                    'source': source,
                    'relevance_score': relevance_score,
                    'type': 'diagnosis'
                })

        # 按相关性排序
        knowledge_items.sort(key=lambda x: x['relevance_score'], reverse=True)

        return knowledge_items[:20]  # 返回前20条

    def _retrieve_general_knowledge(self, query: str, extracted_info: Dict) -> List[Dict]:
        """检索一般知识"""
        knowledge_items = []
        keywords = extracted_info.get('keywords', [])

        # 在知识图谱中搜索
        for s, p, o, source in self.knowledge_graph.triples_with_source:
            relevance_score = 0
            for keyword in keywords:
                if keyword in s or keyword in p or keyword in o:
                    relevance_score += 1

            if relevance_score > 0:
                knowledge_items.append({
                    'subject': s,
                    'predicate': p,
                    'object': o,
                    'source': source,
                    'relevance_score': relevance_score,
                    'type': 'general'
                })

        # 按相关性排序
        knowledge_items.sort(key=lambda x: x['relevance_score'], reverse=True)

        return knowledge_items[:15]

    def generate_diagnosis_response_stream(self, query: str, knowledge_items: List[Dict]) -> Iterator[str]:
        """生成辨证分析响应流"""
        if not self.knowledge_graph.diagnosis_system:
            yield "抱歉，智能辨证系统未初始化。"
            return

        try:
            # 执行智能辨证分析
            diagnosis_result = self.knowledge_graph.smart_diagnosis_query(query)

            # 生成解释性响应
            explanation = self.knowledge_graph.diagnosis_system.explain_diagnosis_logic(diagnosis_result)

            # 分段返回
            paragraphs = explanation.split('\n\n')
            for paragraph in paragraphs:
                if paragraph.strip():
                    yield paragraph + "\n\n"
                    time.sleep(0.5)  # 模拟流式输出

        except Exception as e:
            yield f"辨证分析过程中出现错误：{str(e)}"

    def generate_general_response_stream(self, query: str, knowledge_items: List[Dict]) -> Iterator[str]:
        """生成一般知识响应流"""
        if not knowledge_items:
            yield "抱歉，未找到相关的中医知识。"
            return

        # 构建知识上下文
        context = "根据中医知识图谱，相关信息如下：\n\n"
        for item in knowledge_items[:10]:  # 限制数量
            context += f"• {item['subject']} {item['predicate']} {item['object']}"
            if item['source']:
                context += f"（来源：{item['source']}）"
            context += "\n"

        # 调用LLM生成回答
        try:
            client = self._get_llm_client()

            prompt = f"""
请基于以下中医知识回答用户的问题。要求：
1. 回答要准确、专业
2. 引用知识图谱中的信息
3. 如果知识不足，请明确说明
4. 回答要通俗易懂

用户问题：{query}

相关知识：
{context}

请给出详细的回答：
"""

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
                stream=True
            )

            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"生成回答时出现错误：{str(e)}"

    def _get_llm_client(self):
        """获取LLM客户端"""
        from openai import OpenAI
        return OpenAI(
            api_key=self.api_key,
            base_url=self.api_url,
            default_headers={"Authorization": f"Bearer {self.api_key}"}
        )

    def generate_graphrag_response_stream(self, query: str, context: str, intent: str) -> Iterator[str]:
        """生成GraphRAG响应流"""
        if intent == '智能辨证分析':
            # 从上下文中提取知识项
            knowledge_items = self._parse_knowledge_context(context)
            return self.generate_diagnosis_response_stream(query, knowledge_items)
        else:
            knowledge_items = self._parse_knowledge_context(context)
            return self.generate_general_response_stream(query, knowledge_items)

    def _parse_knowledge_context(self, context: str) -> List[Dict]:
        """解析知识上下文"""
        # 简单的解析逻辑
        knowledge_items = []
        lines = context.split('\n')

        for line in lines:
            if line.strip().startswith('•'):
                # 解析格式：• subject predicate object (来源：source)
                content = line[1:].strip()
                if '（来源：' in content:
                    main_part, source_part = content.split('（来源：', 1)
                    source = source_part.rstrip('）')
                else:
                    main_part = content
                    source = ''

                # 简单的三元组提取
                parts = main_part.split()
                if len(parts) >= 3:
                    subject = parts[0]
                    predicate = parts[1]
                    object_part = ' '.join(parts[2:])

                    knowledge_items.append({
                        'subject': subject,
                        'predicate': predicate,
                        'object': object_part,
                        'source': source,
                        'relevance_score': 1,
                        'type': 'general'
                    })

        return knowledge_items

    def get_general_kimi_response_stream(self, query: str) -> Iterator[str]:
        """获取通用LLM响应流"""
        try:
            client = self._get_llm_client()

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": query}],
                temperature=0.7,
                max_tokens=1500,
                stream=True
            )

            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"获取通用响应时出现错误：{str(e)}"

    def synthesize_responses(self, query: str, graphrag_response: str, general_response: str) -> Iterator[str]:
        """综合响应"""
        synthesis_prompt = f"""
请综合以下两个回答，为用户提供一个完整、准确的中医知识回答。

用户问题：{query}

基于知识图谱的回答：
{graphrag_response}

通用知识回答：
{general_response}

请给出一个综合性的回答，要求：
1. 优先使用知识图谱中的准确信息
2. 补充通用回答中有价值的内容
3. 确保回答的准确性和完整性
4. 标注信息来源

综合回答：
"""

        try:
            client = self._get_llm_client()

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": synthesis_prompt}],
                temperature=0.3,
                max_tokens=2000,
                stream=True
            )

            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"综合回答时出现错误：{str(e)}"


class EnhancedTCMGraphRAGApp:
    """增强版TCM GraphRAG应用"""

    def __init__(self, csv_path: str = None):
        self.rag = EnhancedGraphRAG(csv_path)
        print("增强版TCM GraphRAG系统初始化完成")

        if csv_path:
            print(f"知识图谱文件：{csv_path}")
        else:
            print("警告：未指定知识图谱文件，某些功能可能受限")

    def process_query(self, query: str) -> Dict:
        """处理查询"""
        result = {
            'query': query,
            'intent_analysis': {},
            'knowledge_retrieval': [],
            'responses': {
                'graphrag': '',
                'general': '',
                'synthesized': ''
            }
        }

        try:
            # 1. 意图分析
            extracted_info = self.rag.extract_keywords_and_intent(query)
            result['intent_analysis'] = extracted_info

            # 2. 知识检索
            relevant_knowledge = self.rag.retrieve_relevant_knowledge(query, extracted_info)
            result['knowledge_retrieval'] = relevant_knowledge

            # 3. 生成上下文
            context_for_llm = self._format_knowledge_for_llm(relevant_knowledge)

            # 4. 生成响应
            graphrag_stream = self.rag.generate_graphrag_response_stream(
                query, context_for_llm, extracted_info.get('intent', '未知')
            )
            graphrag_response = "".join(list(graphrag_stream))
            result['responses']['graphrag'] = graphrag_response

            # 5. 通用响应
            general_stream = self.rag.get_general_kimi_response_stream(query)
            general_response = "".join(list(general_stream))
            result['responses']['general'] = general_response

            # 6. 综合响应
            synthesized_stream = self.rag.synthesize_responses(
                query, graphrag_response, general_response
            )
            synthesized_response = "".join(list(synthesized_stream))
            result['responses']['synthesized'] = synthesized_response

        except Exception as e:
            result['error'] = str(e)

        return result

    def _format_knowledge_for_llm(self, knowledge_items: List[Dict]) -> str:
        """为LLM格式化知识"""
        if not knowledge_items:
            return "未找到相关知识。"

        formatted = "相关知识：\n"
        for item in knowledge_items:
            formatted += f"• {item['subject']} {item['predicate']} {item['object']}"
            if item['source']:
                formatted += f"（来源：{item['source']}）"
            formatted += "\n"

        return formatted


# 测试函数
def test_enhanced_system():
    """测试增强版系统"""
    kg_path = "tcm_enhanced_KG.csv"
    if os.path.exists(kg_path):
        app = EnhancedTCMGraphRAGApp(kg_path)

        test_queries = [
            "患者发热恶寒，头痛身痛，无汗，舌苔薄白，脉浮紧，请进行辨证分析",
            "什么是风寒感冒？",
            "舌红苔黄腻代表什么证候？",
            "麻黄汤的组成和功效是什么？"
        ]

        for query in test_queries:
            print(f"\n{'=' * 60}")
            print(f"测试查询：{query}")
            print(f"{'=' * 60}")

            result = app.process_query(query)
            print("意图分析：", result['intent_analysis'])
            print("检索到的知识条数：", len(result['knowledge_retrieval']))
            print("综合回答：")
            print(result['responses']['synthesized'])
    else:
        print(f"知识图谱文件 {kg_path} 不存在")


if __name__ == '__main__':
    test_enhanced_system()