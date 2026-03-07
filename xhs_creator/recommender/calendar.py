"""时间因素模块 - 节假日、季节等日历事件"""

from datetime import datetime
from typing import Dict, List


# 内置日历事件
CALENDAR_EVENTS = [
    {"month": 1, "day_range": (1, 3), "name": "元旦", "boost_tags": ["新年", "跨年", "年度总结"]},
    {"month": 2, "day_range": (14, 14), "name": "情人节", "boost_tags": ["情人节", "礼物", "约会"]},
    {"month": 3, "day_range": (8, 8), "name": "妇女节", "boost_tags": ["女性", "独立", "自我提升"]},
    {"month": 5, "day_range": (1, 3), "name": "劳动节", "boost_tags": ["旅行", "假期", "出行"]},
    {"month": 6, "day_range": (18, 18), "name": "618", "boost_tags": ["购物", "好物推荐", "优惠"]},
    {"month": 9, "day_range": (1, 3), "name": "开学季", "boost_tags": ["开学", "学习", "文具"]},
    {"month": 11, "day_range": (11, 11), "name": "双十一", "boost_tags": ["购物", "好物", "囤货"]},
    {"month": 12, "day_range": (25, 25), "name": "圣诞", "boost_tags": ["圣诞", "礼物", "节日"]},
    # 季节
    {"season": "spring", "months": [3, 4, 5], "name": "春季", "boost_tags": ["春游", "换季", "踏青"]},
    {"season": "summer", "months": [6, 7, 8], "name": "夏季", "boost_tags": ["防晒", "夏日", "清凉"]},
    {"season": "autumn", "months": [9, 10, 11], "name": "秋季", "boost_tags": ["秋天", "秋冬", "穿搭"]},
    {"season": "winter", "months": [12, 1, 2], "name": "冬季", "boost_tags": ["冬天", "保暖", "年味"]},
]


def get_current_events():
    # type: () -> List[Dict]
    """返回当前日期命中的日历事件"""
    now = datetime.now()
    month = now.month
    day = now.day

    matched = []
    for event in CALENDAR_EVENTS:
        # 日期匹配
        if "day_range" in event:
            if event.get("month") == month:
                low, high = event["day_range"]
                if low <= day <= high:
                    matched.append(event)
        # 季节匹配
        elif "months" in event:
            if month in event["months"]:
                matched.append(event)

    return matched


def get_boost_tags():
    # type: () -> List[str]
    """返回当前所有 boost_tags 合集"""
    tags = []
    for event in get_current_events():
        tags.extend(event.get("boost_tags", []))
    # 去重保序
    seen = set()
    result = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result
