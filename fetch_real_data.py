# -*- coding: utf-8 -*-
"""
浙江政府采购网真实数据抓取脚本（正式版）
数据来源：https://zfcg.czt.zj.gov.cn （政采云平台 - 浙江省政府采购网）

功能：
  1. 按145个区县行政区划批量调用 /portal/searchHome API 获取采购公告
  2. 按标题关键词筛选通信/信息化类项目，自动分类行业
  3. 增量导入 SQLite（按 project_name+bid_date 去重，不覆盖已有数据）
  4. 支持命令行参数：--fetch-only（仅抓取不导入）、--full-rebuild（全量重建）

字段映射：
  project_name  <- title (公告标题提取项目名)
  industry      <- 从标题关键词自动分类（通信工程/政企信息化/云服务/网络安全/物联网/IDC数据中心/智慧城市/视频会议）
  region        <- districtName (地区名标准化为城市名)
  bid_date      <- publishDateString (发布日期)
  win_amount    <- 按采购方式估算（列表API不含实际金额）
  status        <- 公告类型（采购项目公告=进行中, 采购结果公告=中标）
  owner_user_id <- "real" (真实数据标记)
"""
import requests
import json
import re
import os
import sys
import sqlite3
import time
import random
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bid_telecom.db")
JSON_PATH = os.path.join(BASE_DIR, "logs", "real_projects.json")
LOG_PATH = os.path.join(BASE_DIR, "logs", "fetch.log")

API_URL = "https://zfcg.czt.zj.gov.cn/portal/searchHome"
DISTRICT_API = "https://zfcg.czt.zj.gov.cn/api/core/getSubDistrictByPid"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://zfcg.czt.zj.gov.cn",
    "Referer": "https://zfcg.czt.zj.gov.cn/ZcyAnnouncement/index.html",
}

SUBCODES = {"project": "110-306476", "result": "110-188043"}

# 通信/信息化关键词 -> 行业分类
INDUSTRY_KEYWORDS = {
    "通信工程": ["通信工程", "通信设施", "通信线路", "光纤", "光缆", "宽带", "基站",
                 "5G", "移动通信", "电信", "应急通信", "通信网络", "弱电", "综合布线",
                 "铁塔", "微波", "卫星通信", "集群通信", "光传输", "传输网", "接入网",
                 "通信电源", "机房动环"],
    "政企信息化": ["信息化", "信息系统", "信息工程", "数字化", "电子政务", "数字政府",
                  "政务云", "办公系统", "管理平台", "业务系统", "应用系统", "软件开发",
                  "软件采购", "系统集成", "数据治理", "大数据", "数据平台", "数据库",
                  "智能化", "IT", "运维", "运维服务", "维保", "数字档案", "电子证照",
                  "政务大厅", "一网通办", "最多跑一次", "数据交换", "数据共享",
                  "中间件", "OA", "ERP", "财务系统", "审批系统", "电子招投标"],
    "云服务": ["云平台", "云计算", "云服务", "云资源", "云主机", "云存储",
              "政务云", "公有云", "私有云", "混合云", "云迁移", "云托管",
              "容器云", "微服务", "DevOps", "云网融合"],
    "网络安全": ["网络安全", "信息安全", "安全设备", "防火墙", "态势感知",
                "等级保护", "密评", "安全审计", "安全建设", "护网",
                "入侵检测", "WAF", "数据安全", "密码", "保密", "零信任",
                "安全运营", "SOC", "SIEM", "漏扫", "渗透"],
    "物联网": ["物联网", "传感器", "RFID", "智能感知", "NB-IoT", "LoRa",
              "智慧传感", "物联感知", "边缘计算", "工业互联网"],
    "IDC数据中心": ["数据中心", "IDC", "机房", "服务器", "存储设备", "机柜",
                   "UPS", "微模块", "动环", "供配电", "精密空调", "冷通道",
                   "综合布线", "机房改造", "机架", "算力", "智算中心"],
    "智慧城市": ["智慧", "视频监控", "安防", "监控", "天网", "雪亮工程",
                "智能交通", "智慧停车", "电子警察", "卡口", "城市大脑",
                "智慧城管", "智慧社区", "智慧消防", "智慧水务", "智慧环保",
                "智慧燃气", "智慧供热", "智慧路灯", "数字孪生"],
    "视频会议": ["视频会议", "融合通信", "指挥调度", "会议系统", "录播",
                "远程会议", "协作平台", "无纸化会议", "大屏", "显示系统",
                "音视频", "扩声", "LED", "投影"],
    "智慧教育": ["智慧校园", "教育信息化", "在线教育", "智慧课堂", "远程教育",
                "数字校园", "智慧教育", "教育云", "微课", "慕课", "MOOC",
                "虚拟仿真", "教学平台", "学习平台", "教育资源"],
    "智慧医疗": ["智慧医疗", "远程医疗", "医院信息化", "电子病历", "健康大数据",
                "医疗云", "智慧医院", "互联网医院", "医疗物联网", "PACS",
                "HIS", "LIS", "智慧后勤", "智慧病房", "移动护理"],
    "数字乡村": ["数字乡村", "农村信息化", "智慧农业", "数字农业", "乡村振兴",
                "智慧农业", "农业大数据", "农产品溯源", "农村电商"],
    "融媒体": ["融媒体", "广电", "数字电视", "广播电视", "应急广播",
              "播控平台", "全媒体", "新闻发布", "宣传矩阵"],
    "人工智能": ["人工智能", "AI", "智能算法", "机器学习", "深度学习",
               "大模型", "智能问答", "智能检索", "知识图谱", "NLP",
               "计算机视觉", "语音识别", "智能推荐", "AIGC", "智能体",
               "智能分析", "智能识别"],
    "区块链": ["区块链", "电子证照", "电子印章", "电子合同", "可信存证"],
}
ALL_KEYWORDS = [kw for kws in INDUSTRY_KEYWORDS.values() for kw in kws]

# 区县名标准化映射
CITY_MAP = {
    "杭州": ["杭州", "西湖", "余杭", "萧山", "临平", "富阳", "临安", "建德", "桐庐", "淳安", "滨江", "上城", "拱墅", "钱塘"],
    "宁波": ["宁波", "鄞州", "海曙", "江北", "镇海", "北仑", "奉化", "余姚", "慈溪", "宁海", "象山"],
    "温州": ["温州", "鹿城", "龙湾", "瓯海", "洞头", "瑞安", "乐清", "永嘉", "平阳", "苍南", "文成", "泰顺", "龙港"],
    "嘉兴": ["嘉兴", "南湖", "秀洲", "嘉善", "海盐", "海宁", "平湖", "桐乡"],
    "湖州": ["湖州", "吴兴", "南浔", "德清", "长兴", "安吉"],
    "绍兴": ["绍兴", "越城", "柯桥", "上虞", "诸暨", "嵊州", "新昌"],
    "金华": ["金华", "婺城", "金东", "兰溪", "义乌", "东阳", "永康", "浦江", "武义", "磐安"],
    "衢州": ["衢州", "柯城", "衢江", "龙游", "江山", "常山", "开化"],
    "舟山": ["舟山", "定海", "普陀", "岱山", "嵊泗"],
    "台州": ["台州", "椒江", "黄岩", "路桥", "温岭", "临海", "玉环", "三门", "天台", "仙居"],
    "丽水": ["丽水", "莲都", "龙泉", "青田", "缙云", "遂昌", "松阳", "云和", "庆元", "景宁"],
}


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {msg}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def classify_industry(title):
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(kw in title for kw in keywords):
            return industry
    return None


def extract_project_name(title):
    name = title
    m = re.match(r'^[^关于]+关于(.+?)(?:的(?:公开招标|竞争性|采购|中标|成交|招标|结果|征集).*$)', title)
    if m:
        name = m.group(1)
    else:
        for suffix in ["中标(成交)结果公告", "公开招标公告", "竞争性谈判公告",
                        "采购招标公告", "采购公告", "招标公告", "结果公告",
                        "成交公告", "中标公告", "合同公告", "公告"]:
            if title.endswith(suffix):
                name = title[:-len(suffix)].strip()
                break
    return name.strip()[:200]


def normalize_region(district_name, dist_label=""):
    combined = f"{district_name} {dist_label}"
    for city, keywords in CITY_MAP.items():
        if any(kw in combined for kw in keywords):
            return city
    if "本级" in combined:
        for city in CITY_MAP:
            if city in combined:
                return city
        return "浙江省本级"
    return district_name[:4] if district_name else "未知"


def estimate_amount(title, method):
    """标题中提取金额，或按采购方式估算（仅当详情API不可用时回退用）"""
    m = re.search(r'(\d+(?:\.\d+)?)\s*万', title)
    if m:
        return float(m.group(1))
    ranges = {"公开招标": (100, 2000), "竞争性磋商": (50, 500),
              "竞争性谈判": (20, 300), "单一来源": (50, 1000),
              "询价": (5, 50), "邀请招标": (80, 800)}
    low, high = ranges.get(method, (10, 200))
    return round(random.uniform(low, high), 2)


# === 详情API：获取真实金额 ===
DETAIL_API = "https://zfcg.czt.zj.gov.cn/portal/detail"
DETAIL_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://zfcg.czt.zj.gov.cn",
    "Referer": "https://zfcg.czt.zj.gov.cn/site/detail",
}


def extract_amount_from_content(content_html, ann_type):
    """从详情页HTML正文中提取真实金额，返回万元"""
    if not content_html:
        return None

    # 1) 去掉 <style>...</style>
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', content_html, flags=re.DOTALL | re.IGNORECASE)
    # 2) 去掉CSS规则块（selector { ... }）—— 匹配 xxx{...} 或 xxx : xxx ;
    text = re.sub(r'[^{}<]*\{[^}]*\}', ' ', text)
    # 3) 去掉HTML标签
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # 需要排除的"假金额"上下文（代理费、工本费等）
    # 注意："收费"不单独使用 — 会误杀"收费标准"上下文中提到的"预算金额"
    FALSE_AMOUNT_KW = ['代理服务', '代理费', '招标代理',
                       '售价', '工本费', '标书', '保证金',
                       '评审费', '公证费', '印花税']

    def _is_false_amount(pos):
        """检查匹配位置前方文本是否表明这是假金额（非项目金额）"""
        before = text[max(0, pos - 25):pos]
        return any(kw in before for kw in FALSE_AMOUNT_KW)

    def try_patterns(patterns, is_yuan=True):
        """尝试一组正则，返回第一个有效金额（万元）
        is_yuan=True: 匹配值单位为元，需除以10000
        is_yuan=False: 匹配值单位为万元，直接返回
        """
        for p in patterns:
            for m in re.finditer(p, text):
                val = float(m.group(1).replace(',', ''))
                if val <= 0:
                    continue
                if _is_false_amount(m.start()):
                    continue
                return round(val / 10000, 2) if is_yuan else round(val, 2)
        return None

    # ── 优先级 1：精确金额关键词（元）— 中标结果/中标公示 ──
    patterns_p1 = [
        # "总价：544500（元）"、"最终报价：4396637.00（元）"
        r'(?:总价|最终报价|中标报价|成交报价)[：:]\s*(\d[\d,]*\.?\d*)\s*[（(]元[)）]',
        r'(?:总价|最终报价|中标报价|成交报价)[：:]\s*(\d[\d,]*\.?\d*)',
        # "中标价：279000"、"中标价：279000元"
        r'中标价[：:]\s*(\d[\d,]*\.?\d*)',
        r'中标价\s*[：:]?\s*(\d[\d,]*\.?\d*)\s*元',
        # "中标（成交）金额(元)：XXX"、"中标金额(元)：XXX"
        r'中标[（(]成交[)）]金额[（(]元[)）]?[：:\s]*(\d[\d,]*\.?\d*)',
        r'中标金额[（(]元[)）]?[：:\s]*(\d[\d,]*\.?\d*)',
        r'成交金额[（(]元[)）]?[：:\s]*(\d[\d,]*\.?\d*)',
        r'中标金额[：:\s]*(\d[\d,]*\.?\d*)',
        r'成交金额[：:\s]*(\d[\d,]*\.?\d*)',
        r'合同金额[（(]元[)）]?[：:\s]*(\d[\d,]*\.?\d*)',
        r'合同金额[：:\s]*(\d[\d,]*\.?\d*)',
        # "合计（元）：7869984" — 中标结果表格中的总金额
        r'合计[（(]?\s*元\s*[)）]?[：:]\s*(\d[\d,]*\.?\d*)',
        r'合计\s*[：:]\s*(\d[\d,]*\.?\d*)\s*[（(]?元[)）]?',
        r'总报价[：:]\s*(\d[\d,]*\.?\d*)',
        r'报价为?\s*(\d[\d,]*\.?\d*)\s*元',
    ]
    found = try_patterns(patterns_p1, is_yuan=True)
    if found is not None:
        return found

    # ── 优先级 1.5：不带关键词的 "XXXXXX元" / "XXXXXX（元）" — 数额直接跟"元" ──
    # 需 ≥1万元且排除 万元/售价/工本费/代理费 等假金额
    for m in re.finditer(r'(?<!万)(\d{5,}(?:\.\d+)?)\s*[（(]?\s*元', text):
        if _is_false_amount(m.start()):
            continue
        val = float(m.group(1).replace(',', ''))
        if val >= 10000:
            return round(val / 10000, 2)

    # ── 优先级 2a：金额关键词 + 元（值在元，需÷10000）— 招标公告 ──
    patterns_p2_yuan = [
        r'预算金额[（(]元[)）][：:\s]*(\d[\d,]*\.?\d*)',
        r'预算(?:金额|总价)?[（(]元[)）][：:\s]*(\d[\d,]*\.?\d*)',
        r'最高(?:投标)?限价[（(]元[)）][：:\s]*(\d[\d,]*\.?\d*)',
        r'控制价[（(]元[)）][：:\s]*(\d[\d,]*\.?\d*)',
        r'预算金额[（(]元[)）]\s*[：:]*\s*(\d[\d,]*\.?\d*)',
    ]
    found = try_patterns(patterns_p2_yuan, is_yuan=True)
    if found is not None:
        return found

    # ── 优先级 2b：金额关键词 + 万元/万（值已为万元）— 招标公告 ──
    patterns_p2_wan = [
        r'采购预算价为?\s*(\d[\d,]*\.?\d*)\s*万元?',
        r'采购预算\s*(\d[\d,]*\.?\d*)\s*万元?',
        r'预算(?:金额|总价)?[：:\s]*(\d[\d,]*\.?\d*)\s*万元?',
        r'最高(?:投标)?限价.{0,50}?(\d[\d,]*\.?\d*)\s*万元?',
        r'控制价.{0,50}?(\d[\d,]*\.?\d*)\s*万元?',
        r'采购预算\s*(\d[\d,]*\.?\d*)\s*万\b',
        r'\b预算\s*(\d{1,6}(?:\.\d+)?)\s*万\b',
    ]
    found = try_patterns(patterns_p2_wan, is_yuan=False)
    if found is not None:
        return found

    # ── 优先级 2.5：表格型 — 表头含关键词 + (元)/(万元)，值与表头分离 ──
    # 2.5a: 万元 列
    for kw in ['预算金额', '预算价', '最高限价', '最高投标限价', '控制价']:
        idx = text.find(kw)
        if idx == -1:
            continue
        ctx = text[idx:idx+280]
        if re.search(r'[（(]\s*万元?\s*[)）]', ctx):
            after = text[idx+len(kw):idx+300]
            for m in re.finditer(r'[\s年月日号项套批次个台][:：.、 ]+(\d{1,8}(?:\.\d+)?)', after):
                val = float(m.group(1))
                if 2017 <= val <= 2026 or val == 0:
                    continue
                if val >= 0.1:
                    return round(val, 2)
            for m in re.finditer(r'(?<!\d)(\d{1,6}(?:\.\d+)?)\s+(?=套|项|批|个|台|次|月|年)', after):
                val = float(m.group(1))
                if 2017 <= val <= 2026:
                    continue
                if val >= 0.1:
                    return round(val, 2)

    # 2.5b: 元 列（值通常 5位以上数字）
    for kw in ['预算金额', '预算价', '最高限价', '最高投标限价', '控制价']:
        idx = text.find(kw)
        if idx == -1:
            continue
        ctx = text[idx:idx+280]
        if re.search(r'[（(]\s*元\s*[)）](?!.*万元)', ctx):
            after = text[idx+len(kw):idx+350]
            for m in re.finditer(r'(?<!\d)(\d{5,})', after):
                val = float(m.group(1))
                if val >= 10000:
                    return round(val / 10000, 2)

    # ── 优先级 3：通用兜底（排除代理费等假金额） ──
    # 3a: "金额（元）：XXX" — 排除"代理服务收费金额"等
    for m in re.finditer(r'金额[（(]元[)）][：:\s]*(\d[\d,]*\.?\d*)', text):
        if _is_false_amount(m.start()):
            continue
        val = float(m.group(1).replace(',', ''))
        if val > 0:
            return round(val / 10000, 2)

    # 3b: "XXX万元"
    found = try_patterns([r'(\d[\d,]*\.?\d*)\s*万元'], is_yuan=False)
    if found is not None:
        return found

    # 3c: 通用兜底 "万" (不含元)
    for m in re.finditer(r'(?<!\d)(\d{2,6}(?:\.\d+)?)\s*万\b(?!元)', text):
        val = float(m.group(1))
        if 2017 <= val <= 2026:
            continue
        if _is_false_amount(m.start()):
            continue
        if val >= 1:
            return round(val, 2)

    return None


def fetch_detail_amount(article_id):
    """调用 /portal/detail API获取单条公告详情，提取真实金额（万元）"""
    try:
        resp = requests.get(DETAIL_API,
                           params={"articleId": article_id, "parentId": "600007"},
                           headers=DETAIL_HEADERS, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            inner = data.get("result", {}).get("data", {})
            ann_type = inner.get("announcementType")
            content = inner.get("content", "")
            project_code = inner.get("projectCode", "")
            project_name = inner.get("projectName", "")
            amount = extract_amount_from_content(content, ann_type)
            # 提取失败时保存原始内容供调试分析
            if amount is None and content:
                debug_path = os.path.join(BASE_DIR, "logs", "amount_missed")
                os.makedirs(debug_path, exist_ok=True)
                # 与 extract_amount_from_content 相同的CSS清理
                dtext = re.sub(r'<style[^>]*>.*?</style>', ' ', content, flags=re.DOTALL | re.IGNORECASE)
                dtext = re.sub(r'[^{}<]*\{[^}]*\}', ' ', dtext)
                dtext = re.sub(r'<[^>]+>', ' ', dtext)
                dtext = re.sub(r'&nbsp;', ' ', dtext)
                dtext = re.sub(r'&[a-zA-Z]+;', '', dtext)
                dtext = re.sub(r'\s+', ' ', dtext).strip()
                safe_name = article_id.replace('/', '_').replace('=', '_')
                with open(os.path.join(debug_path, f"{safe_name}.txt"), "w", encoding="utf-8") as df:
                    df.write(f"articleId: {article_id}\n")
                    df.write(f"announcementType: {ann_type}\n")
                    df.write(f"projectName: {project_name}\n\n")
                    df.write(dtext[:5000])
            return amount, project_code, project_name
    except Exception as e:
        log(f"  [WARN] detail fetch failed for {article_id}: {e}")
    return None, "", ""


def fetch_notices(sub_code, district_code):
    payload = {"code": "110-606633", "subCodes": [sub_code],
               "districtCode": district_code, "pageSize": 20, "isStick": True,
               "needTotal": False, "needNewCnt": False, "needValidCount": False}
    try:
        resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("result", {}).get("data", {}).get("children", []) or []
    except Exception as e:
        log(f"  [ERROR] fetch: {e}")
    return []


def get_all_districts():
    """获取浙江省所有区县代码"""
    resp = requests.get(f"{DISTRICT_API}?pId=953", headers=HEADERS, timeout=15)
    cities = resp.json().get("result", [])
    all_districts = {}
    for city in cities:
        all_districts[city["name"]] = city["code"]
        try:
            resp2 = requests.get(f"{DISTRICT_API}?pId={city['id']}", headers=HEADERS, timeout=10)
            for sub in resp2.json().get("result", []):
                all_districts[f"{city['name']}/{sub['name']}"] = sub["code"]
            time.sleep(0.2)
        except:
            pass
    return all_districts


def fetch_all():
    """抓取所有区县的通信类项目"""
    log("获取浙江省区县代码...")
    districts = get_all_districts()
    log(f"共 {len(districts)} 个区县")

    seen_ids = set()
    all_projects = []

    for i, (dist_name, dist_code) in enumerate(districts.items()):
        if i % 30 == 0:
            log(f"进度: {i}/{len(districts)} (已获取: {len(all_projects)}条)")
        for sub_type, sub_code in SUBCODES.items():
            for n in fetch_notices(sub_code, dist_code):
                aid = n.get("articleId", "")
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)
                title = n.get("title", "")
                if not any(kw in title for kw in ALL_KEYWORDS):
                    continue
                industry = classify_industry(title)
                if not industry:
                    continue

                # 调用详情API获取真实金额
                real_amount, proj_code, proj_name = fetch_detail_amount(aid)
                # 如果详情API没拿到金额，回退估算
                if real_amount is None:
                    real_amount = estimate_amount(title, n.get("purchaseMethod", "其他"))
                    amount_source = "估算"
                else:
                    amount_source = "政采网"

                # 优先用详情API的项目名
                final_name = proj_name if proj_name else extract_project_name(title)

                all_projects.append({
                    "project_name": final_name,
                    "industry": industry,
                    "region": normalize_region(n.get("districtName", ""), dist_name),
                    "bid_date": n.get("publishDateString", ""),
                    "win_amount": real_amount,
                    "status": "中标" if sub_type == "result" else "进行中",
                    "purchase_method": n.get("purchaseMethod", ""),
                    "purchaser": n.get("purchaseName", ""),
                    "project_code": proj_code,
                    "amount_source": amount_source,
                    "article_id": aid,
                    "title": title,
                    "source": "浙江政采网",
                })
            time.sleep(0.15)

    # 统计金额来源
    real_cnt = sum(1 for p in all_projects if p.get("amount_source") == "政采网")
    est_cnt = len(all_projects) - real_cnt
    log(f"抓取完成: 去重后 {len(seen_ids)} 条公告, 通信类 {len(all_projects)} 条")
    log(f"  真实金额: {real_cnt}条, 估算金额: {est_cnt}条")
    return all_projects


def import_to_db(projects, full_rebuild=False):
    """增量导入数据库"""
    conn = sqlite3.connect(DB_PATH)
    if full_rebuild:
        conn.execute("DELETE FROM bid_projects")
        log("全量重建: 已清空旧数据")

    existing = set()
    if not full_rebuild:
        for row in conn.execute("SELECT project_name, bid_date FROM bid_projects"):
            existing.add((row[0], row[1]))

    inserted = 0
    for p in projects:
        key = (p["project_name"], p["bid_date"])
        if key in existing:
            continue
        bid_date = p.get("bid_date") or "2026-01-01"
        if len(bid_date) < 10:
            bid_date = "2026-01-01"
        amount = float(p.get("win_amount", 0) or 0)
        if not p["project_name"]:
            continue
        conn.execute(
            "INSERT INTO bid_projects (project_name, industry, region, bid_date, win_amount, status, owner_user_id) VALUES (?,?,?,?,?,?,?)",
            (p["project_name"], p["industry"], p["region"], bid_date, amount, p["status"], "real"))
        inserted += 1

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM bid_projects").fetchone()[0]
    conn.close()
    log(f"导入完成: 新增 {inserted} 条, 数据库总计 {total} 条")
    return inserted


def main():
    full_rebuild = "--full-rebuild" in sys.argv
    fetch_only = "--fetch-only" in sys.argv

    log("=" * 50)
    log(f"浙江政采网数据抓取 (full_rebuild={full_rebuild}, fetch_only={fetch_only})")
    log("=" * 50)

    projects = fetch_all()

    # 保存 JSON 备份
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)
    log(f"已保存到 {JSON_PATH}")

    if not fetch_only:
        import_to_db(projects, full_rebuild)

    log("完成!")


if __name__ == "__main__":
    main()
