"""
词云图生成模块

本模块对月度、季度、年度的热搜关键词以及热搜的类型标签进行词云图可视化，将结果保存为图片文件。
分词结果以及类型统计结果保存至 `output/keywords_counts` 和 `output/types_counts` 目录下。
词云图保存至 `output/word_clouds/keywords` 和 `output/word_clouds/types` 目录下。

类定义：
    - KeywordExtractor: 关键词分词和统计类
    - WordCloudGenerator: 词云生成类

主要功能：
    1. 读取预处理后的 JSON 数据文件，利用分词提取关键词
    2. 根据关键词出现的次数分月度、季度、年度生成词云图
    3. 热搜类型分析：统计不同类型标签的出现频次，生成对应的词云图
    4. 查询结果分析：从data_query.py的查询结果JSON文件生成词云，分析特定筛选条件下的关键词和分类分布

使用示例：
    1. 处理整个数据目录：
        generator = WordCloudGenerator(output_base="output")
        generator.process_data_dir("data_processed")

    2. 从查询结果生成词云：
        generator = WordCloudGenerator(output_base="output")
        generator.generate_from_query_result(
            query_result_path="data/output/query_result.json",
            output_prefix="my_analysis"
        )
"""

import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import jieba
import matplotlib
from wordcloud import WordCloud

matplotlib.use("Agg")  # 无界面后端，避免显示问题
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.font_manager import FontProperties


class KeywordExtractor:
    """
    关键词分词和统计类
    """

    def __init__(self, min_word_length: int = 2):
        """
        初始化分词器

        参数：
            min_word_length: 最小词语长度（忽略长度小于此值的词）
        """
        self.min_word_length = min_word_length

        # 扩展的停用词集合（包括"回应"和"什么"）
        self.stopwords = {
            "的",
            "了",
            "和",
            "是",
            "在",
            "到",
            "一",
            "个",
            "为",
            "中",
            "回应",
            "什么",
            "了吗",
            "怎么",
            "这么",
            "为什么",
            "不要",
            "真的",
            "是",
            "不是",
            "就是",
            "可能",
            "要求",
            "还是",
            "小时",
            "疑似",
            "吗",
            "呢",
            "吧",
            "啊",
            "哦",
            "这",
            "那",
            "有",
            "没有",
            "没",
            "很",
            "比",
            "更",
            "最",
            "就",
            "还",
            "也",
            "被",
            "把",
            "向",
            "让",
            "给",
            "从",
            "以",
            "经",
            "于",
            "对",
        }

        # 英文缩写过滤集合
        self.abbreviations = {
            "vs",
            "vs.",
            "etc",
            "etc.",
            "i.e",
            "e.g",
            "i.e.",
            "e.g.",
            "vs",
            "v.s",
            "v.s.",
            "vs",
            "v",
            "s",
            "etc",
            "et",
            "al",
            "eg",
            "ie",
            "cf",
            "cf.",
            "ex",
            "ex.",
            "fig",
            "fig.",
            "no",
            "no.",
            "vol",
            "vol.",
            "pp",
            "pp.",
            "ch",
            "ch.",
            "sec",
            "sec.",
            "ref",
            "ref.",
            "eq",
            "eq.",
            "fig",
            "fig.",
        }

        # 向 jieba 添加自定义词语（作为整体词）
        self.custom_words = ["王楚钦"]  # 需要保持整体的词语
        for word in self.custom_words:
            jieba.add_word(word, freq=500)  # freq 高度越高，分词时越可能被识别为整体

    def extract_keywords(self, text: str) -> List[str]:
        """
        从文本中提取关键词

        参数：
            text: 待分词的文本

        返回：
            关键词列表
        """
        words = jieba.cut(text)
        keywords = [
            w
            for w in words
            if len(w) >= self.min_word_length
            and w not in self.stopwords
            and not w.isdigit()  # 过滤纯数字
            and w.lower() not in self.abbreviations  # 过滤英文缩写
        ]
        return keywords


class WordCloudGenerator:
    """
    词云生成类
    """

    def __init__(self, output_base: str = "output"):
        """
        初始化词云生成器

        参数：
            output_base: 输出根目录
        """
        self.output_base = output_base
        self.keywords_counts_dir = os.path.join(output_base, "keywords_counts")
        self.types_counts_dir = os.path.join(output_base, "types_counts")
        self.keywords_wc_dir = os.path.join(output_base, "word_clouds", "keywords")
        self.types_wc_dir = os.path.join(output_base, "word_clouds", "types")

        # 创建输出目录
        for dir_path in [
            self.keywords_counts_dir,
            self.types_counts_dir,
            self.keywords_wc_dir,
            self.types_wc_dir,
        ]:
            os.makedirs(dir_path, exist_ok=True)

        self.extractor = KeywordExtractor()
        self.font_path = self._find_chinese_font()
        self._setup_font_for_matplotlib()

    def _find_chinese_font(self) -> str:
        """
        查找系统中可用的中文字体

        返回：
            字体路径，若找不到则返回空字符串
        """
        # macOS 常见中文字体路径
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",  # 苹方
            "/System/Library/Fonts/STHeiti Light.ttc",  # 黑体
            "/Library/Fonts/Arial Unicode.ttf",  # Arial Unicode
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/SimHei.ttf",  # 微软黑体（如有安装）
            "/Library/Fonts/SimSun.ttf",  # 宋体
            "/home/himkkk/.local/share/fonts/MapleMono-NF-CN-Bold.ttf",  # 这是fyk用的字体
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                return font_path

        # 如果没有找到特定字体，尝试从 matplotlib 的字体列表中获取
        try:
            from matplotlib.font_manager import findSystemFonts

            fonts = findSystemFonts()
            for font in fonts:
                if "SimHei" in font or "PingFang" in font or "Heiti" in font:
                    return font
        except Exception:
            pass

        return ""

    def _setup_font_for_matplotlib(self) -> None:
        """配置 matplotlib 以支持中文字体"""
        if self.font_path:
            # 直接使用找到的字体文件路径
            rcParams["font.sans-serif"] = [self.font_path]
        else:
            # 使用系统字体名称列表（优先级顺序）
            rcParams["font.sans-serif"] = [
                "PingFang SC",  # macOS 苹方
                "SimHei",  # Windows 微软黑体
                "SimSun",  # Windows 宋体
                "Helvetica Neue",  # macOS 备用
            ]

        rcParams["axes.unicode_minus"] = False  # 解决负号显示问题
        rcParams["font.size"] = 12

    def process_data_dir(self, data_dir: str) -> None:
        """
        处理整个数据目录（按月份组织）

        参数：
            data_dir: 数据根目录路径
        """
        monthly_keywords = defaultdict(list)  # {YYYY-MM: [keywords...]}
        monthly_types = defaultdict(list)  # {YYYY-MM: [type...]}

        # 遍历 data_dir 下的月度文件夹
        for month_folder in sorted(os.listdir(data_dir)):
            month_path = os.path.join(data_dir, month_folder)
            if not os.path.isdir(month_path):
                continue

            # 提取 YYYY-MM 格式的月度标识（假设文件夹为 2025-01, 2025-02 等）
            try:
                month_key = month_folder  # e.g., "2025-01"
            except ValueError:
                continue

            # 遍历该月份的所有日期 JSON 文件
            for date_file in sorted(os.listdir(month_path)):
                if not date_file.endswith(".json"):
                    continue

                date_path = os.path.join(month_path, date_file)
                try:
                    with open(date_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 提取关键词和类型
                    for item in data.get("data", []):
                        title = item.get("title", "")
                        category = item.get("category", "")

                        if title:
                            keywords = self.extractor.extract_keywords(title)
                            monthly_keywords[month_key].extend(keywords)

                        if category:
                            monthly_types[month_key].append(category)
                except Exception as e:
                    print(f"处理 {date_path} 时出错: {e}")

        # 按月、季、年统计和生成词云
        self._generate_monthly_wordclouds(monthly_keywords, monthly_types)
        self._generate_quarterly_wordclouds(monthly_keywords, monthly_types)
        self._generate_yearly_wordclouds(monthly_keywords, monthly_types)

    def _generate_monthly_wordclouds(
        self,
        monthly_keywords: Dict[str, List[str]],
        monthly_types: Dict[str, List[str]],
    ) -> None:
        """生成月度词云"""
        for month_key in sorted(monthly_keywords.keys()):
            # 关键词统计
            keywords_counter = Counter(monthly_keywords[month_key])
            self._save_counts_json(
                keywords_counter, f"keywords_{month_key}.json", self.keywords_counts_dir
            )
            self._generate_wordcloud(
                keywords_counter,
                f"keywords_{month_key}.png",
                self.keywords_wc_dir,
                title=f"月度词云 - {month_key}",
            )

            # 类型统计
            types_counter = Counter(monthly_types[month_key])
            self._save_counts_json(
                types_counter, f"types_{month_key}.json", self.types_counts_dir
            )
            self._generate_wordcloud(
                types_counter,
                f"types_{month_key}.png",
                self.types_wc_dir,
                title=f"月度类型分布 - {month_key}",
            )

    def _generate_quarterly_wordclouds(
        self,
        monthly_keywords: Dict[str, List[str]],
        monthly_types: Dict[str, List[str]],
    ) -> None:
        """生成季度词云"""
        # 按季度分组月份数据
        quarterly_keywords = defaultdict(list)  # {2025-Q1: [keywords...]}
        quarterly_types = defaultdict(list)

        for month_key in monthly_keywords.keys():
            try:
                year, month = month_key.split("-")
                month_int = int(month)
                quarter = (month_int - 1) // 3 + 1
                quarter_key = f"{year}-Q{quarter}"

                quarterly_keywords[quarter_key].extend(monthly_keywords[month_key])
                quarterly_types[quarter_key].extend(monthly_types[month_key])
            except (ValueError, KeyError):
                continue

        for quarter_key in sorted(quarterly_keywords.keys()):
            # 关键词统计
            keywords_counter = Counter(quarterly_keywords[quarter_key])
            self._save_counts_json(
                keywords_counter,
                f"keywords_{quarter_key}.json",
                self.keywords_counts_dir,
            )
            self._generate_wordcloud(
                keywords_counter,
                f"keywords_{quarter_key}.png",
                self.keywords_wc_dir,
                title=f"季度词云 - {quarter_key}",
            )

            # 类型统计
            types_counter = Counter(quarterly_types[quarter_key])
            self._save_counts_json(
                types_counter, f"types_{quarter_key}.json", self.types_counts_dir
            )
            self._generate_wordcloud(
                types_counter,
                f"types_{quarter_key}.png",
                self.types_wc_dir,
                title=f"季度类型分布 - {quarter_key}",
            )

    def _generate_yearly_wordclouds(
        self,
        monthly_keywords: Dict[str, List[str]],
        monthly_types: Dict[str, List[str]],
    ) -> None:
        """生成年度词云"""
        # 按年份分组
        yearly_keywords = defaultdict(list)
        yearly_types = defaultdict(list)

        for month_key in monthly_keywords.keys():
            try:
                year = month_key.split("-")[0]
                yearly_keywords[year].extend(monthly_keywords[month_key])
                yearly_types[year].extend(monthly_types[month_key])
            except (ValueError, IndexError):
                continue

        for year_key in sorted(yearly_keywords.keys()):
            # 关键词统计
            keywords_counter = Counter(yearly_keywords[year_key])
            self._save_counts_json(
                keywords_counter, f"keywords_{year_key}.json", self.keywords_counts_dir
            )
            self._generate_wordcloud(
                keywords_counter,
                f"keywords_{year_key}.png",
                self.keywords_wc_dir,
                title=f"年度词云 - {year_key}",
            )

            # 类型统计
            types_counter = Counter(yearly_types[year_key])
            self._save_counts_json(
                types_counter, f"types_{year_key}.json", self.types_counts_dir
            )
            self._generate_wordcloud(
                types_counter,
                f"types_{year_key}.png",
                self.types_wc_dir,
                title=f"年度类型分布 - {year_key}",
            )

    def _save_counts_json(
        self, counter: Counter, filename: str, output_dir: str
    ) -> None:
        """保存统计结果为 JSON 文件"""
        output_path = os.path.join(output_dir, filename)
        # 转换为字典，并按出现频次倒序
        counts_dict = dict(sorted(counter.items(), key=lambda x: x[1], reverse=True))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(counts_dict, f, ensure_ascii=False, indent=2)

    def _generate_wordcloud(
        self, word_freq: Counter, filename: str, output_dir: str, title: str = ""
    ) -> None:
        """
        生成和保存词云图片

        参数：
            word_freq: 词频 Counter 对象
            filename: 输出文件名
            output_dir: 输出目录
            title: 图表标题
        """
        if not word_freq:
            return

        # 转换为字典供 WordCloud 使用
        word_dict = dict(word_freq)

        # 生成词云，优先使用找到的字体
        wc = None
        try:
            if self.font_path:
                wc = WordCloud(
                    width=1200,
                    height=600,
                    background_color="white",
                    max_words=100,
                    font_path=self.font_path,
                    collocations=False,
                    prefer_horizontal=0.7,
                    min_font_size=10,
                ).generate_from_frequencies(word_dict)
            else:
                # 尝试使用 matplotlib 中文字体
                wc = WordCloud(
                    width=1200,
                    height=600,
                    background_color="white",
                    max_words=100,
                    collocations=False,
                    prefer_horizontal=0.7,
                    min_font_size=10,
                ).generate_from_frequencies(word_dict)
        except Exception as e:
            print(f"生成词云时出错 ({filename}): {e}")
            return

        # 绘图并保存
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")

        if title:
            # 设置标题，使用专门的 FontProperties 确保中文正常显示
            if self.font_path:
                font_prop = FontProperties(fname=self.font_path, size=14)
                ax.set_title(title, fontproperties=font_prop, pad=20)
            else:
                # 使用 matplotlib 配置的字体
                ax.set_title(title, fontsize=14, pad=20)

        output_path = os.path.join(output_dir, filename)
        fig.savefig(output_path, dpi=100, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"✓ 已生成: {output_path}")

    def generate_from_query_result(
        self, query_result_path: str, output_prefix: str = "query_result"
    ) -> None:
        """
        从查询结果JSON文件生成词云

        参数：
            query_result_path: 查询结果JSON文件路径（来自data_query.py的save_results方法）
            output_prefix: 输出文件前缀，用于生成输出文件名

        内部逻辑：
            1. 读取查询结果JSON文件
            2. 从结果中提取所有标题和分类
            3. 生成关键词词云和分类词云
            4. 保存到output文件夹
        """
        # 读取查询结果JSON
        with open(query_result_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 提取结果列表
        results = data.get("results", [])
        if not results:
            print(f"警告: 查询结果文件中没有数据: {query_result_path}")
            return

        # 处理查询结果数据
        keywords_counter, types_counter = self._process_query_result_json(results)

        # 生成时间戳用于文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 生成关键词词云
        if keywords_counter:
            keywords_filename = f"{output_prefix}_keywords_{timestamp}.png"
            self._generate_wordcloud(
                keywords_counter,
                keywords_filename,
                self.keywords_wc_dir,
                title=f"查询结果词云 - {output_prefix}",
            )

            # 保存关键词统计
            counts_filename = f"{output_prefix}_keywords_{timestamp}.json"
            self._save_counts_json(
                keywords_counter,
                counts_filename,
                self.keywords_counts_dir,
            )

        # 生成分类词云
        if types_counter:
            types_filename = f"{output_prefix}_types_{timestamp}.png"
            self._generate_wordcloud(
                types_counter,
                types_filename,
                self.types_wc_dir,
                title=f"查询结果类型分布 - {output_prefix}",
            )

            # 保存分类统计
            types_counts_filename = f"{output_prefix}_types_{timestamp}.json"
            self._save_counts_json(
                types_counter,
                types_counts_filename,
                self.types_counts_dir,
            )

        print(f"查询结果词云生成完成！共处理 {len(results)} 条数据")
        if keywords_counter:
            print(f"  - 关键词统计: {len(keywords_counter)} 个关键词")
        if types_counter:
            print(f"  - 分类统计: {len(types_counter)} 个分类")

    def _process_query_result_json(
        self, results: List[Dict[str, Any]]
    ) -> Tuple[Counter, Counter]:
        """
        处理查询结果JSON数据，提取关键词和分类统计

        参数：
            results: 查询结果列表

        返回：
            (keywords_counter, types_counter): 关键词计数器和分类计数器
        """
        all_keywords = []
        all_types = []

        for item in results:
            # 提取标题关键词
            title = item.get("title", "")
            if title:
                keywords = self.extractor.extract_keywords(title)
                all_keywords.extend(keywords)

            # 提取分类
            category = item.get("category", "")
            if category:
                all_types.append(category)

        # 创建计数器
        keywords_counter = Counter(all_keywords)
        types_counter = Counter(all_types)

        return keywords_counter, types_counter


if __name__ == "__main__":
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(__file__))
    data_processed_dir = os.path.join(project_root, "data_processed")
    output_dir = os.path.join(project_root, "output")

    print(f"数据目录: {data_processed_dir}")
    print(f"输出目录: {output_dir}")

    # 生成词云
    generator = WordCloudGenerator(output_base=output_dir)
    generator.process_data_dir(data_processed_dir)

    print("词云生成完成！")
    print(f"  - 分词结果: {generator.keywords_counts_dir}")
    print(f"  - 类型统计: {generator.types_counts_dir}")
    print(f"  - 关键词词云: {generator.keywords_wc_dir}")
    print(f"  - 类型词云: {generator.types_wc_dir}")
