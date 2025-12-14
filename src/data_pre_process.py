"""
数据预处理模块

本模块对原始数据进行清洗、转换和规范化，以便后续分析和建模使用。

主要功能：
    1. 异常值检测与处理：去除haet = 0的数据
    2. 数据标准化：将筛选后的数据重新进行rank排序，并修改count值
    3. 数据保存：将处理后的数据保存为新的JSON文件

使用示例：
    process_file("data/2025-01/2025-01-01.json", "data_processed/2025-01/2025-01-01.json")
    process_dir("data/", "data_processed/")
"""

import json
import os
from typing import Dict, List, Any


def _load_json(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(data: Dict[str, Any], out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _process_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = [item for item in items if float(item.get("heat", 0)) != 0]
    for idx, item in enumerate(filtered, start=1):
        item["rank"] = idx
    return filtered


def process_file(input_path: str, output_dir: str = "data_processed") -> str:
    """
    处理单个 JSON 文件：
    - 去除 heat == 0 的记录
    - 重新计算 rank
    - 更新顶层 count
    - 保存到新目录，文件名保持不变

    返回输出文件路径。
    """
    data = _load_json(input_path)
    items = data.get("data", [])
    processed = _process_items(items)

    data["data"] = processed
    data["count"] = len(processed)

    # 构造输出路径，镜像原有的相对目录结构
    rel_path = os.path.relpath(input_path, start=os.path.commonpath([input_path, os.path.dirname(input_path)]))
    # 更稳妥：从项目根的 data 目录开始镜像
    try:
        rel_from_data = os.path.relpath(input_path, start=os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
    except ValueError:
        rel_from_data = os.path.basename(input_path)

    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), output_dir, rel_from_data)
    _save_json(data, out_path)
    return out_path


def process_dir(input_dir: str, output_dir: str = "data_processed") -> List[str]:
    """
    递归处理目录下的所有 .json 文件，并保存到输出目录的镜像结构中。
    返回处理后的文件路径列表。
    """
    processed_paths: List[str] = []
    for root, _, files in os.walk(input_dir):
        for name in files:
            if name.endswith(".json"):
                in_path = os.path.join(root, name)
                out_path = process_file(in_path, output_dir=output_dir)
                processed_paths.append(out_path)
    return processed_paths


if __name__ == "__main__":
    # 默认从项目根的 data 目录读取，输出到 data_processed
    project_root = os.path.dirname(os.path.dirname(__file__))
    src_dir = os.path.join(project_root, "data")
    out_dir = os.path.join(project_root, "data_processed")

    results = process_dir(src_dir, output_dir="data_processed")
    print(f"Processed {len(results)} files. Output dir: {out_dir}")