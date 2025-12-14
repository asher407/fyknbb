"""
数据查询模块

本模块提供类似数据库的查询功能，用于筛选符合条件的热搜数据。

主要功能：
    1. 从 data_processed 目录加载所有热搜数据
    2. 支持多条件组合查询：日期范围、分类、排名范围、热度范围、阅读量范围、讨论量范围、原创量范围
    3. 查询结果可以保存到 output 目录
    4. 支持索引构建以提高查询性能

使用示例：
    query = DataQuery()
    results = query.query(
        date_range=("2025-01-01", "2025-01-31"),
        categories=["明星", "综艺"],
        rank_range=(1, 10),
        heat_range=(1000, None)
    )
    query.save_results(results, "output/query_results.json")
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


class DataQuery:
    """
    数据查询类，提供热搜数据的多条件筛选功能。

    属性：
        data_dir: 数据目录路径（默认为 data_processed）
        data: 加载的所有热搜数据项列表
        date_index: 日期索引，映射日期字符串到数据项列表
        category_index: 分类索引，映射分类字符串到数据项列表

    方法：
        load_data(): 从数据目录加载所有JSON文件
        build_index(): 构建日期和分类索引
        query(): 执行多条件查询
        save_results(): 保存查询结果到文件
        query_to_file(): 执行查询并直接保存到文件
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化数据查询器。

        参数：
            data_dir: 数据目录路径，如果为None则使用默认的data_processed目录

        返回：
            DataQuery实例
        """
        if data_dir is None:
            # 默认路径：项目根目录下的data_processed文件夹
            script_dir = Path(__file__).parent  # src目录
            project_root = script_dir.parent  # 项目根目录
            self.data_dir = project_root / "data_processed"
        else:
            self.data_dir = Path(data_dir)

        # 数据存储
        self.data: List[Dict[str, Any]] = []  # 所有数据项
        self.date_index: Dict[str, List[Dict[str, Any]]] = {}  # 日期索引
        self.category_index: Dict[str, List[Dict[str, Any]]] = {}  # 分类索引

        # 加载数据并构建索引
        self.load_data()
        self.build_index()

    def load_data(self) -> None:
        """
        从data_processed目录加载所有JSON数据文件。

        内部逻辑：
            1. 递归遍历data_dir目录下的所有.json文件
            2. 读取每个文件，提取date和data字段
            3. 为每个数据项添加date字段（从文件提取）
            4. 将所有数据项合并到self.data列表中

        返回：
            无，但会更新self.data属性
        """
        self.data = []
        json_files = list(self.data_dir.rglob("*.json"))

        if not json_files:
            raise FileNotFoundError(f"在目录 {self.data_dir} 中未找到JSON文件")

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    file_data = json.load(f)

                file_date = file_data.get("date", "")
                items = file_data.get("data", [])

                for item in items:
                    # 确保每个数据项都有日期字段
                    item_with_date = item.copy()
                    item_with_date["date"] = file_date
                    self.data.append(item_with_date)

            except (json.JSONDecodeError, KeyError) as e:
                print(f"警告：加载文件 {json_file} 时出错: {e}")
                continue

        print(f"成功加载 {len(self.data)} 条热搜数据")

    def build_index(self) -> None:
        """
        构建日期和分类索引以提高查询性能。

        内部逻辑：
            1. 遍历所有数据项，按日期分组建立日期索引
            2. 遍历所有数据项，按分类分组建立分类索引
            3. 空分类（""）会被索引为"未分类"

        返回：
            无，但会更新self.date_index和self.category_index属性
        """
        # 构建日期索引
        self.date_index = {}
        for item in self.data:
            date = item.get("date", "")
            if date not in self.date_index:
                self.date_index[date] = []
            self.date_index[date].append(item)

        # 构建分类索引
        self.category_index = {}
        for item in self.data:
            category = item.get("category", "")
            if not category:  # 空字符串视为"未分类"
                category = "未分类"

            if category not in self.category_index:
                self.category_index[category] = []
            self.category_index[category].append(item)

        print(
            f"索引构建完成：{len(self.date_index)} 个日期，{len(self.category_index)} 个分类"
        )

    def query(
        self,
        date_range: Optional[Tuple[str, str]] = None,
        categories: Optional[List[str]] = None,
        rank_range: Optional[Tuple[int, int]] = None,
        heat_range: Optional[Tuple[float, float]] = None,
        reads_range: Optional[Tuple[float, float]] = None,
        discussions_range: Optional[Tuple[float, float]] = None,
        originals_range: Optional[Tuple[float, float]] = None,
        title_keywords: Optional[List[str]] = None,
        sort_by: Optional[str] = "heat_desc",
    ) -> List[Dict[str, Any]]:
        """
        执行多条件数据查询。

        参数：
            date_range: 日期范围，元组格式 (开始日期, 结束日期)，日期格式为 "YYYY-MM-DD"
            categories: 分类列表，如 ["明星", "综艺"]，None表示不过滤
            rank_range: 排名范围，元组格式 (最小排名, 最大排名)，包含边界
            heat_range: 热度范围，元组格式 (最小热度, 最大热度)
            reads_range: 阅读量范围，元组格式 (最小阅读量, 最大阅读量)
            discussions_range: 讨论量范围，元组格式 (最小讨论量, 最大讨论量)
            originals_range: 原创量范围，元组格式 (最小原创量, 最大原创量)
            title_keywords: 标题关键词列表，包含任一关键词的标题都会被选中
            sort_by: 排序方式，可选值: "heat_desc" (默认, 热度降序), "heat_asc" (热度升序),
                    "rank_desc" (排名降序), "rank_asc" (排名升序),
                    "date_desc" (日期降序), "date_asc" (日期升序),
                    "reads_desc" (阅读量降序), "reads_asc" (阅读量升序),
                    "discussions_desc" (讨论量降序), "discussions_asc" (讨论量升序),
                    "originals_desc" (原创量降序), "originals_asc" (原创量升序),
                    "title_asc" (标题升序), "title_desc" (标题降序)

        返回：
            符合所有条件的数据项列表（按指定方式排序）

        内部逻辑：
            1. 如果提供了日期范围，先使用日期索引快速筛选
            2. 如果没有日期范围，从所有数据开始筛选
            3. 按顺序应用各个筛选条件
            4. 按指定方式排序结果
            5. 返回最终结果
        """
        # 初始数据集
        if date_range:
            filtered_items = self._filter_by_date_range(date_range)
        else:
            filtered_items = self.data.copy()

        # 应用各个筛选条件
        if categories:
            filtered_items = self._filter_by_categories(filtered_items, categories)

        if rank_range:
            filtered_items = self._filter_by_numeric_range(
                filtered_items, "rank", rank_range
            )

        if heat_range:
            filtered_items = self._filter_by_numeric_range(
                filtered_items, "heat", heat_range
            )

        if reads_range:
            filtered_items = self._filter_by_numeric_range(
                filtered_items, "reads", reads_range
            )

        if discussions_range:
            filtered_items = self._filter_by_numeric_range(
                filtered_items, "discussions", discussions_range
            )

        if originals_range:
            filtered_items = self._filter_by_numeric_range(
                filtered_items, "originals", originals_range
            )

        if title_keywords:
            filtered_items = self._filter_by_title_keywords(
                filtered_items, title_keywords
            )

        # 对结果进行排序
        sorted_items = self._sort_results(filtered_items, sort_by)

        return sorted_items

    def _filter_by_date_range(
        self, date_range: Tuple[str, str]
    ) -> List[Dict[str, Any]]:
        """
        按日期范围筛选数据。

        内部逻辑：
            1. 解析开始日期和结束日期
            2. 遍历日期索引，选择在范围内的日期对应的数据
            3. 合并所有选中的数据项

        返回：
            指定日期范围内的数据项列表
        """
        start_date, end_date = date_range
        result = []

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"日期格式错误，应为 YYYY-MM-DD 格式: {date_range}")

        for date_str, items in self.date_index.items():
            try:
                item_dt = datetime.strptime(date_str, "%Y-%m-%d")
                if start_dt <= item_dt <= end_dt:
                    result.extend(items)
            except ValueError:
                # 日期格式不正确的跳过
                continue

        return result

    def _filter_by_categories(
        self, items: List[Dict[str, Any]], categories: List[str]
    ) -> List[Dict[str, Any]]:
        """
        按分类筛选数据。

        内部逻辑：
            1. 遍历数据项，检查分类是否在指定分类列表中
            2. 空分类视为"未分类"
            3. 如果"未分类"在分类列表中，空分类的数据也会被选中

        返回：
            指定分类的数据项列表
        """
        # 处理空分类
        normalized_categories = []
        for cat in categories:
            if not cat:
                normalized_categories.append("未分类")
            else:
                normalized_categories.append(cat)

        result = []
        for item in items:
            category = item.get("category", "")
            if not category:
                category = "未分类"

            if category in normalized_categories:
                result.append(item)

        return result

    def _filter_by_numeric_range(
        self,
        items: List[Dict[str, Any]],
        field: str,
        value_range: Tuple[Union[int, float, None], Union[int, float, None]],
    ) -> List[Dict[str, Any]]:
        """
        按数值范围筛选数据。

        内部逻辑：
            1. 解析最小值和最大值（允许为None表示无限制）
            2. 遍历数据项，检查字段值是否在范围内
            3. 处理字段值可能为None的情况

        返回：
            指定数值范围内的数据项列表
        """
        min_val, max_val = value_range
        result = []

        for item in items:
            value = item.get(field)

            # 处理None值
            if value is None:
                continue

            # 转换为浮点数进行比较
            try:
                float_value = float(value)
            except (ValueError, TypeError):
                continue

            # 检查范围
            if min_val is not None and float_value < min_val:
                continue
            if max_val is not None and float_value > max_val:
                continue

            result.append(item)

        return result

    def _sort_results(
        self, items: List[Dict[str, Any]], sort_by: str
    ) -> List[Dict[str, Any]]:
        """
        对查询结果进行排序。

        内部逻辑：
            1. 根据sort_by参数确定排序字段和顺序
            2. 提取排序字段的值，处理可能为None的情况
            3. 按指定顺序进行排序

        返回：
            排序后的数据项列表
        """
        if not items:
            return items

        # 默认排序方式为热度降序
        if sort_by is None:
            sort_by = "heat_desc"

        # 确定排序字段和顺序
        sort_configs = {
            "heat_desc": ("heat", True, False),  # (字段名, 逆序, 字符串类型)
            "heat_asc": ("heat", False, False),
            "rank_desc": ("rank", True, False),
            "rank_asc": ("rank", False, False),
            "date_desc": ("date", True, True),
            "date_asc": ("date", False, True),
            "reads_desc": ("reads", True, False),
            "reads_asc": ("reads", False, False),
            "discussions_desc": ("discussions", True, False),
            "discussions_asc": ("discussions", False, False),
            "originals_desc": ("originals", True, False),
            "originals_asc": ("originals", False, False),
            "title_desc": ("title", True, True),
            "title_asc": ("title", False, True),
        }

        if sort_by not in sort_configs:
            # 默认使用热度降序
            sort_field, reverse, is_string = "heat", True, False
        else:
            sort_field, reverse, is_string = sort_configs[sort_by]

        # 定义排序键函数
        def sort_key(item):
            value = item.get(sort_field)

            # 处理None值
            if value is None:
                # 对于字符串类型，None放在最后；对于数值类型，None视为最小/最大值
                if is_string:
                    return "" if not reverse else "zzzzzzzzzz"
                else:
                    return float("-inf") if reverse else float("inf")

            # 对于字符串类型，直接返回
            if is_string:
                return str(value).lower() if isinstance(value, str) else str(value)

            # 对于数值类型，转换为浮点数
            try:
                return float(value)
            except (ValueError, TypeError):
                return float("-inf") if reverse else float("inf")

        # 执行排序
        sorted_items = sorted(items, key=sort_key, reverse=reverse)
        return sorted_items

    def _filter_by_title_keywords(
        self, items: List[Dict[str, Any]], keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """
        按标题关键词筛选数据。

        内部逻辑：
            1. 遍历数据项，检查标题是否包含任一关键词
            2. 不区分大小写进行匹配

        返回：
            标题包含任一关键词的数据项列表
        """
        if not keywords:
            return items

        result = []
        for item in items:
            title = item.get("title", "")
            if not title:
                continue

            title_lower = title.lower()
            for keyword in keywords:
                if keyword.lower() in title_lower:
                    result.append(item)
                    break

        return result

    def save_results(
        self, results: List[Dict[str, Any]], output_path: Union[str, Path]
    ) -> None:
        """
        保存查询结果到JSON文件。

        参数：
            results: 要保存的数据项列表
            output_path: 输出文件路径

        内部逻辑：
            1. 确保输出目录存在
            2. 将结果保存为JSON格式，包含统计信息
            3. 文件会被覆盖（如果已存在）

        返回：
            无
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建输出数据结构
        output_data = {
            "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "result_count": len(results),
            "results": results,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"查询结果已保存到: {output_path} (共 {len(results)} 条数据)")

    def query_to_file(
        self, output_path: Union[str, Path], **query_kwargs
    ) -> List[Dict[str, Any]]:
        """
        执行查询并直接保存结果到文件。

        参数：
            output_path: 输出文件路径
            **query_kwargs: 传递给query()方法的查询参数，包括排序参数（sort_by）

        返回：
            查询结果的数据项列表

        内部逻辑：
            1. 调用query()方法执行查询（支持排序功能）
            2. 调用save_results()保存结果
            3. 返回查询结果
        """
        results = self.query(**query_kwargs)
        self.save_results(results, output_path)
        return results


def main():
    """
    模块测试函数，提供典型的使用示例。

    测试案例：
        1. 查询2025年1月1日到1月7日的所有热搜
        2. 查询分类为"明星"且排名前10的热搜
        3. 查询热度大于1000的热搜
        4. 查询包含"新年"关键词的热搜
        5. 排序功能演示（热度降序、热度升序、排名升序、日期降序、阅读量降序、标题升序）
        6. 保存查询结果到文件
    """
    print("=== 数据查询模块测试 ===")

    try:
        # 创建查询器
        query = DataQuery()

        # 测试1: 查询2025年1月1日到1月7日的所有热搜
        print("\n1. 查询2025年1月1日到1月7日的所有热搜:")
        results1 = query.query(date_range=("2025-01-01", "2025-01-07"))
        print(f"   找到 {len(results1)} 条数据")

        # 测试2: 查询分类为"明星"且排名前10的热搜
        print("\n2. 查询分类为'明星'且排名前10的热搜:")
        results2 = query.query(categories=["明星"], rank_range=(1, 10))
        print(f"   找到 {len(results2)} 条数据")
        if results2:
            print(
                f"   示例: {results2[0].get('title')} (排名: {results2[0].get('rank')})"
            )

        # 测试3: 查询热度大于1000的热搜
        print("\n3. 查询热度大于1000的热搜:")
        results3 = query.query(heat_range=(1000, None))
        print(f"   找到 {len(results3)} 条数据")

        # 测试4: 查询包含"新年"关键词的热搜
        print("\n4. 查询包含'新年'关键词的热搜:")
        results4 = query.query(title_keywords=["新年"])
        print(f"   找到 {len(results4)} 条数据")
        if results4:
            print(
                f"   示例: {results4[0].get('title')} (日期: {results4[0].get('date')})"
            )

        # 测试5: 排序功能演示
        print("\n5. 排序功能演示:")

        # 5.1 默认排序（热度降序）
        print("\n5.1 默认排序（热度降序）:")
        results5_1 = query.query(
            date_range=("2025-01-01", "2025-01-05"),
            categories=["明星"],
            sort_by="heat_desc",
        )
        print(f"   找到 {len(results5_1)} 条数据")
        if results5_1:
            print("   前3条（按热度降序）:")
            for i, item in enumerate(results5_1[:3], 1):
                print(
                    f"     {i}. {item['title']} (热度: {item['heat']:.1f}, 日期: {item['date']})"
                )

        # 5.2 热度升序排序
        print("\n5.2 热度升序排序:")
        results5_2 = query.query(
            date_range=("2025-01-01", "2025-01-05"),
            categories=["明星"],
            sort_by="heat_asc",
        )
        print(f"   找到 {len(results5_2)} 条数据")
        if results5_2:
            print("   前3条（按热度升序）:")
            for i, item in enumerate(results5_2[:3], 1):
                print(
                    f"     {i}. {item['title']} (热度: {item['heat']:.1f}, 日期: {item['date']})"
                )

        # 5.3 排名升序排序
        print("\n5.3 排名升序排序:")
        results5_3 = query.query(
            date_range=("2025-01-01", "2025-01-03"), sort_by="rank_asc"
        )
        print(f"   找到 {len(results5_3)} 条数据")
        if results5_3:
            print("   前3条（按排名升序）:")
            for i, item in enumerate(results5_3[:3], 1):
                print(
                    f"     {i}. #{item['rank']} {item['title']} (日期: {item['date']})"
                )

        # 5.4 日期降序排序
        print("\n5.4 日期降序排序:")
        results5_4 = query.query(
            date_range=("2025-01-01", "2025-01-05"),
            categories=["综艺"],
            sort_by="date_desc",
        )
        print(f"   找到 {len(results5_4)} 条数据")
        if results5_4:
            print("   前3条（按日期降序）:")
            for i, item in enumerate(results5_4[:3], 1):
                print(
                    f"     {i}. {item['date']} {item['title']} (热度: {item['heat']:.1f})"
                )

        # 5.5 阅读量降序排序
        print("\n5.5 阅读量降序排序:")
        results5_5 = query.query(
            date_range=("2025-01-01", "2025-01-03"), sort_by="reads_desc"
        )
        print(f"   找到 {len(results5_5)} 条数据")
        if results5_5:
            print("   前3条（按阅读量降序）:")
            for i, item in enumerate(results5_5[:3], 1):
                print(
                    f"     {i}. {item['title']} (阅读量: {item['reads']:,.0f}, 日期: {item['date']})"
                )

        # 5.6 标题升序排序
        print("\n5.6 标题升序排序:")
        results5_6 = query.query(
            date_range=("2025-01-01", "2025-01-03"),
            categories=["明星"],
            sort_by="title_asc",
        )
        print(f"   找到 {len(results5_6)} 条数据")
        if results5_6:
            print("   前3条（按标题升序）:")
            for i, item in enumerate(results5_6[:3], 1):
                print(f"     {i}. {item['title']} (日期: {item['date']})")

        # 测试6: 保存查询结果到文件（使用默认排序）
        print("\n6. 保存查询结果到文件（使用默认排序）:")
        project_root = Path(__file__).parent.parent
        output_file = project_root / "data" / "output" / "query_result.json"

        saved_results = query.query_to_file(
            output_path=output_file,
            date_range=("2025-01-01", "2025-01-31"),
            categories=["明星", "综艺"],
            rank_range=(1, 20),
            heat_range=(500, None),
            sort_by="heat_desc",  # 默认排序
        )
        print(f"   已保存到: {output_file}")

        # 显示统计信息
        print("\n=== 数据统计 ===")
        print(f"总数据量: {len(query.data)}")
        print(
            f"日期范围: {min(query.date_index.keys())} 到 {max(query.date_index.keys())}"
        )

        # 分类统计
        print("\n分类统计:")
        for category, items in sorted(query.category_index.items()):
            print(f"  {category}: {len(items)} 条")

    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
