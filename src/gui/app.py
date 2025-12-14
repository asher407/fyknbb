import streamlit as st
from typing import List, Dict, Any
import pandas as pd

# 导入已有爬虫
from src.scrap import RealtimeHotScraper

# -------- 页面注册与路由（可扩展） -------- #
PAGES = {}

def register_page(name: str):
    def decorator(func):
        PAGES[name] = func
        return func
    return decorator

# -------- 实时热搜页面 -------- #
@register_page("实时热搜 Top50")
def page_realtime_hot():
    st.title("微博实时热搜 Top50")

    # 参数设置
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        timeout = st.number_input("请求超时(s)", min_value=5, max_value=120, value=30)
    with col_b:
        max_retries = st.number_input("最大重试次数", min_value=1, max_value=10, value=3)
    with col_c:
        delay = st.number_input("重试间隔(s)", min_value=0.0, max_value=10.0, value=1.0, step=0.5)

    run = st.button("获取 Top50")

    if run:
        with st.spinner("正在获取数据…"):
            scraper = RealtimeHotScraper(timeout=timeout, max_retries=max_retries, delay=delay)
            items: List[Dict[str, Any]] = scraper.fetch_realtime_top50()

        if not items:
            st.error("未获取到数据。请稍后重试或检查网络。")
            st.info("你也可以在工作目录查看 debug_realtime_page_playwright.html 以检查页面结构。")
            return

        st.success(f"成功获取 {len(items)} 条")

        # 展示表格（仅排名和标题）
        df = pd.DataFrame(items)

        sort_by = st.selectbox("排序字段", options=["rank", "title"], index=0)
        ascending = st.checkbox("升序", value=True)
        if sort_by in df.columns:
            df = df.sort_values(by=sort_by, ascending=ascending, kind="stable")

        display_cols = ["rank", "title"]
        st.dataframe(df[display_cols], width='stretch')

        # 下载 JSON
        import json
        json_bytes = json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            label="下载为 JSON",
            data=json_bytes,
            file_name="weibo_realtime_top50.json",
            mime="application/json",
        )

# -------- 其他页面占位（便于扩展） -------- #
@register_page("历史数据可视化")
def page_history_placeholder():
    st.title("历史数据可视化（占位）")
    st.info("后续可添加历史数据图表与分析模块。")

@register_page("数据处理工具")
def page_tools_placeholder():
    st.title("数据处理工具（占位）")
    st.info("后续可添加清洗、转换与导出工具。")

# -------- 主入口 -------- #
def main():
    st.sidebar.title("功能导航")
    page_name = st.sidebar.selectbox("选择页面", options=list(PAGES.keys()))
    PAGES[page_name]()

if __name__ == "__main__":
    main()
