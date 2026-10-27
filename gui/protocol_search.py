#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协议名称的本地搜索索引，只用于界面过滤，不增加依赖或修改协议名称。"""

import re
from types import MappingProxyType
import unicodedata

from protocol.definitions import (
    PROTOCOL_BATTERY_SINGLE_WIRE, PROTOCOL_CHANGZHOU_XINSIWEI, PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_FZ_SIF, PROTOCOL_HANGZHOU_ANXIAN, PROTOCOL_JINGXIAN, PROTOCOL_LISHEN_BMS,
    PROTOCOL_LITHIUM_BMS, PROTOCOL_LUYUAN_BMS, PROTOCOL_RUILUN, PROTOCOL_SHENZHOUXING,
    PROTOCOL_SXSY, PROTOCOL_TAILING_Y34B, PROTOCOL_TAILING_Y34F, PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINCHI, PROTOCOL_XINRI, PROTOCOL_YADEA, PROTOCOL_YOUYIBAO,
)

# 集中维护全拼和首字母；型号和英文保持原样，新协议在此补一条，不改编码注册表。
PROTOCOL_SEARCH_ALIASES = MappingProxyType({
    PROTOCOL_RUILUN: ("ruilunxieyi", "rlxy"),
    PROTOCOL_FZ_SIF: ("fzsifxieyi", "fzsifxy"),
    PROTOCOL_XINRI: ("xinrixieyi", "xrxy"),
    PROTOCOL_HANGZHOU_ANXIAN: ("hangzhouanxianxieyi", "hzaxxy"),
    PROTOCOL_SXSY: ("sxsyyixiantongxieyi", "sxsyyxtxy"),
    PROTOCOL_CHANGZHOU_XINSIWEI: ("changzhouxinsiweixieyi", "czxswxy"),
    PROTOCOL_WUXI_YIGE: ("wuxiyigey67xieyi", "wxygy67xy"),
    PROTOCOL_TAILING_Y34B: ("wuxitailingy34bxieyi", "wxtly34bxy"),
    PROTOCOL_TAILING_Y34F: ("wuxitailingy34fxieyi", "wxtly34fxy"),
    PROTOCOL_SHENZHOUXING: ("shenzhouxingxieyi", "szxxy"),
    PROTOCOL_YADEA: ("yadixieyi", "ydxy"),
    PROTOCOL_YOUYIBAO: ("youyibaoyixiantongxieyi", "yybyxtxy"),
    PROTOCOL_JINGXIAN: ("jingxianyixiantongxieyi", "jxyxtxy"),
    PROTOCOL_DONGWEI_GTXH: ("dongweigtxhxieyi", "dwgtxhxy"),
    PROTOCOL_XINCHI: ("xinchibmsxieyi", "xcbmsxy"),
    PROTOCOL_LUYUAN_BMS: ("lvyuanbmsyixiantongxieyi", "luyuanbmsyixiantongxieyi", "lybmsyxtxy"),
    PROTOCOL_LITHIUM_BMS: ("yixiantonglidianchibms", "yxtldcbms"),
    PROTOCOL_BATTERY_SINGLE_WIRE: ("dianchidanxiantongxunxieyi", "dcdxtxxy"),
    PROTOCOL_LISHEN_BMS: ("lishendanxianbms", "lsdxbms"),
})


def normalize_search_text(text):
    """忽略大小写、全半角及常见拼音分隔符，保留中文、型号和未知字符。"""
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("ü", "v")
    return re.sub(r"[\s_'’\-]+", "", normalized)


def protocol_search_keys(name):
    """原名称总可搜索；未登记别名的新项目也保留原有中文或型号匹配能力。"""
    return tuple(normalize_search_text(value) for value in (name, *PROTOCOL_SEARCH_ALIASES.get(name, ())))
