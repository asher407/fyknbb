"""
微博热搜历史数据爬虫模块

本模块用于爬取微博热搜历史数据网站（https://weibo-trending-hot-history.vercel.app/hots/{date}）
并将数据按日期保存为JSON格式。

类定义：
    WeiboHotScraper: 微博热搜爬虫主类
    RealtimeHotScraper: 实时热搜爬虫类

主要功能：
    1. 爬取指定日期范围的微博热搜数据
    2. 解析HTML页面中的热搜条目信息
    3. 将数据按月份组织并保存为JSON文件
    4. 提供错误处理和重试机制

使用示例：
    scraper = WeiboHotScraper(output_dir="data")
    scraper.scrape_range("2025-01-01", "2025-12-12")
    - 实时爬虫页面运行命令：
    python -m streamlit run src/gui/app.py
"""

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


@dataclass
class HotItem:
    """
    热搜条目数据类

    属性：
        rank: 排名（第几名）
        title: 热搜标题
        category: 分类（如：明星、社会等）
        heat: 热度值（单位：万）
        reads: 阅读量（单位：亿/万）
        discussions: 讨论量（单位：万）
        originals: 原创量（单位：万）
        date: 日期（YYYY-MM-DD格式）
    """

    rank: int
    title: str
    category: str
    heat: float
    reads: float
    discussions: float
    originals: float
    date: str


class WeiboHotScraper:
    """
    微博热搜爬虫主类

    功能：
        - 爬取指定日期的微博热搜数据
        - 解析HTML中的热搜条目信息
        - 将数据保存为JSON格式文件
        - 按月份组织数据文件

    参数：
        base_url (str): 目标网站的基础URL
        output_dir (str): 输出目录路径
        delay (float): 请求间隔时间（秒），防止被封IP
        timeout (int): 请求超时时间（秒）
        max_retries (int): 最大重试次数

    方法：
        fetch_page(date: str) -> Optional[str]: 获取指定日期的页面HTML
        parse_page(html: str, date: str) -> List[HotItem]: 解析HTML提取热搜数据
        save_data(data: List[HotItem], date: str) -> bool: 保存数据到JSON文件
        scrape_date(date: str) -> bool: 爬取并保存指定日期的数据
        scrape_range(start_date: str, end_date: str) -> Dict[str, Any]: 爬取日期范围的数据
    """

    def __init__(
        self,
        base_url: str = "https://weibo-trending-hot-history.vercel.app/hots",
        output_dir: str = "data",
        delay: float = 1.0,
        timeout: int = 10,
        max_retries: int = 3,
    ):
        """
        初始化爬虫

        参数：
            base_url: 目标网站的基础URL
            output_dir: 输出目录路径
            delay: 请求间隔时间（秒）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.base_url = base_url
        self.output_dir = output_dir
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

        # 配置requests会话
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
            }
        )

    def fetch_page(self, date: str) -> Optional[str]:
        """
        获取指定日期的页面HTML

        参数：
            date: 日期字符串，格式为YYYY-MM-DD

        返回：
            HTML字符串或None（如果请求失败）
        """
        url = f"{self.base_url}/{date}"

        for attempt in range(self.max_retries):
            try:
                self.logger.info(
                    f"正在获取 {date} 的数据 (尝试 {attempt + 1}/{self.max_retries})"
                )
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()

                # 检查是否返回有效内容
                if response.status_code == 200 and len(response.text) > 100:
                    # 检查页面是否包含有效数据
                    # 注意：有些页面可能包含"没有找到"或"404"但仍有内容，需要更智能的判断
                    html_text = response.text

                    # 检查是否有热搜条目的特征
                    has_hot_features = (
                        "查看微博话题" in html_text
                        or "text-xl" in html_text
                        or "inline-flex" in html_text
                    )

                    # 如果页面有热搜特征，即使包含"没有找到"或"404"也返回
                    if has_hot_features:
                        self.logger.info(f"成功获取 {date} 的数据（有热搜特征）")
                        return html_text

                    # 否则，检查是否真的是无效页面
                    if "没有找到" in html_text or "404" in html_text:
                        # 进一步确认：检查页面是否真的很小或者没有实际内容结构
                        soup = BeautifulSoup(html_text, "html.parser")
                        a_tags = soup.find_all("a")

                        # 如果几乎没有a标签，可能是真的没有数据
                        if len(a_tags) < 10:  # 普通页面通常有很多a标签
                            self.logger.warning(f"{date} 没有数据（页面结构简单）")
                            return None
                        else:
                            # 有很多a标签，可能只是页面包含404文本但有实际内容
                            self.logger.info(f"获取 {date} 的数据（有a标签结构）")
                            return html_text

                    self.logger.info(f"成功获取 {date} 的数据")
                    return html_text
                else:
                    self.logger.warning(f"{date} 返回了空页面或无效响应")

            except requests.exceptions.RequestException as e:
                self.logger.error(f"获取 {date} 数据失败: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt  # 指数退避
                    self.logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"达到最大重试次数，跳过 {date}")

            except Exception as e:
                self.logger.error(f"获取 {date} 数据时发生未知错误: {e}")
                break

        return None

    def _extract_number(self, text: str) -> float:
        """
        从文本中提取数字，处理中文单位

        参数：
            text: 包含数字和单位的文本（如："855.15万", "1.50亿", "8210"）

        返回：
            转换后的浮点数（统一转换为万单位）
        """
        try:
            # 移除空格和特殊字符
            text = text.strip()

            # 匹配数字部分（支持小数）
            num_match = re.search(r"[\d\.]+", text)
            if not num_match:
                return 0.0

            num = float(num_match.group())

            # 根据单位进行换算（统一转换为万单位）
            if "亿" in text:
                num *= 10000  # 亿转换为万
            elif "万" in text:
                pass  # 已经是万单位
            else:
                # 没有单位的数字，除以10000转换为万单位
                # 例如 "8210" -> 0.821万
                num /= 10000

            return round(num, 2)
        except Exception as e:
            self.logger.warning(f"解析数字失败: {text}, 错误: {e}")
            return 0.0

    def _parse_rank(self, h2_tag) -> Tuple[int, str]:
        """
        从h2标签中解析排名和标题

        参数：
            h2_tag: BeautifulSoup的h2标签对象

        返回：
            (排名, 标题) 元组
        """
        try:
            # 处理可能的两种格式：
            # 格式1: <h2 class="text-xl">第1名：李铁被判20年</h2>
            # 格式2: <h2 class="text-xl"><span class="sr-only">第<!-- -->1<!-- -->名：</span>双轨空降</h2>

            # 获取完整的文本（包括span内的文本）
            full_text = h2_tag.get_text(strip=True)

            # 使用正则表达式提取排名
            rank_match = re.search(r"第\s*(\d+)\s*名", full_text)
            if rank_match:
                rank = int(rank_match.group(1))

                # 提取标题：移除排名部分
                # 注意：BeautifulSoup的get_text()已经处理了HTML注释
                title = re.sub(r"第\s*\d+\s*名：?", "", full_text).strip()

                # 如果标题为空，尝试从span后的文本获取
                if not title:
                    # 查找span标签
                    span_tag = h2_tag.find("span", class_="sr-only")
                    if span_tag:
                        # 获取span之后的所有文本
                        span_text = span_tag.get_text(strip=True)
                        title = full_text.replace(span_text, "").strip()

                return rank, title
            else:
                # 如果没有找到排名格式，尝试其他格式
                rank_match = re.search(r"(\d+)", full_text)
                if rank_match:
                    rank = int(rank_match.group(1))
                    # 移除数字和分隔符获取标题
                    title = re.sub(r"^\d+[\.:：]\s*", "", full_text).strip()
                    return rank, title
                else:
                    # 默认排名为0
                    return 0, full_text.strip()

        except Exception as e:
            self.logger.warning(f"解析排名失败: {str(h2_tag)[:50]}..., 错误: {e}")
            return 0, h2_tag.get_text(strip=True) if hasattr(
                h2_tag, "get_text"
            ) else str(h2_tag)

    def parse_page(self, html: str, date: str) -> List[HotItem]:
        """
        解析HTML页面，提取热搜条目信息

        参数：
            html: 页面HTML字符串
            date: 日期字符串，格式为YYYY-MM-DD

        返回：
            热搜条目列表
        """
        hot_items = []

        try:
            # 添加调试信息
            self.logger.debug(f"HTML长度: {len(html)}")
            if len(html) < 1000:
                self.logger.warning(f"HTML太短，可能有问题: {html[:500]}...")

            # 尝试使用lxml解析器，如果不可用则回退到html.parser
            try:
                soup = BeautifulSoup(html, "lxml")
                self.logger.debug("使用lxml解析器")
            except Exception as e:
                self.logger.warning(f"lxml解析器不可用，使用html.parser: {e}")
                soup = BeautifulSoup(html, "html.parser")
                self.logger.debug("使用html.parser解析器")

            # 查找所有的<a>标签，但只过滤出真正的热搜条目
            # 真正的热搜条目通常有：aria-label包含"查看微博话题"，或者包含h2.text-xl和data div
            all_a_tags = soup.find_all("a")
            hot_a_tags = []

            # 调试：记录前几个a标签的结构
            if len(all_a_tags) == 0:
                self.logger.warning("没有找到任何<a>标签，检查HTML结构...")
                # 检查页面是否有内容
                if soup.title:
                    self.logger.debug(f"页面标题: {soup.title.string}")
                # 检查是否有其他元素
                h2_tags = soup.find_all("h2")
                self.logger.debug(f"找到{h2_tags}个h2标签")
            else:
                self.logger.debug(f"找到第一个a标签预览: {str(all_a_tags[0])[:200]}...")

            for a_tag in all_a_tags:
                aria_label = a_tag.get("aria-label", "")
                h2_tag = a_tag.find("h2", class_="text-xl")
                data_container = a_tag.find("div", class_="flex")

                # 检查是否为真正的热搜条目
                if (("查看微博话题" in aria_label) and h2_tag and data_container) or (
                    h2_tag and data_container
                ):
                    hot_a_tags.append(a_tag)

            self.logger.info(
                f"找到 {len(all_a_tags)} 个<a>标签，其中 {len(hot_a_tags)} 个是热搜条目"
            )

            for a_tag in hot_a_tags:
                try:
                    # 查找h2标签
                    h2_tag = a_tag.find("h2", class_="text-xl")
                    if not h2_tag:
                        continue

                    # 解析排名和标题
                    rank, title = self._parse_rank(h2_tag)

                    # 查找包含分类和数据的div容器
                    data_container = a_tag.find("div", class_="flex")
                    if not data_container:
                        continue

                    # 提取所有数据标签
                    data_tags = data_container.find_all("div", class_="inline-flex")

                    # 初始化数据字段
                    category = ""
                    heat = 0.0
                    reads = 0.0
                    discussions = 0.0
                    originals = 0.0

                    for data_tag in data_tags:
                        text = data_tag.get_text(strip=True)

                        # 根据文本内容判断数据类型
                        # 先检查是否是数据字段
                        if "🔥" in text:
                            # 热度
                            heat = self._extract_number(text.replace("🔥", ""))
                        elif "阅读" in text:
                            # 阅读量
                            reads = self._extract_number(text.replace("阅读", ""))
                        elif "讨论" in text:
                            # 讨论量
                            discussions = self._extract_number(text.replace("讨论", ""))
                        elif "原创" in text:
                            # 原创量
                            originals = self._extract_number(text.replace("原创", ""))
                        else:
                            # 处理分类标签 - 更全面的分类检测
                            category_keywords = {
                                "明星": "明星",
                                "社会": "社会",
                                "娱乐": "娱乐",
                                "体育": "体育",
                                "科技": "科技",
                                "游戏": "游戏",
                                "美食": "美食",
                                "财经": "财经",
                                "时尚": "时尚",
                                "教育": "教育",
                                "健康": "健康",
                                "旅游": "旅游",
                                "汽车": "汽车",
                                "动漫": "动漫",
                                "军事": "军事",
                                "数码": "数码",
                                "音乐": "音乐",
                                "电影": "电影",
                                "电视剧": "电视剧",
                                "综艺": "综艺",
                                "搞笑": "搞笑",
                                "情感": "情感",
                                "生活": "生活",
                                "家居": "家居",
                                "育儿": "育儿",
                                "宠物": "宠物",
                                "摄影": "摄影",
                                "绘画": "绘画",
                                "读书": "读书",
                                "写作": "写作",
                                "职场": "职场",
                                "法律": "法律",
                                "政治": "政治",
                                "历史": "历史",
                                "文化": "文化",
                                "艺术": "艺术",
                                "科学": "科学",
                                "自然": "自然",
                                "环保": "环保",
                                "公益": "公益",
                                "宗教": "宗教",
                                "心理": "心理",
                                "星座": "星座",
                                "彩票": "彩票",
                                "股票": "股票",
                                "房产": "房产",
                                "创业": "创业",
                                "互联网": "互联网",
                                "手机": "手机",
                                "电脑": "电脑",
                                "软件": "软件",
                                "网络": "网络",
                                "电商": "电商",
                                "直播": "直播",
                                "网红": "网红",
                                "美妆": "美妆",
                                "服饰": "服饰",
                                "鞋包": "鞋包",
                                "珠宝": "珠宝",
                                "手表": "手表",
                                "家具": "家具",
                                "家电": "家电",
                                "厨具": "厨具",
                                "食品": "食品",
                                "饮料": "饮料",
                                "酒水": "酒水",
                                "烟草": "烟草",
                                "药品": "药品",
                                "医疗": "医疗",
                                "医院": "医院",
                                "学校": "学校",
                                "教育机构": "教育机构",
                                "公司": "公司",
                                "工厂": "工厂",
                                "农村": "农村",
                                "城市": "城市",
                                "交通": "交通",
                                "航空": "航空",
                                "铁路": "铁路",
                                "公路": "公路",
                                "海运": "海运",
                                "天气": "天气",
                                "地震": "地震",
                                "台风": "台风",
                                "洪水": "洪水",
                                "火灾": "火灾",
                                "事故": "事故",
                                "犯罪": "犯罪",
                                "警察": "警察",
                                "法院": "法院",
                                "监狱": "监狱",
                                "死亡": "死亡",
                                "出生": "出生",
                                "结婚": "结婚",
                                "离婚": "离婚",
                                "恋爱": "恋爱",
                                "分手": "分手",
                                "求婚": "求婚",
                                "婚礼": "婚礼",
                                "生日": "生日",
                                "节日": "节日",
                                "春节": "春节",
                                "中秋": "中秋",
                                "端午": "端午",
                                "清明": "清明",
                                "国庆": "国庆",
                                "元旦": "元旦",
                                "圣诞": "圣诞",
                            }

                            # 检查文本是否包含任何分类关键词
                            for keyword, cat in category_keywords.items():
                                if keyword in text:
                                    category = cat
                                    break

                    # 创建HotItem对象（确保有有效数据）
                    if rank > 0 and title:  # 基本验证
                        hot_item = HotItem(
                            rank=rank,
                            title=title,
                            category=category,
                            heat=heat,
                            reads=reads,
                            discussions=discussions,
                            originals=originals,
                            date=date,
                        )
                        hot_items.append(hot_item)
                    else:
                        self.logger.debug(f"跳过无效条目: rank={rank}, title={title}")

                except Exception as e:
                    self.logger.warning(f"解析单个热搜条目失败: {e}")
                    continue

            # 按排名排序
            hot_items.sort(key=lambda x: x.rank)

            self.logger.info(f"成功解析 {len(hot_items)} 个热搜条目")

            # 如果没有解析到任何条目，可能是页面结构不同，尝试备用解析方法
            if len(hot_items) == 0:
                self.logger.warning("使用主解析方法未找到数据，尝试备用解析方法...")
                hot_items = self._parse_page_backup(soup, date)

        except Exception as e:
            self.logger.error(f"解析页面失败: {e}")

        return hot_items

    def save_data(self, data: List[HotItem], date: str) -> bool:
        """
        保存数据到JSON文件

        参数：
            data: 热搜条目列表
            date: 日期字符串，格式为YYYY-MM-DD

        返回：
            保存成功返回True，否则返回False
        """
        try:
            # 解析日期，创建月份目录
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            year_month = date_obj.strftime("%Y-%m")

            # 创建月份目录
            month_dir = os.path.join(self.output_dir, year_month)
            os.makedirs(month_dir, exist_ok=True)

            # 构建文件路径
            filename = f"{date}.json"
            filepath = os.path.join(month_dir, filename)

            # 转换为字典列表
            data_dicts = [asdict(item) for item in data]

            # 保存为JSON文件
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {"date": date, "count": len(data), "data": data_dicts},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            self.logger.info(f"数据已保存到 {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"保存数据失败: {e}")
            return False

    def scrape_date_with_html(self, date: str, html: str) -> bool:
        """
        使用提供的HTML爬取并保存指定日期的数据（用于测试）

        参数：
            date: 日期字符串，格式为YYYY-MM-DD
            html: 页面HTML字符串

        返回：
            爬取成功返回True，否则返回False
        """
        self.logger.info(f"开始解析 {date} 的数据...")

        # 解析页面
        hot_items = self.parse_page(html, date)
        if not hot_items:
            self.logger.warning(f"{date} 没有解析到热搜数据")

        # 保存数据
        success = self.save_data(hot_items, date)

        if success:
            self.logger.info(f"成功完成 {date} 的数据解析")
        else:
            self.logger.error(f"{date} 的数据解析失败")

        return success

    def scrape_date(self, date: str) -> bool:
        """
        爬取并保存指定日期的数据

        参数：
            date: 日期字符串，格式为YYYY-MM-DD

        返回：
            爬取成功返回True，否则返回False
        """
        self.logger.info(f"开始爬取 {date} 的数据...")

        # 获取页面HTML
        html = self.fetch_page(date)
        if not html:
            self.logger.error(f"无法获取 {date} 的页面")
            return False

        # 等待延迟
        time.sleep(self.delay)

        # 解析页面
        hot_items = self.parse_page(html, date)
        if not hot_items:
            self.logger.warning(f"{date} 没有解析到热搜数据")
            # 仍然尝试保存空数据以记录该日期已被处理

        # 保存数据
        success = self.save_data(hot_items, date)

        if success:
            self.logger.info(f"成功完成 {date} 的数据爬取")
        else:
            self.logger.error(f"{date} 的数据爬取失败")

        return success

    def scrape_range(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        爬取指定日期范围的数据

        参数：
            start_date: 开始日期，格式为YYYY-MM-DD
            end_date: 结束日期，格式为YYYY-MM-DD

        返回：
            包含统计信息的字典
        """
        stats = {"total_dates": 0, "successful": 0, "failed": 0, "failed_dates": []}

        try:
            # 解析日期范围
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")

            # 生成日期列表
            current = start
            date_list = []

            while current <= end:
                date_list.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)

            stats["total_dates"] = len(date_list)
            self.logger.info(f"需要爬取 {len(date_list)} 天的数据")

            # 遍历日期并爬取
            for i, date in enumerate(date_list, 1):
                self.logger.info(f"进度: {i}/{len(date_list)} ({date})")

                try:
                    success = self.scrape_date(date)

                    if success:
                        stats["successful"] += 1
                    else:
                        stats["failed"] += 1
                        stats["failed_dates"].append(date)

                except Exception as e:
                    self.logger.error(f"爬取 {date} 时发生异常: {e}")
                    stats["failed"] += 1
                    stats["failed_dates"].append(date)

                # 在日期之间添加额外延迟，避免请求过快
                if i < len(date_list):
                    time.sleep(self.delay * 0.5)

            # 打印统计信息
            self.logger.info(
                f"爬取完成！成功: {stats['successful']}, 失败: {stats['failed']}"
            )
            if stats["failed_dates"]:
                self.logger.warning(f"失败的日期: {stats['failed_dates']}")

        except ValueError as e:
            self.logger.error(f"日期格式错误: {e}")
        except Exception as e:
            self.logger.error(f"爬取范围数据时发生未知错误: {e}")

        return stats

    def _parse_page_backup(self, soup: BeautifulSoup, date: str) -> List[HotItem]:
        """
        备用解析方法，用于处理不同的页面结构

        参数：
            soup: BeautifulSoup对象
            date: 日期字符串

        返回：
            热搜条目列表
        """
        hot_items = []

        try:
            # 备用方法：查找所有包含热搜数据的容器
            # 有些页面可能有不同的结构
            containers = soup.find_all("div", class_="rounded-lg")

            for container in containers:
                try:
                    # 尝试不同的选择器组合
                    h2_tag = container.find("h2", class_="text-xl")
                    if not h2_tag:
                        continue

                    rank, title = self._parse_rank(h2_tag)

                    # 查找数据
                    data_div = container.find("div", class_="flex")
                    if not data_div:
                        continue

                    data_tags = data_div.find_all("div", class_="inline-flex")

                    # 初始化数据字段
                    category = ""
                    heat = 0.0
                    reads = 0.0
                    discussions = 0.0
                    originals = 0.0

                    for data_tag in data_tags:
                        text = data_tag.get_text(strip=True)

                        if (
                            "明星" in text
                            or "社会" in text
                            or "娱乐" in text
                            or "体育" in text
                        ):
                            category = text
                        elif "🔥" in text:
                            heat = self._extract_number(text.replace("🔥", ""))
                        elif "阅读" in text:
                            reads = self._extract_number(text.replace("阅读", ""))
                        elif "讨论" in text:
                            discussions = self._extract_number(text.replace("讨论", ""))
                        elif "原创" in text:
                            originals = self._extract_number(text.replace("原创", ""))
                        elif "游戏" in text:
                            category = "游戏"
                        elif "美食" in text:
                            category = "美食"
                        elif "财经" in text:
                            category = "财经"

                    if rank > 0 and title:
                        hot_item = HotItem(
                            rank=rank,
                            title=title,
                            category=category,
                            heat=heat,
                            reads=reads,
                            discussions=discussions,
                            originals=originals,
                            date=date,
                        )
                        hot_items.append(hot_item)

                except Exception as e:
                    self.logger.debug(f"备用解析方法处理单个条目失败: {e}")
                    continue

            self.logger.info(f"备用方法解析到 {len(hot_items)} 个热搜条目")

        except Exception as e:
            self.logger.error(f"备用解析方法失败: {e}")

        return hot_items

    def test_parse(self, date: str = "2024-12-13") -> None:
        """
        测试解析功能

        参数：
            date: 测试日期
        """
        print(f"测试解析功能 - 日期: {date}")
        print("=" * 60)

        # 获取页面HTML
        html = self.fetch_page(date)
        if not html:
            print(f"无法获取 {date} 的页面")
            return

        # 解析页面
        hot_items = self.parse_page(html, date)

        # 显示前5个结果
        print(f"共解析到 {len(hot_items)} 个热搜条目")
        print("\n前5个热搜条目:")
        print("-" * 60)

        for i, item in enumerate(hot_items[:5]):
            print(f"{i + 1}. 排名: {item.rank}")
            print(f"   标题: {item.title}")
            print(f"   分类: {item.category}")
            print(f"   热度: {item.heat}万")
            print(f"   阅读: {item.reads}万")
            print(f"   讨论: {item.discussions}万")
            print(f"   原创: {item.originals}万")
            print()

        # 显示统计信息
        if hot_items:
            ranks = [item.rank for item in hot_items]
            print(f"排名范围: {min(ranks)} - {max(ranks)}")
            print(
                f"平均热度: {sum(item.heat for item in hot_items) / len(hot_items):.2f}万"
            )
            print(f"总阅读量: {sum(item.reads for item in hot_items):.2f}万")
            print(f"总讨论量: {sum(item.discussions for item in hot_items):.2f}万")

        print("=" * 60)


def main():
    """
    主函数，用于测试和演示爬虫功能

    功能：
        1. 创建爬虫实例
        2. 爬取指定日期范围的微博热搜数据
        3. 将数据保存到data目录
    """
    print("微博热搜历史数据爬虫")
    print("=" * 60)
    print("使用方法:")
    print("  1. python src/scrap.py                # 运行完整爬取")
    print("  2. python src/scrap.py test          # 测试解析功能")
    print("  3. python src/scrap.py single <date> # 爬取单日数据")
    print("=" * 60)

    import sys

    try:
        # 创建爬虫实例
        scraper = WeiboHotScraper(
            output_dir="data",
            delay=2.0,  # 适当延迟，避免被封IP
            max_retries=3,
        )

        # 检查命令行参数
        if len(sys.argv) > 1:
            if sys.argv[1] == "test":
                # 测试模式
                print("运行测试模式...")
                test_date = sys.argv[2] if len(sys.argv) > 2 else "2024-12-13"
                scraper.test_parse(test_date)
                return
            elif sys.argv[1] == "single" and len(sys.argv) > 2:
                # 单日爬取模式
                date = sys.argv[2]
                print(f"爬取单日数据: {date}")
                success = scraper.scrape_date(date)
                if success:
                    print(f"成功爬取 {date} 的数据")
                else:
                    print(f"爬取 {date} 的数据失败")
                return
            elif sys.argv[1] == "help":
                print("帮助信息:")
                print("  test [date]    - 测试解析功能，可选日期参数")
                print("  single <date>  - 爬取单日数据")
                print("  help          - 显示此帮助信息")
                return

        # 默认模式：完整爬取
        # 设置日期范围（根据用户要求）
        start_date = "2025-01-01"
        end_date = "2025-12-12"

        print(f"开始爬取 {start_date} 到 {end_date} 的数据...")
        print("数据将保存到 data/ 目录下，按月份组织")
        print("注意：这需要较长时间，请耐心等待...")
        print("=" * 60)

        # 开始爬取
        stats = scraper.scrape_range(start_date, end_date)

        # 输出结果
        print("\n爬取完成！")
        print(f"总天数: {stats['total_dates']}")
        print(f"成功: {stats['successful']}")
        print(f"失败: {stats['failed']}")

        if stats["failed_dates"]:
            print(f"失败的日期: {', '.join(stats['failed_dates'][:5])}")
            if len(stats["failed_dates"]) > 5:
                print(f"... 以及 {len(stats['failed_dates']) - 5} 个更多")

        print(f"\n数据已保存到 {scraper.output_dir}/ 目录")

    except KeyboardInterrupt:
        print("\n用户中断，爬虫已停止")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback

        traceback.print_exc()


class RealtimeHotScraper:
    """
    微博实时热搜爬虫

    功能：
        - 爬取微博实时热搜 Top 50
        - 解析排名、标题、热度
        - 支持缓存和错误处理

    数据结构：
        {
            "rank": 3,
            "title": "揭开日本伪装受害者的真面目"
        }
    """

    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = 3,
        delay: float = 1.0,
    ):
        """
        初始化实时热搜爬虫

        参数：
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            delay: 请求间隔时间（秒）
        """
        # 默认使用榜单页（更稳定、无需登录）
        self.base_url = "https://s.weibo.com/top/summary?cate=realtimehot"
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay = delay

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

        # 配置requests会话
        self.session = requests.Session()
        # 更完整的 User-Agent 列表（模拟真实浏览器）
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        import random
        chosen_ua = random.choice(user_agents)
        
        self.session.headers.update(
            {
                "User-Agent": chosen_ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://weibo.com/",
            }
        )
        
        # 添加cookie来模拟已访问用户（可选，但有助于绕过某些限制）
        self.session.cookies.update({
            "login_guide": "0",
        })

    def fetch_realtime_page(self) -> Optional[str]:
        """
        获取微博实时热搜页面 HTML

        尝试多个策略：
        1. 新的热搜专用页面（https://weibo.com/hot/search）
        2. 直接访问微博首页（https://weibo.com/）
        3. 搜索页面URL

        返回：
            HTML 字符串或 None（如果请求失败）
        """
        # 尝试的 URL 列表（按优先级）
        urls_to_try = [
            # 策略1：新的榜单页（实时热搜）：更稳定
            "https://s.weibo.com/top/summary?cate=realtimehot",
            # 策略2：热搜页面
            "https://weibo.com/hot/search",
            # 策略3：微博首页
            "https://weibo.com/",
            # 策略4：搜索首页
            "https://weibo.com/search/index",
        ]

        for url_idx, url in enumerate(urls_to_try, 1):
            for attempt in range(self.max_retries):
                try:
                    self.logger.info(f"[策略 {url_idx}] 正在获取实时热搜页面 (尝试 {attempt + 1}/{self.max_retries})")
                    self.logger.debug(f"目标 URL: {url}")
                    
                    # allow_redirects=True 确保跟随重定向链
                    response = self.session.get(
                        url, 
                        timeout=self.timeout, 
                        allow_redirects=True,
                        verify=True
                    )
                    response.raise_for_status()

                    if response.status_code == 200 and len(response.text) > 5000:
                        self.logger.info(f"[策略 {url_idx}] 成功获取页面 (最终 URL: {response.url}, 大小: {len(response.text)} bytes)")
                        
                        # 检查页面中是否包含热搜相关内容
                        html_text = response.text.lower()
                        if (
                            "realtimehot" in response.url.lower()
                            or "summary" in response.url.lower()
                            or "热搜" in html_text
                            or "实时" in html_text
                            or "weibo" in html_text
                        ):
                            self.logger.info(f"[策略 {url_idx}] 页面包含热搜相关内容，返回")
                            return response.text
                        else:
                            self.logger.warning(f"[策略 {url_idx}] 页面内容不包含热搜数据，尝试下一个策略")
                    else:
                        self.logger.warning(f"[策略 {url_idx}] 页面响应不完整: {response.status_code}, 大小: {len(response.text)} bytes")

                except requests.exceptions.RequestException as e:
                    self.logger.error(f"[策略 {url_idx}] 获取页面失败: {e}")
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt
                        self.logger.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    
                except Exception as e:
                    self.logger.error(f"[策略 {url_idx}] 获取页面时发生未知错误: {e}")
                    break
        
        self.logger.error("所有策略都失败了，无法获取页面")
        return None

    def parse_realtime_page(self, html: str) -> List[Dict[str, Any]]:
        """
        解析实时热搜页面（https://weibo.com/hot/search）

        支持多种热搜项结构，优先级：
        1. ALink_none_1w6rm 链接（主要热搜）
        2. 正则匹配的搜索链接（次要热搜）
        3. 其他可能的容器

        参数：
            html: 页面 HTML 字符串

        返回：
            热搜条目列表，每项包含 rank、title
        """
        hot_items = []

        try:
            soup = BeautifulSoup(html, "html.parser")

            # 调试：检查 HTML 结构
            self.logger.debug(f"HTML 长度: {len(html)}")
            
            # 方案1：解析榜单表格（s.weibo.com/top/summary 页面结构）
            table_container = soup.find(id=re.compile(r"pl_top_realtimehot")) or soup
            rows = []
            # 两种常见结构：tbody > tr 或者直接多个 tr
            tbody = table_container.find("tbody")
            if tbody:
                rows = tbody.find_all("tr")
            else:
                rows = table_container.find_all("tr")

            self.logger.info(f"方案1: 表格行数量 {len(rows)}")

            rank_counter = 0
            for tr in rows:
                try:
                    title_td = tr.find("td", class_=re.compile(r"td-02"))

                    if not title_td:
                        continue

                    # 跳过表头或置顶（无有效排名）
                    tr_class = (tr.get("class") or [])
                    if any(cls for cls in tr_class if re.search(r"thead|top|ad|banner", cls)):
                        continue

                    a = title_td.find("a")
                    if not a:
                        continue

                    title = a.get_text(strip=True).replace("#", "").strip()
                    if not title:
                        continue

                    rank_counter += 1

                    hot_items.append({"rank": rank_counter, "title": title})
                except Exception as e:
                    self.logger.debug(f"解析表格行失败: {e}")
                    continue

            # 方案2：如果上面不足，兜底解析其它可能结构（如备用链接）
            if len(hot_items) < 20:
                self.logger.info("主表格不足，尝试兜底解析候选链接…")
                import re as _re
                extra_links = soup.find_all("a", href=_re.compile(r"s\.weibo\.com/weibo"))
                seen = {i["title"] for i in hot_items}
                for lk in extra_links:
                    try:
                        t = lk.get_text(strip=True).replace("#", "").strip()
                        if not t or t in seen:
                            continue
                        if len(t) < 2 or len(t) > 100:
                            continue
                        hot_items.append({"rank": len(hot_items) + 1, "title": t})
                        seen.add(t)
                        if len(hot_items) >= 50:
                            break
                    except Exception:
                        continue

            # 按排名排序（确保顺序与页面一致）
            if hot_items:
                hot_items.sort(key=lambda x: (isinstance(x["rank"], int), x["rank"]))

            # 去重和清理（移除重复或低质量的项），并重新连续编号
            cleaned_items = []
            seen_titles = set()
            for item in hot_items:
                title = item["title"]

                digit_count = sum(1 for c in title if c.isdigit())
                if digit_count > len(title) / 3:
                    continue

                if title in seen_titles:
                    continue

                cleaned_items.append(item)
                seen_titles.add(title)

            # 重新按照出现顺序连续赋 rank，避免跳号
            for idx, item in enumerate(cleaned_items, start=1):
                item["rank"] = idx

            hot_items = cleaned_items

            self.logger.info(f"成功解析 {len(hot_items)} 个热搜条目")

        except Exception as e:
            self.logger.error(f"解析页面失败: {e}")

        return hot_items

        return hot_items

    def _extract_heat(self, container) -> str:
        """
        从容器中提取热度信息

        参数：
            container: BeautifulSoup 的 div 容器对象

        返回：
            热度字符串（如 "沸"、"爆"、数字等）
        """
        # 尝试从不同位置查找热度标签
        # 根据实际页面结构调整
        heat_spans = container.find_all("span", class_=lambda x: x and "Heat" in x if x else False)

        if heat_spans:
            return heat_spans[0].get_text(strip=True)

        # 如果没有找到，尝试查找包含热度的其他元素
        # 这里可能需要进一步调整
        return "N/A"

    def fetch_realtime_top50(self) -> List[Dict[str, Any]]:
        """
        获取实时热搜 Top 50（使用 Playwright 浏览器自动化）

        返回：
            热搜条目列表（最多 50 项）
        """
        # 优先使用 Playwright 方法（更可靠）
        return self.fetch_realtime_top50_with_playwright()

    def fetch_realtime_top50_with_playwright(self) -> List[Dict[str, Any]]:
        """
        使用 Playwright 获取实时热搜 Top 50（备选方案）

        相比于直接 HTTP 请求，这个方法：
        1. 使用真实浏览器引擎（Chromium）
        2. 执行 JavaScript 代码，加载动态内容
        3. 绕过访客验证系统
        4. 通过多次滚动加载更多热搜项
        5. 更接近真实用户行为

        返回：
            热搜条目列表（最多 50 项）

        依赖：
            playwright>=1.40.0（需要先运行：python -m playwright install chromium）
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.logger.error(
                "Playwright 未安装。请运行: pip install playwright && python -m playwright install chromium"
            )
            return []

        html_content = None

        try:
            self.logger.info("正在使用 Playwright 加载页面...")
            
            with sync_playwright() as p:
                # 启动 Chromium 浏览器
                browser = p.chromium.launch(headless=True)
                self.logger.info("浏览器启动成功")

                page = browser.new_page()
                
                # 设置浏览器标识，进一步模拟真实用户
                page.set_extra_http_headers({
                    "Accept-Language": "zh-CN,zh;q=0.9",
                })

                try:
                    # 访问新的榜单页（无需登录，更稳定）
                    self.logger.info(f"正在访问 {self.base_url} ...")
                    try:
                        page.goto(
                            self.base_url,
                            wait_until="domcontentloaded",
                            timeout=60000
                        )
                        self.logger.info("页面加载完成")
                    except Exception as e:
                        self.logger.warning(f"页面加载超时，继续使用已加载内容: {e}")

                    # 等待初始内容加载
                    page.wait_for_timeout(1500)

                    # 榜单页通常无需滚动即可获得 Top50
                    # 为稳妥，轻微滚动两次触发可能的懒加载
                    for _ in range(2):
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        page.wait_for_timeout(400)

                    # 获取最终的页面 HTML
                    html_content = page.content()
                    self.logger.info(f"页面内容获取成功，大小：{len(html_content)} bytes")

                    # 保存调试 HTML（可选）
                    try:
                        with open("debug_realtime_page_playwright.html", "w", encoding="utf-8") as f:
                            f.write(html_content)
                        self.logger.debug("HTML 已保存到 debug_realtime_page_playwright.html")
                    except Exception as e:
                        self.logger.debug(f"保存调试 HTML 失败: {e}")

                finally:
                    browser.close()
                    self.logger.info("浏览器已关闭")

        except ImportError:
            self.logger.error("Playwright 库未安装，无法使用此方法")
            return []
        except Exception as e:
            self.logger.error(f"Playwright 获取页面失败: {e}")
            return []

        if not html_content:
            self.logger.error("未获取到页面内容")
            return []

        # 解析获取到的 HTML
        items = self.parse_realtime_page(html_content)
        return items[:50]


if __name__ == "__main__":
    main()

