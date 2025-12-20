#!/usr/bin/env python3
"""
微博爬虫与数据分析系统 - 快速启动脚本
默认启动GUI版本
"""

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 8):
        print(
            f"错误: 需要Python 3.8或更高版本，当前版本: {sys.version_info.major}.{sys.version_info.minor}"
        )
        return False
    print(
        f"✓ Python版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    return True


def check_virtual_environment():
    """检查是否在虚拟环境中"""
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    if not in_venv:
        print("⚠ 提示: 建议在虚拟环境中运行本项目")
        print("   可以运行以下命令创建虚拟环境:")
        print("   python3 -m venv venv")
        print("   source venv/bin/activate  # Linux/macOS")
        print("   venv\\Scripts\\activate   # Windows")
        print("   pip install -r requirements.txt")
    else:
        print("✓ 在虚拟环境中运行")
    return in_venv


def check_dependencies():
    """检查依赖包"""
    dependencies = [
        ("requests", "requests"),
        ("beautifulsoup4", "bs4"),
        ("lxml", "lxml"),
        ("jieba", "jieba"),
        ("snownlp", "snownlp"),
        ("wordcloud", "wordcloud"),
        ("matplotlib", "matplotlib"),
        ("streamlit", "streamlit"),
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("playwright", "playwright"),
        ("networkx", "networkx"),
        ("plotly", "plotly"),
    ]

    missing = []
    available = []

    for pip_name, import_name in dependencies:
        spec = importlib.util.find_spec(import_name)
        if spec is None:
            missing.append(pip_name)
        else:
            available.append(import_name)

    print(f"✓ 已安装依赖: {', '.join(available)}")
    if missing:
        print(f"⚠ 缺失依赖: {', '.join(missing)}")

    return missing, available


def check_playwright_browser():
    """检查playwright浏览器是否安装"""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                print("✓ playwright浏览器已安装")
                return True
            except Exception:
                print("⚠ playwright浏览器未安装，实时热搜功能可能受限")
                print(
                    "  如果需要实时热搜功能，请运行: python -m playwright install chromium"
                )
                return False
    except ImportError:
        print("⚠ playwright库未安装")
        return False


def check_data_directories():
    """检查数据目录"""
    project_root = Path(__file__).parent
    data_dirs = ["data_processed"]

    missing_dirs = []
    for dir_name in data_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print(f"✓ 数据目录: {dir_name}")
        else:
            missing_dirs.append(dir_name)
            print(f"⚠ 缺失数据目录: {dir_name}")

    if missing_dirs:
        print("  提示: 部分功能需要预先爬取的数据")
        print("  如果需要爬取数据，请运行: python3 src/main.py scrape")

    return len(missing_dirs) == 0


def install_dependencies():
    """安装依赖"""
    print("正在安装依赖...")
    project_root = Path(__file__).parent
    requirements_file = project_root / "requirements.txt"

    if not requirements_file.exists():
        print(f"错误: 未找到requirements.txt文件")
        return False

    try:
        # 使用当前Python的pip安装
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True,
        )
        print("✓ 依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"错误: 依赖安装失败: {e}")
        return False


def install_playwright_browser():
    """安装playwright浏览器"""
    print("正在安装playwright浏览器...")
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"], check=True
        )
        print("✓ playwright浏览器安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"错误: playwright浏览器安装失败: {e}")
        return False


def start_gui():
    """启动GUI"""
    project_root = Path(__file__).parent
    app_file = project_root / "src" / "gui" / "app.py"

    if not app_file.exists():
        print(f"错误: 未找到GUI应用文件: {app_file}")
        return False

    print("\n" + "=" * 50)
    print("启动图形用户界面...")
    print("如果浏览器没有自动打开，请访问 http://localhost:8501")
    print("按 Ctrl+C 停止服务")
    print("=" * 50 + "\n")

    try:
        # 启动streamlit
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_file)])
        return True
    except KeyboardInterrupt:
        print("\n✓ GUI已关闭")
        return True
    except Exception as e:
        print(f"错误: 启动GUI失败: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="微博爬虫与数据分析系统 - 快速启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                    # 检查环境并启动GUI
  %(prog)s --check            # 只检查环境，不启动GUI
  %(prog)s --install          # 安装缺失的依赖
  %(prog)s --install-browser  # 安装playwright浏览器
  %(prog)s --help             # 显示此帮助信息
        """,
    )

    parser.add_argument("--check", action="store_true", help="只检查环境，不启动GUI")
    parser.add_argument("--install", action="store_true", help="安装缺失的依赖")
    parser.add_argument(
        "--install-browser", action="store_true", help="安装playwright浏览器"
    )
    parser.add_argument(
        "--no-check", action="store_true", help="跳过环境检查直接启动GUI"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("微博爬虫与数据分析系统 - 快速启动")
    print("=" * 50)

    # 处理安装命令
    if args.install:
        install_dependencies()
        return

    if args.install_browser:
        install_playwright_browser()
        return

    # 检查环境
    if not args.no_check:
        print("\n检查环境...")
        checks_passed = True

        # 检查Python版本
        if not check_python_version():
            checks_passed = False

        # 检查虚拟环境
        check_virtual_environment()

        # 检查依赖
        missing_deps, _ = check_dependencies()

        # 检查playwright浏览器
        check_playwright_browser()

        # 检查数据目录
        check_data_directories()

        # 如果有缺失依赖，提示用户
        if missing_deps:
            print(f"\n⚠ 有缺失的依赖: {', '.join(missing_deps)}")
            print("  可以使用以下命令安装:")
            print(f"  pip install {' '.join(missing_deps)}")
            print("  或者运行: python run.py --install")

            if not args.check:
                response = input("\n是否继续启动GUI? (y/n): ").strip().lower()
                if response != "y" and response != "yes":
                    print("启动取消")
                    return

        if args.check:
            print("\n环境检查完成")
            return

        if not checks_passed:
            response = (
                input("\n环境检查未通过，是否继续启动GUI? (y/n): ").strip().lower()
            )
            if response != "y" and response != "yes":
                print("启动取消")
                return

    # 启动GUI
    start_gui()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)
