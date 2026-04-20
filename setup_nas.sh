#!/bin/bash

# 大语文学习系统环境安装脚本
# 适用于ARM架构NAS

echo "开始安装大语文学习系统环境..."

# 检查Python版本
echo "检查Python版本..."
python3 --version

# 创建虚拟环境
echo "创建虚拟环境..."
python3 -m venv venv

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "升级pip..."
pip install --upgrade pip

# 安装依赖
echo "安装依赖包..."
pip install streamlit pandas pillow openai

# 验证安装
echo "验证安装..."
pip list | grep -E "streamlit|pandas|pillow|openai"

echo "环境安装完成！"
echo "使用以下命令启动系统："
echo "source venv/bin/activate && streamlit run app.py"
