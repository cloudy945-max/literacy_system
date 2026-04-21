import streamlit as st
from db import Database

import os
from openai import OpenAI
import json
import config
import time
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm
import qrcode
import io
import base64
from datetime import datetime

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "sk-23e4dbfe8f5747d090c7b9458c24a314"),
    base_url="https://api.deepseek.com/v1",
)

def generate_exercise():
    conn = db.connect()
    cursor = conn.cursor()
    
    # 优先选择错误率高或从未复习的词
    # 1. 从未复习的词
    cursor.execute('''
        SELECT v.id, v.content, v.pinyin, v.type, v.difficulty
        FROM vocabulary v
        LEFT JOIN learning_progress lp ON v.id = lp.vocabulary_id
        WHERE lp.vocabulary_id IS NULL
        ORDER BY v.difficulty DESC
        LIMIT 10
    ''')
    never_reviewed = cursor.fetchall()
    
    # 2. 错误率高的词
    cursor.execute('''
        SELECT v.id, v.content, v.pinyin, v.type, v.difficulty
        FROM vocabulary v
        JOIN learning_progress lp ON v.id = lp.vocabulary_id
        WHERE lp.error_count > 0
        ORDER BY lp.error_count DESC
        LIMIT 10
    ''')
    high_error = cursor.fetchall()
    
    # 3. 其他词
    cursor.execute('''
        SELECT v.id, v.content, v.pinyin, v.type, v.difficulty
        FROM vocabulary v
        LEFT JOIN learning_progress lp ON v.id = lp.vocabulary_id
        ORDER BY RANDOM()
        LIMIT 10
    ''')
    other_words = cursor.fetchall()
    
    # 合并并去重
    all_words = {}
    for word in never_reviewed + high_error + other_words:
        all_words[word[0]] = word
    
    # 取前20个
    selected_words = list(all_words.values())[:20]
    conn.close()
    
    return selected_words

def generate_pdf(exercises, student_name, task_id):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # 注册中文字体
    try:
        pdfmetrics.registerFont(TTFont('SimSun', 'C:/Windows/Fonts/simsun.ttc'))
        font_normal = 'SimSun'
    except:
        font_normal = 'Helvetica'
    
    # 标题
    p.setFont('Helvetica-Bold', 16)
    p.drawString(100, height - 50, 'Literacy Practice Sheet')
    
    # 姓名日期
    p.setFont('Helvetica', 12)
    p.drawString(50, height - 80, f'Name: {student_name}')
    p.drawString(50, height - 95, f'Date: {datetime.now().strftime("%Y-%m-%d")}')
    p.drawString(50, height - 110, f'Task ID: {task_id}')
    
    # 二维码
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(f'task_id:{task_id}')
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save('qr_temp.png')
    p.drawImage('qr_temp.png', width - 100, height - 90, width=60, height=60)
    os.remove('qr_temp.png')
    
    # 练习内容
    p.setFont('Helvetica-Bold', 14)
    p.drawString(50, height - 150, 'Practice Questions:')
    
    y = height - 180
    for i, exercise in enumerate(exercises[:20], 1):
        content = str(exercise[1])
        pinyin = str(exercise[2]) if len(exercise) > 2 else ''
        
        p.setFont('Helvetica', 8)
        p.drawString(50, y, f'{i}.')
        
        p.setFont('Helvetica', 10)
        p.drawString(70, y, pinyin)
        y -= 15
        
        p.setFont(font_normal, 12)
        p.drawString(70, y, content)
        y -= 20
        
        # 下划线
        for _ in range(3):
            p.line(70, y, width - 50, y)
            y -= 15
        
        y -= 10
        
        if y < 100:
            p.showPage()
            y = height - 50
    
    p.save()
    buffer.seek(0)
    return buffer

def parse_textbook_content(text, max_retries=3):
    for attempt in range(max_retries):
        try:
            # --- 核心改进 2：调用方式改为 client ---
            response = client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=[
                    {
                        "role": "system", 
                        "content": "你是一个语文知识点提取助手。请从课文中提取生字、词语、重点句子。必须仅返回JSON数组，不要包含Markdown标签。格式示例：[{\"content\":\"词语\",\"type\":\"word\",\"pinyin\":\"ci yu\",\"difficulty\":2}]"
                    },
                    {
                        "role": "user", 
                        "content": f"请提取：{text}"
                    }
                ],
                timeout=60
            )
            result_text = response.choices[0].message.content
            
            # --- 核心改进 3：防止 Markdown 标签干扰 ---
            if "```" in result_text:
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.split("```")[0].strip()
            
            return json.loads(result_text)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            # 在这里打印出具体的错误，方便我们定位
            st.error(f"详细错误诊断: {type(e).__name__} - {str(e)}")
            raise e

@st.cache_resource
def init_db():
    db = Database()
    db.create_tables()
    return db

db = init_db()

# 设置页面标题
st.title('大语文学习系统')

# 侧边栏导航
st.sidebar.title('导航')
page = st.sidebar.selectbox(
    '选择功能',
    ['今日任务', '上传批改', '进度看板', '后台录入', '数据库状态检查']
)

# 数据库状态检查页面
if page == '数据库状态检查':
    st.header('数据库状态检查')
    tables = db.check_tables()
    
    st.subheader('现有表')
    for table in tables:
        st.write(f'- {table}')
    
    expected_tables = ['vocabulary', 'learning_progress', 'records']
    missing_tables = [table for table in expected_tables if table not in tables]
    
    if not missing_tables:
        st.success('所有必要的表已创建')
    else:
        st.error(f'缺少以下表: {missing_tables}')

# 今日任务页面
elif page == '今日任务':
    st.header('今日任务')
    
    student_name = st.text_input('学生姓名')
    
    if st.button('生成今日练习单', type='primary'):
        if not student_name:
            st.error('请输入学生姓名')
        else:
            with st.spinner('正在生成练习单...'):
                # 生成练习内容
                exercises = generate_exercise()
                
                if not exercises:
                    st.error('没有可用的知识点，请先在后台录入')
                else:
                    # 生成任务ID
                    task_id = f"{student_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # 生成PDF
                    pdf_output = generate_pdf(exercises, student_name, task_id)
                    
                    # 转换为Base64以便下载
                    b64 = base64.b64encode(pdf_output.read()).decode('utf-8')
                    href = f'<a href="data:application/pdf;base64,{b64}" download="练习单_{task_id}.pdf">下载练习单</a>'
                    
                    st.success('练习单生成成功！')
                    st.markdown(href, unsafe_allow_html=True)
                    
                    # 显示练习内容预览
                    st.subheader('练习内容预览')
                    for i, exercise in enumerate(exercises, 1):
                        st.write(f"{i}. {exercise[1]} ({exercise[2]})")

# 上传批改页面
elif page == '上传批改':
    st.header('上传批改')
    st.write('请上传练习照片进行批改')

# 进度看板页面
elif page == '进度看板':
    st.header('进度看板')
    st.write('学习进度数据将在这里显示')

elif page == '后台录入':
    st.header('后台录入')
    
    tab1, tab2 = st.tabs(['课文解析', '手动录入'])
    
    with tab1:
        st.subheader('课文内容解析')
        text_input = st.text_area('粘贴课文内容', height=200, key='text_input')
        
        col1, col2 = st.columns([1, 1])
        with col1:
            parse_btn = st.button('解析课文', type='primary')
        
        if parse_btn:
            if not text_input:
                st.error('请粘贴课文内容')
            elif not config.API_KEY:
                st.error('请在config.py中配置API密钥')
            else:
                with st.spinner('正在解析...'):
                    try:
                        result = parse_textbook_content(text_input)
                        if isinstance(result, dict) and 'knowledge_points' in result:
                            st.session_state['parsed_knowledge'] = result['knowledge_points']
                        elif isinstance(result, list):
                            st.session_state['parsed_knowledge'] = result
                        else:
                            st.error('解析结果格式不正确')
                    except Exception as e:
                        st.error(f"解析失败: {str(e)}")
        
        if 'parsed_knowledge' in st.session_state and st.session_state['parsed_knowledge']:
            st.subheader('预览解析结果（勾选要保存的内容）')
            
            col_grade, col_unit = st.columns([1, 1])
            with col_grade:
                save_grade = st.selectbox('选择年级', [2, 4], key='save_grade')
            with col_unit:
                save_unit = st.number_input('选择单元', 1, 10, 1, key='save_unit')
            
            selected_items = []
            for i, item in enumerate(st.session_state['parsed_knowledge']):
                with st.container():
                    col1, col2 = st.columns([0.1, 0.9])
                    with col1:
                        is_selected = st.checkbox('', key=f'select_{i}', value=True)
                    with col2:
                        st.write(f"**{item.get('content', '')}**")
                        cols = st.columns([1, 1, 1, 1])
                        cols[0].write(f"拼音: {item.get('pinyin', '-')}")
                        cols[1].write(f"类型: {item.get('type', '-')}")
                        cols[2].write(f"难度: {item.get('difficulty', '-')}")
                        cols[3].write(f"解释: {item.get('explanation', '-')}")
                        st.divider()
                    
                    if is_selected:
                        item['idx'] = i
                        selected_items.append(item)
            
            st.session_state['selected_knowledge'] = selected_items
            st.success(f'已选择 {len(selected_items)} 个知识点')
            
            if st.button('保存到数据库', type='primary'):
                if 'selected_knowledge' in st.session_state:
                    conn = db.connect()
                    cursor = conn.cursor()
                    
                    for item in st.session_state['selected_knowledge']:
                        cursor.execute(
                            "INSERT INTO vocabulary (grade, unit, content, pinyin, type, difficulty, knowledge_unit) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (save_grade, save_unit, item['content'], item.get('pinyin', ''), item.get('type', 'word'), item.get('difficulty', 3), 'default')
                        )
                    
                    conn.commit()
                    db.close()
                    st.success(f'已保存 {len(st.session_state["selected_knowledge"])} 个知识点到数据库')
                    del st.session_state['parsed_knowledge']
                    del st.session_state['selected_knowledge']
                    st.rerun()
    
    with tab2:
        st.subheader('手动录入知识点')
        with st.form('manual_input'):
            content = st.text_input('词语/内容 *')
            pinyin = st.text_input('拼音')
            type_ = st.selectbox('类型', ['char', 'word', 'sentence', 'poetry'])
            difficulty = st.slider('难度', 1, 5, 3)
            grade = st.selectbox('年级', [2, 4])
            unit = st.number_input('单元', 1, 10, 1)
            knowledge_unit = st.text_input('知识单元', 'default')
            
            submitted = st.form_submit_button('添加知识点')
            if submitted:
                if not content:
                    st.error('请输入内容')
                else:
                    conn = db.connect()
                    cursor = conn.cursor()
                    
                    cursor.execute(
                        "INSERT INTO vocabulary (grade, unit, content, pinyin, type, difficulty, knowledge_unit) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (grade, unit, content, pinyin, type_, difficulty, knowledge_unit)
                    )
                    
                    conn.commit()
                    db.close()
                    st.success('知识点已添加')
