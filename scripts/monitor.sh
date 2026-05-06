#!/bin/bash
# 性能监控脚本 - 每 5 秒采集一次指标

LOG_FILE="/home/admin/ai-wenan-backend/perf_monitor.log"

echo "=== 性能监控启动 ===" >> $LOG_FILE
echo "时间：$(date '+%Y-%m-%d %H:%M:%S')" >> $LOG_FILE

while true; do
    echo "" >> $LOG_FILE
    echo "=== $(date '+%H:%M:%S') ===" >> $LOG_FILE
    
    # CPU & 内存
    ps aux | grep "app_v2.py" | grep -v grep | awk '{print "CPU: "$3"% MEM: "$4"%"}' >> $LOG_FILE
    
    # 磁盘使用
    df -h /home | tail -1 | awk '{print "磁盘：" $5}' >> $LOG_FILE
    
    # 数据库大小
    ls -lh /home/admin/ai-wenan-backend/*.db 2>/dev/null | awk '{print "DB: "$5}' >> $LOG_FILE
    
    # 活跃连接数（如果有 nginx 日志）
    if [ -f /var/log/nginx/access.log ]; then
        tail -100 /var/log/nginx/access.log | wc -l | xargs echo "最近请求：" >> $LOG_FILE
    fi
    
    sleep 5
done
