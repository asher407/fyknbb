import threading
import time
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

# 导入已有爬虫
from src.scrap import RealtimeHotScraper

# 设置页面布局为宽屏模式
st.set_page_config(
    page_title="微博热搜数据分析系统",
    page_icon="📊",
    layout="wide",  # 使用宽屏布局
    initial_sidebar_state="expanded",
)

# -------- 页面注册与路由（可扩展） -------- #
PAGES = {}


def register_page(name: str):
    def decorator(func):
        PAGES[name] = func
        return func

    return decorator


# -------- 实时热搜页面 -------- #
@st.cache_resource
def get_realtime_scraper(timeout: int = 30, max_retries: int = 3, delay: float = 1.0):
    """缓存爬虫实例"""
    return RealtimeHotScraper(timeout=timeout, max_retries=max_retries, delay=delay)


@st.cache_data(ttl=300)  # 缓存5分钟
def fetch_realtime_data(
    timeout: int = 30,
    max_retries: int = 3,
    delay: float = 1.0,
    force_refresh: bool = False,
):
    """获取实时热搜数据，缓存5分钟"""
    scraper = get_realtime_scraper(timeout, max_retries, delay)
    # 如果强制刷新，不使用缓存
    return scraper.fetch_realtime_top50(use_cache=not force_refresh)


@register_page("实时热搜 Top50")
def page_realtime_hot():
    st.title("微博实时热搜 Top50")

    # 参数设置（使用 columns 排列）
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        timeout = st.number_input("请求超时(s)", min_value=5, max_value=120, value=30)
    with col_b:
        max_retries = st.number_input(
            "最大重试次数", min_value=1, max_value=10, value=3
        )
    with col_c:
        delay = st.number_input(
            "重试间隔(s)", min_value=0.0, max_value=10.0, value=1.0, step=0.5
        )
    with col_d:
        refresh_btn = st.button("🔄 刷新数据", help="强制刷新热搜数据（忽略缓存）")

    # 自动获取数据或在用户点击刷新时重新获取
    if refresh_btn:
        # 清空缓存并重新获取
        st.cache_data.clear()
        items: List[Dict[str, Any]] = fetch_realtime_data(
            timeout, max_retries, delay, force_refresh=True
        )
    else:
        # 首次加载或显示缓存数据
        placeholder = st.empty()

        # 显示加载提示
        with placeholder.container():
            st.info("⏳ 正在获取实时热搜数据，请稍候…")

        # 后台获取数据
        items = fetch_realtime_data(timeout, max_retries, delay, force_refresh=False)
        placeholder.empty()

    if not items:
        st.error("❌ 未获取到数据。请尝试以下操作：")
        st.markdown("""
        1. 检查网络连接
        2. 稍后重试
        3. 在终端运行：`python -m playwright install chromium`
        4. 或在命令行运行：`python src/scrap.py realtime` 预先获取数据缓存
        """)
        st.info(
            "📝 你也可以在工作目录查看 debug_realtime_page_playwright.html 以检查页面结构。"
        )
        return

    # 获取时间戳
    from datetime import datetime

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.success(f"✅ 成功获取 {len(items)} 条热搜 (更新时间: {current_time})")

    # 展示表格
    df = pd.DataFrame(items)
    display_cols = ["rank", "title"]

    # 使用HTML表格实现美化
    html_table = "<table style='width:100%; border-collapse: collapse;'>"
    html_table += "<thead><tr style='background-color: #f0f0f0;'>"
    html_table += "<th style='text-align:center; padding:10px; border-bottom:2px solid #ddd; font-weight:bold;'>排名</th>"
    html_table += "<th style='text-align:left; padding:10px; border-bottom:2px solid #ddd; font-weight:bold;'>热搜标题</th>"
    html_table += "</tr></thead><tbody>"

    for idx, (_, row) in enumerate(df[display_cols].iterrows()):
        # 交替行颜色
        bg_color = "#fafafa" if idx % 2 == 0 else "white"
        html_table += f"<tr style='background-color: {bg_color};'>"
        html_table += f"<td style='text-align:center; padding:8px; border-bottom:1px solid #eee; font-weight:bold;'>{row['rank']}</td>"
        html_table += f"<td style='text-align:left; padding:8px; border-bottom:1px solid #eee;'>{row['title']}</td>"
        html_table += "</tr>"

    html_table += "</tbody></table>"
    st.markdown(html_table, unsafe_allow_html=True)

    # 分列显示下载和其他选项
    col1, col2, col3 = st.columns(3)

    with col1:
        # 下载 JSON
        import json

        json_bytes = json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            label="📥 下载为 JSON",
            data=json_bytes,
            file_name="weibo_realtime_top50.json",
            mime="application/json",
        )

    with col2:
        # 下载为 CSV
        csv_bytes = (
            df[display_cols].to_csv(index=False, encoding="utf-8-sig").encode("utf-8")
        )
        st.download_button(
            label="📥 下载为 CSV",
            data=csv_bytes,
            file_name="weibo_realtime_top50.csv",
            mime="text/csv",
        )

    with col3:
        # 显示统计信息
        if st.button("📊 显示统计", help="显示更多统计信息"):
            st.subheader("数据统计")
            st.write(f"**总条数**: {len(items)}")
            st.write(f"**排名范围**: {df['rank'].min()} - {df['rank'].max()}")


# -------- 其他页面占位（便于扩展） -------- #
@register_page("历史数据可视化")
def page_history_visualization():
    st.title("历史数据可视化")

    import os
    from pathlib import Path

    # 获取词云图目录
    word_clouds_dir = Path("output/word_clouds")

    if not word_clouds_dir.exists():
        st.error("词云图目录不存在，请先运行数据处理生成词云图")
        return

    # 居中显示选项
    st.markdown("### 📊 词云图查看器")

    # 创建居中的选项区域
    col1, col2, col3, col4, col5 = st.columns([1, 2, 2, 2, 1])

    with col2:
        # 选择类型：关键词或类型
        viz_type = st.selectbox(
            "选择分析维度",
            options=["关键词", "类型"],
            help="关键词：基于热搜标题的词频分析\n类型：基于热搜分类的统计",
        )

    with col3:
        # 获取可用的月份选项
        type_folder = "keywords" if viz_type == "关键词" else "types"
        folder_path = word_clouds_dir / type_folder

        # 扫描可用的图片文件
        available_files = []
        if folder_path.exists():
            available_files = sorted(
                [
                    f.stem
                    for f in folder_path.glob("*.png")
                    if not f.name.startswith("custom_analysis")
                ]
            )

        if not available_files:
            st.warning(f"未找到{viz_type}词云图")
            return

        # 构建月份选项
        month_options = []
        month_display = {}

        for filename in available_files:
            if filename.endswith("2025"):
                display_name = "全年汇总 (2025)"
                month_options.append(filename)
                month_display[filename] = display_name
            elif "Q" in filename:
                quarter = filename.split("-")[-1]
                display_name = f"季度汇总 ({quarter})"
                month_options.append(filename)
                month_display[filename] = display_name
            elif "-" in filename:
                parts = filename.split("_")[-1].split("-")
                if len(parts) == 2:
                    year, month = parts
                    display_name = f"{year}年{month}月"
                    month_options.append(filename)
                    month_display[filename] = display_name

        # 选择月份
        selected_file = st.selectbox(
            "选择时间范围",
            options=month_options,
            format_func=lambda x: month_display.get(x, x),
            help="选择要查看的月份或汇总期间",
        )

    with col4:
        # 添加刷新按钮
        if st.button("🔄 刷新", help="重新加载词云图"):
            st.rerun()

    # 显示词云图
    if selected_file:
        image_path = folder_path / f"{selected_file}.png"

        if image_path.exists():
            # 居中显示词云图
            col_left, col_center, col_right = st.columns([0.5, 3, 0.5])
            with col_center:
                st.image(str(image_path), use_column_width=True)

            # 显示下载按钮
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            st.download_button(
                label="📥 下载词云图",
                data=image_bytes,
                file_name=f"{selected_file}.png",
                mime="image/png",
            )

            # 显示统计信息
            with st.expander("📊 查看其他时间范围", expanded=False):
                # 显示所有可用的时间范围
                st.markdown("#### 可用的词云图：")
                cols = st.columns(4)
                for idx, file in enumerate(month_options):
                    with cols[idx % 4]:
                        if file == selected_file:
                            st.markdown(f"**✓ {month_display[file]}**")
                        else:
                            st.markdown(f"- {month_display[file]}")
        else:
            st.error(f"词云图文件不存在：{image_path}")
    else:
        st.warning("请选择要查看的时间范围")


@register_page("数据处理工具")
def page_tools_placeholder():
    st.title("数据处理工具（占位）")
    st.info("后续可添加清洗、转换与导出工具。")


@register_page("JSON数据分析")
def page_json_analysis():
    st.title("JSON数据分析工具")
    st.markdown("""
    本工具用于分析微博热搜JSON数据，生成统计图表和可视化报告。

    **支持的数据格式：**
    - 原始数据格式（包含 `date`, `count`, `data` 字段）
    - 查询结果格式（包含 `query_time`, `result_count`, `results` 字段）
    - 数据列表格式
    """)

    # 文件上传区域
    st.markdown("### 1. 选择数据文件")
    uploaded_file = st.file_uploader(
        "上传JSON文件", type=["json"], help="选择要分析的JSON数据文件"
    )

    # 或者输入文件路径
    col1, col2 = st.columns(2)
    with col1:
        file_path = st.text_input(
            "或输入文件路径",
            placeholder="例如：data/2025-01/2025-01-01.json",
            help="相对于项目根目录的路径",
        )

    with col2:
        font_name = st.text_input(
            "图表字体", value="Maple Mono NF CN", help="用于图表显示的字体名称"
        )

    # 分析选项
    st.markdown("### 2. 分析选项")
    col3, col4, col5 = st.columns(3)
    with col3:
        generate_charts = st.checkbox("生成图表", value=True)
    with col4:
        generate_report = st.checkbox("生成分析报告", value=True)
    with col5:
        high_resolution = st.checkbox("高分辨率图表", value=True)

    # 执行分析按钮
    st.markdown("### 3. 执行分析")
    analyze_button = st.button("🚀 开始分析", type="primary", use_container_width=True)

    if analyze_button:
        # 确定要分析的文件
        json_file = None
        if uploaded_file is not None:
            # 保存上传的文件到临时位置
            import os
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                json_file = tmp_file.name
                st.info(f"已上传文件: {uploaded_file.name}")
        elif file_path and os.path.exists(file_path):
            json_file = file_path
            st.info(f"使用文件: {file_path}")
        else:
            st.error("请上传文件或输入有效的文件路径")
            return

        if json_file:
            try:
                # 设置字体
                from src.json_analyzer import setup_font

                setup_font(font_name)

                # 执行分析
                with st.spinner("正在分析数据，请稍候..."):
                    from src.json_analyzer import analyze_json

                    # 调用分析函数
                    analyze_json(json_file)

                st.success("✅ 分析完成！")

                # 显示输出信息
                st.markdown("### 4. 分析结果")

                # 获取输出目录（基于文件名）
                import datetime
                from pathlib import Path

                file_name = Path(json_file).stem
                output_dir = Path("output") / f"{file_name}"

                if output_dir.exists():
                    st.info(f"分析结果已保存到: `{output_dir}`")

                    # 列出生成的图表文件
                    png_files = list(output_dir.glob("*.png"))
                    if png_files:
                        st.markdown("**生成的图表：**")
                        cols = st.columns(3)
                        for idx, png_file in enumerate(png_files[:6]):  # 最多显示6个
                            with cols[idx % 3]:
                                st.image(
                                    str(png_file),
                                    caption=png_file.name,
                                    use_column_width=True,
                                )

                        if len(png_files) > 6:
                            st.info(f"还有 {len(png_files) - 6} 个图表未显示")

                    # 检查分析报告
                    report_file = output_dir / "analysis_report.txt"
                    if report_file.exists():
                        with open(report_file, "r", encoding="utf-8") as f:
                            report_content = f.read()

                        with st.expander("📄 查看分析报告", expanded=False):
                            st.text(report_content)

                        # 下载按钮
                        st.download_button(
                            label="📥 下载分析报告",
                            data=report_content,
                            file_name="analysis_report.txt",
                            mime="text/plain",
                        )

                    # 提供下载所有结果的选项
                    st.markdown("**下载所有结果：**")

                    # 创建ZIP文件
                    import io
                    import zipfile

                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(
                        zip_buffer, "w", zipfile.ZIP_DEFLATED
                    ) as zip_file:
                        for file_path in output_dir.glob("*"):
                            if file_path.is_file():
                                zip_file.write(file_path, file_path.name)

                    zip_buffer.seek(0)

                    st.download_button(
                        label="📦 下载所有图表和报告 (ZIP)",
                        data=zip_buffer,
                        file_name=f"analysis_results_{file_name}.zip",
                        mime="application/zip",
                    )

                # 清理临时文件
                if uploaded_file is not None:
                    import os

                    os.unlink(json_file)

            except Exception as e:
                st.error(f"分析过程中出错: {str(e)}")
                import traceback

                with st.expander("查看错误详情"):
                    st.code(traceback.format_exc())

    # 示例数据
    with st.expander("📋 查看示例JSON格式", expanded=False):
        st.code(
            """{
    "date": "2025-01-01",
    "count": 50,
    "data": [
        {
            "rank": 1,
            "title": "示例热搜标题",
            "category": "明星",
            "heat": 1234567.8,
            "reads": 9876543,
            "discussions": 12345,
            "originals": 6789
        }
        // ... 更多数据
    ]
}""",
            language="json",
        )


# -------- 主入口 -------- #
def main():
    st.sidebar.title("功能导航")
    page_name = st.sidebar.selectbox("选择页面", options=list(PAGES.keys()))

    # 添加侧边栏信息
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 项目信息")
    st.sidebar.info("**微博热搜数据分析系统**\n\n实时获取和分析微博热搜趋势")

    st.sidebar.markdown("### 📖 使用说明")
    with st.sidebar.expander("实时热搜", expanded=False):
        st.markdown("""
        - 获取微博实时 Top 50 热搜
        - 支持缓存加速
        - 可下载 JSON 数据
        """)

    with st.sidebar.expander("历史数据可视化", expanded=False):
        st.markdown("""
        - 查看历史词云图
        - 按关键词/类型分析
        - 支持月度/季度/年度
        """)

    with st.sidebar.expander("数据处理", expanded=False):
        st.markdown("""
        - 数据清洗与转换
        - 批量导出工具
        - 自定义分析
        """)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ 系统状态")
    import os
    from pathlib import Path

    # 统计数据
    data_dir = Path("data")
    output_dir = Path("output/word_clouds")

    if data_dir.exists():
        json_files = list(data_dir.glob("**/*.json"))
        st.sidebar.success(f"✓ 已存储 {len(json_files)} 个数据文件")
    else:
        st.sidebar.warning("⚠ 数据目录不存在")

    if output_dir.exists():
        img_files = list(output_dir.glob("**/*.png"))
        st.sidebar.success(f"✓ 已生成 {len(img_files)} 张词云图")
    else:
        st.sidebar.warning("⚠ 词云图目录不存在")

    PAGES[page_name]()


if __name__ == "__main__":
    main()
