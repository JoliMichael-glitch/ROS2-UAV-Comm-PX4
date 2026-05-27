#!/usr/bin/env bash
# 严格模式：命令出错、未定义变量、管道任一失败时立即退出。
set -euo pipefail

# ===== host and account mapping =====
# 所有远程 SSH 登录统一使用该私钥。
# 如需覆盖，可在执行前 export SSH_KEY=...。
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"

# R1 节点主机（发布端），运行 ROS 2 Foxy。
R1_USER="amov"
R1_HOST="172.20.10.2"
R1_SHELL="bash"
R1_ROS_SETUP="/opt/ros/foxy/setup.bash"
R1_WS="~/ros2_ws"

# R2 节点主机（中继端），运行 ROS 2 Humble。
R2_USER="ubuntu"
R2_HOST="172.20.10.4"
R2_SHELL="zsh"
R2_ROS_SETUP="/opt/ros/humble/setup.bash"
R2_WS="~/ros2_ws"

# C 节点主机（采集/订阅端），运行 ROS 2 Humble。
C_USER="ros2"
C_HOST="172.20.10.3"
C_SHELL="bash"
C_ROS_SETUP="/opt/ros/humble/setup.bash"
C_WS="~/ros2_ws"

# ===== experiment settings =====
# 话题链路：R1 发布到 hop1，R2 转发到 hop2，C 订阅 hop2。
TOPIC_HOP1="/hop1/rel"
TOPIC_HOP2="/hop2/rel"
# 传给 r1/r2/c 的 QoS 与业务流参数。
HISTORY="10"
PAYLOAD="0"
PERIOD_MS="50"
PACKETS="1200"
PORT="2077"
R1_IP_ADDR="172.20.10.2"

# C 端输出文件：单向时延 CSV 与各进程日志。
C_LOG_DIR="/home/ros2/dds_logs"
C_LOG_FILE="${C_LOG_DIR}/publisher_log.csv"
R1_PUBLISHER_CSV="/home/amov/uav_ws/publisher_log.csv"

# 在指定远端主机上停止可能残留的旧进程，
# 防止与本次实验冲突。
stop_remote() {
  local user="$1"
  local host="$2"
  local shell_name="$3"
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "${user}@${host}" \
    "${shell_name} -lc 'pkill -f \"ros2 run dds_study r1\" || true; pkill -f \"ros2 run dds_study r2\" || true; pkill -f \"ros2 run dds_study c\" || true; pkill -f \"ros2 run dds_study publisher\" || true; pkill -f \"ros2 run dds_study pub_sub\" || true; pkill -f \"ros2 run dds_study subscriber\" || true; pkill -f \"monitor_hud.py\" || true; pkill -f \"analyze_latency.py\" || true'"
}

  # 通用远程后台执行函数：
  # 先进入工作区并 source ROS 与 install 环境，再用 nohup 后台启动命令。
run_remote_bg() {
  local user="$1"
  local host="$2"
  local shell_name="$3"
  local ws="$4"
  local ros_setup="$5"
  local cmd="$6"
  local log_file="$7"

  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "${user}@${host}" \
    "${shell_name} -lc 'cd ${ws}; source ${ros_setup}; source install/setup.bash; nohup ${cmd} > ${log_file} 2>&1 < /dev/null & echo started:${cmd}'"
}

# 第 1 步：清理三台主机上的旧实验进程。
echo "[1/5] stop old processes"
stop_remote "$R1_USER" "$R1_HOST" "$R1_SHELL"
stop_remote "$R2_USER" "$R2_HOST" "$R2_SHELL"
stop_remote "$C_USER" "$C_HOST" "$C_SHELL"

# 第 2 步：确保 C 端日志目录存在。
echo "[2/5] prepare C log dir"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "${C_USER}@${C_HOST}" \
  "${C_SHELL} -lc 'mkdir -p ${C_LOG_DIR}'"

# 第 3 步：先启动 R2 中继，保证下游链路就绪。
echo "[3/5] start R2"
run_remote_bg "$R2_USER" "$R2_HOST" "$R2_SHELL" "$R2_WS" "$R2_ROS_SETUP" \
  "ros2 run dds_study pub_sub --ros-args -p relay_input_topic:=${TOPIC_HOP1} -p relay_output_topic:=${TOPIC_HOP2} -p history:=${HISTORY} -p payload_bytes:=${PAYLOAD}" \
  "/home/ubuntu/dds_logs/r2.log"

# 第 4 步：启动 C 端订阅节点与监测工具。
# - c 节点写入单向时延 CSV
# - HUD 提供实时可视化指标
# - analyzer 周期性输出统计结果
echo "[4/5] start C node + HUD + analyzer"
run_remote_bg "$C_USER" "$C_HOST" "$C_SHELL" "$C_WS" "$C_ROS_SETUP" \
  "ros2 run dds_study subscriber --ros-args -p subscriber_topic:=${TOPIC_HOP2} -p port:=${PORT} -p history:=${HISTORY} -p payload_bytes:=${PAYLOAD}" \
  "${C_LOG_DIR}/c_node.log"

run_remote_bg "$C_USER" "$C_HOST" "$C_SHELL" "$C_WS" "$C_ROS_SETUP" \
  "python3 src/monitor_hud.py --ros-args -p subscriber_topic:=${TOPIC_HOP2}" \
  "${C_LOG_DIR}/hud.log"

run_remote_bg "$C_USER" "$C_HOST" "$C_SHELL" "$C_WS" "$C_ROS_SETUP" \
  "python3 src/analyze_latency.py --input ${C_LOG_FILE} --watch --interval 10" \
  "${C_LOG_DIR}/analyze.log"

# 第 5 步：在下游就绪后启动 R1 源发布节点。
echo "[5/5] start R1"
run_remote_bg "$R1_USER" "$R1_HOST" "$R1_SHELL" "$R1_WS" "$R1_ROS_SETUP" \
  "ros2 run dds_study publisher --ros-args -p ip_addr:=${R1_IP_ADDR} -p publisher_topic:=${TOPIC_HOP1} -p port:=${PORT} -p file_name:=${R1_PUBLISHER_CSV} -p payload_bytes:=${PAYLOAD} -p history:=${HISTORY} -p packets_to_send:=${PACKETS} -p publisher_period_ms:=${PERIOD_MS}" \
  "/home/amov/dds_logs/r1.log"

# 最终摘要输出。
echo "done"
echo "C logs: ${C_USER}@${C_HOST}:${C_LOG_DIR}"
