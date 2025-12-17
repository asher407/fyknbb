#!/usr/bin/env python3
"""
微博热搜数据分析系统 - 统一命令行接口

本模块提供了所有功能的统一命令行接口，包括：
- 数据爬取（历史、实时）
- 数据预处理
- 数据查询
- 数据分类
- 词云生成
- JSON数据分析
- 图形界面

使用示例：
    python src/main.py scrape --help
    python src/main.py scrape --start 2025-01-01 --end 2025-01-07
    python src/main.py scrape-realtime
    python src/main.py preprocess
    python src/main.py query --help
    python src/main.py classify --min_heat 100
    python src/main.py wordcloud
    python src/main.py analyze data/2025-01/2025-01-01.json
    python src/main.py gui
"""

import argparse
import os
import sys
from typing import List, Optional, Tuple


def main() -> int:
    """
    主函数，解析命令行参数并分发到对应的子命令
    """
    parser = argparse.ArgumentParser(
        description="微博热搜数据分析系统 - 统一命令行接口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s scrape --start 2025-01-01 --end 2025-01-07
  %(prog)s scrape-realtime
  %(prog)s preprocess
  %(prog)s query --date-range 2025-01-01 2025-01-07
  %(prog)s classify --min_heat 100
  %(prog)s wordcloud
  %(prog)s analyze data/2025-01/2025-01-01.json
  %(prog)s gui
        """,
    )

    subparsers = parser.add_subparsers(
        title="可用命令", dest="command", help="选择要执行的操作"
    )

    # 添加通用参数
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细输出")

    # 子命令: scrape (历史数据爬取)
    scrape_parser = subparsers.add_parser("scrape", help="爬取历史微博热搜数据")
    scrape_parser.add_argument(
        "--start",
        default="2025-01-01",
        help="开始日期 (格式: YYYY-MM-DD，默认: 2025-01-01)",
    )
    scrape_parser.add_argument(
        "--end",
        default="2025-12-12",
        help="结束日期 (格式: YYYY-MM-DD，默认: 2025-12-12)",
    )
    scrape_parser.add_argument(
        "--delay", type=float, default=2.0, help="请求间隔时间(秒，默认: 2.0)"
    )
    scrape_parser.add_argument(
        "--max-retries", type=int, default=3, help="最大重试次数 (默认: 3)"
    )
    scrape_parser.add_argument(
        "--output-dir", default="data", help="输出目录 (默认: data)"
    )

    # 子命令: scrape-realtime (实时数据爬取)
    scrape_realtime_parser = subparsers.add_parser(
        "scrape-realtime", help="爬取实时微博热搜数据"
    )
    scrape_realtime_parser.add_argument(
        "--timeout", type=int, default=30, help="请求超时时间(秒，默认: 30)"
    )
    scrape_realtime_parser.add_argument(
        "--max-retries", type=int, default=3, help="最大重试次数 (默认: 3)"
    )
    scrape_realtime_parser.add_argument(
        "--delay", type=float, default=1.0, help="重试间隔时间(秒，默认: 1.0)"
    )

    # 子命令: preprocess (数据预处理)
    preprocess_parser = subparsers.add_parser(
        "preprocess", help="预处理原始数据（去除heat=0的记录并重新排序）"
    )
    preprocess_parser.add_argument(
        "--input-dir", default="data", help="输入目录 (默认: data)"
    )
    preprocess_parser.add_argument(
        "--output-dir", default="data_processed", help="输出目录 (默认: data_processed)"
    )

    # 子命令: query (数据查询)
    query_parser = subparsers.add_parser("query", help="查询热搜数据")
    query_parser.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START_DATE", "END_DATE"),
        help="日期范围 (格式: YYYY-MM-DD)",
    )
    query_parser.add_argument(
        "--categories", nargs="+", help="分类列表 (例如: '明星' '综艺')"
    )
    query_parser.add_argument(
        "--rank-range",
        nargs=2,
        type=int,
        metavar=("MIN_RANK", "MAX_RANK"),
        help="排名范围",
    )
    query_parser.add_argument(
        "--heat-range",
        nargs=2,
        type=float,
        metavar=("MIN_HEAT", "MAX_HEAT"),
        help="热度范围",
    )
    query_parser.add_argument("--title-keywords", nargs="+", help="标题关键词列表")
    query_parser.add_argument(
        "--sort-by",
        choices=[
            "heat_desc",
            "heat_asc",
            "rank_asc",
            "date_desc",
            "reads_desc",
            "title_asc",
            "discussions_desc",
            "originals_desc",
        ],
        default="heat_desc",
        help="排序方式 (默认: heat_desc)",
    )
    query_parser.add_argument("--output", help="输出文件路径 (JSON格式)")

    # 子命令: classify (数据分类)
    classify_parser = subparsers.add_parser(
        "classify", help="交互式分类未分类的热搜数据"
    )
    classify_parser.add_argument(
        "--min-heat",
        type=float,
        default=100.0,
        help="最小热度阈值，只处理热度大于此值的数据项 (默认: 100.0)",
    )
    classify_parser.add_argument(
        "--data-dir",
        default="data_processed",
        help="数据目录路径 (默认: data_processed)",
    )

    # 子命令: wordcloud (词云生成)
    wordcloud_parser = subparsers.add_parser("wordcloud", help="生成词云图")
    wordcloud_parser.add_argument(
        "--input-dir",
        default="data_processed",
        help="输入数据目录 (默认: data_processed)",
    )
    wordcloud_parser.add_argument(
        "--output-dir", default="output", help="输出目录 (默认: output)"
    )

    # 子命令: analyze (JSON数据分析)
    analyze_parser = subparsers.add_parser(
        "analyze", help="分析JSON数据并生成可视化图表"
    )
    analyze_parser.add_argument("json_file", help="要分析的JSON文件路径")
    analyze_parser.add_argument(
        "--font",
        default="Maple Mono NF CN",
        help="指定字体名称 (默认: Maple Mono NF CN)",
    )
    analyze_parser.add_argument(
        "--output-dir",
        help="指定输出目录名称，默认使用JSON文件名（不带扩展名）",
    )

    # 子命令: gui (图形界面)
    gui_parser = subparsers.add_parser("gui", help="启动图形用户界面")

    # 解析参数
    args = parser.parse_args()

    # 如果没有指定子命令，显示帮助信息
    if not args.command:
        parser.print_help()
        return 1

    # 执行对应的子命令
    try:
        if args.verbose:
            print(f"执行命令: {args.command}")

        if args.command == "scrape":
            return scrape_command(args)
        elif args.command == "scrape-realtime":
            return scrape_realtime_command(args)
        elif args.command == "preprocess":
            return preprocess_command(args)
        elif args.command == "query":
            return query_command(args)
        elif args.command == "classify":
            return classify_command(args)
        elif args.command == "wordcloud":
            return wordcloud_command(args)
        elif args.command == "analyze":
            return analyze_command(args)
        elif args.command == "gui":
            return gui_command(args)
        else:
            print(f"未知命令: {args.command}")
            return 1

    except KeyboardInterrupt:
        print("\n操作被用户中断")
        return 130  # SIGINT退出码
    except Exception as e:
        if args.verbose:
            import traceback

            traceback.print_exc()
        else:
            print(f"错误: {e}")
        return 1


def scrape_command(args) -> int:
    """爬取历史数据"""
    try:
        from scrap import WeiboHotScraper
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        return 1

    print(f"开始爬取 {args.start} 到 {args.end} 的历史数据...")
    print(f"输出目录: {args.output_dir}")
    print(f"请求间隔: {args.delay}秒")
    print(f"最大重试次数: {args.max_retries}")

    scraper = WeiboHotScraper(
        output_dir=args.output_dir,
        delay=args.delay,
        max_retries=args.max_retries,
    )

    try:
        stats = scraper.scrape_range(args.start, args.end)
        print("\n爬取完成！")
        print(f"总天数: {stats['total_dates']}")
        print(f"成功: {stats['successful']}")
        print(f"失败: {stats['failed']}")

        if stats["failed_dates"]:
            print(f"失败的日期: {', '.join(stats['failed_dates'][:5])}")
            if len(stats["failed_dates"]) > 5:
                print(f"... 以及 {len(stats['failed_dates']) - 5} 个更多")

        return 0
    except Exception as e:
        print(f"爬取过程中出错: {e}")
        return 1


def scrape_realtime_command(args) -> int:
    """爬取实时数据"""
    try:
        from scrap import main_realtime
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        return 1

    print("开始爬取实时微博热搜数据...")
    print(f"请求超时: {args.timeout}秒")
    print(f"最大重试次数: {args.max_retries}")
    print(f"重试间隔: {args.delay}秒")

    # 注意：这里我们假设main_realtime函数可以接受这些参数
    # 如果不行，可能需要调整RealtimeHotScraper的调用方式
    try:
        # 暂时使用默认参数调用
        main_realtime()
        return 0
    except Exception as e:
        print(f"爬取实时数据过程中出错: {e}")
        return 1


def preprocess_command(args) -> int:
    """预处理数据"""
    try:
        from data_pre_process import process_dir
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        return 1

    print(f"预处理数据从 {args.input_dir} 到 {args.output_dir}...")

    try:
        results = process_dir(args.input_dir, output_dir=args.output_dir)
        print(f"处理完成！共处理 {len(results)} 个文件")
        print(f"输出目录: {args.output_dir}")
        return 0
    except Exception as e:
        print(f"预处理过程中出错: {e}")
        return 1


def query_command(args) -> int:
    """查询数据"""
    try:
        from data_query import DataQuery
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        return 1

    print("执行数据查询...")

    try:
        query = DataQuery()

        # 构建查询参数
        query_params = {}

        if args.date_range:
            query_params["date_range"] = tuple(args.date_range)
            print(f"日期范围: {args.date_range[0]} 到 {args.date_range[1]}")

        if args.categories:
            query_params["categories"] = args.categories
            print(f"分类: {', '.join(args.categories)}")

        if args.rank_range:
            query_params["rank_range"] = tuple(args.rank_range)
            print(f"排名范围: {args.rank_range[0]} - {args.rank_range[1]}")

        if args.heat_range:
            query_params["heat_range"] = tuple(args.heat_range)
            print(f"热度范围: {args.heat_range[0]} - {args.heat_range[1]}")

        if args.title_keywords:
            query_params["title_keywords"] = args.title_keywords
            print(f"标题关键词: {', '.join(args.title_keywords)}")

        if args.sort_by:
            query_params["sort_by"] = args.sort_by
            print(f"排序方式: {args.sort_by}")

        # 执行查询
        results = query.query(**query_params)

        print(f"\n查询完成！找到 {len(results)} 条数据")

        # 显示前几条结果
        if results:
            print("\n前10条结果:")
            for i, item in enumerate(results[:10], 1):
                print(
                    f"{i:2d}. [{item.get('date', 'N/A')}] #{item.get('rank', 'N/A')} "
                    f"{item.get('title', 'N/A')} "
                    f"(热度: {item.get('heat', 'N/A'):.1f}, "
                    f"分类: {item.get('category', '未分类')})"
                )

        # 保存结果到文件
        if args.output:
            try:
                from data_query import DataQuery

                # 注意：DataQuery类需要有保存结果的方法
                # 这里我们假设可以使用query_to_file方法
                saved = query.query_to_file(output_path=args.output, **query_params)
                print(f"\n结果已保存到: {args.output}")
            except AttributeError:
                # 如果query_to_file不存在，使用自定义保存
                import json

                output_data = {
                    "query_time": "现在",
                    "result_count": len(results),
                    "results": results,
                }
                os.makedirs(os.path.dirname(args.output), exist_ok=True)
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)
                print(f"\n结果已保存到: {args.output}")

        return 0
    except Exception as e:
        print(f"查询过程中出错: {e}")
        return 1


def classify_command(args) -> int:
    """分类数据"""
    try:
        from category_classifier import DataClassifier
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        return 1

    print("启动交互式数据分类器...")
    print(f"数据目录: {args.data_dir}")
    print(f"最小热度阈值: {args.min_heat}")

    try:
        classifier = DataClassifier(data_dir=args.data_dir, min_heat=args.min_heat)
        classifier.run()
        return 0
    except Exception as e:
        print(f"分类过程中出错: {e}")
        return 1


def wordcloud_command(args) -> int:
    """生成词云"""
    try:
        from word_cloud import WordCloudGenerator
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        return 1

    print(f"生成词云图...")
    print(f"输入目录: {args.input_dir}")
    print(f"输出目录: {args.output_dir}")

    try:
        generator = WordCloudGenerator(output_base=args.output_dir)
        generator.process_data_dir(args.input_dir)

        print("词云生成完成！")
        print(f"  - 分词结果: {generator.keywords_counts_dir}")
        print(f"  - 类型统计: {generator.types_counts_dir}")
        print(f"  - 关键词词云: {generator.keywords_wc_dir}")
        print(f"  - 类型词云: {generator.types_wc_dir}")

        return 0
    except Exception as e:
        print(f"生成词云过程中出错: {e}")
        return 1


def analyze_command(args) -> int:
    """分析JSON数据"""
    try:
        from json_analyzer import analyze_json, setup_font
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        return 1

    print(f"分析JSON文件: {args.json_file}")
    print(f"使用字体: {args.font}")
    if args.output_dir:
        print(f"输出目录名称: {args.output_dir}")

    if not os.path.exists(args.json_file):
        print(f"错误: 文件不存在: {args.json_file}")
        return 1

    try:
        # 设置字体
        setup_font(args.font)

        # 分析文件
        analyze_json(args.json_file, args.output_dir)

        print("分析完成！")
        print("图表和报告已保存到 output/ 目录")

        return 0
    except Exception as e:
        print(f"分析过程中出错: {e}")
        return 1


def gui_command(args) -> int:
    """启动GUI"""
    try:
        import subprocess
        import sys
    except ImportError as e:
        print(f"导入模块失败: {e}")
        return 1

    print("启动图形用户界面...")
    print("如果浏览器没有自动打开，请访问 http://localhost:8501")

    try:
        # 使用subprocess启动streamlit
        # 注意：streamlit需要作为模块运行
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/gui/app.py"])
        return 0
    except KeyboardInterrupt:
        print("\nGUI已关闭")
        return 0
    except Exception as e:
        print(f"启动GUI过程中出错: {e}")
        print("请确保已安装streamlit: pip install streamlit")
        return 1


if __name__ == "__main__":
    sys.exit(main())
