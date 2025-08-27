import os
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv
import json
import time


load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 尝试导入增强版TCM系统
ENHANCED_MODE = True  # 设置为True以使用增强版功能
TCM_RAG_APP_LOADED = False
tcm_app_instance = None

if ENHANCED_MODE:
    try:
        from enhanced_GraphRAG import EnhancedTCMGraphRAGApp
        TCM_RAG_APP_LOADED = True
        logger.info("成功导入增强版TCM GraphRAG系统")
    except ImportError as e:
        logger.warning(f"无法导入增强版系统: {e}, 尝试导入原版系统...")
        ENHANCED_MODE = False

# 如果增强版导入失败，尝试导入原版
if not TCM_RAG_APP_LOADED:
    try:
        from GraphRAG import TCMGraphRAGApp
        TCM_RAG_APP_LOADED = True
        logger.info("成功导入原版TCM GraphRAG系统")
    except ImportError as e:
        logger.error(f"无法导入TCMGraphRAGApp: {e}. 请确保GraphRAG.py文件存在且无误。")
        TCMGraphRAGApp = None 


app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app) 

# 初始化TCM应用实例
tcm_app_instance = None

if TCM_RAG_APP_LOADED:
    # 根据模式选择CSV文件路径
    if ENHANCED_MODE:
        csv_path = os.getenv("TCM_CSV_PATH", r"tcm_enhanced_KG.csv")
        app_class = EnhancedTCMGraphRAGApp
    else:
        csv_path = os.getenv("TCM_CSV_PATH", r"tcm_KG.csv")
        app_class = TCMGraphRAGApp
    
    api_key = os.getenv("MOONSHOT_API_KEY")

    if not api_key:
        logger.warning("警告: 未设置 MOONSHOT_API_KEY 环境变量，API 调用将失败。")
    
    if not os.path.exists(csv_path):
        logger.error(f"错误: 知识图谱 CSV 文件 '{csv_path}' 未找到!")
        logger.info(f"提示: 如果使用增强版功能，请先运行 enhanced_TCMKG.py 构建 tcm_enhanced_KG.csv")
    
    if api_key and os.path.exists(csv_path):
        try:
            if ENHANCED_MODE:
                logger.info(f"正在初始化增强版TCM系统，使用 CSV: {csv_path}...")
                tcm_app_instance = EnhancedTCMGraphRAGApp(csv_path=csv_path)
                logger.info("增强版TCM系统初始化成功。")
            else:
                logger.info(f"正在初始化原版TCM系统，使用 CSV: {csv_path}...")
                tcm_app_instance = TCMGraphRAGApp(csv_path=csv_path)
                logger.info("原版TCM系统初始化成功。")
        except Exception as e:
            logger.error(f"TCM系统初始化失败: {e}", exc_info=True)
            tcm_app_instance = None
    else:
        logger.warning("因缺少 CSV 文件、API 密钥，服务核心功能可能受限。")
else:
    logger.error("TCM系统模块未加载，核心聊天功能将不可用。")



def generate_step_by_step_streaming_response(query):
    """
    生成分步流式响应，将"思考过程"暴露给前端。
    支持增强版智能辨证分析功能。
    """
    def yield_json(data):
        """辅助函数，用于生成 SSE 格式的 JSON 数据"""
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    try:
        rag_instance = tcm_app_instance.rag
        
        # 确定系统模式
        mode_title = "🧠 增强版智能辨证分析" if ENHANCED_MODE else "🤔 思考中..."
        yield yield_json({'type': 'thinking_start', 'title': mode_title})

        # 步骤1: 分析问题意图和关键词
        yield yield_json({'type': 'thinking_step', 'step': 1, 'title': '分析问题意图和关键词'})
        extracted_info = rag_instance.extract_keywords_and_intent(query)
        
        intent_text = extracted_info.get('intent', '未知')
        keywords_text = ', '.join(extracted_info.get('keywords', []))
        
        # 增强版系统显示更多信息
        if ENHANCED_MODE and extracted_info.get('is_diagnosis'):
            mode_info = " (智能辨证模式)"
        else:
            mode_info = " (一般查询模式)"
            
        yield yield_json({'type': 'thinking_content', 'step': 1, 'content': f"意图: {intent_text}{mode_info}\n关键词: {keywords_text}"})

        # 步骤2: 查询中医知识图谱
        yield yield_json({'type': 'thinking_step', 'step': 2, 'title': '查询中医知识图谱'})
        relevant_knowledge_items = rag_instance.retrieve_relevant_knowledge(query, extracted_info)
        
        knowledge_summary = f"找到 {len(relevant_knowledge_items)} 条相关知识"
        if ENHANCED_MODE and extracted_info.get('is_diagnosis'):
            diagnosis_items = [item for item in relevant_knowledge_items if item.get('type') == 'diagnosis']
            knowledge_summary += f" (其中 {len(diagnosis_items)} 条辨证相关知识)"
        
        yield yield_json({'type': 'thinking_content', 'step': 2, 'content': knowledge_summary})
        
        context_for_llm = rag_instance._format_knowledge_for_llm(relevant_knowledge_items)
        graphrag_stream = rag_instance.generate_graphrag_response_stream(query, context_for_llm, extracted_info.get('intent', '未知'))
        
        graphrag_response_chunks = []
        for chunk in graphrag_stream:
            graphrag_response_chunks.append(chunk)
            yield yield_json({'type': 'thinking_content', 'step': 2, 'content': chunk})
        graphrag_response = "".join(graphrag_response_chunks)

        # 步骤3: 通用中医知识补充
        yield yield_json({'type': 'thinking_step', 'step': 3, 'title': '通用中医知识补充'})
        general_stream = rag_instance.get_general_kimi_response_stream(query)
        
        general_response_chunks = []
        for chunk in general_stream:
            general_response_chunks.append(chunk)
            yield yield_json({'type': 'thinking_content', 'step': 3, 'content': chunk})
        general_response = "".join(general_response_chunks)

        yield yield_json({'type': 'thinking_end'})

        # 步骤4: 综合分析结果
        answer_title = "💡 智能辨证分析结果" if ENHANCED_MODE and extracted_info.get('is_diagnosis') else "💡 综合分析结果"
        yield yield_json({'type': 'final_answer_start', 'title': answer_title})
        
        final_answer_stream = rag_instance.synthesize_responses(query, graphrag_response, general_response)
        
        for chunk in final_answer_stream:
            yield yield_json({'type': 'final_answer_content', 'content': chunk})
        
        # 增强版免责声明
        if ENHANCED_MODE:
            disclaimer = "\n\n📝 **重要提醒：** 本系统基于增强版中医知识图谱提供智能辨证分析建议，具有可解释性推导过程。但仅供参考学习，不能替代专业中医师诊断。如有健康问题请及时就医。"
        else:
            disclaimer = "\n\n📝 **重要提醒：** 基于GraphRAG得到的知识有精确来源，其他内容仅供参考。注意，OpenTCM不是真正的中医，如需看病请前往医院就诊。"
        
        yield yield_json({'type': 'final_answer_content', 'content': disclaimer})
        yield yield_json({'type': 'final_end'})

    except Exception as e:
        logger.error(f"分步流式响应生成错误: {e}", exc_info=True)
        yield yield_json({
            'type': 'error',
            'content': f"处理您的请求时发生内部错误: {str(e)}"
        })


@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/chat_page')
def chat_ui_page():
    return render_template('chat.html')

@app.route('/api/chat', methods=['GET'])
def handle_chat_api():
    global tcm_app_instance
    if not tcm_app_instance:
        logger.error("API 调用失败：tcm_app_instance 未初始化。")
        
        def error_stream():
            error_data = {'type': 'error', 'content': '服务核心组件未初始化'}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        return Response(error_stream(), mimetype='text/event-stream')

    
    user_query = request.args.get('query')

    if not user_query:
        logger.warning("API 调用错误：缺少 'query' 参数。")
        def error_stream():
            error_data = {'type': 'error', 'content': '查询内容不能为空'}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        return Response(error_stream(), mimetype='text/event-stream')

    logger.info(f"收到用户查询: {user_query}")
    
    return Response(
        generate_step_by_step_streaming_response(user_query), 
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )
    
@app.route('/static/images/<filename>')
def serve_image(filename):
    return send_from_directory(os.path.join(app.static_folder, 'images'), filename)


if __name__ == '__main__':
    logger.info("启动 Flask 开发服务器...")
    app.run(host='0.0.0.0', port=8000, debug=True)
