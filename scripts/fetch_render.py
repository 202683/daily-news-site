#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
多源 RSS 新闻聚合脚本
支持：36氪、钛媒体、虎嗅、红板报、Google News（补充国际新闻）
"""

import json
import os
import re
from datetime import datetime
import pytz
import feedparser
import requests
from jinja2 import Environment, FileSystemLoader

# ==================== 配置项 ====================

SH_TZ = pytz.timezone("Asia/Shanghai")
MAX_NEWS_PER_SECTION = 10
OUTPUT_HTML = "index.html"
DATA_PATH = "data/latest_news.json"

# ==================== RSS 源配置 ====================

RSS_SOURCES = {
    "国内科技新闻": [
        {
            "name": "36氪",
            "url": "https://36kr.com/feed",
            "max": 8
        },
        {
            "name": "钛媒体",
            "url": "https://www.tmtpost.com/feed",
            "max": 8
        },
        {
            "name": "虎嗅",
            "url": "https://rsshub.app/huxiu/index",
            "max": 6
        }
    ],
    "国际科技新闻": [
        {
            "name": "红板报·科技",
            "url": "https://rsshub.app/flipboard/topic/technology",
            "max": 10
        },
        {
            "name": "红板报·AI",
            "url": "https://rsshub.app/flipboard/topic/artificialintelligence",
            "max": 6
        }
    ],
    "国内新消费新闻": [
        {
            "name": "36氪·消费",
            "url": "https://rsshub.app/36kr/news/consumer",
            "max": 8
        },
        {
            "name": "钛媒体·消费",
            "url": "https://rsshub.app/tmtpost/tag/消费",
            "max": 8
        }
    ],
    "国际新消费新闻": [
        {
            "name": "红板报·消费",
            "url": "https://rsshub.app/flipboard/topic/consumer",
            "max": 10
        }
    ]
}

# ==================== RSS 抓取函数 ====================

def clean_text(text: str) -> str:
    """清洗HTML标签和多余空白"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 150:
        text = text[:147] + "..."
    return text

def fetch_rss_feed(url: str, max_items: int = 10) -> list:
    """抓取单个 RSS 源"""
    try:
        print(f"  抓取: {url}")
        feed = feedparser.parse(url)
        
        if feed.bozo:
            print(f"  ⚠️ RSS 解析警告: {feed.bozo_exception}")
            return []
        
        articles = []
        for entry in feed.entries[:max_items]:
            # 跳过没有标题的条目
            if not hasattr(entry, 'title') or not entry.title:
                continue
            
            # 提取摘要
            summary = ""
            if hasattr(entry, 'summary'):
                summary = clean_text(entry.summary)
            elif hasattr(entry, 'description'):
                summary = clean_text(entry.description)
            
            # 提取发布时间
            pub_date = ""
            if hasattr(entry, 'published'):
                pub_date = entry.published
            elif hasattr(entry, 'updated'):
                pub_date = entry.updated
            
            # 提取来源名称
            source_name = feed.feed.title if hasattr(feed.feed, 'title') else "未知来源"
            
            articles.append({
                "title": clean_text(entry.title),
                "title_en": "",  # RSS 源本身是中文
                "summary": summary,
                "url": entry.link,
                "source": source_name,
                "publish_time": pub_date
            })
        
        return articles
    except Exception as e:
        print(f"  ❌ RSS 抓取失败: {e}")
        return []

def fetch_section_news(section_name: str) -> list:
    """采集单个板块的新闻"""
    all_articles = []
    sources = RSS_SOURCES.get(section_name, [])
    
    for source in sources:
        articles = fetch_rss_feed(source["url"], source["max"])
        print(f"    → {source['name']} 获取 {len(articles)} 条")
        all_articles.extend(articles)
    
    # 去重（按标题去重）
    seen_titles = set()
    unique_articles = []
    for article in all_articles:
        title = article.get("title", "")
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_articles.append(article)
    
    return unique_articles[:MAX_NEWS_PER_SECTION]

def render_html(news_data: dict):
    """生成 HTML 页面"""
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
    print("=" * 60)
    print("🚀 多源 RSS 新闻聚合器")
    print(f"⏰ 运行时间: {datetime.now(SH_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_news = {}
    for section in RSS_SOURCES.keys():
        print(f"\n📌 正在采集: {section}")
        all_news[section] = fetch_section_news(section)
        print(f"  ✅ {section} 共 {len(all_news[section])} 条有效新闻")
    
    # 保存 JSON 数据
    output = {
        "update_time": datetime.now(SH_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "sections": all_news
    }
    
    os.makedirs("data", exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 生成 HTML
    render_html(output)
    print("\n" + "=" * 60)
    print(f"✅ 新闻更新完成，页面已生成: {OUTPUT_HTML}")
    print("=" * 60)