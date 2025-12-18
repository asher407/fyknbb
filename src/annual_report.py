"""
2025年度报告分析模块

功能：
    - 汇总全年数据
    - 提取关键词并统计频率（集成 word_cloud.KeywordExtractor）
    - 分析时间分布
    - 构建关键词共现网络（集成 word_network.KeywordNetwork）
    - 生成关键词网络图可视化
    - 生成年度综合报告
    
已集成的现有成果：
    - word_cloud.KeywordExtractor: 专业的中文分词和关键词提取
    - word_network.KeywordNetwork: 关键词共现网络构建与可视化
    - word_network.NetworkConfig: 网络配置参数
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any
import re
from collections import Counter
import pandas as pd
import numpy as np
from datetime import datetime
import sys

# 导入已有模块
try:
    from .word_cloud import KeywordExtractor
    from .word_network import KeywordNetwork, NetworkConfig
except ImportError:
    try:
        from word_cloud import KeywordExtractor
        from word_network import KeywordNetwork, NetworkConfig
    except ImportError:
        # 降级处理
        KeywordExtractor = None
        KeywordNetwork = None
        NetworkConfig = None


def load_all_json_data(data_dir: str = "data") -> pd.DataFrame:
    """
    递归加载指定目录内所有 JSON 文件，处理嵌套数据结构
    
    Args:
        data_dir: 数据目录路径
        
    Returns:
        合并后的 DataFrame
    """
    all_data = []
    data_path = Path(data_dir)
    
    if not data_path.exists():
        return pd.DataFrame()
    
    for json_file in data_path.rglob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 处理不同的数据结构
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            # 检查是否是嵌套结构（包含 'data' 字段）
                            if 'data' in item and isinstance(item['data'], list):
                                all_data.extend(item['data'])
                            else:
                                all_data.append(item)
                elif isinstance(data, dict):
                    if 'data' in data and isinstance(data['data'], list):
                        all_data.extend(data['data'])
                    else:
                        all_data.append(data)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
    
    if not all_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(all_data)
    
    # 标准化列名
    if 'title' not in df.columns and 'content' in df.columns:
        df.rename(columns={'content': 'title'}, inplace=True)
    
    return df


def extract_keywords(titles: List[str], top_n: int = 50) -> Dict[str, int]:
    """
    从标题中提取关键词（优先使用 KeywordExtractor，提供多级降级方案）
    
    Args:
        titles: 标题列表
        top_n: 返回前N个频率最高的关键词
        
    Returns:
        关键词及频率的字典
    """
    # 一级方案：使用 KeywordExtractor（最完善的分词和停用词处理）
    if KeywordExtractor is not None:
        try:
            extractor = KeywordExtractor(min_word_length=2)
            word_freq = Counter()
            for title in titles:
                words = extractor.extract_keywords(title)
                word_freq.update(words)
            return dict(word_freq.most_common(top_n))
        except Exception as e:
            print(f"KeywordExtractor failed: {e}, falling back to jieba")
    
    # 二级方案：使用 jieba 分词
    try:
        import jieba
        
        stopwords = {
            '的', '了', '和', '是', '在', '到', '一', '个', '为', '中',
            '回应', '什么', '怎么', '这么', '为什么', '不要', '真的',
            '吗', '呢', '吧', '啊', '哦', '这', '那', '有', '没有',
            '很', '比', '更', '最', '就', '还', '也', '被', '把', '向',
            '让', '给', '从', '以', '经', '于', '对', '疑似', '不是'
        }
        
        word_freq = Counter()
        for title in titles:
            words = jieba.cut(title, cut_all=False)
            for word in words:
                if len(word) >= 2 and word not in stopwords:
                    word_freq[word] += 1
        
        return dict(word_freq.most_common(top_n))
    except ImportError:
        print("jieba not available, using regex fallback")
    
    # 三级方案：使用正则分割
    word_freq = Counter()
    for title in titles:
        words = re.findall(r'[\u4e00-\u9fff]+', title)
        word_freq.update(words)
    return dict(word_freq.most_common(top_n))


def analyze_temporal_distribution(df: pd.DataFrame) -> Dict[str, int]:
    """
    分析时间分布（按月统计）
    
    Args:
        df: 数据框
        
    Returns:
        月份分布字典 {月份: 数量}
    """
    if df.empty:
        return {}
    
    # 寻找时间列
    date_col = None
    for col in ['create_time', 'date', 'timestamp', 'time']:
        if col in df.columns:
            date_col = col
            break
    
    if date_col is None:
        return {}
    
    try:
        # 转换为时间类型
        df['parsed_date'] = pd.to_datetime(df[date_col], errors='coerce')
        
        # 提取月份
        df['month'] = df['parsed_date'].dt.strftime('%Y-%m')
        
        # 按月统计
        monthly_dist = df['month'].value_counts().sort_index().to_dict()
        
        return monthly_dist
    except Exception as e:
        print(f"Error analyzing temporal distribution: {e}")
        return {}


def build_keyword_cooccurrence_network(titles: List[str]) -> Dict[str, List[str]]:
    """
    构建关键词共现网络（优先使用 word_network.KeywordNetwork）
    
    Args:
        titles: 标题列表
        
    Returns:
        关键词共现字典 {word: [related_words]}
    """
    if not titles:
        return {}
    
    # 一级方案：使用 KeywordNetwork（高质量的共现网络构建）
    if KeywordNetwork is not None and NetworkConfig is not None:
        try:
            network_builder = KeywordNetwork()
            cfg = NetworkConfig(year="2025", min_keyword_freq=5, min_cooccur=2)
            
            # 构建统计
            word_freq, cooccur_freq = network_builder.build_stats(titles, cfg)
            
            # 转换为邻接表格式
            network = {}
            for (word1, word2), count in cooccur_freq.items():
                if word1 not in network:
                    network[word1] = []
                if word2 not in network:
                    network[word2] = []
                if word2 not in network[word1]:
                    network[word1].append(word2)
                if word1 not in network[word2]:
                    network[word2].append(word1)
            
            # 过滤低度节点
            network = {k: v for k, v in network.items() if len(v) >= 2}
            
            return network
        except Exception as e:
            print(f"KeywordNetwork failed: {e}, falling back to jieba")
    
    # 二级方案：使用 jieba 构建简单网络
    try:
        import jieba
        
        network = {}
        stopwords = {
            '的', '了', '和', '是', '在', '到', '一', '个', '为', '中',
            '回应', '什么', '怎么', '这么', '为什么', '不要', '真的',
            '吗', '呢', '吧', '啊', '哦', '这', '那', '有', '没有'
        }
        
        for title in titles:
            words = [w for w in jieba.cut(title) if len(w) >= 2 and w not in stopwords]
            for word in words:
                if word not in network:
                    network[word] = []
                for related_word in words:
                    if related_word != word and related_word not in network[word]:
                        network[word].append(related_word)
        
        # 去重并过滤低度节点
        network = {k: list(set(v)) for k, v in network.items() if len(set(v)) >= 2}
        
        return network
    except ImportError:
        print("jieba not available, using regex fallback")
        return {}


def generate_word_network_visualization(titles: List[str], output_dir: str = "output") -> Dict[str, Any]:
    """
    使用 word_network 模块生成高质量的关键词网络可视化
    
    Args:
        titles: 标题列表
        output_dir: 输出目录
        
    Returns:
        包含图片路径和图数据的字典
    """
    if KeywordNetwork is None or not titles:
        return {}
    
    try:
        network_builder = KeywordNetwork(output_base=output_dir)
        cfg = NetworkConfig(
            year="2025",
            min_keyword_freq=5,
            min_cooccur=2,
            max_nodes=100,
            max_edges=300,
            layout="kk"
        )
        
        # 构建图
        word_freq, cooccur_freq = network_builder.build_stats(titles, cfg)
        G = network_builder.build_graph(word_freq, cooccur_freq, cfg)
        
        if G.number_of_nodes() == 0:
            return {"success": False, "error": "No nodes in graph"}
        
        # 绘制并保存
        img_path = network_builder.draw(G, "2025", cfg, title="2025年度热搜关键词共现网络")
        
        return {
            "image_path": img_path,
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "success": True
        }
    except Exception as e:
        print(f"Error generating network visualization: {e}")
        return {"success": False, "error": str(e)}


def generate_annual_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    生成年度汇总统计
    
    Args:
        df: 数据框
        
    Returns:
        统计摘要字典
    """
    if df.empty:
        return {
            "error": "No data available",
            "total_records": 0,
            "total_unique_titles": 0,
            "heat_stats": {},
            "date_range": {},
            "top_10_titles": [],
            "keyword_frequency": {}
        }
    
    # 基本统计
    summary = {
        "total_records": len(df),
        "total_unique_titles": df['title'].nunique() if 'title' in df.columns else 0,
    }
    
    # 热度统计
    heat_col = None
    for col in ['heat', 'heat_num', 'heat_value']:
        if col in df.columns:
            heat_col = col
            break
    
    if heat_col is not None:
        heat_values = pd.to_numeric(df[heat_col], errors='coerce').dropna()
        if len(heat_values) > 0:
            summary['heat_stats'] = {
                'max': float(heat_values.max()),
                'min': float(heat_values.min()),
                'mean': float(heat_values.mean()),
                'median': float(heat_values.median()),
                'std': float(heat_values.std()),
            }
        else:
            summary['heat_stats'] = {}
    else:
        summary['heat_stats'] = {}
    
    # 时间范围
    date_col = None
    for col in ['create_time', 'date', 'timestamp', 'time']:
        if col in df.columns:
            date_col = col
            break
    
    if date_col is not None:
        try:
            dates = pd.to_datetime(df[date_col], errors='coerce')
            summary['date_range'] = {
                'start': str(dates.min().date()),
                'end': str(dates.max().date()),
            }
        except:
            summary['date_range'] = {'start': 'N/A', 'end': 'N/A'}
    else:
        summary['date_range'] = {'start': 'N/A', 'end': 'N/A'}
    
    # Top 10 热搜
    if heat_col is not None and 'title' in df.columns:
        top_titles = df.nlargest(10, heat_col)
        summary['top_10_titles'] = [
            {
                'title': row['title'],
                'heat': float(row[heat_col]),
                'rank': int(row['rank']) if 'rank' in df.columns else i+1
            }
            for i, (_, row) in enumerate(top_titles.iterrows())
        ]
    else:
        summary['top_10_titles'] = []
    
    # 关键词频率（使用优化后的提取器）
    if 'title' in df.columns:
        keywords = extract_keywords(df['title'].dropna().tolist(), top_n=40)
        summary['keyword_frequency'] = keywords
    else:
        summary['keyword_frequency'] = {}
    
    return summary


def generate_annual_report(data_dir: str = "data") -> Dict[str, Any]:
    """
    生成完整的年度报告（集成现有成果）
    
    Args:
        data_dir: 数据目录
        
    Returns:
        完整的报告字典，包括：
        - summary: 年度统计汇总
        - temporal_distribution: 月度分布
        - keyword_network: 关键词共现网络
        - network_visualization: 网络可视化（如可用）
    """
    # 加载数据
    df = load_all_json_data(data_dir)
    
    # 生成各个部分
    summary = generate_annual_summary(df)
    
    if "error" in summary:
        return summary
    
    temporal_dist = analyze_temporal_distribution(df)
    
    titles = df['title'].dropna().tolist() if 'title' in df.columns else []
    
    # 构建关键词共现网络
    keyword_network = build_keyword_cooccurrence_network(titles)
    
    # 生成关键词网络可视化
    network_viz = generate_word_network_visualization(titles)
    
    # 组合报告
    report = {
        "year": 2025,
        "report_date": datetime.now().isoformat(),
        "summary": summary,
        "temporal_distribution": temporal_dist,
        "keyword_network": keyword_network,
        "network_visualization": network_viz,
    }
    
    return report
