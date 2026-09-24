# -*- coding: utf-8 -*-
"""
Cloudflare 优选 IPv4 收集脚本（GitHub Actions 版）
"""

import os
import re
import sys
import time
import ipaddress
import requests

# ============ 配置区 ============
URLS = [
    'https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/bestcfv4.txt',
    'https://raw.githubusercontent.com/rong2er/IP666/refs/heads/main/Ranking.txt',
    'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt',
    'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/JP.txt',
    'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/DE.txt',
    'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/NL.txt',
]

OUTPUT_PORT = 8443
OUTPUT_FILE = 'ip.txt'
REQUEST_TIMEOUT = 10

IP_API_BATCH_URL = "http://ip-api.com/batch"
IP_API_FIELDS = "status,countryCode,query"
IP_API_BATCH_SIZE = 100
IP_API_INTERVAL = 5

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

IPV4_RE = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')


# ============ 抓取 ============
def fetch(url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            bust = url
            if 'wetest.vip' in url or '090227' in url:
                sep = '&' if '?' in url else '?'
                bust = f"{url}{sep}t={int(time.time())}"

            resp = requests.get(bust, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                resp.encoding = resp.encoding or resp.apparent_encoding or 'utf-8'
                return resp.text
            print(f"[warn] {url} -> HTTP {resp.status_code} (attempt {attempt})")
        except requests.RequestException as e:
            print(f"[warn] {url} -> {e} (attempt {attempt})")
        time.sleep(1.5 * attempt)
    print(f"[error] 放弃 {url}")
    return ""


# ============ 提取 IPv4 ============
def extract_ipv4(text):
    result = set()
    if not text:
        return result
    for m in IPV4_RE.findall(text):
        try:
            ipaddress.IPv4Address(m)
            result.add(m)
        except ValueError:
            continue
    return result


# ============ 批量查国家码 ============
def batch_country_codes(ips):
    result = {}
    ip_list = list(ips)
    if not ip_list:
        return result

    total = (len(ip_list) + IP_API_BATCH_SIZE - 1) // IP_API_BATCH_SIZE
    print(f"[info] 共 {len(ip_list)} 个 IPv4，分 {total} 批查询")

    for i in range(0, len(ip_list), IP_API_BATCH_SIZE):
        batch = ip_list[i:i + IP_API_BATCH_SIZE]
        batch_num = i // IP_API_BATCH_SIZE + 1
        payload = [{"query": ip, "fields": IP_API_FIELDS} for ip in batch]

        try:
            resp = requests.post(IP_API_BATCH_URL, json=payload, timeout=20)
            if resp.status_code == 200:
                for item in resp.json():
                    ip = item.get("query", "")
                    cc = (item.get("countryCode") or "ZZ").upper() \
                        if item.get("status") == "success" else "ZZ"
                    result[ip] = cc
                print(f"  [batch {batch_num}/{total}] 完成 {len(batch)} 个")
            else:
                print(f"  [batch {batch_num}/{total}] HTTP {resp.status_code}，整批标记 ZZ")
                for ip in batch:
                    result[ip] = "ZZ"
        except (requests.RequestException, ValueError) as e:
            print(f"  [batch {batch_num}/{total}] 异常: {e}，整批标记 ZZ")
            for ip in batch:
                result[ip] = "ZZ"

        if batch_num < total:
            time.sleep(IP_API_INTERVAL)

    return result


# ============ 主流程 ============
def main():
    start = time.time()

    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    unique_v4 = set()
    for url in URLS:
        print(f"\n=== Fetch: {url}")
        content = fetch(url)
        if not content or len(content) < 50:
            print(f"[skip] 内容为空或过短：{url}")
            continue
        v4 = extract_ipv4(content)
        unique_v4 |= v4
        print(f"[ok] +{len(v4)} IPv4（累计 {len(unique_v4)}）")

    print(f"\n抓取完成：唯一 IPv4 = {len(unique_v4)}")

    print("\n=== 查询国家码 ...")
    cc_map = batch_country_codes(unique_v4)

    sorted_v4 = sorted(unique_v4, key=lambda x: tuple(int(p) for p in x.split('.')))
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for ip in sorted_v4:
            f.write(f"{ip}:{OUTPUT_PORT}#{cc_map.get(ip, 'ZZ')}\n")
    print(f"[write] {OUTPUT_FILE} -> {len(sorted_v4)} 条")

    size = os.path.getsize(OUTPUT_FILE) if os.path.exists(OUTPUT_FILE) else 0
    print(f"  size: {size} bytes")
    print(f"总耗时: {time.time() - start:.1f}s")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)