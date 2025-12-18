import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# 兼容在不同工作目录下运行 Streamlit：确保项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入已有爬虫（兼容不同工作目录）
try:
    from src.scrap import RealtimeHotScraper
except ModuleNotFoundError:
    ALT_SRC = PROJECT_ROOT / "src"
    if str(ALT_SRC) not in sys.path:
        sys.path.insert(0, str(ALT_SRC))
    from scrap import RealtimeHotScraper

# 导入json_analyzer模块
try:
    from src.json_analyzer import (
        analyze_data,
        analyze_json,
        basic_analysis,
        load_json_data,
        setup_font,
    )
except ModuleNotFoundError:
    from json_analyzer import (
        analyze_data,
        analyze_json,
        basic_analysis,
        load_json_data,
        setup_font,
    )

# 导入DataQuery模块
try:
    from src.data_query import DataQuery
except ModuleNotFoundError:
    from data_query import DataQuery

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


@st.cache_resource
def get_data_query():
    """缓存DataQuery实例"""
    return DataQuery()


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


# -------- 单日数据分析页面 -------- #
@register_page("单日热搜分析 ")
def page_daily_analysis():
    st.title("单日热搜数据分析")

    # 选择日期
    data_processed_dir = Path("data_processed")

    if not data_processed_dir.exists():
        st.error("data_processed 目录不存在")
        return

    # 获取所有可用的日期
    available_dates = []
    for year_folder in sorted(data_processed_dir.glob("202*")):
        for json_file in sorted(year_folder.glob("*.json")):
            date_str = json_file.stem
            available_dates.append((date_str, str(json_file)))

    if not available_dates:
        st.error("没有可用的数据文件")
        return

    # 选择日期
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_date, json_path = st.selectbox(
            "选择分析日期", options=available_dates, format_func=lambda x: x[0]
        )

    with col2:
        analysis_button = st.button(
            "🔄 生成分析", help="调用 json_analyzer 生成完整分析图表"
        )

    with col3:
        if st.button("🔃 刷新", help="刷新页面"):
            st.rerun()

    # 当点击生成分析按钮时
    if analysis_button:
        with st.spinner("正在生成分析..."):
            try:
                import io
                from contextlib import redirect_stdout

                # 捕获 analyze_json 的输出
                f = io.StringIO()
                with redirect_stdout(f):
                    analyze_json(json_path)

                output_log = f.getvalue()
                st.success("✅ 分析完成！")

                # 显示输出日志
                with st.expander("📋 分析日志"):
                    st.code(output_log, language="text")

            except Exception as e:
                st.error(f"分析失败: {str(e)}")
                import traceback

                st.error(traceback.format_exc())
                return

    # 显示生成的分析结果
    from datetime import datetime

    # 构造输出目录路径
    date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
    output_dir = Path("output") / selected_date

    if not output_dir.exists():
        st.info("👉 请先点击 '🔄 生成分析' 按钮来生成分析结果")
        return

    # 查找所有生成的 PNG 图表
    chart_files = sorted(output_dir.glob("*.png"))

    if not chart_files:
        st.warning("没有生成的图表")
        return

    # 创建选项卡显示各个图表
    st.markdown("### 📊 分析图表")

    # 为每个图表创建选项卡
    if len(chart_files) > 0:
        tabs = st.tabs(
            [
                f.stem.replace(f"{selected_date}_", "").replace("_", " ")
                for f in chart_files
            ]
        )

        for tab, chart_file in zip(tabs, chart_files):
            with tab:
                # 直接使用文件路径显示图片，避免字节流解码问题
                st.image(
                    str(chart_file), use_column_width=True, caption=chart_file.name
                )

                # 提供下载按钮（读取字节供下载）
                try:
                    with open(chart_file, "rb") as f:
                        image_data = f.read()
                    st.download_button(
                        f"📥 下载 {chart_file.name}",
                        data=image_data,
                        file_name=chart_file.name,
                        mime="image/png",
                    )
                except Exception as e:
                    st.warning(f"无法提供下载：{e}")

    # 显示分析报告
    report_file = output_dir / "analysis_report.txt"
    if report_file.exists():
        st.markdown("### 📄 分析报告")
        with open(report_file, "r", encoding="utf-8") as f:
            report_content = f.read()

        with st.expander("展开查看完整报告"):
            st.text(report_content)

        # 提供报告下载
        st.download_button(
            "📥 下载分析报告",
            data=report_content.encode("utf-8"),
            file_name=f"{selected_date}_analysis_report.txt",
            mime="text/plain",
        )


# -------- 关键词共现网络页面 -------- #
@register_page("年度关键词网络")
def page_keyword_network():
    st.title("关键词共现网络分析")

    network_data_dir = Path("output/word_networks/data")

    if not network_data_dir.exists():
        st.error("网络数据目录不存在，请先运行 word_network.py")
        return

    # 获取可用的网络数据
    available_networks = []
    for json_file in sorted(network_data_dir.glob("nodes_*.json")):
        year = json_file.stem.replace("nodes_", "")
        available_networks.append(year)

    if not available_networks:
        st.error("没有可用的网络数据")
        return

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_year = st.selectbox(
            "选择年份", options=available_networks, format_func=lambda x: f"{x} 年"
        )

    with col2:
        if st.button("🔄 刷新", help="重新加载数据"):
            st.rerun()

    # 加载节点和边数据
    try:
        with open(
            network_data_dir / f"nodes_{selected_year}.json", "r", encoding="utf-8"
        ) as f:
            nodes_data = json.load(f)

        with open(
            network_data_dir / f"edges_{selected_year}.json", "r", encoding="utf-8"
        ) as f:
            edges_data = json.load(f)
    except Exception as e:
        st.error(f"加载失败: {e}")
        return

    # ========== TAB 视图 ==========
    tab1, tab2, tab3 = st.tabs(["🖼️ 网络图", "📊 统计", "📋 数据表"])

    with tab1:
        st.subheader("关键词共现网络可视化")

        # 显示网络图
        network_img_path = (
            Path("output/word_networks/figures")
            / f"keyword_network_{selected_year}.png"
        )
        if network_img_path.exists():
            st.image(str(network_img_path), use_column_width=True)

            with open(network_img_path, "rb") as f:
                st.download_button(
                    "📥 下载网络图",
                    f.read(),
                    f"keyword_network_{selected_year}.png",
                    "image/png",
                )
        else:
            st.warning("网络图文件不存在")

    with tab2:
        st.subheader("网络统计")

        nodes_count = len(nodes_data)
        edges_count = len(edges_data)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("节点数（关键词）", nodes_count)

        with col2:
            st.metric("边数（共现关系）", edges_count)

        with col3:
            if edges_count > 0:
                avg_cooccur = np.mean([e["weight"] for e in edges_data])
                st.metric("平均共现度", f"{avg_cooccur:.2f}")
            else:
                st.metric("平均共现度", "0")

        with col4:
            if nodes_count > 0:
                avg_freq = np.mean([n["frequency"] for n in nodes_data])
                st.metric("平均关键词频次", f"{avg_freq:.2f}")
            else:
                st.metric("平均关键词频次", "0")

        # 频次TOP 10
        import plotly.express as px

        top_nodes = sorted(nodes_data, key=lambda x: x["frequency"], reverse=True)[:10]

        fig = px.bar(
            x=[n["frequency"] for n in top_nodes],
            y=[n["keyword"] for n in top_nodes],
            orientation="h",
            title="关键词频次 Top 10",
            color=[n["frequency"] for n in top_nodes],
            color_continuous_scale="Viridis",
        )
        fig.update_yaxes(automargin=True)
        st.plotly_chart(fig, use_container_width=True)

        # 共现度最高的关系
        top_edges = sorted(edges_data, key=lambda x: x["weight"], reverse=True)[:10]

        edge_labels = [f"{e['source']} - {e['target']}" for e in top_edges]
        edge_weights = [e["weight"] for e in top_edges]

        fig = px.bar(
            x=edge_weights,
            y=edge_labels,
            orientation="h",
            title="共现关系 Top 10",
            color=edge_weights,
            color_continuous_scale="Reds",
        )
        fig.update_yaxes(automargin=True)
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("节点和边数据")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 关键词节点")
            nodes_df = pd.DataFrame(nodes_data).sort_values(
                "frequency", ascending=False
            )
            st.dataframe(nodes_df, use_container_width=True, height=400)

            csv = nodes_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8")
            st.download_button(
                "📥 下载节点数据", csv, f"nodes_{selected_year}.csv", "text/csv"
            )

        with col2:
            st.markdown("#### 共现关系")
            edges_df = pd.DataFrame(edges_data).sort_values("weight", ascending=False)
            st.dataframe(edges_df, use_container_width=True, height=400)

            csv = edges_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8")
            st.download_button(
                "📥 下载边数据", csv, f"edges_{selected_year}.csv", "text/csv"
            )


# -------- 2025年度报告页面 -------- #
@register_page("2025年度报告")
def page_annual_report():
    st.title("2025年度微博热搜分析报告")

    # 导入年度报告模块
    try:
        from src.annual_report import generate_annual_report
    except ImportError:
        from annual_report import generate_annual_report

    # 设置字体
    try:
        from src.json_analyzer import setup_font

        setup_font()
    except:
        pass

    # 标签页
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 数据总览", "📈 热搜排名", "🔗 关键词分析", "📅 时间分布"]
    )

    # 生成年度报告
    with st.spinner("正在生成年度报告..."):
        report = generate_annual_report("data")

    if "error" in report:
        st.error(f"报告生成失败: {report['error']}")
        st.info("请确保 data 目录中有 JSON 数据文件")
        return

    summary = report.get("summary", {})

    # Tab 1: 数据总览
    with tab1:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "📊 总记录数", f"{summary.get('total_records', 0):,}", delta="条热搜"
            )

        with col2:
            st.metric(
                "🎯 独特标题", f"{summary.get('total_unique_titles', 0):,}", delta="个"
            )

        with col3:
            heat_stats = summary.get("heat_stats", {})
            st.metric(
                "🔥 平均热度",
                f"{heat_stats.get('mean', 0):.1f}",
                delta=f"中位数: {heat_stats.get('median', 0):.1f}",
            )

        with col4:
            date_range = summary.get("date_range", {})
            st.metric(
                "📅 统计周期",
                f"{date_range.get('start', 'N/A')} ~ {date_range.get('end', 'N/A')}",
                delta="共计",
            )

        st.divider()

        # 热度统计详情
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🔥 热度统计详情")
            heat_stats = summary.get("heat_stats", {})

            stats_table = pd.DataFrame(
                {
                    "指标": ["最高热度", "最低热度", "平均热度", "中位数", "标准差"],
                    "数值": [
                        f"{heat_stats.get('max', 0):.1f}",
                        f"{heat_stats.get('min', 0):.1f}",
                        f"{heat_stats.get('mean', 0):.1f}",
                        f"{heat_stats.get('median', 0):.1f}",
                        f"{heat_stats.get('std', 0):.1f}",
                    ],
                }
            )

            st.dataframe(stats_table, use_container_width=True, hide_index=True)

        with col2:
            st.subheader("📅 时间分布")
            temporal_dist = report.get("temporal_distribution", {})

            if temporal_dist:
                # 创建时间分布图
                months = sorted(temporal_dist.keys())
                counts = [temporal_dist[m] for m in months]

                import plotly.express as px

                fig = px.line(
                    x=months,
                    y=counts,
                    markers=True,
                    title="每月热搜数量趋势",
                    labels={"x": "月份", "y": "热搜数量"},
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

    # Tab 2: 热搜排名
    with tab2:
        st.subheader("🏆 全年热度最高的10条热搜")

        top_titles = summary.get("top_10_titles", [])

        if top_titles:
            # 创建排名表
            rank_data = []
            for i, item in enumerate(top_titles, 1):
                rank_data.append(
                    {
                        "排名": i,
                        "标题": item.get("title", ""),
                        "热度": f"{item.get('heat', 0):.1f}",
                        "在榜排名": item.get("rank", "N/A"),
                    }
                )

            df_top = pd.DataFrame(rank_data)
            st.dataframe(df_top, use_container_width=True, hide_index=True)

            # 热度柱状图
            import plotly.express as px

            fig = px.bar(
                x=list(range(1, len(top_titles) + 1)),
                y=[item.get("heat", 0) for item in top_titles],
                labels={"x": "排名", "y": "热度值"},
                title="热度排名前10的热搜",
                color=[item.get("heat", 0) for item in top_titles],
                color_continuous_scale="Reds",
                text=[item.get("title", "")[:20] for item in top_titles],
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无热搜排名数据")

    # Tab 3: 关键词分析
    with tab3:
        st.subheader("🔑 关键词频率分析")

        keyword_freq = summary.get("keyword_frequency", {})

        if keyword_freq:
            # 关键词排行
            col1, col2 = st.columns([2, 1])

            with col1:
                # 热力图
                import plotly.express as px

                top_keywords = dict(
                    sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:20]
                )

                fig = px.bar(
                    x=list(top_keywords.values()),
                    y=list(top_keywords.keys()),
                    orientation="h",
                    title="关键词频率 Top 20",
                    labels={"x": "出现次数", "y": "关键词"},
                    color=list(top_keywords.values()),
                    color_continuous_scale="Viridis",
                )
                fig.update_yaxes(automargin=True)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.metric("总关键词数", len(keyword_freq))
                st.metric(
                    "最频繁关键词",
                    max(keyword_freq, key=keyword_freq.get) if keyword_freq else "N/A",
                )
                st.metric("最高频率", max(keyword_freq.values()) if keyword_freq else 0)

            # 关键词表
            st.markdown("#### 📋 关键词列表")
            keyword_df = pd.DataFrame(
                [
                    {"关键词": k, "频率": v}
                    for k, v in sorted(
                        keyword_freq.items(), key=lambda x: x[1], reverse=True
                    )
                ]
            )
            st.dataframe(keyword_df, use_container_width=True, height=400)
        else:
            st.info("暂无关键词数据")

        # 关键词网络
        st.markdown("---")
        st.subheader("🔗 关键词共现网络")

        keyword_network = report.get("keyword_network", {})

        if keyword_network:
            st.info(f"共检测到 {len(keyword_network)} 个核心关键词节点")

            # 显示网络数据
            network_data = []
            for keyword, related in keyword_network.items():
                network_data.append(
                    {
                        "中心词": keyword,
                        "相关词": ", ".join(related),
                        "连接数": len(related),
                    }
                )

            df_network = pd.DataFrame(network_data).sort_values(
                "连接数", ascending=False
            )
            st.dataframe(df_network, use_container_width=True, hide_index=True)
        else:
            st.info("暂无关键词网络数据")

    # Tab 4: 时间分布
    with tab4:
        st.subheader("📅 按时间分布统计")

        temporal_dist = report.get("temporal_distribution", {})

        if temporal_dist:
            col1, col2 = st.columns([2, 1])

            with col1:
                # 月度分布表
                months = sorted(temporal_dist.keys())
                month_data = [{"月份": m, "热搜数": temporal_dist[m]} for m in months]

                df_temporal = pd.DataFrame(month_data)
                st.dataframe(df_temporal, use_container_width=True, hide_index=True)

            with col1:
                # 累积图
                import plotly.graph_objects as go

                cumulative = np.cumsum([temporal_dist[m] for m in months])

                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=months,
                        y=cumulative,
                        mode="lines+markers",
                        fill="tozeroy",
                        name="累积热搜数",
                    )
                )
                fig.update_layout(
                    title="热搜数累积趋势",
                    xaxis_title="月份",
                    yaxis_title="累积数量",
                    hovermode="x unified",
                )
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.metric("平均月度", f"{np.mean(list(temporal_dist.values())):.0f}")
                st.metric("最高月份", f"{max(temporal_dist.values())}")
                st.metric("最低月份", f"{min(temporal_dist.values())}")
        else:
            st.info("暂无时间分布数据")

    # 底部下载报告
    st.divider()
    st.markdown("### 💾 导出报告")

    col1, col2 = st.columns(2)

    with col1:
        # 导出 JSON
        json_report = json.dumps(report, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 下载完整报告 (JSON)",
            data=json_report.encode("utf-8"),
            file_name="annual_report_2025.json",
            mime="application/json",
        )

    with col2:
        # 导出简要文本
        text_report = f"""
2025年度微博热搜分析报告
{"=" * 60}

生成时间: {report.get("report_date", "N/A")}

【数据概览】
总热搜记录数: {summary.get("total_records", 0)} 条
独特热搜数: {summary.get("total_unique_titles", 0)} 个
统计时间: {summary.get("date_range", {}).get("start", "N/A")} ~ {summary.get("date_range", {}).get("end", "N/A")}

【热度统计】
最高热度: {summary.get("heat_stats", {}).get("max", 0):.1f}
最低热度: {summary.get("heat_stats", {}).get("min", 0):.1f}
平均热度: {summary.get("heat_stats", {}).get("mean", 0):.1f}
中位数: {summary.get("heat_stats", {}).get("median", 0):.1f}

【Top10热搜】
"""
        for i, item in enumerate(summary.get("top_10_titles", []), 1):
            text_report += (
                f"{i}. {item.get('title', 'N/A')} (热度: {item.get('heat', 0):.1f})\n"
            )

        st.download_button(
            label="📥 下载简要报告 (TXT)",
            data=text_report.encode("utf-8"),
            file_name="annual_report_2025_summary.txt",
            mime="text/plain",
        )


# -------- 词云图可视化页面 -------- #
@register_page("词云图可视化")
def page_word_cloud_visualization():
    st.title("词云图可视化")

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


# -------- 去年今日页面 -------- #
@register_page("去年今日")
def page_random_hot_today():
    st.title("去年今日")
    st.markdown("""
    从历史数据中随机找出与今天日期相同或相近（年份不同）且热度较高的热搜。

    **筛选条件：**
    - 📆 日期：与今天相同的月日（跨越不同年份）
    - 🔥 热度：大于 1 的条目
    """)

    # 导入模块
    try:
        from src.random_hot_today import RandomHotToday
    except ImportError:
        from random_hot_today import RandomHotToday

    # 创建两列布局
    col1, col2 = st.columns([3, 1])

    with col2:
        if st.button("🎲 换一条", type="primary", use_container_width=True):
            st.session_state.random_hot_today_cache = None

    with col1:
        st.markdown("### 查找数据")

    # 缓存数据以避免重复查询
    if "random_hot_today_cache" not in st.session_state:
        st.session_state.random_hot_today_cache = None

    # 执行查询
    with st.spinner("正在从历史数据中查找..."):
        try:
            random_today = RandomHotToday()

            # 加载并筛选数据
            matching_items = random_today.load_and_filter_data()

            if not matching_items:
                st.warning("❌ 未找到符合条件的数据")
                st.info("💡 请确保已加载足够的历史数据")
                return

            # 随机选择一条
            selected_item = random_today.select_random_item(matching_items)

            if selected_item:
                st.session_state.random_hot_today_cache = selected_item
            else:
                st.error("未能选择数据")
                return

        except Exception as e:
            st.error(f"❌ 加载数据失败: {str(e)}")
            import traceback

            with st.expander("查看错误详情"):
                st.code(traceback.format_exc())
            return

    # 显示选中的数据
    item = st.session_state.random_hot_today_cache
    if item:
        # 获取数据
        title = item.get("title", "N/A")
        rank = item.get("rank", "N/A")
        date = item.get("date", "N/A")
        heat = item.get("heat", 0)
        category = item.get("category", "")
        reads = item.get("reads", 0)
        discussions = item.get("discussions", 0)
        originals = item.get("originals", 0)

        # 创建卡片展示
        st.markdown("---")
        st.markdown("### 🏆 选中的热搜")

        # 主标题区域
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"#### {title}")
        with col2:
            st.metric("热度", f"{heat:.2f}")

        # 详细信息表格
        info_data = {
            "📅 日期": str(date),
            "🏅 排名": str(rank),
            "🏷️  分类": category if category else "未分类",
            "📖 阅读量": f"{reads:.0f}" if reads else "N/A",
            "💬 讨论量": f"{discussions:.0f}" if discussions else "N/A",
            "✍️  原创量": f"{originals:.0f}" if originals else "N/A",
        }

        # 两列显示
        col1, col2 = st.columns(2)
        with col1:
            for key in list(info_data.keys())[:3]:
                st.markdown(f"**{key}** {info_data[key]}")
        with col2:
            for key in list(info_data.keys())[3:]:
                st.markdown(f"**{key}** {info_data[key]}")

        st.markdown("---")

        # 统计信息
        st.markdown("### 📊 数据统计")

        # 四个指标卡
        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric("热度排名", f"#{rank}", delta=None)
        with metric_cols[1]:
            st.metric("热度值", f"{heat:.1f}", delta="相对参考")
        with metric_cols[2]:
            st.metric(
                "阅读量", f"{reads / 1000:.1f}K" if reads >= 1000 else f"{reads:.0f}"
            )
        with metric_cols[3]:
            st.metric("讨论热度", f"{discussions:.1f}")

        # 导出选项
        st.markdown("### 💾 导出数据")

        col1, col2, col3 = st.columns(3)

        with col1:
            # JSON 导出
            json_str = json.dumps(item, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 JSON 格式",
                data=json_str.encode("utf-8"),
                file_name=f"hot_today_{date}.json",
                mime="application/json",
            )

        with col2:
            # CSV 导出
            import csv
            import io

            csv_buffer = io.StringIO()
            writer = csv.DictWriter(csv_buffer, fieldnames=item.keys())
            writer.writeheader()
            writer.writerow(item)
            csv_data = csv_buffer.getvalue()

            st.download_button(
                label="📥 CSV 格式",
                data=csv_data.encode("utf-8"),
                file_name=f"hot_today_{date}.csv",
                mime="text/csv",
            )

        with col3:
            # 文本导出
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            text_output = f"""去年今日 - {date}
{"=" * 50}

标题: {title}
排名: #{rank}
分类: {category if category else "未分类"}

热度数据:
- 热度值: {heat:.2f}
- 阅读量: {reads:.0f}
- 讨论量: {discussions:.0f}
- 原创量: {originals:.0f}

生成时间: {current_time}
"""
            st.download_button(
                label="📥 文本格式",
                data=text_output.encode("utf-8"),
                file_name=f"hot_today_{date}.txt",
                mime="text/plain",
            )

        # 相关信息
        st.markdown("---")
        st.markdown("### ℹ️  说明")
        st.info("""
        💡 **如何使用这个页面：**

        1. **查看内容**：页面会从历史数据中随机选择一条与今天日期相同/相近的热搜
        2. **刷新数据**：点击"换一条"按钮重新抽取一条
        3. **导出数据**：支持 JSON、CSV 和 TXT 格式导出
        4. **数据来源**：来自历史热搜数据，可能来自去年或更早的相同日期
        """)


# -------- 高级数据查询页面 -------- #
@register_page("高级数据查询")
def page_advanced_query():
    st.title("高级数据查询系统")
    st.markdown("""
        本工具提供多条件数据查询功能，支持日期范围、分类筛选、热度范围、排序等多种条件。
        查询结果将自动保存为JSON文件，并进行数据分析生成可视化图表。
        """)

    # 创建查询器实例
    query = get_data_query()

    # ========== 查询条件设置 ==========
    st.markdown("### 1. 查询条件设置")

    # 使用多列布局
    col1, col2 = st.columns(2)

    with col1:
        # 日期范围
        st.markdown("#### 📅 日期范围")
        date_start = st.text_input(
            "开始日期 (YYYY-MM-DD)", value="2025-01-01", help="例如: 2025-01-01"
        )
        date_end = st.text_input(
            "结束日期 (YYYY-MM-DD)", value="2025-01-31", help="例如: 2025-01-31"
        )

        # 分类筛选
        st.markdown("#### 🏷️ 分类筛选")
        categories_input = st.text_input(
            "分类 (多个用逗号分隔)",
            placeholder="明星,综艺,影视",
            help="例如: 明星,综艺 或留空表示不过滤",
        )

        # 标题关键词
        st.markdown("#### 🔍 标题关键词")
        title_keywords_input = st.text_input(
            "标题关键词 (多个用逗号分隔)",
            placeholder="新年,春晚,电影",
            help="包含任一关键词的标题都会被选中",
        )

    with col2:
        # 排名范围
        st.markdown("#### 🏆 排名范围")
        rank_min = st.number_input("最小排名", min_value=1, max_value=50, value=1)
        rank_max = st.number_input("最大排名", min_value=1, max_value=50, value=50)

        # 热度范围
        st.markdown("#### 🔥 热度范围")
        heat_min = st.number_input("最小热度", min_value=0.0, value=0.0, step=100.0)
        heat_max = st.number_input(
            "最大热度", min_value=0.0, value=10000000.0, step=1000.0
        )

        # 阅读量范围
        st.markdown("#### 📖 阅读量范围")
        reads_min = st.number_input("最小阅读量", min_value=0, value=0, step=1000)
        reads_max = st.number_input(
            "最大阅读量", min_value=0, value=50000000, step=1000
        )

    # 其他范围设置
    st.markdown("### 2. 其他筛选条件")

    col3, col4 = st.columns(2)

    with col3:
        # 讨论量范围
        st.markdown("#### 💬 讨论量范围")
        discussions_min = st.number_input("最小讨论量", min_value=0, value=0, step=100)
        discussions_max = st.number_input(
            "最大讨论量", min_value=0, value=200000, step=100
        )

        # 原创量范围
        st.markdown("#### ✍️ 原创量范围")
        originals_min = st.number_input("最小原创量", min_value=0, value=0, step=100)
        originals_max = st.number_input(
            "最大原创量", min_value=0, value=200000, step=100
        )

    with col4:
        # 排序方式
        st.markdown("#### 📊 排序方式")
        sort_options = {
            "热度降序": "heat_desc",
            "热度升序": "heat_asc",
            "排名降序": "rank_desc",
            "排名升序": "rank_asc",
            "日期降序": "date_desc",
            "日期升序": "date_asc",
            "阅读量降序": "reads_desc",
            "阅读量升序": "reads_asc",
            "讨论量降序": "discussions_desc",
            "讨论量升序": "discussions_asc",
            "原创量降序": "originals_desc",
            "原创量升序": "originals_asc",
            "标题升序": "title_asc",
            "标题降序": "title_desc",
        }
        selected_sort = st.selectbox("选择排序方式", options=list(sort_options.keys()))
        sort_by = sort_options[selected_sort]

    # ========== 执行查询 ==========
    st.markdown("### 3. 执行查询与分析")

    query_button = st.button(
        "🚀 执行查询并分析", type="primary", use_container_width=True
    )

    if query_button:
        with st.spinner("正在执行查询，请稍候..."):
            try:
                # 准备查询参数
                query_params = {}

                # 日期范围
                if date_start and date_end:
                    query_params["date_range"] = (date_start, date_end)

                # 分类筛选
                if categories_input.strip():
                    categories = [
                        c.strip() for c in categories_input.split(",") if c.strip()
                    ]
                    if categories:
                        query_params["categories"] = categories

                # 排名范围
                if rank_min > 0 or rank_max < 50:
                    query_params["rank_range"] = (rank_min, rank_max)

                # 热度范围
                if heat_min > 0 or heat_max < 10000000.0:
                    query_params["heat_range"] = (heat_min, heat_max)

                # 阅读量范围
                if reads_min > 0 or reads_max < 50000000:
                    query_params["reads_range"] = (reads_min, reads_max)

                # 讨论量范围
                if discussions_min > 0 or discussions_max < 200000:
                    query_params["discussions_range"] = (
                        discussions_min,
                        discussions_max,
                    )

                # 原创量范围
                if originals_min > 0 or originals_max < 200000:
                    query_params["originals_range"] = (originals_min, originals_max)

                # 标题关键词
                if title_keywords_input.strip():
                    keywords = [
                        k.strip() for k in title_keywords_input.split(",") if k.strip()
                    ]
                    if keywords:
                        query_params["title_keywords"] = keywords

                # 排序方式
                query_params["sort_by"] = sort_by

                # 执行查询
                results = query.query(**query_params)

                if not results:
                    st.warning("⚠️ 没有找到符合条件的数据")
                    return

                st.success(f"✅ 查询成功！找到 {len(results)} 条符合条件的数据")

                # 保存查询结果到临时文件
                import os
                import tempfile
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_dir = tempfile.mkdtemp()
                temp_json_path = os.path.join(
                    temp_dir, f"query_results_{timestamp}.json"
                )

                # 保存结果
                query.save_results(results, temp_json_path)

                # ========== 显示查询结果表格 ==========
                st.markdown("### 4. 查询结果表格")

                # 转换为DataFrame用于显示
                df_results = pd.DataFrame(results)

                # 显示数据预览
                st.dataframe(df_results, use_container_width=True, height=400)

                # 下载按钮
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    # 下载JSON
                    with open(temp_json_path, "r", encoding="utf-8") as f:
                        json_data = f.read()
                    st.download_button(
                        label="📥 下载JSON数据",
                        data=json_data,
                        file_name=f"query_results_{timestamp}.json",
                        mime="application/json",
                    )

                with col_d2:
                    # 下载CSV
                    csv_data = df_results.to_csv(index=False, encoding="utf-8-sig")
                    st.download_button(
                        label="📥 下载CSV数据",
                        data=csv_data.encode("utf-8"),
                        file_name=f"query_results_{timestamp}.csv",
                        mime="text/csv",
                    )

                # ========== 数据分析与可视化 ==========
                st.markdown("### 5. 数据分析与可视化")

                with st.spinner("正在进行数据分析，生成可视化图表..."):
                    try:
                        # 创建输出目录
                        output_dir_name = f"query_analysis_{timestamp}"
                        output_dir = Path("output") / output_dir_name
                        output_dir.mkdir(parents=True, exist_ok=True)

                        # 调用json_analyzer分析数据
                        analysis_result = analyze_data(
                            results, output_dir_name, temp_json_path
                        )

                        st.success("✅ 数据分析完成！")

                        # 显示生成的图表
                        chart_files = list(output_dir.glob("*.png"))
                        if chart_files:
                            st.markdown("#### 📈 分析图表")

                            # 创建选项卡显示图表
                            tabs = st.tabs(
                                [f"图表{i + 1}" for i in range(len(chart_files))]
                            )

                            for tab, chart_file in zip(tabs, chart_files):
                                with tab:
                                    st.image(
                                        str(chart_file),
                                        use_column_width=True,
                                        caption=chart_file.name,
                                    )

                            # 显示分析报告
                            report_file = output_dir / "analysis_report.txt"
                            if report_file.exists():
                                with st.expander("📄 查看分析报告"):
                                    with open(report_file, "r", encoding="utf-8") as f:
                                        report_content = f.read()
                                    st.text(report_content)

                        # 显示统计信息
                        st.markdown("#### 📊 数据统计")
                        col_s1, col_s2, col_s3, col_s4 = st.columns(4)

                        with col_s1:
                            st.metric("总记录数", len(results))

                        with col_s2:
                            if results:
                                avg_heat = sum(r.get("heat", 0) for r in results) / len(
                                    results
                                )
                                st.metric("平均热度", f"{avg_heat:.1f}")

                        with col_s3:
                            if results:
                                unique_categories = set(
                                    r.get("category", "")
                                    for r in results
                                    if r.get("category")
                                )
                                st.metric("分类数量", len(unique_categories))

                        with col_s4:
                            if results and "date" in results[0]:
                                dates = set(
                                    r.get("date", "") for r in results if r.get("date")
                                )
                                st.metric("日期数量", len(dates))

                    except Exception as e:
                        st.error(f"数据分析失败: {str(e)}")
                        import traceback

                        st.error(traceback.format_exc())

                # 清理临时文件
                try:
                    os.unlink(temp_json_path)
                    os.rmdir(temp_dir)
                except:
                    pass

            except Exception as e:
                st.error(f"查询失败: {str(e)}")
                import traceback

                st.error(traceback.format_exc())

    # ========== 查询示例 ==========
    with st.expander("📋 查询示例", expanded=False):
        st.markdown("""
        **示例1：查询2025年1月所有明星类热搜**
        - 开始日期: 2025-01-01
        - 结束日期: 2025-01-31
        - 分类: 明星
        - 排序: 热度降序

        **示例2：查询热度大于10000的热搜**
        - 热度范围: 最小热度 10000
        - 排序: 热度降序

        **示例3：查询包含"新年"关键词的热搜**
        - 标题关键词: 新年
        - 排序: 日期降序
        """)


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

    with st.sidebar.expander("单日热搜分析", expanded=False):
        st.markdown("""
        - 选择日期分析单日数据
        - 调用 json_analyzer 模块
        - 支持数据导出
        """)

    with st.sidebar.expander("年度关键词网络", expanded=False):
        st.markdown("""
        - 查看关键词共现网络
        - 节点和边的统计数据
        - 导出数据为 CSV
        """)

    with st.sidebar.expander("词云图可视化", expanded=False):
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

    with st.sidebar.expander("去年今日", expanded=False):
        st.markdown("""
        - 从历史数据随机查找
        - 相同日期的往年热搜
        - 支持多格式导出
        """)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ 系统状态")
    import os
    from pathlib import Path

    # 统计数据
    data_dir = Path("data")
    output_dir = Path("output/word_clouds")
    network_dir = Path("output/word_networks")

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

    if network_dir.exists():
        network_files = list(network_dir.glob("**/*.json"))
        st.sidebar.success(f"✓ 已生成 {len(network_files) // 2} 个网络图")
    else:
        st.sidebar.warning("⚠ 网络图目录不存在")

    PAGES[page_name]()


if __name__ == "__main__":
    main()
