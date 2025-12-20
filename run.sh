#!/bin/bash

# 快速启动脚本 - 微博爬虫与数据分析系统
# 默认启动GUI版本

set -e

echo "========================================="
echo "微博爬虫与数据分析系统 - 快速启动"
echo "========================================="

# 检查Python版本
echo "检查Python环境..."
python_version=$(python3 --version 2>/dev/null || echo "none")
if [[ $python_version == "none" ]]; then
    echo "错误: 未找到python3，请先安装Python 3.8或更高版本"
    exit 1
fi
echo "Python版本: $python_version"

# 检查虚拟环境
if [[ -z "$VIRTUAL_ENV" ]] && [[ -z "$CONDA_PREFIX" ]]; then
    echo "提示: 建议使用虚拟环境运行本项目"
    echo "可以运行以下命令创建虚拟环境:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
fi

# 检查依赖是否安装
echo "检查依赖..."
missing_deps=()
for dep in streamlit requests bs4 jieba snownlp wordcloud matplotlib pandas numpy playwright networkx plotly; do
    if ! python3 -c "import $dep" 2>/dev/null; then
        missing_deps+=($dep)
    fi
done

if [[ ${#missing_deps[@]} -gt 0 ]]; then
    echo "警告: 以下依赖未安装: ${missing_deps[*]}"
    echo "建议先安装依赖: pip install -r requirements.txt"
    read -p "是否现在安装依赖? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "正在安装依赖..."
        pip install -r requirements.txt
    else
        echo "跳过依赖安装，如果启动失败请手动安装依赖"
    fi
fi

# 检查playwright浏览器
echo "检查playwright浏览器..."
if python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    if ! python3 -c "
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        browser.close()
except:
    exit(1)
" 2>/dev/null; then
        echo "提示: playwright浏览器未安装，实时热搜功能可能受限"
        echo "如果需要实时热搜功能，请运行: python -m playwright install chromium"
    fi
fi

# 检查数据目录
echo "检查数据目录..."
if [[ ! -d "data_processed" ]]; then
    echo "提示: 未找到已处理的数据目录 (data_processed)"
    echo "部分功能可能需要预先爬取的数据"
    echo "如果需要爬取数据，请运行: python3 src/main.py scrape"
fi

# 启动GUI
echo ""
echo "========================================="
echo "启动图形用户界面..."
echo "如果浏览器没有自动打开，请访问 http://localhost:8501"
echo "按 Ctrl+C 停止服务"
echo "========================================="

# 运行streamlit
python3 -m streamlit run src/gui/app.py
