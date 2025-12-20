"""
热度指数计算模块 - 基于熵权TOPSIS算法

功能：
    - 利用 heat, reads, discussions, originals 四个指标
    - 自动计算各指标的信息熵和权重
    - 使用TOPSIS方法进行综合评分
    - 生成0-100的热度指数

原理：
    熵权法：信息熵越大，指标差异越小，权重越低；反之权重越高
    TOPSIS：加权距离法，靠近理想方案，远离负理想方案
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Any, Union
import warnings

warnings.filterwarnings('ignore')


class HeatIndexCalculator:
    """热度指数计算器 - 基于熵权TOPSIS"""
    
    def __init__(self, 
                 metrics: List[str] = None,
                 epsilon: float = 1e-10):
        """
        初始化计算器
        
        Args:
            metrics: 要使用的指标列表，默认为 ['heat', 'reads', 'discussions', 'originals']
            epsilon: 防止除以零的小数值
        """
        self.metrics = metrics or ['heat', 'reads', 'discussions', 'originals']
        self.epsilon = epsilon
        self.weights = None
        self.normalized_data = None
        self.ideal_solution = None
        self.negative_ideal_solution = None
        
    def normalize_data(self, data: np.ndarray) -> np.ndarray:
        """
        Min-Max标准化：将数据映射到[0, 1]区间
        
        公式：x_norm = (x - x_min) / (x_max - x_min)
        
        Args:
            data: 输入数据矩阵 (n_samples, n_features)
            
        Returns:
            标准化后的数据矩阵
        """
        n_samples, n_features = data.shape
        normalized = np.zeros_like(data, dtype=float)
        
        for j in range(n_features):
            col = data[:, j]
            col_min = np.min(col)
            col_max = np.max(col)
            col_range = col_max - col_min
            
            if col_range < self.epsilon:
                # 如果该列全为同一值，则归一化为0
                normalized[:, j] = 0
            else:
                normalized[:, j] = (col - col_min) / col_range
        
        self.normalized_data = normalized
        return normalized
    
    def calculate_entropy_weights(self, data: np.ndarray) -> np.ndarray:
        """
        计算各指标的熵权
        
        步骤：
            1. 数据标准化
            2. 计算指标权重：p_ij = x_ij / sum(x_ij)
            3. 计算信息熵：H_j = -sum(p_ij * ln(p_ij))
            4. 计算权重：w_j = (1 - H_j) / sum(1 - H_j)
        
        Args:
            data: 原始数据矩阵 (n_samples, n_features)
            
        Returns:
            权重向量 (n_features,)
        """
        # 标准化数据
        normalized = self.normalize_data(data)
        n_samples, n_features = normalized.shape
        
        # 计算各指标权重
        weights_matrix = np.zeros_like(normalized)
        for j in range(n_features):
            col_sum = np.sum(normalized[:, j])
            if col_sum < self.epsilon:
                weights_matrix[:, j] = 1 / n_samples
            else:
                weights_matrix[:, j] = normalized[:, j] / col_sum
        
        # 计算信息熵
        entropy = np.zeros(n_features)
        for j in range(n_features):
            for i in range(n_samples):
                p_ij = weights_matrix[i, j]
                if p_ij > self.epsilon:
                    entropy[j] -= p_ij * np.log(p_ij)
        
        # 熵值标准化 (除以ln(n))
        entropy = entropy / np.log(n_samples)
        
        # 计算权重：差异度 = 1 - 信息熵
        divergence = 1 - entropy
        weights = divergence / np.sum(divergence)
        
        self.weights = weights
        return weights
    
    def topsis_score(self, data: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """
        TOPSIS (Technique for Order Preference by Similarity to Ideal Solution)
        
        步骤：
            1. 加权标准化矩阵
            2. 确定理想方案和负理想方案
            3. 计算距离
            4. 计算贴近度：C_i = D- / (D+ + D-)
        
        Args:
            data: 原始数据矩阵 (n_samples, n_features)
            weights: 权重向量 (n_features,)
            
        Returns:
            相对贴近度向量 (n_samples,) - 范围[0, 1]
        """
        # 标准化数据
        normalized = self.normalize_data(data)
        n_samples = normalized.shape[0]
        
        # 加权标准化矩阵
        weighted_normalized = normalized * weights
        
        # 确定理想方案和负理想方案
        ideal_solution = np.max(weighted_normalized, axis=0)
        negative_ideal_solution = np.min(weighted_normalized, axis=0)
        
        self.ideal_solution = ideal_solution
        self.negative_ideal_solution = negative_ideal_solution
        
        # 计算到理想方案的距离 (D+)
        d_plus = np.sqrt(np.sum((weighted_normalized - ideal_solution) ** 2, axis=1))
        
        # 计算到负理想方案的距离 (D-)
        d_minus = np.sqrt(np.sum((weighted_normalized - negative_ideal_solution) ** 2, axis=1))
        
        # 计算相对贴近度
        scores = np.zeros(n_samples)
        for i in range(n_samples):
            if d_plus[i] + d_minus[i] < self.epsilon:
                scores[i] = 0
            else:
                scores[i] = d_minus[i] / (d_plus[i] + d_minus[i])
        
        return scores
    
    def calculate_heat_index(self, data: np.ndarray, scale: int = 100) -> np.ndarray:
        """
        计算综合热度指数
        
        流程：
            1. 从原始数据提取指标值
            2. 计算熵权
            3. TOPSIS评分
            4. 转换为0-scale的指数
        
        Args:
            data: 原始数据矩阵 (n_samples, n_features)
            scale: 热度指数的最大值，默认100
            
        Returns:
            热度指数向量 (n_samples,)
        """
        # 计算权重
        weights = self.calculate_entropy_weights(data)
        
        # TOPSIS评分 [0, 1]
        scores = self.topsis_score(data, weights)
        
        # 转换到 [0, scale]
        heat_indices = scores * scale
        
        return heat_indices, weights
    
    def process_json_file(self, 
                         file_path: Union[str, Path],
                         output_path: Union[str, Path] = None,
                         scale: int = 100) -> Dict[str, Any]:
        """
        处理JSON数据文件，添加热度指数
        
        Args:
            file_path: 输入JSON文件路径
            output_path: 输出JSON文件路径，如果为None则覆盖原文件
            scale: 热度指数的最大值
            
        Returns:
            包含处理结果的字典
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        try:
            # 读取JSON文件
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # 提取data列表
            if isinstance(json_data, dict) and 'data' in json_data:
                data_list = json_data['data']
            elif isinstance(json_data, list):
                data_list = json_data
            else:
                return {"success": False, "error": "JSON格式不符合预期"}
            
            if not data_list or len(data_list) == 0:
                return {"success": False, "error": "数据为空"}
            
            # 提取指标值
            metrics_data = []
            for item in data_list:
                row = []
                for metric in self.metrics:
                    value = item.get(metric, 0.0)
                    # 处理缺失值
                    if value is None or (isinstance(value, float) and np.isnan(value)):
                        value = 0.0
                    row.append(float(value))
                metrics_data.append(row)
            
            metrics_array = np.array(metrics_data, dtype=float)
            
            # 计算热度指数
            heat_indices, weights = self.calculate_heat_index(metrics_array, scale)
            
            # 标准化后的数据（用于调试）
            normalized_data = self.normalize_data(metrics_array)
            
            # 添加热度指数到原始数据
            for i, item in enumerate(data_list):
                item['heat_index'] = round(float(heat_indices[i]), 2)
                item['normalized_metrics'] = {
                    metric: round(float(normalized_data[i, j]), 4)
                    for j, metric in enumerate(self.metrics)
                }
            
            # 构建输出JSON
            if isinstance(json_data, dict):
                json_data['data'] = data_list
                json_data['entropy_weights'] = {
                    metric: round(float(weights[i]), 4)
                    for i, metric in enumerate(self.metrics)
                }
            else:
                json_data = data_list
            
            # 保存输出文件
            if output_path is None:
                output_path = file_path
            else:
                output_path = Path(output_path)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            return {
                "success": True,
                "file": str(output_path),
                "total_records": len(data_list),
                "entropy_weights": {
                    metric: round(float(weights[i]), 4)
                    for i, metric in enumerate(self.metrics)
                },
                "heat_index_stats": {
                    "min": round(float(np.min(heat_indices)), 2),
                    "max": round(float(np.max(heat_indices)), 2),
                    "mean": round(float(np.mean(heat_indices)), 2),
                    "median": round(float(np.median(heat_indices)), 2),
                    "std": round(float(np.std(heat_indices)), 2)
                }
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def process_directory(self,
                         dir_path: Union[str, Path],
                         output_dir: Union[str, Path] = None,
                         scale: int = 100) -> List[Dict[str, Any]]:
        """
        批量处理目录下的所有JSON文件
        
        Args:
            dir_path: 输入目录路径
            output_dir: 输出目录路径，如果为None则覆盖原文件
            scale: 热度指数的最大值
            
        Returns:
            处理结果列表
        """
        dir_path = Path(dir_path)
        
        if not dir_path.exists():
            return [{"success": False, "error": f"目录不存在: {dir_path}"}]
        
        results = []
        json_files = list(dir_path.rglob("*.json"))
        
        if not json_files:
            return [{"success": False, "error": f"目录中没有JSON文件: {dir_path}"}]
        
        for json_file in json_files:
            if output_dir is None:
                output_path = json_file
            else:
                output_path = Path(output_dir) / json_file.relative_to(dir_path)
            
            result = self.process_json_file(json_file, output_path, scale)
            results.append({
                "file": str(json_file),
                "result": result
            })
        
        return results


def main():
    """示例使用"""
    import sys
    
    # 创建计算器
    calculator = HeatIndexCalculator()
    
    # 示例1：处理单个文件
    file_path = "data_processed/2024-05/2024-05-20.json"
    
    # 先读取数据，用于详细分析
    with open(file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    data_list = json_data['data'] if isinstance(json_data, dict) else json_data
    
    # 提取指标值
    metrics_data = []
    for item in data_list:
        row = []
        for metric in calculator.metrics:
            value = item.get(metric, 0.0)
            if value is None or (isinstance(value, float) and np.isnan(value)):
                value = 0.0
            row.append(float(value))
        metrics_data.append(row)
    
    metrics_array = np.array(metrics_data, dtype=float)
    
    # 显示原始数据统计
    print("=" * 80)
    print("原始数据统计")
    print("=" * 80)
    print(f"{'指标':<15} {'最小值':<15} {'最大值':<15} {'平均值':<15} {'标准差':<15}")
    print("-" * 80)
    for j, metric in enumerate(calculator.metrics):
        col = metrics_array[:, j]
        print(f"{metric:<15} {np.min(col):>14.2f} {np.max(col):>14.2f} {np.mean(col):>14.2f} {np.std(col):>14.2f}")
    
    # 计算权重
    weights = calculator.calculate_entropy_weights(metrics_array)
    normalized = calculator.normalized_data
    
    # 显示标准化数据统计
    print("\n" + "=" * 80)
    print("标准化数据统计 (Min-Max归一化到[0,1])")
    print("=" * 80)
    print(f"{'指标':<15} {'最小值':<15} {'最大值':<15} {'平均值':<15} {'标准差':<15}")
    print("-" * 80)
    for j, metric in enumerate(calculator.metrics):
        col = normalized[:, j]
        print(f"{metric:<15} {np.min(col):>14.4f} {np.max(col):>14.4f} {np.mean(col):>14.4f} {np.std(col):>14.4f}")
    
    # 显示权重计算详情
    print("\n" + "=" * 80)
    print("熵权法计算详情")
    print("=" * 80)
    n_samples = metrics_array.shape[0]
    print(f"样本数量: {n_samples}")
    print(f"指标数量: {len(calculator.metrics)}")
    
    # 重新计算以展示中间步骤
    weights_matrix = np.zeros_like(normalized)
    for j in range(len(calculator.metrics)):
        col_sum = np.sum(normalized[:, j])
        if col_sum < calculator.epsilon:
            weights_matrix[:, j] = 1 / n_samples
        else:
            weights_matrix[:, j] = normalized[:, j] / col_sum
    
    entropy = np.zeros(len(calculator.metrics))
    for j in range(len(calculator.metrics)):
        for i in range(n_samples):
            p_ij = weights_matrix[i, j]
            if p_ij > calculator.epsilon:
                entropy[j] -= p_ij * np.log(p_ij)
    
    entropy = entropy / np.log(n_samples)
    divergence = 1 - entropy
    
    print(f"\n{'指标':<15} {'信息熵':<15} {'差异度':<15} {'权重':<15} {'权重占比':<15}")
    print("-" * 80)
    for j, metric in enumerate(calculator.metrics):
        print(f"{metric:<15} {entropy[j]:>14.4f} {divergence[j]:>14.4f} {weights[j]:>14.4f} {weights[j]*100:>13.2f}%")
    
    print(f"\n权重总和验证: {np.sum(weights):.4f} (应为 1.0000)")
    
    # 处理文件
    result = calculator.process_json_file(file_path)
    
    print("\n" + "=" * 80)
    print("热度指数计算结果")
    print("=" * 80)
    
    if result['success']:
        print(f"✓ 文件: {result['file']}")
        print(f"✓ 处理记录数: {result['total_records']}")
        print(f"\n最终指标权重:")
        for metric, weight in result['entropy_weights'].items():
            print(f"  - {metric}: {weight:.4f} ({weight*100:.2f}%)")
        print(f"\n热度指数统计:")
        for key, value in result['heat_index_stats'].items():
            print(f"  - {key}: {value}")
    else:
        print(f"✗ 处理失败: {result['error']}")
    
    # 示例2：显示前10条记录的热度指数
    if result['success']:
        with open(result['file'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n热度指数 Top 10:")
        print("-" * 100)
        print(f"{'排名':<5} {'标题':<45} {'热度指数':<12} {'原始热度':<12} {'阅读':<10} {'讨论':<10}")
        print("-" * 100)
        
        data_list = data['data'] if isinstance(data, dict) else data
        sorted_data = sorted(data_list, key=lambda x: x.get('heat_index', 0), reverse=True)[:10]
        
        for i, item in enumerate(sorted_data, 1):
            title = item.get('title', 'N/A')[:40]
            heat_idx = item.get('heat_index', 0)
            heat = item.get('heat', 0)
            reads = item.get('reads', 0)
            discussions = item.get('discussions', 0)
            print(f"{i:<5} {title:<45} {heat_idx:<12.2f} {heat:<12.2f} {reads:<10.0f} {discussions:<10.0f}")


if __name__ == "__main__":
    main()
