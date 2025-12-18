"""
随机获取与今日日期相近的热搜数据

功能：
    1. 读取所有与今日日期相同或相差1天的数据（年份不一样）
    2. 筛选热度值大于1的条目
    3. 随机给出一条数据并输出
    4. 输出文件保存在output目录下

使用方法：
    python random_hot_today.py

输出：
    控制台打印随机选择的热搜条目信息
    同时将结果保存到output/random_hot_today_YYYY-MM-DD.json文件中

代码规范：
    模块化代码结构，每个类定义的方法需要有标准的用户手册
"""

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# 处理导入路径
try:
    from .data_query import DataQuery
except ImportError:
    try:
        from data_query import DataQuery
    except ImportError:
        # 如果还是找不到，从兄弟目录导入
        sys.path.insert(0, str(Path(__file__).parent))
        from data_query import DataQuery


class RandomHotToday:
    """随机获取与今日日期相近的热搜数据"""

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化

        参数：
            data_dir: 数据目录路径，如果为None则使用默认的data_processed目录

        返回：
            RandomHotToday实例

        内部逻辑：
            1. 初始化DataQuery实例用于加载数据
            2. 设置当前日期
            3. 创建输出目录
        """
        # 首先获取项目根目录
        script_dir = Path(__file__).parent  # src目录
        project_root = script_dir.parent  # 项目根目录

        # 初始化DataQuery实例
        if data_dir is None:
            # DataQuery默认使用data_processed目录
            self.data_query = DataQuery()
        else:
            self.data_query = DataQuery(data_dir)

        self.today = datetime.now()
        self.output_dir = project_root / "output"

        # 确保输出目录存在
        self.output_dir.mkdir(exist_ok=True)

    def _date_within_one_day(self, date_str: str) -> bool:
        """
        检查给定日期是否与今天相差1天以内（忽略年份）

        参数：
            date_str: 日期字符串，格式为"YYYY-MM-DD"

        返回：
            如果日期与今天相差1天以内（忽略年份）返回True，否则False

        内部逻辑：
            1. 将日期字符串转换为datetime对象
            2. 使用基准年份（2000年）创建比较日期
            3. 计算与今天日期的最小天数差（考虑跨年情况）
            4. 返回是否小于等于1天
        """
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")

            # 创建基准日期（使用相同的年份以便比较）
            base_year = 2000  # 任意年份
            today_base = datetime(base_year, self.today.month, self.today.day)
            file_date_base = datetime(base_year, file_date.month, file_date.day)

            # 计算天数差（考虑跨年情况）
            # 方法：计算两个日期之间的最小天数差
            diff1 = abs((file_date_base - today_base).days)

            # 考虑跨年情况：比如12月31日和1月1日相差1天
            # 将file_date_base的年份加1再计算
            file_date_base_next_year = datetime(
                base_year + 1, file_date.month, file_date.day
            )
            diff2 = abs((file_date_base_next_year - today_base).days)

            # 将file_date_base的年份减1再计算
            file_date_base_prev_year = datetime(
                base_year - 1, file_date.month, file_date.day
            )
            diff3 = abs((file_date_base_prev_year - today_base).days)

            # 取最小天数差
            min_diff = min(diff1, diff2, diff3)

            return min_diff <= 1

        except ValueError:
            print(f"警告：日期格式错误: {date_str}")
            return False

    def load_and_filter_data(self) -> List[Dict[str, Any]]:
        """
        加载并筛选数据

        返回：
            符合条件的数据项列表

        内部逻辑：
            1. 使用DataQuery获取所有热度大于1的数据
            2. 筛选日期与今天相差1天以内的数据
            3. 返回符合所有条件的数据列表
        """
        print(f"今天是: {self.today.strftime('%Y-%m-%d')}")
        print(f"寻找与今天相差1天以内（忽略年份）且热度大于1的数据...")

        # 使用DataQuery获取所有热度大于1的数据
        try:
            # 先获取所有数据，然后自己筛选日期
            print("正在加载所有数据...")
            all_data = self.data_query.query()
            print(f"共加载 {len(all_data)} 条热搜数据")

            # 筛选热度大于1且日期符合条件的数据
            matching_items = []

            for item in all_data:
                # 检查热度
                heat = item.get("heat", 0)
                if not isinstance(heat, (int, float)) or heat <= 1:
                    continue

                # 检查日期
                date_str = item.get("date", "")
                if not date_str or not self._date_within_one_day(date_str):
                    continue

                # 复制条目并添加额外信息
                item_copy = item.copy()
                matching_items.append(item_copy)

            print(f"找到 {len(matching_items)} 条符合条件的数据")
            return matching_items

        except Exception as e:
            print(f"加载数据时出错: {e}")
            return []

    def select_random_item(
        self, items: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        随机选择一条数据

        参数：
            items: 数据项列表

        返回：
            随机选择的数据项，如果列表为空则返回None

        内部逻辑：
            1. 检查列表是否为空
            2. 使用random.choice随机选择一个条目
        """
        if not items:
            return None

        return random.choice(items)

    def display_item(self, item: Dict[str, Any]) -> None:
        """
        显示数据项信息

        参数：
            item: 数据项

        内部逻辑：
            1. 格式化输出数据项的各个字段
            2. 显示分隔线以提高可读性
        """
        print("\n" + "=" * 60)
        print("随机选择的热搜数据：")
        print("=" * 60)

        print(f"标题: {item.get('title', 'N/A')}")
        print(f"排名: {item.get('rank', 'N/A')}")
        print(f"分类: {item.get('category', 'N/A')}")
        print(f"热度: {item.get('heat', 'N/A')}")
        print(f"阅读量: {item.get('reads', 'N/A')}")
        print(f"讨论量: {item.get('discussions', 'N/A')}")
        print(f"原创量: {item.get('originals', 'N/A')}")
        print(f"日期: {item.get('date', 'N/A')}")

        print("=" * 60)

    def save_to_file(self, item: Dict[str, Any]) -> str:
        """
        将结果保存到文件

        参数：
            item: 要保存的数据项

        返回：
            保存的文件路径

        内部逻辑：
            1. 生成带时间戳的文件名
            2. 创建包含元数据和条目的输出数据结构
            3. 将数据写入JSON文件
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"random_hot_today_{timestamp}.json"
        output_path = self.output_dir / filename

        # 准备保存的数据
        output_data = {
            "selected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "today_date": self.today.strftime("%Y-%m-%d"),
            "selection_criteria": {
                "date_filter": "within 1 day of today (ignoring year)",
                "heat_filter": "> 1",
            },
            "item": item,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存到: {output_path}")
        return str(output_path)

    def run(self) -> bool:
        """
        运行主程序

        返回：
            成功返回True，失败返回False

        内部逻辑：
            1. 加载并筛选数据
            2. 随机选择一条数据
            3. 显示选择的数据
            4. 保存结果到文件
        """
        try:
            # 加载并筛选数据
            matching_items = self.load_and_filter_data()

            if not matching_items:
                print("没有找到符合条件的数据")
                return False

            # 随机选择一条数据
            selected_item = self.select_random_item(matching_items)

            if not selected_item:
                print("无法选择数据")
                return False

            # 显示数据
            self.display_item(selected_item)

            # 保存到文件
            self.save_to_file(selected_item)

            return True

        except Exception as e:
            print(f"程序运行出错: {e}")
            import traceback

            traceback.print_exc()
            return False


def main():
    """主函数

    功能：
        程序入口点，创建RandomHotToday实例并运行

    内部逻辑：
        1. 显示程序标题
        2. 创建RandomHotToday实例
        3. 执行运行逻辑
        4. 处理退出状态
    """
    print("随机获取与今日日期相近的热搜数据")
    print("-" * 40)

    try:
        processor = RandomHotToday()
        success = processor.run()

        if success:
            print("\n程序执行完成！")
            sys.exit(0)
        else:
            print("\n程序执行失败！")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n程序发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
