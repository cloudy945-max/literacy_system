import streamlit as st
from db import Database
import openai
import json
import config
import time

openai.api_key = config.API_KEY
openai.api_base = config.BASE_URL

def parse_textbook_content(text, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = openai.chat.completions.create(
                model=config.MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": """你是一个语文知识点提取助手。请从课文中提取颗粒化的知识点，包括生字、词语、重点句子。
每个知识点需要包含：
- content: 内容
- type: 类型（char/word/sentence/poetry）
- pinyin: 拼音（仅对生字和词语）
- difficulty: 难度等级（1-5）

请以JSON数组格式返回结果。"""
                    },
                    {
                        "role": "user",
                        "content": f"请从以下课文中提取知识点：{text}"
                    }
                ],
                timeout=60
            )
            result_text = response.choices[0].message.content
            return json.loads(result_text)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise Exception(f"API调用失败: {str(e)}")

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
    st.write('今日练习任务将在这里显示')

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
