"""
数据分类交互程序

本程序允许用户手动对未分类的热搜数据进行分类。
用户可以选择特定月份或时间段的数据，程序将提取所有category为空的数据项，
提供交互式界面供用户进行分类。

使用方式：
    python3 category_classifier.py
"""

import json
import os

# 导入单字符读取模块
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HAS_TERMIOS = False
HAS_MSVCRT = False

if sys.platform != "win32":
    # Unix/Linux系统
    try:
        import termios
        import tty

        HAS_TERMIOS = True
    except ImportError:
        HAS_TERMIOS = False
else:
    # Windows系统
    try:
        import msvcrt

        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False


class DataClassifier:
    """数据分类器类"""

    def __init__(self, data_dir: str = None):
        """
        初始化分类器

        参数:
            data_dir: 数据目录路径，如果为None则使用默认路径
        """
        if data_dir is None:
            # 默认路径：项目根目录下的data_processed文件夹
            script_dir = Path(__file__).parent  # src目录
            project_root = script_dir.parent  # 项目根目录
            self.data_dir = project_root / "data_processed"
        else:
            self.data_dir = Path(data_dir)
        self.category_map = {
            0: "其他",  # 跳过/不分类
            1: "明星",
            2: "综艺",
            3: "体育",
            4: "科技",
            5: "娱乐",
            6: "社会",
            7: "财经",
            8: "游戏",
            9: None,  # 自定义分类
        }

        # 分类统计数据
        self.stats = {"total": 0, "processed": 0, "skipped": 0, "updated": 0}

        # 当前处理的数据
        self.current_data = []  # 原始数据列表
        self.unclassified_items = []  # 未分类数据项
        self.date_range = ""  # 日期范围显示字符串

        # 防抖动设置
        self.last_key_time = 0
        self.debounce_delay = 0.5  # 500毫秒，增加防抖时间
        self.input_history = []  # 输入历史，用于调试
        self.last_key = None  # 记录上一次按键

    def parse_date_range(self, date_input: str) -> Tuple[List[str], str]:
        """
        解析用户输入的日期范围

        参数:
            date_input: 用户输入的日期范围，格式如 "2025-01" 或 "2025-01-01--2025-01-24"

        返回:
            (date_list, display_range): 日期列表和显示字符串
        """
        date_list = []

        if "--" in date_input:
            # 处理日期范围
            start_str, end_str = date_input.split("--")
            try:
                start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d")
                end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d")
            except ValueError:
                print("错误: 日期格式不正确，请使用 YYYY-MM-DD 格式")
                return [], ""

            current_date = start_date
            while current_date <= end_date:
                date_list.append(current_date.strftime("%Y-%m-%d"))
                current_date += timedelta(days=1)

            display_range = f"{start_str} 至 {end_str}"

        elif len(date_input) == 7 and date_input[4] == "-":
            # 处理月份
            try:
                year_month = date_input
                year, month = map(int, year_month.split("-"))

                # 验证月份范围
                if year < 2000 or year > 2100:
                    print(f"错误: 年份 {year} 超出合理范围")
                    return [], ""
                if month < 1 or month > 12:
                    print(f"错误: 月份 {month} 无效")
                    return [], ""

                # 获取该月的所有日期
                month_dir = self.data_dir / year_month
                if not month_dir.exists():
                    print(f"错误: 目录 {month_dir} 不存在")
                    return [], ""

                if not month_dir.is_dir():
                    print(f"错误: {month_dir} 不是目录")
                    return [], ""

                # 读取该月所有JSON文件
                try:
                    json_files = sorted(list(month_dir.glob("*.json")))
                except Exception as e:
                    print(f"错误: 读取目录 {month_dir} 时出错: {e}")
                    return [], ""

                for json_file in json_files:
                    try:
                        # 验证文件名格式
                        date_str = json_file.stem
                        # 检查日期格式
                        datetime.strptime(date_str, "%Y-%m-%d")
                        date_list.append(date_str)
                    except ValueError:
                        print(
                            f"警告: 文件 {json_file.name} 文件名不是有效日期格式，跳过"
                        )
                        continue

                if date_list:
                    display_range = f"{year_month} (全月)"
                else:
                    print(f"警告: {year_month} 月份没有有效的数据文件")
                    return [], ""

            except ValueError as e:
                print(f"错误: 日期格式不正确: {e}")
                return [], ""
            except Exception as e:
                print(f"错误: 处理月份时出错: {e}")
                return [], ""

        else:
            print("错误: 输入格式不正确")
            print("  有效格式: ")
            print("  - 月份: 2025-01")
            print("  - 日期范围: 2025-01-01--2025-01-24")
            return [], ""

        return date_list, display_range

    def load_data(self, date_list: List[str]) -> List[Dict[str, Any]]:
        """
        加载指定日期列表的数据

        参数:
            date_list: 日期列表

        返回:
            数据列表
        """
        all_data = []

        for date_str in date_list:
            # 解析年月日
            year_month = date_str[:7]  # YYYY-MM
            file_path = self.data_dir / year_month / f"{date_str}.json"

            if not file_path.exists():
                print(f"警告: 文件 {file_path} 不存在，跳过")
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 验证数据结构
                if not isinstance(data, dict):
                    print(f"警告: 文件 {file_path} 格式不正确，跳过")
                    continue

                if "data" not in data or not isinstance(data["data"], list):
                    print(f"警告: 文件 {file_path} 缺少data字段或格式不正确，跳过")
                    continue

                # 添加日期信息到每个数据项（如果不存在）
                for item in data.get("data", []):
                    if not isinstance(item, dict):
                        continue  # 跳过非字典项
                    if "date" not in item or not item["date"]:
                        item["date"] = date_str
                    item["source_file"] = str(file_path)

                all_data.append(
                    {
                        "date": date_str,
                        "file_path": str(file_path),
                        "data": data.get("data", []),
                    }
                )

            except json.JSONDecodeError as e:
                print(f"错误: 文件 {file_path} JSON格式错误: {e}")
            except UnicodeDecodeError as e:
                print(f"错误: 文件 {file_path} 编码错误: {e}")
            except Exception as e:
                print(f"错误: 读取文件 {file_path} 时出错: {e}")
                if __debug__:
                    import traceback

                    traceback.print_exc()

        return all_data

    def find_unclassified_items(
        self, all_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        找出所有未分类的数据项

        参数:
            all_data: 所有数据

        返回:
            未分类数据项列表
        """
        unclassified = []

        for date_data in all_data:
            for item in date_data["data"]:
                # 检查category是否为空或只有空白字符
                category = item.get("category", "")
                if not category or category.strip() == "":
                    # 添加源文件信息
                    item_copy = item.copy()
                    item_copy["source_file"] = date_data["file_path"]
                    item_copy["source_date"] = date_data["date"]
                    unclassified.append(item_copy)

        return unclassified

    def display_header(self):
        """显示程序头部信息"""
        os.system("clear" if os.name == "posix" else "cls")

        print("=" * 60)
        print("                  数据分类工具")
        print("=" * 60)
        print(f"当前处理: {self.date_range}")
        print(f"未分类数据: {len(self.unclassified_items)}条")
        print(f"已处理: {self.stats['processed']}/{len(self.unclassified_items)}")
        print()

        print("分类映射:")
        for key, value in self.category_map.items():
            if key == 9:
                print(f"  {key}: 自定义分类 (输入分类名称)")
            elif key == 0:
                print(f"  {key}: '' (跳过/不分类)")
            else:
                print(f"  {key}: '{value}'")

        print()
        print("命令:")
        print("  q - 退出程序 (quit)")
        print("  h - 显示帮助 (help)")
        print("  s - 保存当前进度 (save)")
        print("  t - 显示统计信息 (stats)")
        print("  k - 跳过当前项 (skip)")
        print("  0-9 - 选择分类（无需按Enter键）")
        print("")
        print("注意: 输入数字0-9后立即生效")
        print("-" * 60)

    def display_item(self, item: Dict[str, Any], index: int):
        """
        显示单个数据项

        参数:
            item: 数据项
            index: 当前序号
        """
        print(f"[{index}/{len(self.unclassified_items)}]")
        print(f"日期: {item.get('date', '未知')}")
        print(f"排名: {item.get('rank', '未知')}")
        print(f"热度: {item.get('heat', '未知')}")
        print()
        print(f"标题: {item.get('title', '无标题')}")
        print()
        print("请按分类数字 (0-9) 或命令键 (q/h/s/t/k):")

    def get_custom_category(self) -> str:
        """
        获取自定义分类名称

        返回:
            分类名称
        """
        print("请输入自定义分类名称 (例如: '影视', '音乐', '美食'):")
        while True:
            custom_input = input("> ").strip()
            if custom_input:
                return custom_input
            print("分类名称不能为空，请重新输入:")

    def getch(self) -> str:
        """
        读取单个字符（无需按Enter键）

        返回:
            读取的字符，如果出错则返回空字符串
        """
        try:
            if HAS_TERMIOS:
                # Unix/Linux系统
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(sys.stdin.fileno())
                    ch = sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                return ch
            elif HAS_MSVCRT:
                # Windows系统
                ch = msvcrt.getch()
                # msvcrt.getch()返回bytes，需要解码
                if isinstance(ch, bytes):
                    try:
                        return ch.decode("utf-8")
                    except UnicodeDecodeError:
                        # 如果不能解码为utf-8，尝试其他编码
                        try:
                            return ch.decode("gbk")
                        except UnicodeDecodeError:
                            return ch.decode("latin-1", errors="ignore")
                return ch
            else:
                # 其他系统，回退到input
                try:
                    import select

                    # 尝试使用select实现非阻塞读取
                    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                        return sys.stdin.read(1)
                    else:
                        return ""
                except Exception:
                    # 如果select不可用，回退到input
                    try:
                        user_input = input("> ")
                        return user_input[0] if user_input else ""
                    except Exception:
                        return ""
        except Exception as e:
            # 记录错误但不中断程序
            if __debug__:
                print(f"读取输入时出错（继续运行）: {e}", file=sys.stderr)
            return ""

    def clear_input_buffer(self) -> None:
        """
        清空输入缓冲区，防止积累的按键被误读
        """
        try:
            if HAS_TERMIOS:
                import fcntl

                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    # 设置非阻塞模式
                    old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)
                    try:
                        # 读取并丢弃所有缓冲的字符
                        while True:
                            try:
                                ch = sys.stdin.read(1)
                                if not ch:
                                    break
                            except (IOError, OSError):
                                break
                    finally:
                        # 恢复阻塞模式
                        fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            elif HAS_MSVCRT:
                # Windows系统，msvcrt.kbhit()检查是否有按键
                try:
                    while msvcrt.kbhit():
                        msvcrt.getch()  # 读取并丢弃
                except Exception:
                    pass  # 忽略清空缓冲区的错误
        except Exception as e:
            if __debug__:
                print(f"清空输入缓冲区时出错: {e}", file=sys.stderr)
            # 继续执行，不影响主要功能

    def get_single_input(self) -> str:
        """
        获取单字符输入，带防抖动功能

        返回:
            用户输入的字符
        """
        current_time = time.time()

        # 防抖动检查：如果上次按键时间太近，等待剩余时间
        time_since_last = current_time - self.last_key_time
        if time_since_last < self.debounce_delay:
            wait_time = self.debounce_delay - time_since_last
            time.sleep(wait_time)
            # 等待期间清空输入缓冲区
            self.clear_input_buffer()

        # 在处理新输入前先清空缓冲区
        self.clear_input_buffer()

        print("> ", end="", flush=True)
        ch = self.getch()
        current_time = time.time()

        # 防止长按重复输入：如果按键与上次相同且时间间隔太短，可能是长按重复
        if ch == self.last_key and current_time - self.last_key_time < 0.2:
            if __debug__:
                print(f" [长按重复忽略]", end="", flush=True)
            # 忽略这个重复输入
            self.clear_input_buffer()
            return ""

        self.last_key = ch
        self.last_key_time = current_time

        # 如果是数字或q/h/s等命令字符，直接返回
        if ch:
            print(ch, end="", flush=True)  # 回显字符，不换行
            # 对于数字输入，立即显示确认反馈
            if ch.isdigit():
                print(" ✓", end="", flush=True)
            time.sleep(0.1)  # 短暂延迟让用户看到反馈
            print()  # 换行
            return ch.lower()
        return ""

    def process_item(self, item: Dict[str, Any], file_path: str) -> bool:
        """
        处理单个数据项

        参数:
            item: 数据项
            file_path: 源文件路径

        返回:
            True表示成功处理，False表示用户退出
        """
        while True:
            user_input = self.get_single_input()

            if not user_input:
                continue

            # 防抖动：如果输入太快，可能是误操作，忽略
            # 已经在get_single_input中处理了防抖动，这里可以简化
            pass

            if user_input == "q":  # quit
                return False
            elif user_input == "h":  # help
                self.show_help()
                continue
            elif user_input == "s":  # save
                self.save_changes()
                print("进度已保存")
                continue
            elif user_input == "t":  # stats
                self.show_stats()
                continue
            elif user_input == "k":  # skip
                self.stats["skipped"] += 1
                # 跳过时也添加短暂延迟
                time.sleep(0.3)
                return True

            # 处理数字分类
            if user_input.isdigit():
                choice = int(user_input)

                if choice in self.category_map:
                    if choice == 9:
                        # 自定义分类 - 需要额外输入
                        print("\n自定义分类，请输入分类名称: ", end="", flush=True)
                        # 对于自定义分类，需要读取完整输入
                        custom_input = input().strip()
                        if custom_input:
                            item["category"] = custom_input
                        else:
                            print("分类名称不能为空")
                            continue
                    elif choice == 0:
                        # 跳过/不分类
                        item["category"] = ""
                        self.stats["skipped"] += 1
                    else:
                        # 预设分类
                        item["category"] = self.category_map[choice]

                    # 更新文件
                    if self.update_file(item, file_path):
                        self.stats["updated"] += 1
                        # 成功处理后添加短暂延迟，防止用户误按下一个
                        time.sleep(0.3)
                        return True
                    else:
                        print("错误: 更新文件失败，请重试")
                        continue
                else:
                    print(f"错误: 数字 {choice} 不在有效范围内 (0-9)")
                    continue
            else:
                print("错误: 请输入有效数字 (0-9) 或命令")
                print("命令: q=退出, h=帮助, s=保存, t=统计, k=跳过")
                # 短暂停顿让用户看到错误信息
                time.sleep(0.3)
                continue

    def update_file(self, item: Dict[str, Any], file_path: str) -> bool:
        """
        更新文件中的分类信息

        参数:
            item: 更新后的数据项
            file_path: 文件路径

        返回:
            True表示成功，False表示失败
        """
        import shutil
        import tempfile

        # 创建临时文件路径
        temp_file = None

        try:
            # 读取整个文件
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证数据结构
            if (
                not isinstance(data, dict)
                or "data" not in data
                or not isinstance(data["data"], list)
            ):
                print(f"错误: 文件 {file_path} 数据结构无效")
                return False

            # 找到并更新对应的数据项
            found = False
            for data_item in data.get("data", []):
                if not isinstance(data_item, dict):
                    continue
                if data_item.get("title") == item.get("title") and data_item.get(
                    "date"
                ) == item.get("date"):
                    data_item["category"] = item["category"]
                    found = True
                    break

            if not found:
                print(f"警告: 未找到匹配的数据项: {item.get('title')}")
                return False

            # 先写入临时文件
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".json", delete=False
            ) as tf:
                json.dump(data, tf, ensure_ascii=False, indent=2)
                temp_file = tf.name

            # 备份原文件（可选）
            backup_file = file_path + ".bak"
            try:
                shutil.copy2(file_path, backup_file)
            except Exception:
                pass  # 备份失败不影响主流程

            # 用临时文件替换原文件
            shutil.move(temp_file, file_path)

            # 清理临时文件（如果还存在）
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

            return True

        except json.JSONDecodeError as e:
            print(f"错误: 文件 {file_path} JSON格式错误: {e}")
        except PermissionError as e:
            print(f"错误: 没有权限写入文件 {file_path}: {e}")
        except Exception as e:
            print(f"错误: 更新文件时出错: {e}")
            # 清理临时文件
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
            if __debug__:
                import traceback

                traceback.print_exc()
        return False

    def save_changes(self):
        """保存所有更改（实际上每次更改都已实时保存）"""
        print(
            f"统计信息: 已更新 {self.stats['updated']} 条，跳过 {self.stats['skipped']} 条"
        )

    def show_help(self):
        """显示帮助信息"""
        print("\n帮助信息:")
        print("  0-9: 选择对应的分类（无需按Enter键）")
        print("  9: 自定义分类（会提示输入分类名称）")
        print("  0: 跳过/不分类（保持category为空）")
        print()
        print("  单字符命令:")
        print("    q - 退出程序")
        print("    h - 显示此帮助")
        print("    s - 保存进度（显示统计）")
        print("    t - 显示统计信息")
        print("    k - 跳过当前项")
        print()
        print("  注意:")
        print("    - 输入数字0-9后立即生效，无需按Enter键")
        print("    - 防抖动机制：快速连续按键会被忽略，长按不会重复输入")
        print("    - 输入后会显示'✓'确认，有短暂延迟防止误操作")
        print("    - 支持Windows、Linux/macOS和其他系统")
        print("    - 输入9后，会提示输入完整的分类名称")
        print()
        input("按Enter键继续...")

    def show_stats(self):
        """显示统计信息"""
        print("\n统计信息:")
        print(f"  总未分类项: {len(self.unclassified_items)}")
        print(f"  已处理: {self.stats['processed']}")
        print(f"  已更新: {self.stats['updated']}")
        print(f"  已跳过: {self.stats['skipped']}")
        print(f"  剩余: {len(self.unclassified_items) - self.stats['processed']}")
        print()
        input("按Enter键继续...")

    def run(self):
        """运行分类程序"""
        print("数据分类交互程序")
        print("=" * 40)

        # 获取用户输入的日期范围
        while True:
            print("\n请输入要处理的日期范围:")
            print("  格式1: 月份，如 2025-01")
            print("  格式2: 日期范围，如 2025-01-01--2025-01-24")
            print("  输入 'quit' 退出程序")

            date_input = input("> ").strip()

            if date_input.lower() == "quit":
                print("程序退出")
                return

            date_list, display_range = self.parse_date_range(date_input)

            if date_list:
                self.date_range = display_range
                break

        # 加载数据
        print(f"\n加载 {self.date_range} 的数据...")
        all_data = self.load_data(date_list)

        if not all_data:
            print("错误: 没有找到有效数据")
            return

        # 找出未分类的数据
        self.unclassified_items = self.find_unclassified_items(all_data)

        if not self.unclassified_items:
            print(f"恭喜！在 {self.date_range} 中没有未分类的数据。")
            return

        print(f"找到 {len(self.unclassified_items)} 条未分类数据")
        print("开始分类...")

        # 主处理循环
        self.stats = {
            "total": len(self.unclassified_items),
            "processed": 0,
            "skipped": 0,
            "updated": 0,
        }

        for i, item in enumerate(self.unclassified_items, 1):
            self.stats["processed"] = i

            # 显示界面
            self.display_header()
            self.display_item(item, i)

            # 处理当前项
            if not self.process_item(item, item["source_file"]):
                # 用户选择退出
                print("\n用户中断处理")
                break

        # 显示最终结果
        print("\n" + "=" * 40)
        print("处理完成!")
        print(f"  总未分类项: {self.stats['total']}")
        print(f"  已处理: {self.stats['processed']}")
        print(f"  已更新: {self.stats['updated']}")
        print(f"  已跳过: {self.stats['skipped']}")
        print("=" * 40)


def main():
    """主函数"""
    try:
        classifier = DataClassifier()
        classifier.run()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n程序运行出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
