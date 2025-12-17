"""
JSON 数据分析模块

该模块用于读取微博热搜 JSON 数据，进行基本数据量分析，并生成可视化图表。
支持自定义字体 (Maple Mono NF CN) 和图表导出。

函数说明：
- analyze_json(json_file_path): 主函数，读取 JSON 文件并进行分析和图表生成

使用方法：
    from json_analyzer import analyze_json
    analyze_json("data/2025-01-01.json")

或命令行：
    python json_analyzer.py <json_file_path>
"""

import argparse
import json
import os
import platform
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 过滤警告
warnings.filterwarnings("ignore")

# 全局字体属性，后续直接使用
GLOBAL_FONT_PROP = None


def sanitize_for_matplotlib(text: str) -> str:
    """移除 Matplotlib 通常无法正常显示的字符（如彩色 Emoji/非常用符号）。

    规则：过滤掉超出 BMP 平面的字符 (ord > 0xFFFF)。
    说明：绝大多数常用中英文都在 BMP 内，Emoji 等位于补充平面会被去除，避免显示为方块。
    """
    if not isinstance(text, str):
        return text
    try:
        return "".join(ch for ch in text if ord(ch) <= 0xFFFF)
    except Exception:
        return text


def setup_font(font_name: str = "") -> bool:
    """统一设置 Matplotlib 字体，确保所有中文一致显示。

    优先从系统路径加载常用 CJK 字体；加载后将字体注册到 Matplotlib，
    并同时设置 rcParams 的 font.family 与 font.sans-serif，统一全局默认。
    """
    global GLOBAL_FONT_PROP
    
    try:
        font_path = None
        
        # Windows: 直接使用微软雅黑
        if platform.system() == "Windows":
            font_path = r"C:\Windows\Fonts\msyh.ttc"
            if not os.path.exists(font_path):
                font_path = r"C:\Windows\Fonts\simhei.ttf"
        # macOS: 苹方
        elif platform.system() == "Darwin":
            font_path = "/System/Library/Fonts/PingFang.ttc"
            if not os.path.exists(font_path):
                font_path = "/System/Library/Fonts/STHeiti Light.ttc"
        # Linux: Noto Sans CJK
        else:
            font_path = "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
            if not os.path.exists(font_path):
                font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
        
        if font_path and os.path.exists(font_path):
            # 注册字体，获取标准字体名称
            try:
                fm.fontManager.addfont(font_path)
            except Exception:
                # 某些环境 addfont 可能已注册，忽略
                pass

            GLOBAL_FONT_PROP = fm.FontProperties(fname=font_path)
            font_name_resolved = GLOBAL_FONT_PROP.get_name()

            # 统一全局字体（family 与 sans-serif 一致指定）
            matplotlib.rcParams["font.family"] = font_name_resolved
            matplotlib.rcParams["font.sans-serif"] = [font_name_resolved]
            matplotlib.rcParams["axes.unicode_minus"] = False
            print(f"✓ 已加载字体: {font_name_resolved} from {font_path}")
            return True
        else:
            print(f"⚠ 字体文件不存在: {font_path}")
            # 兜底：使用系统可用字体
            matplotlib.rcParams["axes.unicode_minus"] = False
            return False
            
    except Exception as e:
        print(f"✗ 字体加载异常: {e}")
        matplotlib.rcParams["axes.unicode_minus"] = False
        return False



def load_json_data(file_path: str) -> Dict[str, Any]:
    """
    加载 JSON 数据文件

    Args:
        file_path: JSON 文件路径

    Returns:
        Dict: 解析后的 JSON 数据

    Raises:
        FileNotFoundError: 文件不存在
        JSONDecodeError: JSON 格式错误
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def basic_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行基本数据分析

    Args:
        data: JSON 数据

    Returns:
        Dict: 分析结果统计
    """
    # 从数据中提取基本信息
    date = data.get("date", "未知日期")
    count = data.get("count", 0)
    items = data.get("data", [])

    if not items:
        print(f"警告: {date} 的数据为空")
        return {}

    # 转换为 DataFrame 以便分析
    df = pd.DataFrame(items)

    # 基本统计信息
    analysis_result = {
        "date": date,
        "total_items": count,
        "actual_items": len(items),
        "heat_stats": {
            "mean": df["heat"].mean() if "heat" in df.columns else 0,
            "median": df["heat"].median() if "heat" in df.columns else 0,
            "max": df["heat"].max() if "heat" in df.columns else 0,
            "min": df["heat"].min() if "heat" in df.columns else 0,
            "std": df["heat"].std() if "heat" in df.columns else 0,
        },
        "reads_stats": {
            "mean": df["reads"].mean() if "reads" in df.columns else 0,
            "median": df["reads"].median() if "reads" in df.columns else 0,
            "max": df["reads"].max() if "reads" in df.columns else 0,
            "min": df["reads"].min() if "reads" in df.columns else 0,
            "total": df["reads"].sum() if "reads" in df.columns else 0,
        },
        "discussions_stats": {
            "mean": df["discussions"].mean() if "discussions" in df.columns else 0,
            "median": df["discussions"].median() if "discussions" in df.columns else 0,
            "max": df["discussions"].max() if "discussions" in df.columns else 0,
            "min": df["discussions"].min() if "discussions" in df.columns else 0,
            "total": df["discussions"].sum() if "discussions" in df.columns else 0,
        },
        "category_distribution": {},
        "top_titles": [],
    }

    # 类别分布分析
    if "category" in df.columns:
        category_counts = df["category"].value_counts()
        analysis_result["category_distribution"] = category_counts.to_dict()

    # 热度最高的前10个标题
    if "title" in df.columns and "heat" in df.columns:
        top_titles = df.nlargest(10, "heat")[["title", "heat", "rank"]]
        analysis_result["top_titles"] = top_titles.to_dict("records")

    return analysis_result


def create_output_directory(date_str: str) -> str:
    """
    创建输出目录

    Args:
        date_str: 日期字符串，用于创建子目录

    Returns:
        str: 输出目录路径
    """
    # 项目根目录的 output 文件夹
    base_output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

    # 按日期创建子目录
    output_dir = os.path.join(base_output_dir, date_str)

    # 创建目录（如果不存在）
    os.makedirs(output_dir, exist_ok=True)

    return output_dir


def generate_charts(
    data: Dict[str, Any], analysis_result: Dict[str, Any], output_dir: str
):
    """
    生成可视化图表

    Args:
        data: JSON 数据
        analysis_result: 分析结果
        output_dir: 输出目录
    """
    df = pd.DataFrame(data.get("data", []))
    date_str = data.get("date", "unknown_date")

    if df.empty:
        print("没有数据可用于生成图表")
        return

    # 设置图表风格
    plt.style.use("seaborn-v0_8-darkgrid")

    # 1. 热度排名前20的条形图
    if "title" in df.columns and "heat" in df.columns:
        plt.figure(figsize=(14, 8))
        top_20 = df.nlargest(20, "heat")

        # 创建条形图
        bars = plt.barh(
            range(len(top_20)), top_20["heat"], color="steelblue", alpha=0.8
        )

        # 添加标题和标签
        plt.title(sanitize_for_matplotlib(f"{date_str} 热度排名前20的热搜"), fontsize=16, fontweight="bold", fontproperties=GLOBAL_FONT_PROP)
        plt.xlabel("热度值", fontsize=12, fontproperties=GLOBAL_FONT_PROP)
        # 去除标题中的不可显示字符（emoji 等）
        _yticks = [sanitize_for_matplotlib(str(t)) for t in top_20["title"]]
        plt.yticks(range(len(top_20)), _yticks, fontsize=10, fontproperties=GLOBAL_FONT_PROP)

        # 在条形图上添加数值标签
        for i, (bar, heat) in enumerate(zip(bars, top_20["heat"])):
            width = bar.get_width()
            plt.text(
                width + max(top_20["heat"]) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{heat:.1f}",
                va="center",
                fontsize=9,
                fontproperties=GLOBAL_FONT_PROP,
            )

        plt.tight_layout()
        plt.savefig(
            os.path.join(output_dir, f"{date_str}_top20_heat.png"),
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()

    # 2. 热度分布直方图
    if "heat" in df.columns:
        plt.figure(figsize=(12, 6))

        # 创建直方图
        n, bins, patches = plt.hist(
            df["heat"], bins=30, color="lightcoral", alpha=0.7, edgecolor="black"
        )

        plt.title(sanitize_for_matplotlib(f"{date_str} 热搜热度分布直方图"), fontsize=16, fontweight="bold", fontproperties=GLOBAL_FONT_PROP)
        plt.xlabel("热度值", fontsize=12, fontproperties=GLOBAL_FONT_PROP)
        plt.ylabel("频数", fontsize=12, fontproperties=GLOBAL_FONT_PROP)

        # 添加均值线
        mean_heat = df["heat"].mean()
        plt.axvline(
            mean_heat,
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"均值: {mean_heat:.2f}",
        )

        # 添加中位数线
        median_heat = df["heat"].median()
        plt.axvline(
            median_heat,
            color="green",
            linestyle="--",
            linewidth=2,
            label=f"中位数: {median_heat:.2f}",
        )

        plt.legend(prop=GLOBAL_FONT_PROP)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(
            os.path.join(output_dir, f"{date_str}_heat_distribution.png"),
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()

    # 3. 阅读量 vs 讨论量的散点图
    if "reads" in df.columns and "discussions" in df.columns:
        plt.figure(figsize=(12, 8))

        # 创建散点图，点的大小表示热度
        scatter = plt.scatter(
            df["reads"],
            df["discussions"],
            c=df["heat"] if "heat" in df.columns else "blue",
            s=100,
            alpha=0.6,
            cmap="viridis",
        )

        plt.title(
            f"{date_str} 阅读量与讨论量关系散点图", fontsize=16, fontweight="bold", fontproperties=GLOBAL_FONT_PROP
        )
        plt.xlabel("阅读量（万）", fontsize=12, fontproperties=GLOBAL_FONT_PROP)
        plt.ylabel("讨论量（万）", fontsize=12, fontproperties=GLOBAL_FONT_PROP)

        # 添加颜色条表示热度
        if "heat" in df.columns:
            cbar = plt.colorbar(scatter)
            cbar.set_label(sanitize_for_matplotlib("热度值"), fontsize=12, fontproperties=GLOBAL_FONT_PROP)

        # 添加趋势线
        if len(df) > 1:
            z = np.polyfit(df["reads"], df["discussions"], 1)
            p = np.poly1d(z)
            plt.plot(df["reads"], p(df["reads"]), "r--", alpha=0.8, label=sanitize_for_matplotlib("趋势线"))

        plt.legend(prop=GLOBAL_FONT_PROP)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(
            os.path.join(output_dir, f"{date_str}_reads_vs_discussions.png"),
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()

    # 4. 类别分布饼图（如果有类别信息）
    if "category" in df.columns and df["category"].notna().any():
        # 过滤空类别
        valid_categories = df[df["category"].notna() & (df["category"] != "")][
            "category"
        ]

        if len(valid_categories) > 0:
            plt.figure(figsize=(10, 8))

            # 统计类别分布
            category_counts = valid_categories.value_counts()

            # 如果类别太多，只显示前10个，其余合并为"其他"
            if len(category_counts) > 10:
                top_categories = category_counts.head(10)
                other_count = category_counts[10:].sum()
                top_categories["其他"] = other_count
                category_counts = top_categories

            # 创建饼图
            colors = plt.cm.Set3(np.linspace(0, 1, len(category_counts)))
            labels_clean = [sanitize_for_matplotlib(str(x)) for x in category_counts.index]
            wedges, texts, autotexts = plt.pie(
                category_counts.values,
                labels=labels_clean,
                autopct="%1.1f%%",
                startangle=90,
                colors=colors,
                textprops={"fontsize": 10, "fontproperties": GLOBAL_FONT_PROP},
            )

            plt.title(sanitize_for_matplotlib(f"{date_str}"), fontsize=16, fontweight="bold", fontproperties=GLOBAL_FONT_PROP)
            plt.axis("equal")  # 确保饼图是圆形

            plt.tight_layout()
            plt.savefig(
                os.path.join(output_dir, f"{date_str}_category_distribution.png"),
                dpi=300,
                bbox_inches="tight",
            )
            plt.close()

    # 5. 综合统计信息图表
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))

    # 5.1 排名分布
    if "rank" in df.columns:
        axes[0, 0].bar(
            df["rank"],
            df["heat"] if "heat" in df.columns else range(len(df)),
            color="skyblue",
            alpha=0.7,
        )
        axes[0, 0].set_title(sanitize_for_matplotlib("排名分布"), fontsize=14, fontproperties=GLOBAL_FONT_PROP)
        axes[0, 0].set_xlabel(sanitize_for_matplotlib("排名"), fontproperties=GLOBAL_FONT_PROP)
        axes[0, 0].set_ylabel(sanitize_for_matplotlib("热度" if "heat" in df.columns else "数量"), fontproperties=GLOBAL_FONT_PROP)
        axes[0, 0].invert_xaxis()  # 排名1在左边
        axes[0, 0].grid(True, alpha=0.3)

    # 5.2 原创数量分布
    if "originals" in df.columns:
        originals_data = df["originals"].value_counts().sort_index()
        axes[0, 1].bar(
            originals_data.index, originals_data.values, color="lightgreen", alpha=0.7
        )
        axes[0, 1].set_title(sanitize_for_matplotlib("原创数量分布"), fontsize=14, fontproperties=GLOBAL_FONT_PROP)
        axes[0, 1].set_xlabel(sanitize_for_matplotlib("原创数量"), fontproperties=GLOBAL_FONT_PROP)
        axes[0, 1].set_ylabel(sanitize_for_matplotlib("频数"), fontproperties=GLOBAL_FONT_PROP)
        axes[0, 1].grid(True, alpha=0.3)

    # 5.3 热度箱线图
    if "heat" in df.columns:
        axes[1, 0].boxplot(
            df["heat"],
            vert=True,
            patch_artist=True,
            boxprops=dict(facecolor="lightcoral"),
        )
        axes[1, 0].set_title(sanitize_for_matplotlib("热度箱线图"), fontsize=14, fontproperties=GLOBAL_FONT_PROP)
        axes[1, 0].set_ylabel(sanitize_for_matplotlib("热度值"), fontproperties=GLOBAL_FONT_PROP)
        axes[1, 0].grid(True, alpha=0.3)

    # 5.4 阅读量箱线图（增强版：统一字体、自动缩放、统计注记）
    if "reads" in df.columns:
        reads = pd.to_numeric(df["reads"], errors="coerce").dropna()
        if len(reads) > 0:
            axes[1, 1].boxplot(
                reads,
                vert=True,
                patch_artist=True,
                notch=False,
                showmeans=True,
                meanline=True,
                boxprops=dict(facecolor="gold", alpha=0.65, linewidth=1),
                medianprops=dict(color="royalblue", linewidth=1.5),
                meanprops=dict(color="red", linewidth=1.2),
                whiskerprops=dict(color="gray"),
                capprops=dict(color="gray"),
                flierprops=dict(marker="o", markerfacecolor="gray", markersize=3, alpha=0.5),
            )
            axes[1, 1].set_title(sanitize_for_matplotlib("阅读量箱线图"), fontsize=14, fontproperties=GLOBAL_FONT_PROP)
            axes[1, 1].set_ylabel(sanitize_for_matplotlib("阅读量（万）"), fontproperties=GLOBAL_FONT_PROP)

            # 自动缩放（避免极端离群点压缩盒体）
            try:
                p01 = np.nanpercentile(reads, 1)
                p99 = np.nanpercentile(reads, 99)
                if np.isfinite(p99) and reads.max() > p99 * 1.1:
                    axes[1, 1].set_ylim(bottom=min(0, p01), top=p99)
                    txt = "提示：已按P99截断显示"
                    axes[1, 1].text(
                        1.02, 0.02, sanitize_for_matplotlib(txt),
                        transform=axes[1, 1].transAxes,
                        ha="left", va="bottom",
                        fontsize=9, fontproperties=GLOBAL_FONT_PROP, color="gray"
                    )
            except Exception:
                pass

            # 统计注记
            mean_v = float(np.nanmean(reads))
            median_v = float(np.nanmedian(reads))
            min_v = float(np.nanmin(reads))
            max_v = float(np.nanmax(reads))
            stats_text = f"均值: {mean_v:.2f} 万\n中位数: {median_v:.2f} 万\n最小: {min_v:.2f} 万\n最大: {max_v:.2f} 万"
            axes[1, 1].text(
                0.98, 0.98, sanitize_for_matplotlib(stats_text),
                transform=axes[1, 1].transAxes,
                ha="right", va="top",
                fontsize=9, fontproperties=GLOBAL_FONT_PROP,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="lightgray", alpha=0.7)
            )

            axes[1, 1].grid(True, alpha=0.3)
        else:
            axes[1, 1].text(
                0.5, 0.5, sanitize_for_matplotlib("无有效阅读量数据"),
                transform=axes[1, 1].transAxes, ha="center", va="center",
                fontsize=12, fontproperties=GLOBAL_FONT_PROP, color="gray"
            )
            axes[1, 1].set_title(sanitize_for_matplotlib("阅读量箱线图"), fontsize=14, fontproperties=GLOBAL_FONT_PROP)
            axes[1, 1].set_ylabel(sanitize_for_matplotlib("阅读量（万）"), fontproperties=GLOBAL_FONT_PROP)
            axes[1, 1].grid(True, alpha=0.3)

    plt.suptitle(sanitize_for_matplotlib(f"{date_str}"), fontsize=18, fontweight="bold", fontproperties=GLOBAL_FONT_PROP)
    plt.tight_layout()
    plt.savefig(
        os.path.join(output_dir, f"{date_str}_comprehensive_analysis.png"),
        dpi=300,
        bbox_inches="tight",
    )
    plt.close()


def save_analysis_report(analysis_result: Dict[str, Any], output_dir: str):
    """
    保存分析报告到文本文件

    Args:
        analysis_result: 分析结果
        output_dir: 输出目录
    """
    report_path = os.path.join(output_dir, "analysis_report.txt")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"微博热搜数据分析报告\n")
        f.write("=" * 50 + "\n\n")

        f.write(f"分析日期: {analysis_result.get('date', '未知日期')}\n")
        f.write(f"总条目数: {analysis_result.get('total_items', 0)}\n")
        f.write(f"实际条目数: {analysis_result.get('actual_items', 0)}\n\n")

        # 热度统计
        heat_stats = analysis_result.get("heat_stats", {})
        if heat_stats:
            f.write("热度统计:\n")
            f.write(f"  平均值: {heat_stats.get('mean', 0):.2f}\n")
            f.write(f"  中位数: {heat_stats.get('median', 0):.2f}\n")
            f.write(f"  最大值: {heat_stats.get('max', 0):.2f}\n")
            f.write(f"  最小值: {heat_stats.get('min', 0):.2f}\n")
            f.write(f"  标准差: {heat_stats.get('std', 0):.2f}\n\n")

        # 阅读量统计
        reads_stats = analysis_result.get("reads_stats", {})
        if reads_stats:
            f.write("阅读量统计:\n")
            f.write(f"  平均值: {reads_stats.get('mean', 0):.2f} 万\n")
            f.write(f"  中位数: {reads_stats.get('median', 0):.2f} 万\n")
            f.write(f"  最大值: {reads_stats.get('max', 0):.2f} 万\n")
            f.write(f"  最小值: {reads_stats.get('min', 0):.2f} 万\n")
            f.write(f"  总计: {reads_stats.get('total', 0):.2f} 万\n\n")

        # 讨论量统计
        discussions_stats = analysis_result.get("discussions_stats", {})
        if discussions_stats:
            f.write("讨论量统计:\n")
            f.write(f"  平均值: {discussions_stats.get('mean', 0):.2f} 万\n")
            f.write(f"  中位数: {discussions_stats.get('median', 0):.2f} 万\n")
            f.write(f"  最大值: {discussions_stats.get('max', 0):.2f} 万\n")
            f.write(f"  最小值: {discussions_stats.get('min', 0):.2f} 万\n")
            f.write(f"  总计: {discussions_stats.get('total', 0):.2f} 万\n\n")

        # 类别分布
        category_dist = analysis_result.get("category_distribution", {})
        if category_dist:
            f.write("类别分布:\n")
            for category, count in category_dist.items():
                if category:  # 跳过空类别
                    f.write(f"  {category}: {count} 条\n")
            f.write("\n")

        # 热度最高标题
        top_titles = analysis_result.get("top_titles", [])
        if top_titles:
            f.write("热度最高的10个热搜:\n")
            for i, item in enumerate(top_titles[:10], 1):
                title = item.get("title", "未知标题")
                heat = item.get("heat", 0)
                rank = item.get("rank", 0)
                f.write(f"  {i}. [{rank}位] {title} (热度: {heat:.2f})\n")

    print(f"分析报告已保存到: {report_path}")


def analyze_json(json_file_path: str):
    """
    主函数：分析 JSON 数据并生成图表

    Args:
        json_file_path: JSON 文件路径
    """
    print(f"开始分析 JSON 文件: {json_file_path}")

    # 1. 设置字体
    print("设置字体...")
    font_setup_success = setup_font()
    if not font_setup_success:
        print("警告: 字体设置失败，图表可能无法正常显示中文")

    try:
        # 2. 加载数据
        print("加载数据...")
        data = load_json_data(json_file_path)

        # 3. 基本分析
        print("执行基本分析...")
        analysis_result = basic_analysis(data)

        if not analysis_result:
            print("分析结果为空，可能数据格式不正确")
            return

        # 4. 创建输出目录
        date_str = data.get("date", "unknown_date")
        output_dir = create_output_directory(date_str)
        print(f"输出目录: {output_dir}")

        # 5. 生成图表
        print("生成图表...")
        generate_charts(data, analysis_result, output_dir)

        # 6. 保存分析报告
        print("保存分析报告...")
        save_analysis_report(analysis_result, output_dir)

        # 7. 打印简要结果
        print("\n" + "=" * 50)
        print(f"分析完成!")
        print(f"日期: {analysis_result.get('date', '未知日期')}")
        print(f"总条目数: {analysis_result.get('total_items', 0)}")
        print(f"热度平均值: {analysis_result.get('heat_stats', {}).get('mean', 0):.2f}")
        print(f"图表已保存到: {output_dir}")
        print("=" * 50)

    except FileNotFoundError as e:
        print(f"错误: {e}")
    except json.JSONDecodeError as e:
        print(f"错误: JSON 文件格式不正确 - {e}")
    except Exception as e:
        print(f"错误: 分析过程中出现异常 - {e}")
        import traceback

        traceback.print_exc()


def main():
    """命令行入口点"""
    parser = argparse.ArgumentParser(description="微博热搜 JSON 数据分析工具")
    parser.add_argument("json_file", help="要分析的 JSON 文件路径")
    parser.add_argument(
        "--font",
        default="Maple Mono NF CN",
        help="指定字体名称 (默认: Maple Mono NF CN)",
    )

    args = parser.parse_args()

    # 设置字体
    setup_font(args.font)

    # 分析 JSON 文件
    analyze_json(args.json_file)


if __name__ == "__main__":
    main()
