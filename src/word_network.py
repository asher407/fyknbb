"""
关键词共现网络模块

功能概述：
    - 汇总指定年份（默认 2025）所有热搜标题
    - 利用分词提取关键词并统计词频
    - 统计关键词在同一条热搜标题中的共现关系
    - 使用 NetworkX 构建关系网络，并用 Matplotlib 可视化

可视化说明：
    - 节点：关键词
    - 节点大小：与关键词出现次数（词频）正相关（越大出现越多）
    - 边：两个关键词在同一条热搜标题中同时出现
    - 边粗细：共现次数（同现频次）越大越粗

输出：
    - 图片：output/word_networks/figures/keyword_network_YYYY.png
    - 数据：output/word_networks/data/{nodes,edges}_YYYY.json
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

# 使用无 GUI 后端，避免在服务器/终端环境报错
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib import cm, colors, rcParams
from matplotlib.font_manager import FontProperties

# 兼容作为脚本运行或作为包导入
try:
    from .word_cloud import KeywordExtractor  # type: ignore
except Exception:  # pragma: no cover
    try:
        from word_cloud import KeywordExtractor  # type: ignore
    except Exception:
        import sys
        sys.path.append(os.path.dirname(__file__))
        from word_cloud import KeywordExtractor  # type: ignore


@dataclass
class NetworkConfig:
    year: str = "2025"
    min_word_length: int = 2
    min_keyword_freq: int = 8  # 节点纳入阈值（低频词过滤）
    min_cooccur: int = 4  # 边纳入阈值（低共现过滤）
    max_nodes: int | None = 150  # 限制展示的最大节点数，None 表示不限制
    max_edges: int | None = 400  # 限制展示的最大边数，None 表示不限制
    layout: str = "kk"  # "spring" | "kk"（Kamada-Kawai）
    node_cmap: str = "viridis"
    edge_cmap: str = "plasma"
    max_radius_quantile: float = 0.97  # 移除离中心过远的节点（按半径分位数）


class KeywordNetwork:
    def __init__(self, output_base: str = "output") -> None:
        self.output_base = output_base
        self.output_dir_fig = os.path.join(output_base, "word_networks", "figures")
        self.output_dir_data = os.path.join(output_base, "word_networks", "data")
        os.makedirs(self.output_dir_fig, exist_ok=True)
        os.makedirs(self.output_dir_data, exist_ok=True)

        self.extractor = KeywordExtractor()
        # 字体配置，确保中文正常显示
        self.font_path = self._find_chinese_font()
        self.font_prop = FontProperties(fname=self.font_path) if self.font_path else None
        self._setup_font_for_matplotlib()

    def _find_chinese_font(self) -> str:
        """尽可能找到可用的中文字体文件路径（Windows 优先）。"""
        candidates = [
            # Windows 常见中文字体
            r"C:\\Windows\\Fonts\\msyh.ttc",  # 微软雅黑
            r"C:\\Windows\\Fonts\\msyhbd.ttc",  # 微软雅黑 Bold
            r"C:\\Windows\\Fonts\\simhei.ttf",  # 黑体
            r"C:\\Windows\\Fonts\\SIMHEI.TTF",
            r"C:\\Windows\\Fonts\\simsun.ttc",  # 宋体
            r"C:\\Windows\\Fonts\\SIMSUN.TTC",
            # macOS / Linux 常见中文字体
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        # 最后尝试在系统字体列表中寻找
        try:
            from matplotlib.font_manager import findSystemFonts

            for fp in findSystemFonts():
                name = os.path.basename(fp).lower()
                if any(k in name for k in ["simhei", "simsun", "msyh", "pingfang", "heiti", "notosanscjk"]):
                    return fp
        except Exception:
            pass
        return ""

    def _setup_font_for_matplotlib(self) -> None:
        # 作为兜底，配置 sans-serif 候选列表
        rcParams["font.sans-serif"] = [
            "Microsoft YaHei",
            "SimHei",
            "SimSun",
            "PingFang SC",
            "Noto Sans CJK SC",
            "Arial Unicode MS",
        ]
        rcParams["axes.unicode_minus"] = False

    def load_year_titles(self, data_root: str, year: str) -> Iterable[str]:
        """
        从 data_processed 目录中加载某年的所有标题文本。

        目录结构假定为：data_processed/YYYY-MM/YYYY-MM-DD.json
        """
        root = Path(data_root)
        for month_dir in sorted(root.iterdir()):
            if not month_dir.is_dir():
                continue
            if not month_dir.name.startswith(year + "-"):
                continue
            for day_file in sorted(month_dir.glob("*.json")):
                try:
                    with open(day_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for item in data.get("data", []):
                        title = (item or {}).get("title", "")
                        if title:
                            yield title
                except Exception as e:
                    print(f"读取失败: {day_file} -> {e}")

    def build_stats(self, titles: Iterable[str], cfg: NetworkConfig) -> Tuple[Counter, Counter]:
        """
        基于标题序列构建：
            - 关键词词频统计（nodes）
            - 关键词对共现统计（edges）
        返回 (word_freq, cooccur_freq)
        """
        word_freq: Counter = Counter()
        cooccur_freq: Counter = Counter()

        for title in titles:
            words = [
                w
                for w in self.extractor.extract_keywords(title)
                if len(w) >= cfg.min_word_length
            ]
            if not words:
                continue

            # 同一条标题中去重，避免同词对在该标题重复计数
            uniq_words = sorted(set(words))

            # 词频累计
            word_freq.update(uniq_words)

            # 共现（两两组合）
            for a, b in combinations(uniq_words, 2):
                cooccur_freq[(a, b)] += 1

        return word_freq, cooccur_freq

    def build_graph(
        self, word_freq: Counter, cooccur_freq: Counter, cfg: NetworkConfig
    ) -> nx.Graph:
        """
        根据统计结果构建 NetworkX 无向图。
        仅纳入：
          - 词频 >= cfg.min_keyword_freq 的节点
          - 共现次数 >= cfg.min_cooccur 且两端节点均被纳入 的边
        如果设置了 max_nodes，则选取最高词频的前 N 个节点，并据此筛边。
        """
        # 过滤节点
        nodes = {w: c for w, c in word_freq.items() if c >= cfg.min_keyword_freq}
        if cfg.max_nodes is not None and len(nodes) > cfg.max_nodes:
            # 取前 N 高频
            top = sorted(nodes.items(), key=lambda x: x[1], reverse=True)[: cfg.max_nodes]
            nodes = dict(top)

        G = nx.Graph()
        for w, c in nodes.items():
            G.add_node(w, frequency=c)

        # 过滤边（两端都在 nodes，且权重达标）
        for (a, b), w in cooccur_freq.items():
            if a in nodes and b in nodes and w >= cfg.min_cooccur:
                G.add_edge(a, b, weight=w)

        # 如需限制边数，保留权重最高的前 N 条，并移除孤立点
        if cfg.max_edges is not None and G.number_of_edges() > cfg.max_edges:
            edges_sorted = sorted(G.edges(data=True), key=lambda x: x[2].get("weight", 1), reverse=True)
            keep = set((u, v) for u, v, _ in edges_sorted[: cfg.max_edges])
            for u, v in list(G.edges()):
                if (u, v) not in keep and (v, u) not in keep:
                    G.remove_edge(u, v)

        # 移除没有连边的孤立节点，减少视觉噪声
        isolates = [n for n in list(G.nodes) if G.degree(n) == 0]
        if isolates:
            G.remove_nodes_from(isolates)

        return G

    def _compute_layout(self, G: nx.Graph, layout: str) -> Dict[str, Tuple[float, float]]:
        if layout == "spring":
            return nx.spring_layout(G, k=0.4, seed=42, weight="weight")
        # 默认使用 Kamada-Kawai，通常更稳定
        return nx.kamada_kawai_layout(G, weight="weight")

    def _separate_nodes(
        self,
        pos: Dict[str, Tuple[float, float]],
        min_dist: float = 0.035,
        iterations: int = 40,
        strength: float = 0.04,
    ) -> Dict[str, Tuple[float, float]]:
        """对已有坐标做轻量级排斥，缓解节点重叠。"""
        nodes = list(pos.keys())
        coords = {n: [pos[n][0], pos[n][1]] for n in nodes}
        for _ in range(iterations):
            moved = False
            for i, a in enumerate(nodes):
                ax, ay = coords[a]
                for b in nodes[i + 1 :]:
                    bx, by = coords[b]
                    dx, dy = ax - bx, ay - by
                    dist2 = dx * dx + dy * dy
                    if dist2 == 0:
                        dx, dy, dist2 = 1e-4, 0.0, 1e-8
                    if dist2 < min_dist * min_dist:
                        dist = dist2 ** 0.5
                        push = (min_dist - dist) * strength / (dist or 1e-4)
                        ox, oy = dx * push, dy * push
                        coords[a][0] += ox
                        coords[a][1] += oy
                        coords[b][0] -= ox
                        coords[b][1] -= oy
                        moved = True
            if not moved:
                break
        return {n: (coords[n][0], coords[n][1]) for n in nodes}

    def _remove_far_nodes(
        self,
        G: nx.Graph,
        pos: Dict[str, Tuple[float, float]],
        quantile: float = 0.97,
    ) -> Tuple[Dict[str, Tuple[float, float]], List[str]]:
        """按半径分位数剔除离中心过远的节点。"""
        if not pos or quantile <= 0 or quantile >= 1:
            return pos, []

        dists = [(n, (x * x + y * y) ** 0.5) for n, (x, y) in pos.items()]
        if len(dists) < 5:  # 节点太少不做剔除
            return pos, []

        dists_sorted = sorted(dists, key=lambda t: t[1])
        cut_index = int(len(dists_sorted) * quantile)
        cut_index = min(max(cut_index, 0), len(dists_sorted) - 1)
        cutoff = dists_sorted[cut_index][1]

        removed = [n for n, d in dists_sorted if d > cutoff]
        if not removed:
            return pos, []

        for n in removed:
            pos.pop(n, None)
            if G.has_node(n):
                G.remove_node(n)
        return pos, removed

    def _scale_sizes(self, values: List[int], min_size: int = 200, max_size: int = 3000) -> List[float]:
        if not values:
            return []
        vmin, vmax = min(values), max(values)
        if vmin == vmax:
            return [float((min_size + max_size) // 2)] * len(values)
        return [min_size + (v - vmin) / (vmax - vmin) * (max_size - min_size) for v in values]

    def draw(
        self, G: nx.Graph, year: str, cfg: NetworkConfig, title: str | None = None
    ) -> str:
        """
        将图形绘制并保存为 PNG，返回图片路径。
        """
        if G.number_of_nodes() == 0:
            raise ValueError("图为空：请降低过滤阈值或确认数据")

        pos = self._compute_layout(G, cfg.layout)
        # 加强排斥，减少重合
        pos = self._separate_nodes(pos, min_dist=0.06, iterations=80, strength=0.08)
        pos, removed_far = self._remove_far_nodes(G, pos, quantile=cfg.max_radius_quantile)

        # 节点大小：按 frequency 线性缩放
        node_freq = [G.nodes[n]["frequency"] for n in G.nodes]
        node_sizes = self._scale_sizes(node_freq, min_size=320, max_size=6500)

        # 节点颜色：统一淡蓝色，提升文字可读性
        node_colors = ["#bcd7ff"] * len(node_freq)

        # 边宽度：按 weight 线性缩放
        edge_weights = [G.edges[e]["weight"] for e in G.edges]
        edge_widths = self._scale_sizes(edge_weights, min_size=0.5, max_size=6)

        # 边颜色：按权重梯度着色
        edge_norm = colors.Normalize(vmin=min(edge_weights), vmax=max(edge_weights)) if edge_weights else None
        edge_cmap = cm.get_cmap(cfg.edge_cmap)
        edge_colors = "#000000"  # 固定黑色边，提升对比度

        fig, ax = plt.subplots(figsize=(16, 12))
        ax.set_axis_off()

        # 画边
        nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            width=edge_widths,
            edge_color=edge_colors,
            alpha=0.5,
        )

        # 画点
        nodes = nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_size=node_sizes,
            node_color=node_colors,
            alpha=0.85,
        )
        nodes.set_edgecolor("#ffffff")
        nodes.set_linewidth(0.5)

        # 画标签（字号按词频轻微缩放）
        label_fontsizes = self._scale_sizes(node_freq, min_size=8, max_size=18)
        for (n, (x, y)), fs in zip(pos.items(), label_fontsizes):
            if self.font_prop:
                ax.text(
                    x,
                    y,
                    n,
                    fontsize=fs,
                    ha="center",
                    va="center",
                    color="#1a1a1a",
                    fontproperties=self.font_prop,
                )
            else:
                ax.text(x, y, n, fontsize=fs, ha="center", va="center", color="#1a1a1a")

        if not title:
            title = f"{year} 关键词共现网络（节点大小∝词频，边粗∝共现）"
        if self.font_prop:
            ax.set_title(title, fontsize=16, pad=12, fontproperties=self.font_prop)
        else:
            ax.set_title(title, fontsize=16, pad=12)

        out_png = os.path.join(self.output_dir_fig, f"keyword_network_{year}.png")
        fig.savefig(out_png, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"✓ 网络图已保存: {out_png}")
        return out_png

    def save_graph_data(self, G: nx.Graph, year: str) -> Tuple[str, str]:
        nodes_path = os.path.join(self.output_dir_data, f"nodes_{year}.json")
        edges_path = os.path.join(self.output_dir_data, f"edges_{year}.json")

        nodes_out = [
            {"keyword": n, "frequency": int(G.nodes[n]["frequency"]) }
            for n in G.nodes
        ]
        edges_out = [
            {"source": u, "target": v, "weight": int(d.get("weight", 1))}
            for u, v, d in G.edges(data=True)
        ]

        with open(nodes_path, "w", encoding="utf-8") as f:
            json.dump(nodes_out, f, ensure_ascii=False, indent=2)
        with open(edges_path, "w", encoding="utf-8") as f:
            json.dump(edges_out, f, ensure_ascii=False, indent=2)

        print(f"✓ 网络数据已保存: {nodes_path} & {edges_path}")
        return nodes_path, edges_path


def generate_keyword_network_for_year(
    data_processed_dir: str,
    output_base: str = "output",
    year: str = "2025",
    min_keyword_freq: int = 5,
    min_cooccur: int = 2,
    max_nodes: int | None = 200,
    max_edges: int | None = None,
) -> Tuple[str, str, str]:
    """
    端到端生成年共现网络（图片 + 数据）。
    返回 (png_path, nodes_json, edges_json)
    """
    cfg = NetworkConfig(
        year=year,
        min_keyword_freq=min_keyword_freq,
        min_cooccur=min_cooccur,
        max_nodes=max_nodes,
        max_edges=max_edges,
    )

    kn = KeywordNetwork(output_base=output_base)
    titles = kn.load_year_titles(data_processed_dir, year)
    word_freq, cooccur_freq = kn.build_stats(titles, cfg)
    G = kn.build_graph(word_freq, cooccur_freq, cfg)
    png_path = kn.draw(G, year=year, cfg=cfg)
    nodes_json, edges_json = kn.save_graph_data(G, year=year)
    return png_path, nodes_json, edges_json


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(__file__))
    data_processed_dir = os.path.join(project_root, "data_processed")
    output_dir = os.path.join(project_root, "output")

    # 默认生成 2025 年的关键词共现网络
    try:
        png, nj, ej = generate_keyword_network_for_year(
            data_processed_dir=data_processed_dir,
            output_base=output_dir,
            year="2025",
            min_keyword_freq=12,  # 提高阈值以减少节点
            min_cooccur=6,        # 提高共现阈值以减少边
            max_nodes=110,        # 控制可视节点数量
            max_edges=300,        # 保留高权重边以降低复杂度
        )
        print("生成完成：")
        print("  - 图片:", png)
        print("  - 节点:", nj)
        print("  - 边:", ej)
    except Exception as e:
        print("生成失败:", e)

