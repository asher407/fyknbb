"""
关键词关系网络可视化模块 (整合版)

整合了 keyword_network.py、demo_network.py 和 test_keyword_network.py 的功能。
提供关键词提取、关系网络构建和可视化功能。

主要功能：
    1. 关键词提取：使用 jieba 分词从标题中提取关键词
    2. 网络构建：基于关键词在同一热搜条目中的共现关系构建网络
    3. 网络分析：计算节点中心性等网络指标
    4. 可视化：生成交互式网络图（HTML）和静态图（PNG）
    5. 命令行接口：支持处理单个文件或整个目录

使用示例：
    # 命令行使用
    python keyword_network.py data_processed/2025-01/2025-01-01.json

    # Python API 使用
    from keyword_network import KeywordNetwork
    processor = KeywordNetwork()
    processor.process_file("data.json", "output")
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set

# 可选依赖，运行时检查
try:
    import jieba

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

try:
    from pyvis.network import Network

    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False

try:
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class KeywordNetwork:
    """
    关键词关系网络处理器
    """

    def __init__(
        self,
        min_word_length: int = 2,
        stopwords: Optional[Set[str]] = None,
        font_family: str = "DejaVu Serif",
        font_size: int = 20,
        static_font_family: str = "DejaVu Serif",
        static_font_size: int = 16,
        node_label_font_size: int = 10,
    ):
        """
        初始化关键词网络处理器

        参数：
            min_word_length: 最小词语长度
            stopwords: 自定义停用词集合，如果为None则使用默认停用词
            font_family: 交互式网络图字体 (默认: Microsoft YaHei)
            font_size: 交互式网络图字体大小 (默认: 20)
            static_font_family: 静态图字体 (默认: sans-serif)
            static_font_size: 静态图标题字体大小 (默认: 16)
            node_label_font_size: 静态图节点标签字体大小 (默认: 10)
        """
        if not JIEBA_AVAILABLE:
            raise ImportError("jieba 库未安装，请运行: pip install jieba")

        self.min_word_length = min_word_length

        # 默认停用词集合（精简版）
        self.default_stopwords = {
            "的",
            "了",
            "和",
            "是",
            "在",
            "到",
            "一",
            "个",
            "为",
            "中",
            "回应",
            "什么",
            "怎么",
            "这么",
            "为什么",
            "不要",
            "真的",
            "不是",
            "就是",
            "可能",
            "要求",
            "还是",
            "小时",
            "疑似",
            "吗",
            "呢",
            "吧",
            "啊",
            "哦",
            "这",
            "那",
            "有",
            "没有",
            "没",
            "很",
            "比",
            "更",
            "最",
            "就",
            "还",
            "也",
            "被",
            "把",
            "向",
            "让",
            "给",
            "从",
        }

        self.stopwords = stopwords if stopwords is not None else self.default_stopwords

        # 字体配置
        self.font_family = font_family
        self.font_size = font_size
        self.static_font_family = static_font_family
        self.static_font_size = static_font_size
        self.node_label_font_size = node_label_font_size

        # 自定义词典（保持整体识别）
        self.custom_words = [
            "王楚钦",
            "赵露思",
            "肖战",
            "王一博",
            "易烊千玺",
            "迪丽热巴",
            "杨幂",
            "刘亦菲",
            "胡歌",
            "周杰伦",
        ]

        for word in self.custom_words:
            jieba.add_word(word, freq=1000)

    def load_json(self, file_path: str) -> Dict[str, Any]:
        """
        加载 JSON 文件

        参数：
            file_path: JSON 文件路径

        返回：
            JSON 数据字典
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def extract_keywords(self, text: str) -> List[str]:
        """
        从单条文本中提取关键词

        参数：
            text: 输入文本

        返回：
            关键词列表
        """
        # 移除特殊字符和标点
        text = re.sub(r"[^\w\u4e00-\u9fff]", " ", text)

        # 使用 jieba 分词
        words = jieba.cut(text)

        # 过滤条件
        keywords = []
        for word in words:
            word = word.strip()
            if len(word) < self.min_word_length:
                continue
            if word in self.stopwords:
                continue
            if word.isdigit():
                continue
            if re.match(r"^[a-zA-Z]{1,2}$", word):  # 过滤单个或两个字母的英文
                continue

            keywords.append(word)

        return keywords

    def extract_keywords_from_data(self, data: Dict[str, Any]) -> List[List[str]]:
        """
        从数据中提取所有条目的关键词

        参数：
            data: JSON 数据，包含 'data' 字段

        返回：
            每个条目的关键词列表的列表
        """
        items = data.get("data", [])
        keywords_by_item = []

        for item in items:
            title = item.get("title", "")
            if not title:
                continue

            keywords = self.extract_keywords(title)
            if keywords:  # 只保留有关键词的条目
                keywords_by_item.append(keywords)

        return keywords_by_item

    def build_cooccurrence_network(
        self, keywords_by_item: List[List[str]], min_cooccurrence: int = 1
    ) -> nx.Graph:
        """
        构建关键词共现网络

        参数：
            keywords_by_item: 每个条目的关键词列表
            min_cooccurrence: 最小共现次数阈值

        返回：
            networkx 图对象
        """
        if not NETWORKX_AVAILABLE:
            raise ImportError("networkx 库未安装，请运行: pip install networkx")

        # 统计关键词频率和共现次数
        keyword_freq = Counter()
        cooccurrence_counts = defaultdict(int)

        for keywords in keywords_by_item:
            # 更新关键词频率
            for keyword in keywords:
                keyword_freq[keyword] += 1

            # 更新共现次数（同一条目内的关键词两两共现）
            for i in range(len(keywords)):
                for j in range(i + 1, len(keywords)):
                    pair = tuple(sorted([keywords[i], keywords[j]]))
                    cooccurrence_counts[pair] += 1

        # 创建图
        G = nx.Graph()

        # 添加节点（关键词）
        for keyword, freq in keyword_freq.items():
            if freq >= 1:  # 至少出现一次
                G.add_node(keyword, size=freq, frequency=freq)

        # 添加边（共现关系）
        for (kw1, kw2), count in cooccurrence_counts.items():
            if count >= min_cooccurrence and kw1 in G.nodes() and kw2 in G.nodes():
                G.add_edge(kw1, kw2, weight=count)

        return G

    def calculate_network_metrics(self, graph: nx.Graph) -> Dict[str, Any]:
        """
        计算网络指标

        参数：
            graph: networkx 图对象

        返回：
            包含各种网络指标的字典
        """
        if len(graph.nodes()) == 0:
            return {}

        metrics = {}

        # 基础指标
        metrics["num_nodes"] = graph.number_of_nodes()
        metrics["num_edges"] = graph.number_of_edges()
        metrics["density"] = nx.density(graph)

        # 度中心性
        try:
            degree_centrality = nx.degree_centrality(graph)
            if degree_centrality:
                top_degree = sorted(
                    degree_centrality.items(), key=lambda x: x[1], reverse=True
                )[:10]
                metrics["top_degree_centrality"] = top_degree
        except:
            pass

        # 平均聚类系数
        try:
            metrics["average_clustering"] = nx.average_clustering(graph)
        except:
            pass

        return metrics

    def visualize_network(
        self,
        graph: nx.Graph,
        output_path: str,
        title: str = "关键词关系网络",
        height: str = "800px",
        width: str = "100%",
    ) -> str:
        """
        生成交互式网络可视化（HTML）

        参数：
            graph: networkx 图对象
            output_path: 输出文件路径
            title: 网络图标题
            height: 画布高度
            width: 画布宽度

        返回：
            输出文件路径
        """
        if not PYVIS_AVAILABLE:
            raise ImportError("pyvis 库未安装，请运行: pip install pyvis")

        if len(graph.nodes()) == 0:
            print("警告：图中没有节点，跳过可视化")
            return ""

        # 创建 pyvis 网络
        net = Network(height=height, width=width, directed=False, notebook=False)

        # 添加节点和边到 pyvis
        net.from_nx(graph)

        # 设置基本选项
        options = {
            "nodes": {
                "borderWidth": 2,
                "font": {"size": self.font_size, "face": self.font_family},
                "scaling": {"min": 20, "max": 60},
            },
            "edges": {"color": "#848484", "smooth": {"type": "continuous"}, "width": 2},
            "physics": {"enabled": True, "solver": "forceAtlas2Based"},
        }

        # 修复：使用 set_options 方法正确传递选项
        import json

        net.set_options(json.dumps(options))

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存为 HTML
        net.save_graph(output_path)

        # 同时生成一个静态 PNG 图像（可选）
        if MATPLOTLIB_AVAILABLE:
            try:
                static_path = output_path.replace(".html", ".png")
                self._save_static_plot(graph, static_path, title)
            except Exception as e:
                print(f"警告：静态图生成失败: {e}")

        return output_path

    def _save_static_plot(self, graph: nx.Graph, output_path: str, title: str):
        """
        生成静态网络图（PNG）

        参数：
            graph: networkx 图对象
            output_path: 输出文件路径
            title: 图标题
        """

        # 字体检查与回退机制
        def get_available_font():
            """检查字体是否可用，如果不可用则尝试替代字体"""
            import matplotlib.font_manager as fm

            # 首选字体列表（按优先级排序）
            font_candidates = [
                self.static_font_family,  # 用户指定的字体
                "Noto Sans CJK SC",  # Ubuntu 中文默认字体
                "DejaVu Sans",  # Linux 广泛可用字体
                "Ubuntu",  # Ubuntu 默认英文字体
                "WenQuanYi Micro Hei",  # 文泉驿微米黑
                "sans-serif",  # 系统默认
            ]

            # 获取系统可用字体
            available_fonts = [f.name for f in fm.fontManager.ttflist]

            # 查找第一个可用的字体
            for font_name in font_candidates:
                if font_name in available_fonts:
                    if font_name != self.static_font_family:
                        print(
                            f"提示: 使用替代字体 '{font_name}' (原字体 '{self.static_font_family}' 不可用)"
                        )
                    return font_name

            # 如果没有找到任何候选字体，使用默认
            print("警告: 所有候选字体都不可用，使用默认字体 'sans-serif'")
            return "sans-serif"

        try:
            # 获取可用的字体
            actual_font_family = get_available_font()
        except Exception as e:
            print(f"字体检查失败: {e}，使用默认字体")
            actual_font_family = "sans-serif"

        plt.figure(figsize=(12, 10))

        # 计算节点大小（基于度）
        node_sizes = []
        for node in graph.nodes():
            size = (
                graph.nodes[node].get("size", 1)
                if hasattr(graph.nodes[node], "get")
                else 1
            )
            node_sizes.append(size * 50)

        # 计算节点颜色（基于度）
        degrees = dict(graph.degree())
        max_degree = max(degrees.values()) if degrees else 1
        node_colors = [degrees[node] / max_degree for node in graph.nodes()]

        # 绘制网络
        pos = nx.spring_layout(graph, seed=42)

        # 绘制边
        nx.draw_networkx_edges(graph, pos, alpha=0.3, edge_color="gray")

        # 绘制节点
        nx.draw_networkx_nodes(
            graph,
            pos,
            node_size=node_sizes,
            node_color=node_colors,
            cmap="viridis",
            alpha=0.8,
        )

        # 绘制标签（只显示高频词）
        labels = {}
        for node in graph.nodes():
            freq = (
                graph.nodes[node].get("frequency", 0)
                if hasattr(graph.nodes[node], "get")
                else 0
            )
            if freq >= 3:  # 只显示出现3次以上的词
                labels[node] = node

        nx.draw_networkx_labels(
            graph,
            pos,
            labels,
            font_size=self.node_label_font_size,
            font_family=actual_font_family,
        )

        plt.title(title, fontsize=self.static_font_size, fontfamily=actual_font_family)
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

    def save_metrics(self, metrics: Dict[str, Any], output_path: str):
        """
        保存网络指标到 JSON 文件

        参数：
            metrics: 网络指标字典
            output_path: 输出文件路径
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)

    def process_file(
        self,
        input_json_path: str,
        output_dir: str = "output/keyword_networks",
        min_cooccurrence: int = 1,
    ) -> Dict[str, Any]:
        """
        处理单个 JSON 文件

        参数：
            input_json_path: 输入 JSON 文件路径
            output_dir: 输出目录
            min_cooccurrence: 最小共现次数阈值

        返回：
            处理结果字典
        """
        print(f"处理文件: {input_json_path}")

        # 加载数据
        data = self.load_json(input_json_path)

        # 提取关键词
        keywords_by_item = self.extract_keywords_from_data(data)

        if not keywords_by_item:
            print(f"警告: {input_json_path} 中没有提取到关键词")
            return {}

        # 构建网络
        graph = self.build_cooccurrence_network(keywords_by_item, min_cooccurrence)

        if len(graph.nodes()) == 0:
            print(f"警告: {input_json_path} 构建的网络没有节点")
            return {}

        # 计算指标
        metrics = self.calculate_network_metrics(graph)

        # 生成输出文件名
        base_name = os.path.splitext(os.path.basename(input_json_path))[0]
        output_base = os.path.join(output_dir, base_name)

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 保存网络可视化
        html_path = f"{output_base}_network.html"
        self.visualize_network(graph, html_path, title=f"关键词关系网络 - {base_name}")

        # 保存网络指标
        metrics_path = f"{output_base}_metrics.json"
        self.save_metrics(metrics, metrics_path)

        result = {
            "input_file": input_json_path,
            "output_html": html_path,
            "output_metrics": metrics_path,
            "num_items": len(keywords_by_item),
            "num_nodes": graph.number_of_nodes(),
            "num_edges": graph.number_of_edges(),
            "metrics": metrics,
        }

        print(
            f"完成: 生成网络图 {html_path} (节点: {graph.number_of_nodes()}, 边: {graph.number_of_edges()})"
        )
        return result

    def process_directory(
        self,
        input_dir: str,
        output_dir: str = "output/keyword_networks",
        min_cooccurrence: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        处理目录下的所有 JSON 文件（合并所有文件数据）

        参数：
            input_dir: 输入目录
            output_dir: 输出目录
            min_cooccurrence: 最小共现次数阈值

        返回：
            处理结果列表（包含单个结果的列表以保持兼容性）
        """
        print(f"处理目录（合并模式）: {input_dir}")

        all_keywords_by_item = []
        file_count = 0
        processed_files = []

        # 收集所有文件的数据（递归遍历）
        for root, _, files in os.walk(input_dir):
            for file in files:
                if file.endswith(".json") and not file.endswith(".bak"):
                    input_path = os.path.join(root, file)
                    print(f"  读取文件: {input_path}")

                    # 加载数据
                    try:
                        data = self.load_json(input_path)
                        keywords_by_item = self.extract_keywords_from_data(data)

                        if keywords_by_item:
                            all_keywords_by_item.extend(keywords_by_item)
                            file_count += 1
                            processed_files.append(input_path)
                        else:
                            print(f"  警告: {input_path} 中没有提取到关键词")
                    except Exception as e:
                        print(f"  错误: 处理文件 {input_path} 时出错: {e}")

        if not all_keywords_by_item:
            print(f"警告: 目录 {input_dir} 中没有提取到任何关键词")
            return []

        print(f"  从 {file_count} 个文件中提取了 {len(all_keywords_by_item)} 个条目")

        # 构建网络
        graph = self.build_cooccurrence_network(all_keywords_by_item, min_cooccurrence)

        if len(graph.nodes()) == 0:
            print(f"警告: 目录 {input_dir} 构建的网络没有节点")
            return []

        # 计算指标
        metrics = self.calculate_network_metrics(graph)

        # 生成输出文件名（使用目录名）
        dir_name = os.path.basename(os.path.normpath(input_dir))
        if not dir_name or dir_name == ".":
            dir_name = "combined"

        output_base = os.path.join(output_dir, dir_name)

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 保存网络可视化
        html_path = f"{output_base}_network.html"
        self.visualize_network(
            graph, html_path, title=f"关键词关系网络 - {dir_name} ({file_count}个文件)"
        )

        # 保存网络指标
        metrics_path = f"{output_base}_metrics.json"
        self.save_metrics(metrics, metrics_path)

        result = {
            "input_dir": input_dir,
            "processed_files": processed_files,
            "output_html": html_path,
            "output_metrics": metrics_path,
            "num_files": file_count,
            "num_items": len(all_keywords_by_item),
            "num_nodes": graph.number_of_nodes(),
            "num_edges": graph.number_of_edges(),
            "metrics": metrics,
        }

        print(
            f"完成: 生成合并网络图 {html_path} "
            f"(来自 {file_count} 个文件, "
            f"节点: {graph.number_of_nodes()}, "
            f"边: {graph.number_of_edges()})"
        )

        # 返回包含单个结果的列表以保持与现有代码的兼容性
        return [result]

    def _generate_summary_report(self, results: List[Dict[str, Any]], output_dir: str):
        """
        生成处理结果的汇总报告

        参数：
            results: 处理结果列表
            output_dir: 输出目录
        """
        summary = {
            "total_files": len(results),
            "total_nodes": sum(r.get("num_nodes", 0) for r in results),
            "total_edges": sum(r.get("num_edges", 0) for r in results),
            "files": results,
        }

        summary_path = os.path.join(output_dir, "summary_report.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"生成汇总报告: {summary_path}")


def print_banner():
    """打印程序横幅"""
    banner = """
    ========================================
        关键词关系网络可视化工具
    ========================================

    功能：
    1. 从微博热搜数据中提取关键词
    2. 构建关键词共现网络
    3. 计算网络分析指标
    4. 生成交互式网络可视化

    支持输入：单个JSON文件或整个目录
    输出目录：output/keyword_networks/
    ========================================
    """
    print(banner)


def print_summary(results, elapsed_time):
    """打印处理结果摘要"""
    print("\n" + "=" * 50)
    print("处理完成！")
    print("=" * 50)

    if not results:
        print("未处理任何文件")
        return

    total_files = len(results)
    total_nodes = sum(r.get("num_nodes", 0) for r in results)
    total_edges = sum(r.get("num_edges", 0) for r in results)

    print(f"处理时间: {elapsed_time:.2f} 秒")
    print(f"处理文件数: {total_files}")
    print(f"总节点数: {total_nodes}")
    print(f"总边数: {total_edges}")
    print(f"平均节点/文件: {total_nodes / total_files:.1f}")
    print(f"平均边/文件: {total_edges / total_files:.1f}")

    # 显示前几个文件的详细信息
    print("\n前5个文件详情:")
    print("-" * 50)
    for i, result in enumerate(results[:5]):
        input_file = os.path.basename(result["input_file"])
        num_nodes = result.get("num_nodes", 0)
        num_edges = result.get("num_edges", 0)
        html_file = os.path.basename(result["output_html"])
        print(f"{i + 1}. {input_file}: {num_nodes} 节点, {num_edges} 边 → {html_file}")

    if len(results) > 5:
        print(f"... 还有 {len(results) - 5} 个文件")

    # 提供使用提示
    print("\n" + "=" * 50)
    print("使用提示:")
    print("=" * 50)
    print("1. 打开生成的HTML文件进行交互式网络探索")
    print("2. 查看JSON指标文件获取详细网络分析数据")
    print("3. 使用浏览器打开HTML文件查看交互式网络图")


def validate_input_path(input_path):
    """验证输入路径"""
    if not os.path.exists(input_path):
        print(f"错误: 输入路径不存在: {input_path}")
        return False

    if os.path.isfile(input_path) and not input_path.endswith(".json"):
        print(f"错误: 输入文件必须是JSON格式: {input_path}")
        return False

    return True


def quick_test():
    """
    快速功能测试
    """
    print("=== 快速功能测试 ===\n")

    test_data = {
        "date": "2025-01-01",
        "count": 3,
        "data": [
            {
                "rank": 1,
                "title": "赵露思发长文回应",
                "category": "文娱",
                "heat": 1000.0,
                "date": "2025-01-01",
            },
            {
                "rank": 2,
                "title": "新年快乐",
                "category": "生活",
                "heat": 800.0,
                "date": "2025-01-01",
            },
            {
                "rank": 3,
                "title": "种地吧直播",
                "category": "影视",
                "heat": 600.0,
                "date": "2025-01-01",
            },
        ],
    }

    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(test_data, f, ensure_ascii=False)
        temp_file = f.name

    try:
        processor = KeywordNetwork(min_word_length=2)

        # 测试数据加载
        data = processor.load_json(temp_file)
        print("✅ 数据加载测试通过")

        # 测试关键词提取
        keywords_by_item = processor.extract_keywords_from_data(data)
        print(f"✅ 关键词提取测试通过，提取到 {len(keywords_by_item)} 个条目")

        # 测试网络构建
        graph = processor.build_cooccurrence_network(keywords_by_item)
        print(f"✅ 网络构建测试通过，构建了 {graph.number_of_nodes()} 个节点")

        # 清理临时文件
        os.unlink(temp_file)

        print("\n🎉 所有测试通过！")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        if os.path.exists(temp_file):
            os.unlink(temp_file)
        return False


def load_config(config_file: str) -> Optional[Dict[str, Any]]:
    """
    从配置文件加载参数

    参数：
        config_file: 配置文件路径 (JSON格式)

    返回：
        配置参数字典，失败时返回None
    """
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"错误: 配置文件不存在: {config_file}")
        return None
    except json.JSONDecodeError as e:
        print(f"错误: 配置文件格式错误: {e}")
        return None
    except Exception as e:
        print(f"错误: 无法加载配置文件: {e}")
        return None


def main():
    """
    命令行入口点
    """
    parser = argparse.ArgumentParser(description="关键词关系网络可视化工具")
    parser.add_argument("input", help="输入文件或目录路径", nargs="?")
    parser.add_argument(
        "-c",
        "--config",
        help="配置文件路径 (JSON格式)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output/keyword_networks",
        help="输出目录 (默认: output/keyword_networks)",
    )
    parser.add_argument(
        "-m",
        "--min-cooccurrence",
        type=int,
        default=1,
        help="最小共现次数阈值 (默认: 1)",
    )
    parser.add_argument(
        "-l", "--min-length", type=int, default=2, help="最小词语长度 (默认: 2)"
    )
    parser.add_argument(
        "--font-family",
        default="Noto Sans CJK SC",
        help="交互式网络图字体 (默认: Noto Sans CJK SC)",
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=20,
        help="交互式网络图字体大小 (默认: 20)",
    )
    parser.add_argument(
        "--static-font-family",
        default="DejaVu Sans",
        help="静态图字体 (默认: DejaVu Sans)",
    )
    parser.add_argument(
        "--static-font-size",
        type=int,
        default=16,
        help="静态图标题字体大小 (默认: 16)",
    )
    parser.add_argument(
        "--node-label-font-size",
        type=int,
        default=10,
        help="静态图节点标签字体大小 (默认: 10)",
    )
    parser.add_argument("-t", "--test", action="store_true", help="运行快速功能测试")
    parser.add_argument("-q", "--quiet", action="store_true", help="安静模式，减少输出")

    args = parser.parse_args()

    # 如果提供了配置文件，加载并更新参数
    if args.config:
        config = load_config(args.config)
        if config is None:
            return 1  # load_config已经打印了错误信息

        # 更新参数，配置文件的优先级高于命令行参数
        if "processing_settings" in config:
            ps = config["processing_settings"]
            if "min_word_length" in ps:
                args.min_length = ps["min_word_length"]
            if "min_cooccurrence" in ps:
                args.min_cooccurrence = ps["min_cooccurrence"]

        if "output_settings" in config and "output_dir" in config["output_settings"]:
            args.output = config["output_settings"]["output_dir"]

        # 只有在命令行未提供输入时，才使用配置文件的输入路径
        if (
            not args.input
            and "input_settings" in config
            and "input_path" in config["input_settings"]
        ):
            args.input = config["input_settings"]["input_path"]

        # 更新字体配置
        if "visualization_settings" in config:
            vs = config["visualization_settings"]
            if "html_output" in vs and "font_family" in vs["html_output"]:
                args.font_family = vs["html_output"]["font_family"]
            if "html_output" in vs and "font_size" in vs["html_output"]:
                args.font_size = vs["html_output"]["font_size"]
            if "static_output" in vs and "font_family" in vs["static_output"]:
                args.static_font_family = vs["static_output"]["font_family"]
            if "static_output" in vs and "font_size" in vs["static_output"]:
                args.static_font_size = vs["static_output"]["font_size"]
            # 节点标签字体大小可能需要在config中添加新字段
            if "node_label_font_size" in vs:
                args.node_label_font_size = vs["node_label_font_size"]

    # 测试模式
    if args.test:
        success = quick_test()
        return 0 if success else 1

    # 正常模式
    else:
        # 正常模式需要输入参数
        if not args.input:
            print("错误: 需要指定输入文件或目录路径")
            print("使用 --help 查看帮助信息")
            return 1

        if not args.quiet:
            print_banner()

        # 验证输入路径
        if not validate_input_path(args.input):
            return 1

        # 创建输出目录
        os.makedirs(args.output, exist_ok=True)

        # 创建处理器
        try:
            processor = KeywordNetwork(
                min_word_length=args.min_length,
                font_family=args.font_family,
                font_size=args.font_size,
                static_font_family=args.static_font_family,
                static_font_size=args.static_font_size,
                node_label_font_size=args.node_label_font_size,
            )
        except ImportError as e:
            print(f"错误: {e}")
            print("请安装所需依赖: pip install jieba networkx pyvis matplotlib")
            return 1
        except Exception as e:
            print(f"错误: 无法创建关键词处理器: {e}")
            return 1

        # 根据输入类型进行处理
        try:
            start_time = time.time()

            if os.path.isfile(args.input):
                print(f"正在处理文件: {args.input}")
                result = processor.process_file(
                    args.input, args.output, min_cooccurrence=args.min_cooccurrence
                )
                results = [result] if result else []
            else:
                print(f"正在处理目录: {args.input}")
                results = processor.process_directory(
                    args.input, args.output, min_cooccurrence=args.min_cooccurrence
                )

            elapsed_time = time.time() - start_time

            if results:
                if not args.quiet:
                    print_summary(results, elapsed_time)
            else:
                print("没有处理任何有效文件")

        except KeyboardInterrupt:
            print("\n\n用户中断处理")
            return 0
        except Exception as e:
            print(f"\n处理过程中出现错误: {e}")
            import traceback

            traceback.print_exc()
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
