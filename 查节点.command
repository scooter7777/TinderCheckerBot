#!/bin/bash
cd "$(dirname "$0")"
echo "SOCKS5 节点位置批量查询（IP2Location）"
echo "-----------------------------------"
python3 ip2location_proxy_checker.py "$@"
echo ""
read -p "按回车键退出..." _
