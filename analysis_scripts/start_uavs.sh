#!/bin/bash


# 1. 加载 Foxy 环境


source /opt/ros/foxy/setup.bash
source /home/amov/uav_ws/install/setup.bash

LAPTOP_IP="172.20.10.2"

echo "==== 正在启动 10 个 Foxy 模拟节点 (Publisher) ===="

for i in {1..10}
do
    # 动态分配独立端口，解决 Socket 绑定冲突


    NODE_PORT=$((2077 + i))
    echo "-> 启动 uav$i，反馈端口: $NODE_PORT"
    
    ros2 run dds_study publisher --ros-args \
        -r __ns:=/uav$i \
        -p ip_addr:=$LAPTOP_IP \
        -p publisher_topic:=rel \
        -p port:=$NODE_PORT \
        -p file_name:=/home/amov/uav_ws/publisher_log$i.csv \
        -p payload_bytes:=0 \
        -p history:=10 \
        -p packets_to_send:=1200 \
        -p publisher_period_ms:=50 &
done
wait
