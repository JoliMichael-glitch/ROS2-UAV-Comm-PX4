# ROS2-UAV-Comm-PX4

> 基于 ROS 2、DDS、NVIDIA Jetson 与 PX4 的分布式无人机通信实验平台

[中文版](README_zh.md) | [English Version](README.md)

本项目基于 NVIDIA Jetson、PX4 飞控、ROS 2 和 WiFi 网络，研究真实硬件环境下多节点 ROS 2/DDS 通信的性能，并验证 ROS 2 与实体 PX4 飞控之间的双向通信。

主要实验包括：

- C2R / R2C / R2R 多节点通信
- LOS / NLOS 通信性能测试
- 不同 Payload 下的通信性能测试
- Reliable / BestEffort QoS 对比
- 多节点通信竞争
- 应用层 Relay / Multi-hop 实验
- PX4–MAVROS–ROS 2 双向通信验证
- 延迟、丢包率、抖动及吞吐量分析

> **项目定位：** 本仓库主要用于保存和复现真实硬件实验环境、实验程序和数据分析脚本，并非面向生产环境的通用无人机通信框架。

---

## 🏗️ System Architecture

```text
                         ┌─────────────────────┐
                         │    Ground Station   │
                         │ Ubuntu 22.04        │
                         │ ROS 2 Humble        │
                         │ x86 / VMware        │
                         └──────────┬──────────┘
                                    │
                              ROS 2 / DDS
                                    │
                         ┌──────────▼──────────┐
                         │     WiFi Router     │
                         │      2.4 GHz        │
                         └───────┬───────┬──────┘
                                 │       │
                              WiFi     WiFi
                                 │       │
                    ┌────────────▼─┐   ┌─▼────────────┐
                    │ UAV Edge Node│   │  Other Node  │
                    │ Jetson       │   │ Jetson / UAV │
                    │ ROS 2 Foxy   │   │ ROS 2        │
                    └───────┬──────┘   └──────────────┘
                            │
                       UART / MAVLink
                            │
                    ┌───────▼──────┐
                    │ PX4 Flight   │
                    │ Controller   │
                    └──────────────┘
```

### 主要硬件与软件环境

| Component | Configuration |
|---|---|
| UAV Edge Node | NVIDIA Jetson Orin NX |
| Flight Controller | Pixhawk 4 / CUAV V5+ |
| Ground Station | x86 PC / VMware |
| Wireless Network | 2.4 GHz WiFi Router |
| UAV ROS 2 | Ubuntu 20.04 + ROS 2 Foxy |
| Ground ROS 2 | Ubuntu 22.04 + ROS 2 Humble |
| DDS | Fast DDS |
| Flight Stack | PX4 v1.13+ |
| FCU Bridge | MAVROS |

---

## 🔄 Communication Architecture

ROS 2 节点之间通过 DDS 进行分布式通信：

```text
ROS 2 Node
    │
    ▼
Fast DDS
    │
    ▼
WiFi Network
    │
    ▼
Remote ROS 2 Node
```

PX4 与 ROS 2 之间通过 MAVROS 连接：

```text
PX4
 │
 │ MAVLink / UART
 ▼
MAVROS
 │
 │ ROS 2
 ▼
Fast DDS / WiFi
 │
 ▼
Ground Station
```

---

## 🧪 Experimental Scenarios

### 1. C2R / R2C / R2R Communication

项目主要测试三类通信：

| Model | Direction | Typical Application |
|---|---|---|
| C2R | Center → Robot | 控制指令、任务信息 |
| R2C | Robot → Center | 状态、传感器和环境数据 |
| R2R | Robot ↔ Robot | 节点协同与状态同步 |

---

### 2. LOS / NLOS

比较不同物理传播条件下的：

- Latency
- Packet Loss
- Communication Stability

---

### 3. Payload Stress Test

测试不同数据负载下的通信性能：

```text
256 B
16 KB
256 KB
1 MB
4 MB
```

重点分析：

- Latency
- Packet Loss
- Throughput
- Network Congestion

---

### 4. QoS Comparison

对比 ROS 2 DDS 中：

- `Reliable`
- `BestEffort`

两种 QoS 策略在不同负载条件下的性能差异。

---

### 5. Multi-node Contention

逐步增加通信节点数量，测试共享 WiFi 网络中的：

- 延迟变化
- 丢包变化
- 网络资源竞争

---

### 6. Relay / Multi-hop

在直接通信质量下降时，引入 ROS 2 Relay 节点：

```text
Robot A
   │
   ▼
Relay Node
   │
   ▼
Robot B
```

> Relay 主要通过 ROS 2 应用层实现，不等同于 WiFi Mesh 或网络层路由协议。

---

## 📊 Experimental Results

项目完成了真实硬件环境下的多组通信性能测试，包括：

| Experiment | Metrics |
|---|---|
| Basic Communication | Latency / Packet Loss / Jitter |
| LOS / NLOS | Latency / Packet Loss |
| Payload Stress | Latency / Throughput / Packet Loss |
| QoS Comparison | Reliable / BestEffort |
| Multi-node | Contention / Latency / Packet Loss |
| Relay | Direct vs. Relay Communication |
| PX4 Validation | Bidirectional Communication |

> 实验结果均来自特定硬件、WiFi 环境、Payload、QoS 和通信频率配置，不代表其他网络环境下的固定性能指标。

---

# ⚡ Quick Start

> ⚠️ 本部分仅提供快速配置和验证方法。进行实际多节点物理部署时，请参考 **[详细部署指南](docs/DEPLOYMENT.md)**，其中包含静态 IP、`ROS_DOMAIN_ID`、UART、`udev` 权限和硬件接线等配置。

## 🖥️ UAV Edge Node

UAV 机载计算机运行 Ubuntu 20.04 + ROS 2 Foxy：

```bash
sudo apt update

sudo apt install -y \
  ros-foxy-rmw-fastrtps-cpp \
  ros-foxy-mavros \
  ros-foxy-mavros-extras
```

## 🖥️ Ground Station

Ground Station 运行 Ubuntu 22.04 + ROS 2 Humble：

```bash
sudo apt update

sudo apt install -y \
  ros-humble-rmw-fastrtps-cpp \
  ros-humble-plotjuggler \
  ros-humble-rqt*
```

---

## 🔧 Workspace Build

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws

git clone https://github.com/JoliMichael-glitch/ROS2-UAV-Comm-PX4.git \
src/ROS2-UAV-Comm-PX4

rosdep install --from-paths src --ignore-src -r -y

colcon build --symlink-install

source install/setup.bash
```

> **Note:** 本仓库中的代码和实验程序来自本科毕业设计的实际实验环境。不同实验可能需要根据目标节点、硬件平台和实验条件调整相应参数。

---

## 🚁 PX4–MAVROS Validation

### 1. Launch MAVROS

在 UAV 机载计算机上：

```bash
ros2 launch mavros px4.launch \
  fcu_url:=/dev/ttyTHS0:921600 \
  namespace:=/uav1
```

> `/dev/ttyTHS0` 为原实验环境中的 UART 设备名称，实际设备可能根据 Jetson 平台和 UART 配置有所不同。

### 2. Check IMU Data

在 Ground Station 上：

```bash
ros2 topic echo /uav1/mavros/imu/data
```

如果能够持续收到 IMU 数据，则说明：

```text
PX4
 ↓
MAVLink
 ↓
MAVROS
 ↓
ROS 2
 ↓
DDS / WiFi
 ↓
Ground Station
```

通信链路已经建立。

### 3. Test PX4 Mode Command

在 Ground Station 上：

```bash
ros2 service call \
  /uav1/mavros/set_mode \
  mavros_msgs/srv/SetMode \
  "{custom_mode: 'AUTO.LOITER'}"
```

该命令用于验证 ROS 2 → MAVROS → PX4 的反向控制链路。

### Expected Results

成功验证后，应能够观察到：

- PX4 IMU 数据能够通过 ROS 2 Topic 获取
- Ground Station 能够访问 UAV 端 MAVROS
- ROS 2 能够向 PX4 发送模式切换指令
- PX4 能够正确响应模式切换
- PX4 ↔ MAVROS ↔ ROS 2 ↔ Ground Station 双向通信建立

> ⚠️ **Safety Note:** PX4 模式切换应仅在安全测试环境下进行。`AUTO.LOITER` 在此仅用于通信验证，并不代表完整的自主飞行流程。

---

## 📈 Data Analysis

仓库中包含实验数据分析和绘图脚本，可用于分析：

- End-to-End Latency
- Packet Loss
- Jitter
- Reliable / BestEffort QoS
- Payload Stress
- Throughput
- Multi-node Contention
- Relay Communication

例如：

```bash
python analysis_scripts/plot_latency.py
```

不同分析脚本可能需要指定相应的实验数据文件或参数，请在运行前查看脚本中的输入和输出配置。

原实验过程中生成的数据和图像主要根据脚本配置保存，例如：

```text
~/comms_testbed_data/
```

---

## 📂 Repository Structure

```text
ROS2-UAV-Comm-PX4/
├── src/                      # ROS 2 节点及通信实验程序
│   ├── center_node.cpp       # Center 端通信节点
│   ├── uav_node.cpp          # UAV 端通信节点
│   ├── R1.cpp                # Relay / Communication 实验节点
│   ├── R2.cpp                # Relay / Multi-hop 实验节点
│   ├── C.cpp                 # 通信测量/接收节点
│   └── ...                   # 其他实验源文件
│
├── analysis_scripts/         # Python 数据分析和绘图脚本
│   ├── plot_QoS.py
│   ├── cdf_plot.py
│   ├── plotgraph.py
│   └── ...
│
├── scripts/                  # 辅助监控和实验脚本
├── config/                   # 实验配置文件
├── assets/                   # 架构图、实验照片、结果图
│
├── docs/
│   └── DEPLOYMENT.md         # 详细物理部署指南
│
├── README.md
└── LICENSE
```

---

## ⚠️ Limitations

- 实验结果与实际 WiFi 环境、信道、距离、遮挡、Payload 和通信频率等因素有关。
- Relay 实验主要采用 ROS 2 应用层转发，不等同于 WiFi Mesh 或网络层多跳路由。
- 部分节点、Topic 和参数保留了原毕业设计中的实验配置，需要扩展到更大规模网络时进行调整。
- ROS 2 Foxy 与 Humble 的跨版本通信依赖 DDS、QoS、消息类型和网络配置的兼容性。
- 本项目的实验结果用于描述特定实验条件下的通信行为，不应直接作为其他网络环境下的固定性能指标。

---

## 🎓 Project Background

本仓库是本科毕业设计项目的开源归档，主要保存：

- ROS 2 分布式通信环境
- NVIDIA Jetson 机载计算平台配置
- PX4 / MAVROS 通信
- C2R / R2C / R2R 通信实验
- LOS / NLOS 实验
- Payload Stress Test
- QoS 对比实验
- Multi-node Communication 实验
- Relay / Multi-hop 实验
- 通信性能数据分析
- PX4–MAVROS–ROS 2 双向通信验证

项目的主要目的，是将毕业设计期间搭建的真实硬件实验环境和实验代码进行整理和开源，方便后续复现、学习和进一步扩展。

---

## 🔭 Future Work

后续可以进一步扩展：

- 更大规模的多无人机通信实验
- 动态节点发现与配置
- WiFi Mesh / 网络层 Multi-hop
- 更完整的 DDS QoS 参数测试
- 自动化实验与数据采集
- 与 VINS/VIO 等定位系统集成
- 与 Ego-Planner 等自主规划系统结合
- 真实飞行闭环条件下的通信性能测试

---

## 📜 License

This project is licensed under the **Apache License 2.0**.

See the [LICENSE](./LICENSE) file for details.
