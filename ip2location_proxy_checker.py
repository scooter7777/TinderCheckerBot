#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOCKS5 节点位置批量查询工具（IP2Location 无密钥接口）。"""

import argparse
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_API = "https://api.ip2location.io/"
DEFAULT_TIMEOUT = 25
DEFAULT_THREADS = 10

COUNTRY_ZH = {
    "United States of America": "美国",
    "Spain": "西班牙",
    "Lithuania": "立陶宛",
    "United Kingdom": "英国",
    "Germany": "德国",
    "France": "法国",
    "Netherlands": "荷兰",
    "Singapore": "新加坡",
    "Japan": "日本",
    "Korea, Republic of": "韩国",
    "South Korea": "韩国",
    "Taiwan": "台湾",
    "Hong Kong": "香港",
    "China": "中国",
    "India": "印度",
    "Brazil": "巴西",
    "Canada": "加拿大",
    "Australia": "澳大利亚",
    "Russia": "俄罗斯",
    "Ukraine": "乌克兰",
    "Poland": "波兰",
    "Italy": "意大利",
    "Sweden": "瑞典",
    "Norway": "挪威",
    "Finland": "芬兰",
    "Denmark": "丹麦",
    "Switzerland": "瑞士",
    "Austria": "奥地利",
    "Belgium": "比利时",
    "Portugal": "葡萄牙",
    "Greece": "希腊",
    "Turkey": "土耳其",
    "Malaysia": "马来西亚",
    "Indonesia": "印度尼西亚",
    "Thailand": "泰国",
    "Vietnam": "越南",
    "Philippines": "菲律宾",
    "Mexico": "墨西哥",
    "Argentina": "阿根廷",
    "Chile": "智利",
    "Colombia": "哥伦比亚",
    "South Africa": "南非",
    "Egypt": "埃及",
    "United Arab Emirates": "阿联酋",
    "Saudi Arabia": "沙特阿拉伯",
    "Israel": "以色列",
    "New Zealand": "新西兰",
    "Ireland": "爱尔兰",
    "Croatia": "克罗地亚",
    "Romania": "罗马尼亚",
    "Slovakia": "斯洛伐克",
    "Netherlands": "荷兰",
    "Netherlands (Kingdom of the)": "荷兰",
    "United States": "美国",
}

REGION_ZH = {
    "Alabama": "阿拉巴马",
    "Alaska": "阿拉斯加",
    "Arizona": "亚利桑那",
    "Arkansas": "阿肯色",
    "California": "加利福尼亚",
    "Colorado": "科罗拉多",
    "Connecticut": "康涅狄格",
    "Delaware": "特拉华",
    "Florida": "佛罗里达",
    "Georgia": "佐治亚",
    "Hawaii": "夏威夷",
    "Idaho": "爱达荷",
    "Illinois": "伊利诺伊",
    "Indiana": "印第安纳",
    "Iowa": "艾奥瓦",
    "Kansas": "堪萨斯",
    "Kentucky": "肯塔基",
    "Louisiana": "路易斯安那",
    "Maine": "缅因",
    "Maryland": "马里兰",
    "Massachusetts": "马萨诸塞",
    "Michigan": "密歇根",
    "Minnesota": "明尼苏达",
    "Mississippi": "密西西比",
    "Missouri": "密苏里",
    "Montana": "蒙大拿",
    "Nebraska": "内布拉斯加",
    "Nevada": "内华达",
    "New Hampshire": "新罕布什尔",
    "New Jersey": "新泽西",
    "New Mexico": "新墨西哥",
    "New York": "纽约",
    "North Carolina": "北卡罗来纳",
    "North Dakota": "北达科他",
    "Ohio": "俄亥俄",
    "Oklahoma": "俄克拉何马",
    "Oregon": "俄勒冈",
    "Pennsylvania": "宾夕法尼亚",
    "Rhode Island": "罗德岛",
    "South Carolina": "南卡罗来纳",
    "South Dakota": "南达科他",
    "Tennessee": "田纳西",
    "Texas": "德克萨斯",
    "Utah": "犹他",
    "Vermont": "佛蒙特",
    "Virginia": "弗吉尼亚",
    "Washington": "华盛顿",
    "West Virginia": "西弗吉尼亚",
    "Wisconsin": "威斯康星",
    "Wyoming": "怀俄明",
    "District of Columbia": "哥伦比亚特区",
    "Andalucia": "安达卢西亚",
    "Vilniaus apskritis": "维尔纽斯县",
    "Grad Zagreb": "萨格勒布县",
    "Oslo": "奥斯陆",
    "Stockholms lan": "斯德哥尔摩省",
    "Noord-Holland": "北荷兰省",
    "Arges": "阿尔杰什县",
    "Bucuresti": "布加勒斯特",
    "Bratislavsky kraj": "布拉迪斯拉发州",
    "Madrid, Comunidad de": "马德里自治区",
    "Hovedstaden": "首都大区",
    "Dublin": "都柏林",
    "Sheridan": "谢里丹",
    "Ile-de-France": "法兰西岛",
}

CITY_ZH = {
    "Los Angeles": "洛杉矶",
    "San Jose": "圣何塞",
    "Santa Clara": "圣克拉拉",
    "Santa Cruz": "圣克鲁斯",
    "Washington": "华盛顿",
    "Boca Raton": "博卡拉顿",
    "Melbourne": "墨尔本",
    "Miami": "迈阿密",
    "Piscataway": "皮斯卡塔韦",
    "Buffalo": "布法罗",
    "New York City": "纽约市",
    "Charlotte": "夏洛特",
    "Easton": "伊斯顿",
    "Philadelphia": "费城",
    "Dallas": "达拉斯",
    "Houston": "休斯顿",
    "Orem": "奥勒姆",
    "Ashburn": "阿什本",
    "Manassas": "马纳萨斯",
    "Casper": "卡斯珀",
    "Phoenix": "菲尼克斯",
    "Marbella": "马贝拉",
    "Vilnius": "维尔纽斯",
    "Zagreb": "萨格勒布",
    "Oslo": "奥斯陆",
    "Stockholm": "斯德哥尔摩",
    "Bucharest": "布加勒斯特",
    "Bratislava": "布拉迪斯拉发",
    "Madrid": "马德里",
    "Copenhagen": "哥本哈根",
    "Dublin": "都柏林",
    "Cadiz": "加的斯",
    "Sheridan": "谢里丹",
    "Curtea de Arges": "阿尔杰什库尔泰亚",
    "London": "伦敦",
    "Tokyo": "东京",
    "Osaka": "大阪",
    "Singapore": "新加坡",
    "Paris": "巴黎",
    "Frankfurt": "法兰克福",
    "Amsterdam": "阿姆斯特丹",
    "Toronto": "多伦多",
    "Vancouver": "温哥华",
    "Sydney": "悉尼",
}

_LOCK = threading.Lock()
_DONE = 0
_OK = 0
_TOTAL = 0


@dataclass
class Node:
    ip: str
    port: str
    user: str = ""
    password: str = ""
    original: str = ""

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    @property
    def proxy_url(self) -> str:
        if self.user:
            user = quote(self.user, safe="")
            password = quote(self.password, safe="")
            return f"socks5h://{user}:{password}@{self.ip}:{self.port}"
        return f"socks5h://{self.ip}:{self.port}"

    @property
    def full(self) -> str:
        return self.original or self.address


@dataclass
class Result:
    node: str
    exit_ip: str
    country_code: str
    country: str
    region: str
    city: str
    asn: str
    isp: str
    status: str
    note: str


def parse_nodes(path: str) -> list[Node]:
    nodes: list[Node] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) < 2 or not parts[1].isdigit():
                continue
            user = parts[2] if len(parts) >= 4 else ""
            password = parts[3] if len(parts) >= 4 else ""
            nodes.append(Node(parts[0], parts[1], user, password, line))
    return nodes


def query_node(node: Node, timeout: float) -> Result:
    proxies = {"http": node.proxy_url, "https": node.proxy_url}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(
            DEFAULT_API,
            proxies=proxies,
            timeout=timeout,
            headers=headers,
        )
        if response.status_code != 200:
            return Result(node.full, "", "", "", "", "", "", "", "失败", f"HTTP {response.status_code}")

        data = response.json()
        exit_ip = str(data.get("ip") or "")
        if not exit_ip:
            return Result(node.full, "", "", "", "", "", "", "", "失败", str(data.get("message", "返回结果缺少 IP")))

        return Result(
            node.full,
            exit_ip,
            str(data.get("country_code") or ""),
            str(data.get("country_name") or ""),
            str(data.get("region_name") or ""),
            str(data.get("city_name") or ""),
            str(data.get("asn") or ""),
            str(data.get("as") or ""),
            "成功",
            "",
        )
    except Exception as exc:
        return Result(node.full, "", "", "", "", "", "", "", "失败", f"{type(exc).__name__}: {exc}")


def tick(success: bool) -> None:
    global _DONE, _OK
    with _LOCK:
        _DONE += 1
        if success:
            _OK += 1
        print(f"[{_DONE}/{_TOTAL}] 成功 {_OK} 失败 {_DONE - _OK}", flush=True)


def sanitize(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", str(name)).strip()
    return cleaned or "未知"


def ascii_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_")
    return cleaned or "Unknown"


def zh(name: str, table: dict) -> str:
    return table.get(name, name)


def write_outputs(results: list[Result], out_dir: Path) -> None:
    ok = [r for r in results if r.status == "成功"]
    failed = [r for r in results if r.status != "成功"]

    txt_path = out_dir / "节点地区.txt"
    with open(txt_path, "w", encoding="utf-8-sig") as fh:
        for r in ok:
            country_zh = zh(r.country, COUNTRY_ZH) or "未知国家"
            region_zh = zh(r.region, REGION_ZH)
            city_zh = zh(r.city, CITY_ZH)
            location_label = "-".join(part for part in (country_zh, region_zh, city_zh) if part) or "未知地区"
            fh.write(f"{r.node} ---- {location_label}\n")

    failed_path = out_dir / "失败节点.txt"
    with open(failed_path, "w", encoding="utf-8-sig") as fh:
        if failed:
            for r in failed:
                fh.write(f"{r.node}\t{r.note}\n")
        else:
            fh.write("无失败节点\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="SOCKS5 节点位置批量查询（IP2Location）")
    parser.add_argument("input", nargs="?", help="节点文件，每行 ip:port 或 ip:port:user:pass")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS, help=f"并发线程数，默认 {DEFAULT_THREADS}")
    parser.add_argument("--output", help="输出目录，默认桌面")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"单个节点超时秒数，默认 {DEFAULT_TIMEOUT}")
    parser.add_argument("--no-open", action="store_true", help="完成后不自动打开输出目录")
    parser.add_argument("--name", help="输出文件夹标识（建议英文），例如 Europe 或 USA")
    args = parser.parse_args()

    input_path = args.input
    if not input_path:
        input_path = input("请把节点文件拖进来或输入完整路径: ").strip().strip('"').strip("'")
    if not input_path:
        print("未提供节点文件")
        sys.exit(1)

    nodes = parse_nodes(input_path)
    if not nodes:
        print("没有解析到有效节点")
        sys.exit(1)

    global _TOTAL
    _TOTAL = len(nodes)
    threads = max(1, args.threads)

    base = Path(args.output) if args.output else Path.home() / "Desktop"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name_part = ascii_filename(args.name) if args.name else ""
    folder_name = f"IP2Location_Results_{name_part}_{timestamp}" if name_part else f"IP2Location_Results_{timestamp}"
    out_dir = base / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"节点数量: {len(nodes)}，线程数: {threads}")
    print(f"输出目录: {out_dir}")

    results: list[Result] = []
    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = {pool.submit(query_node, node, args.timeout): node for node in nodes}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            tick(result.status == "成功")

    results.sort(key=lambda r: (r.status != "成功", r.country, r.region, r.city, r.node))
    write_outputs(results, out_dir)

    ok_count = sum(1 for r in results if r.status == "成功")
    fail_count = len(results) - ok_count
    print(f"\n完成: 成功 {ok_count}，失败 {fail_count}")
    print(f"结果已导出: {out_dir}")

    if sys.platform == "darwin" and not args.no_open:
        subprocess.Popen(["open", str(out_dir)])


if __name__ == "__main__":
    main()
