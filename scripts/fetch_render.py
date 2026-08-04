#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新闻采集与渲染脚本（带自动翻译功能）
功能：从 Google News 抓取新闻 → 翻译标题为中文 → 按四个板块分类 → 生成 index.html
依赖库：gnews, jinja2, python-dateutil, pytz, googletrans==4.0.0-rc1
"""

import json
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
import pytz
from gnews import GNews
from jinja2 import Environment, FileSystemLoader
from googletrans import Translator

# ==================== 配置项 ====================

SH_TZ = pytz.timezone("Asia/Shanghai")
MAX_NEWS_PER_SECTION = 10
OUTPUT_HTML = "index.html"
DATA_PATH = "data/latest_news.json"

# 翻译器实例（全局复用）
translator = Translator()

# ==================== 板块搜索关键词 ====================

SECTIONS = {
    "国际科技新闻": {
        "query": (
            "(英伟达 OR NVIDIA OR 谷歌 OR Google OR SpaceX OR OpenAI OR Anthropic "
            "OR 特斯拉 OR Tesla OR Meta OR 博通 OR Broadcom OR 微软 OR Microsoft "
            "OR 亚马逊 OR Amazon OR 甲骨文 OR Oracle OR 英特尔 OR Intel OR AMD "
            "OR Palantir OR Robinhood OR 海力士 OR SK海力士 OR 三星 OR Samsung "
            "OR 美光科技 OR Micron OR 闪迪 OR SanDisk OR Lumentum OR Nebius "
            "OR CoreWeave OR Hims & Hers Health) "
            "(AI OR 人工智能 OR 芯片 OR 半导体 OR 云计算 OR 云服务 OR 航天 OR 火箭 "
            "OR 卫星发射 OR 自动驾驶 OR 具身智能 OR 人形机器人 OR 加密货币 OR 区块链 "
            "OR 数据中心 OR 液冷 OR 散热 OR 电力设施 OR 网络基础设施 OR 卫星通信 "
            "OR 卫星互联网 OR 空间数据 OR 金融科技 OR 广告科技)"
        ),
        "language": "zh",
        "country": None
    },
    "国内科技新闻": {
        "query": (
            "(字节跳动 OR 腾讯 OR 阿里巴巴 OR 字树科技) "
            "(AI OR 人工智能 OR 芯片 OR 半导体 OR 云计算 OR 云服务 OR 航天 OR 火箭 "
            "OR 卫星发射 OR 自动驾驶 OR 具身智能 OR 人形机器人 OR 加密货币 OR 区块链 "
            "OR 数据中心 OR 液冷 OR 散热 OR 电力设施 OR 网络基础设施 OR 卫星通信 "
            "OR 卫星互联网 OR 空间数据 OR 金融科技 OR 广告科技)"
        ),
        "language": "zh",
        "country": "CN"
    },
    "国内新消费新闻": {
        "query": (
            "(泡泡玛特 OR 贵州茅台 OR 茅台 OR 美的集团 OR 美的 OR 安踏集团 OR 安踏 "
            "OR 新消费 OR 国潮 OR 本土零售 OR 国货消费 OR 电商零售) "
            "-AI -人工智能 -芯片 -半导体 -云计算 -航天 -火箭 -自动驾驶 -具身智能 "
            "-加密货币 -区块链 -数据中心"
        ),
        "language": "zh",
        "country": "CN"
    },
    "国际新消费新闻": {
        "query": (
            "(国际新消费 OR 全球消费品牌 OR 跨境消费 OR 海外零售 OR 国际零售 "
            "OR 全球消费趋势 OR 海外新品 OR 跨境电商 OR 星巴克 OR 耐克 OR 欧莱雅 "
            "OR 可口可乐 OR 麦当劳) "
            "-AI -人工智能 -芯片 -半导体 -云计算 -航天 -火箭 -自动驾驶 -具身智能 "
            "-加密货币 -区块链 -数据中心"
        ),
        "language": "zh",
        "country": None
    }
}

# ==================== 工具函数 ====================

def clean_text(text: str) -> str:
    """清洗HTML标签和多余空白"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 120:
        text = text[:117] + "..."
    return text

def is_similar(title1: str, title2: str, threshold: float = 0.8) -> bool:
    """判断两个标题是否相似（用于去重）"""
    return SequenceMatcher(None, title1, title2).ratio() > threshold

def translate_title(text: str) -> str:
    """
    使用 googletrans 将英文标题翻译成中文
    如果翻译失败则返回原文本
    """
    if not text:
        return ""
    try:
        # 限制长度避免超时
        if len(text) > 500:
            text = text[:500]
        result = translator.translate(text, dest='zh-cn')
        return result.text
    except Exception as e:
        print(f"翻译失败: {e}，保留原文")
        return text

def fetch_section_news(section_name: str, config: dict) -> list:
    """采集单个板块的新闻，并翻译标题"""
    try:
        gn = GNews(
            language=config["language"],
            country=config["country"],
            period="1d",
            max_results=MAX_NEWS_PER_SECTION * 2
        )
        raw_news = gn.get_news(config["query"])
    except Exception as e:
        print(f"采集 {section_name} 失败: {str(e)}")
        return []

    processed = []
    for item in raw_news:
        # 提取原始标题（英文）
        raw_title = clean_text(item.get("title", ""))
        if not raw_title:
            continue
        
        # 翻译标题
        translated_title = translate_title(raw_title)
        
        news_item = {
            "title": translated_title,          # 翻译后的中文标题
            "title_en": raw_title,              # 英文原标题
            "summary": clean_text(item.get("description", "")),
            "url": item.get("url", ""),
            "source": item.get("publisher", {}).get("title", "未知来源"),
            "publish_time": ""
        }

        if not news_item["url"]:
            continue

        # 处理发布时间
        pub_date = item.get("published date")
        if pub_date:
            try:
                dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                dt = pytz.utc.localize(dt).astimezone(SH_TZ)
                news_item["publish_time"] = dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass

        # 去重（基于英文标题，避免翻译造成的差异）
        duplicate = False
        for existing in processed:
            if is_similar(raw_title, existing.get("title_en", "")):
                duplicate = True
                break
        if not duplicate:
            processed.append(news_item)

    return processed[:MAX_NEWS_PER_SECTION]

def render_html(news_data: dict):
    """用 Jinja2 渲染 HTML 页面"""
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("index.html")
    html = template.render(
        update_time=news_data["update_time"],
        sections=news_data["sections"]
    )
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

# ==================== 主流程 ====================

if __name__ == "__main__":
    print("开始采集新闻...")
    all_news = {}
    for section, config in SECTIONS.items():
        print(f"正在采集: {section}")
        all_news[section] = fetch_section_news(section, config)
        print(f"{section} 采集完成，共 {len(all_news[section])} 条有效新闻")

    output = {
        "update_time": datetime.now(SH_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "sections": all_news
    }

    os.makedirs("data", exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    render_html(output)
    print(f"新闻更新完成，页面已生成: {OUTPUT_HTML}")