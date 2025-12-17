"""
微博热搜情感分析模块

该模块提供对微博热搜数据进行情感分析的功能，包括批量处理data_processed目录下的数据，
以及提供API接口处理JSON输入并输出情感分析结果。

主要功能：
1. 从data_processed目录加载热搜数据
2. 对标题文本进行情感分析（正面/负面/中性）
3. 提供API接口处理JSON输入并返回情感分析结果
4. 将分析结果保存到output/sentiment_analysis目录

使用方法：
    # 从文件导入
    from sentiment_analyzer import SentimentAnalyzer

    # 创建分析器实例
    analyzer = SentimentAnalyzer()

    # 分析单个文件
    results = analyzer.analyze_file("data_processed/2025-01/2025-01-01.json")

    # 分析整个目录
    results = analyzer.analyze_directory()

    # 使用API接口
    api_result = analyzer.api_analyze({"data": [{"title": "测试标题", "heat": 100}]})

    # 或者直接使用函数
    from sentiment_analyzer import analyze_json_api
    result = analyze_json_api('{"data": [{"title": "测试"}]}')

命令行使用：
    python sentiment_analyzer.py --file data_processed/2025-01/2025-01-01.json
    python sentiment_analyzer.py --dir data_processed/2025-01
    python sentiment_analyzer.py --all
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from snownlp import SnowNLP

    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False
    print("警告: snownlp库未安装，情感分析功能将不可用。请运行: pip install snownlp")
    SnowNLP = None


class SentimentAnalyzer:
    """微博热搜情感分析器

    该类用于对微博热搜数据进行情感分析，主要分析标题文本的情感倾向。
    支持批量处理数据，并将结果保存到指定目录。

    属性:
        data_dir (Path): 数据目录路径，默认为data_processed
        output_dir (Path): 输出目录路径，默认为output/sentiment_analysis
        data (List[Dict]): 加载的数据列表
        results (List[Dict]): 分析结果列表

    示例:
        >>> analyzer = SentimentAnalyzer()
        >>> results = analyzer.load_and_analyze()
        >>> analyzer.save_all_results()
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        output_dir: str = "output/sentiment_analysis",
    ) -> None:
        """初始化情感分析器

        参数:
            data_dir: 输入数据目录路径，包含JSON格式的微博热搜数据，如果为None则使用默认的data_processed目录
            output_dir: 输出结果目录路径，情感分析结果将保存到此目录

        返回:
            无
        """
        # 计算项目根目录
        script_dir = Path(__file__).parent  # src目录
        project_root = script_dir.parent  # 项目根目录

        # 设置数据目录
        if data_dir is None:
            self.data_dir = project_root / "data_processed"
        else:
            self.data_dir = project_root / data_dir

        self.output_dir = project_root / output_dir
        self.data = []
        self.results = []

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not SNOWNLP_AVAILABLE:
            print("警告: snownlp库不可用，情感分析功能受限")

    def load_data_from_file(self, json_file: Union[str, Path]) -> List[Dict[str, Any]]:
        """从单个JSON文件加载数据

        内部逻辑:
            1. 读取JSON文件内容
            2. 解析文件中的date和data字段
            3. 为每个数据项添加文件日期信息
            4. 返回规范化后的数据列表

        参数:
            json_file: JSON文件路径

        返回:
            List[Dict]: 加载的数据项列表，每个数据项包含原始字段和file_date字段

        异常:
            FileNotFoundError: 文件不存在时抛出
            json.JSONDecodeError: JSON格式错误时抛出
        """
        json_path = Path(json_file)
        if not json_path.exists():
            raise FileNotFoundError(f"文件不存在: {json_file}")

        with open(json_path, "r", encoding="utf-8") as f:
            file_data = json.load(f)

        # 处理不同的数据格式
        file_date = file_data.get("date", "")

        if "data" in file_data:
            items = file_data["data"]
        elif "results" in file_data:
            items = file_data["results"]
        elif isinstance(file_data, list):
            items = file_data
        else:
            items = []

        # 为每个数据项添加文件日期信息
        normalized_items = []
        for item in items:
            item_copy = item.copy()
            item_copy["file_date"] = file_date
            normalized_items.append(item_copy)

        return normalized_items

    def load_all_data(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """从data_dir目录加载所有JSON数据

        内部逻辑:
            1. 递归查找所有.json文件
            2. 按日期范围过滤文件
            3. 逐个文件加载数据
            4. 合并所有数据项

        参数:
            start_date: 开始日期（格式: YYYY-MM-DD），可选
            end_date: 结束日期（格式: YYYY-MM-DD），可选

        返回:
            List[Dict]: 所有加载的数据项列表
        """
        all_data = []

        # 查找所有JSON文件
        json_files = list(self.data_dir.rglob("*.json"))

        if not json_files:
            print(f"警告: 在目录 {self.data_dir} 中未找到JSON文件")
            return []

        # 按日期过滤文件
        filtered_files = []
        for json_file in json_files:
            file_date_str = None

            # 从文件路径提取日期（假设路径格式为 .../YYYY-MM/YYYY-MM-DD.json）
            try:
                # 尝试从文件名提取日期
                filename = json_file.stem
                if len(filename) == 10 and filename[4] == "-" and filename[7] == "-":
                    file_date_str = filename
                # 或者从父目录名提取月份
                elif json_file.parent.name and len(json_file.parent.name) == 7:
                    month_str = json_file.parent.name
                    day_part = (
                        json_file.stem.split("-")[-1] if "-" in json_file.stem else "01"
                    )
                    file_date_str = f"{month_str}-{day_part}"
            except:
                pass

            if file_date_str:
                try:
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d")

                    # 应用日期过滤
                    if start_date:
                        start = datetime.strptime(start_date, "%Y-%m-%d")
                        if file_date < start:
                            continue
                    if end_date:
                        end = datetime.strptime(end_date, "%Y-%m-%d")
                        if file_date > end:
                            continue
                except ValueError:
                    pass

            filtered_files.append(json_file)

        print(f"找到 {len(filtered_files)} 个JSON文件")

        # 加载所有文件数据
        for json_file in filtered_files:
            try:
                file_data = self.load_data_from_file(json_file)
                all_data.extend(file_data)
                print(f"已加载文件: {json_file.name} ({len(file_data)} 条数据)")
            except Exception as e:
                print(f"加载文件 {json_file} 时出错: {e}")
                continue

        print(f"总共加载 {len(all_data)} 条数据")
        self.data = all_data
        return all_data

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """分析单条文本的情感

        内部逻辑:
            1. 使用SnowNLP进行情感分析得到0-1之间的情感分数
            2. 根据分数将情感分类为正面、负面或中性
            3. 返回包含分数和分类的字典

        参数:
            text: 要分析的文本内容

        返回:
            Dict: 包含情感分数和分类的字典
                - score: 情感分数 (0.0-1.0，越高越正面)
                - sentiment: 情感分类 ("positive", "negative", "neutral")
                - confidence: 置信度（基于分数距离分类阈值的距离）
        """
        if not SNOWNLP_AVAILABLE or not text:
            return {
                "score": 0.5,
                "sentiment": "neutral",
                "confidence": 0.0,
                "error": "SNOWNLP not available" if not SNOWNLP_AVAILABLE else None,
            }

        try:
            s = SnowNLP(text)
            score = s.sentiments

            # 分类阈值
            if score > 0.6:
                sentiment = "positive"
                confidence = (score - 0.6) / 0.4  # 归一化到0-1
            elif score < 0.4:
                sentiment = "negative"
                confidence = (0.4 - score) / 0.4  # 归一化到0-1
            else:
                sentiment = "neutral"
                # 计算距离中性中心0.5的距离
                confidence = 1.0 - abs(score - 0.5) / 0.1

            return {
                "score": float(score),
                "sentiment": sentiment,
                "confidence": min(max(float(confidence), 0.0), 1.0),
            }
        except Exception as e:
            print(f"分析文本 '{text[:50]}...' 时出错: {e}")
            return {
                "score": 0.5,
                "sentiment": "neutral",
                "confidence": 0.0,
                "error": str(e),
            }

    def analyze_data_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """分析单个数据项的情感

        内部逻辑:
            1. 提取标题文本进行情感分析
            2. 合并原始数据和情感分析结果
            3. 添加分析时间戳

        参数:
            item: 数据项字典，应包含title字段

        返回:
            Dict: 包含原始数据和情感分析结果的字典
        """
        title = item.get("title", "")

        sentiment_result = self.analyze_sentiment(title)

        result = item.copy()
        result.update(
            {
                "sentiment_analysis": sentiment_result,
                "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        return result

    def analyze_batch(
        self, data: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """批量分析数据

        内部逻辑:
            1. 如果没有提供数据，使用self.data
            2. 遍历每个数据项进行情感分析
            3. 统计情感分类分布
            4. 返回分析结果列表

        参数:
            data: 要分析的数据列表，可选

        返回:
            List[Dict]: 包含情感分析结果的数据项列表
        """
        if data is None:
            data = self.data

        if not data:
            print("警告: 没有数据可供分析")
            return []

        results = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        print(f"开始分析 {len(data)} 条数据...")

        for i, item in enumerate(data):
            # 显示进度
            if (i + 1) % 100 == 0 or (i + 1) == len(data):
                print(f"进度: {i + 1}/{len(data)}")

            result = self.analyze_data_item(item)
            results.append(result)

            # 统计
            sentiment = result["sentiment_analysis"]["sentiment"]
            if sentiment == "positive":
                positive_count += 1
            elif sentiment == "negative":
                negative_count += 1
            else:
                neutral_count += 1

        # 打印统计信息
        total = len(results)
        print("\n情感分析统计:")
        print(f"  正面: {positive_count} ({positive_count / total * 100:.1f}%)")
        print(f"  负面: {negative_count} ({negative_count / total * 100:.1f}%)")
        print(f"  中性: {neutral_count} ({neutral_count / total * 100:.1f}%)")
        print(f"  总计: {total}")

        self.results = results
        return results

    def analyze_file(self, json_file: Union[str, Path]) -> List[Dict[str, Any]]:
        """分析单个JSON文件

        内部逻辑:
            1. 从指定文件加载数据
            2. 对数据进行情感分析
            3. 返回分析结果列表

        参数:
            json_file: JSON文件路径

        返回:
            List[Dict]: 包含情感分析结果的数据项列表

        示例:
            >>> analyzer = SentimentAnalyzer()
            >>> results = analyzer.analyze_file("data_processed/2025-01/2025-01-01.json")
        """
        print(f"分析文件: {json_file}")
        data = self.load_data_from_file(json_file)
        results = self.analyze_batch(data)
        print(f"文件分析完成，共分析 {len(results)} 条数据")
        return results

    def analyze_directory(
        self,
        directory: Optional[Union[str, Path]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """分析指定目录下的所有JSON文件

        内部逻辑:
            1. 如果未指定目录，使用self.data_dir
            2. 加载指定日期范围内的所有数据
            3. 进行情感分析
            4. 返回分析结果列表

        参数:
            directory: 要分析的目录路径，如果为None则使用data_dir
            start_date: 开始日期（格式: YYYY-MM-DD），可选
            end_date: 结束日期（格式: YYYY-MM-DD），可选

        返回:
            List[Dict]: 包含情感分析结果的数据项列表

        示例:
            >>> analyzer = SentimentAnalyzer()
            >>> results = analyzer.analyze_directory("data_processed/2025-01")
        """
        if directory is not None:
            # 临时设置数据目录
            original_data_dir = self.data_dir
            self.data_dir = Path(directory)

        print(f"分析目录: {self.data_dir}")
        self.load_all_data(start_date, end_date)
        results = self.analyze_batch()

        if directory is not None:
            # 恢复原始数据目录
            self.data_dir = original_data_dir

        print(f"目录分析完成，共分析 {len(results)} 条数据")
        return results

    def save_results(
        self, results: List[Dict[str, Any]], filename: Optional[str] = None
    ) -> str:
        """保存分析结果到文件

        内部逻辑:
            1. 生成默认文件名（如果未提供）
            2. 创建包含统计信息和详细结果的JSON结构
            3. 保存到output_dir目录

        参数:
            results: 要保存的分析结果列表
            filename: 输出文件名，可选

        返回:
            str: 保存的文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sentiment_analysis_{timestamp}.json"

        output_path = self.output_dir / filename

        # 统计信息
        positive_count = sum(
            1 for r in results if r["sentiment_analysis"]["sentiment"] == "positive"
        )
        negative_count = sum(
            1 for r in results if r["sentiment_analysis"]["sentiment"] == "negative"
        )
        neutral_count = sum(
            1 for r in results if r["sentiment_analysis"]["sentiment"] == "neutral"
        )
        total = len(results)

        # 构建输出结构
        output_data = {
            "metadata": {
                "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_items": total,
                "sentiment_distribution": {
                    "positive": positive_count,
                    "negative": negative_count,
                    "neutral": neutral_count,
                    "positive_percentage": positive_count / total * 100
                    if total > 0
                    else 0,
                    "negative_percentage": negative_count / total * 100
                    if total > 0
                    else 0,
                    "neutral_percentage": neutral_count / total * 100
                    if total > 0
                    else 0,
                },
                "average_sentiment_score": sum(
                    r["sentiment_analysis"]["score"] for r in results
                )
                / total
                if total > 0
                else 0.5,
            },
            "results": results,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"分析结果已保存到: {output_path}")
        return str(output_path)

    def api_analyze(self, input_json: Union[str, Dict, List]) -> Dict[str, Any]:
        """API接口：分析输入的JSON数据

        内部逻辑:
            1. 解析输入JSON（可以是字符串、字典或列表）
            2. 规范化数据格式
            3. 进行情感分析
            4. 返回包含统计信息和详细结果的JSON

        参数:
            input_json: 输入数据，可以是：
                - JSON字符串
                - Python字典
                - Python列表

        返回:
            Dict: 包含情感分析结果的字典，结构同save_results的输出

        异常:
            ValueError: 输入数据格式无效时抛出
        """
        # 解析输入数据
        if isinstance(input_json, str):
            try:
                data = json.loads(input_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"无效的JSON字符串: {e}")
        else:
            data = input_json

        # 规范化数据格式
        if isinstance(data, dict):
            if "data" in data:
                items = data["data"]
            elif "results" in data:
                items = data["results"]
            else:
                # 假设字典本身就是数据项
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError(f"不支持的输入格式: {type(data)}")

        # 分析数据
        results = []
        for item in items:
            if isinstance(item, dict):
                result = self.analyze_data_item(item)
                results.append(result)

        # 构建响应
        positive_count = sum(
            1 for r in results if r["sentiment_analysis"]["sentiment"] == "positive"
        )
        negative_count = sum(
            1 for r in results if r["sentiment_analysis"]["sentiment"] == "negative"
        )
        neutral_count = sum(
            1 for r in results if r["sentiment_analysis"]["sentiment"] == "neutral"
        )
        total = len(results)

        response = {
            "success": True,
            "message": f"成功分析 {total} 条数据",
            "metadata": {
                "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_items": total,
                "sentiment_distribution": {
                    "positive": positive_count,
                    "negative": negative_count,
                    "neutral": neutral_count,
                },
            },
            "results": results,
        }

        return response

    def load_and_analyze(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """加载数据并进行分析的便捷方法

        内部逻辑:
            1. 加载指定日期范围内的数据
            2. 进行情感分析
            3. 自动保存结果

        参数:
            start_date: 开始日期，可选
            end_date: 结束日期，可选

        返回:
            List[Dict]: 分析结果列表
        """
        print("加载数据...")
        self.load_all_data(start_date, end_date)

        if not self.data:
            print("没有数据可供分析")
            return []

        print("进行情感分析...")
        results = self.analyze_batch(self.data)

        print("保存结果...")
        self.save_results(results)

        return results


def analyze_json_api(input_json: Union[str, Dict, List]) -> Dict[str, Any]:
    """API函数：分析JSON输入并返回情感分析结果

    参数:
        input_json: 输入数据，可以是JSON字符串、字典或列表

    返回:
        Dict: 情感分析结果

    示例:
        >>> result = analyze_json_api('{"data": [{"title": "好消息！"}]}')
        >>> result = analyze_json_api([{"title": "测试"}])
    """
    analyzer = SentimentAnalyzer()
    return analyzer.api_analyze(input_json)


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="微博热搜情感分析工具")
    parser.add_argument("--file", type=str, help="分析单个JSON文件")
    parser.add_argument("--dir", type=str, help="分析指定目录下的所有JSON文件")
    parser.add_argument(
        "--all", action="store_true", help="分析data_processed目录下的所有数据"
    )
    parser.add_argument("--start", type=str, help="开始日期 (格式: YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="结束日期 (格式: YYYY-MM-DD)")
    parser.add_argument("--output", type=str, help="自定义输出目录")

    args = parser.parse_args()

    if not SNOWNLP_AVAILABLE:
        print("错误: snownlp库未安装，无法进行情感分析")
        print("请运行: pip install snownlp")
        sys.exit(1)

    # 创建分析器
    output_dir = args.output if args.output else "output/sentiment_analysis"
    analyzer = SentimentAnalyzer(output_dir=output_dir)

    if args.file:
        # 分析单个文件
        print(f"分析文件: {args.file}")
        try:
            data = analyzer.load_data_from_file(args.file)
            results = analyzer.analyze_batch(data)
            filename = Path(args.file).stem + "_sentiment.json"
            analyzer.save_results(results, filename)
        except Exception as e:
            print(f"分析文件时出错: {e}")
            sys.exit(1)

    elif args.dir:
        # 分析指定目录
        print(f"分析目录: {args.dir}")
        analyzer.data_dir = Path(args.dir)
        analyzer.load_and_analyze(args.start, args.end)

    elif args.all or (not args.file and not args.dir):
        # 分析所有数据
        print("分析data_processed目录下的所有数据")
        analyzer.load_and_analyze(args.start, args.end)

    else:
        parser.print_help()


def test_sentiment_analyzer():
    """测试情感分析器功能

    这是一个典型测试案例，用于验证模块功能是否正常。
    测试内容包括：
    1. 创建分析器实例
    2. 分析单条文本
    3. 使用API接口
    4. 批量分析示例数据
    """
    print("=== 测试情感分析器 ===")

    # 创建分析器
    analyzer = SentimentAnalyzer()

    # 测试单条文本分析
    test_texts = [
        "这个产品太好了！我非常喜欢！",
        "服务太差了，再也不来了",
        "今天天气不错，适合出门",
        "这是一个中性的陈述",
    ]

    print("\n1. 测试单条文本分析:")
    for text in test_texts:
        result = analyzer.analyze_sentiment(text)
        print(f"  文本: {text[:20]}...")
        print(f"    情感: {result['sentiment']}, 分数: {result['score']:.3f}")

    # 测试API接口
    print("\n2. 测试API接口:")
    test_data = {
        "data": [
            {"title": "中国队在奥运会获得金牌", "heat": 1000000},
            {"title": "某公司产品出现质量问题", "heat": 500000},
            {"title": "今日股市平稳运行", "heat": 300000},
        ]
    }

    try:
        api_result = analyzer.api_analyze(test_data)
        print(f"  API调用成功: {api_result['message']}")
        print(f"  分析结果数: {len(api_result['results'])}")
    except Exception as e:
        print(f"  API测试失败: {e}")

    # 测试批量分析（使用模拟数据）
    print("\n3. 测试批量分析:")
    mock_data = [
        {"title": "好消息！经济发展迅速", "heat": 100, "category": "经济"},
        {"title": "灾难发生，多人受伤", "heat": 200, "category": "社会"},
        {"title": "普通新闻事件", "heat": 50, "category": "其他"},
    ]

    batch_results = analyzer.analyze_batch(mock_data)
    print(f"  批量分析完成，处理 {len(batch_results)} 条数据")

    # 统计结果
    sentiments = [r["sentiment_analysis"]["sentiment"] for r in batch_results]
    pos_count = sentiments.count("positive")
    neg_count = sentiments.count("negative")
    neu_count = sentiments.count("neutral")

    print(f"  正面: {pos_count}, 负面: {neg_count}, 中性: {neu_count}")

    print("\n=== 测试完成 ===")

    return True


if __name__ == "__main__":
    # 如果没有命令行参数，运行测试
    if len(sys.argv) == 1:
        test_sentiment_analyzer()
    else:
        main()
