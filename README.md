# 🚁 ROS2-UAV-Comm-PX4

> Hardware-in-the-loop ROS 2 communication benchmark framework for distributed UAV robotic systems.

ROS 2 Foxy/Humble-based distributed UAV communication framework using PX4 and NVIDIA Jetson platforms, featuring multi-drone coordination, QoS-aware networking, LOS/NLOS stress testing, and hardware-in-the-loop validation.

[![ROS 2](https://img.shields.io/badge/ROS%202-Foxy%20%7C%20Humble-22303c?logo=ros)](https://docs.ros.org/)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04%20LTS-e95420?logo=ubuntu)](https://releases.ubuntu.com/20.04/)
[![Platform](https://img.shields.io/badge/Edge-Jetson%20Orin%20%7C%20Nano-76b900?logo=nvidia)](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/)
[![PX4](https://img.shields.io/badge/PX4-Autopilot-3d4db8)](https://px4.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)

---

## ✨ Core Features

- **Hardware-in-the-loop validation** — Real Jetson Orin NX (UAV) and Jetson Nano (UGV) nodes communicating over 2.4 GHz WiFi infrastructure mode. No simulation.
- **Cross-Version ROS 2 Architecture** — Seamless DDS communication between legacy edge devices (Foxy/Ubuntu 20.04) and modern ground stations (Humble/Ubuntu 22.04).
- **PX4 Closed-Loop Integration** — Bidirectional MAVROS bridge supporting telemetry uplink and command downlink on physical flight controllers.
- **Physical Boundary Stress Testing** — Real-world LOS/NLOS baseline data, multi-node contention, and Reliable vs. BestEffort QoS limits.

---

## 🛰️ System Architecture

```text
       WiFi AP (2.4 GHz, Infrastructure Mode)
                 │
      ┌──────────┴──────────────┐
      │                         │
      ▼                         ▼
┌──────────────────┐  ┌──────────────────┐
│   UAV Node       │  │   UGV Node       │
│   ────────────── │  │   ────────────── │
│   Jetson Orin NX │  │   Jetson Nano    │
│   Ubuntu 20.04   │  │   Ubuntu 20.04   │
│   ROS 2 Foxy     │  │   ROS 2 Foxy     │
│        │         │  │        │         │
│   MAVROS ↔ UART  │  │   Sensor Bridge  │
│        │         │  │                  │
│   PX4 FCU        │  │   Wheel Odometry │
└──────────────────┘  └──────────────────┘
         ↕                      ↕
   ┌──────────────────────────────────┐
   │       Center Control Node        │
   │   ───────────────                │
   │   x86 PC / VMware                │
   │   Ubuntu 22.04                   │
   │   ROS 2 Humble                   │
   │   PlotJuggler / rqt / CLI tools  │
   └──────────────────────────────────┘
```

---

## 🔄 Data Flow (PX4 ↔ ROS 2)

**Uplink (Telemetry):**
```text
PX4 IMU → uORB → MAVLink → UART → MAVROS → /mavros/imu/data (DDS Topic) → Center Node
```
**Downlink (Command)**
```text
Center Node → /mavros/set_mode (DDS) → MAVROS → MAVLink → UART → PX4 State Machine
```

---

## 📡 Communication Links Under Test

| Link | Direction | Typical Payload | QoS Requirement |
|---|---|---|---|
| **C2R** | Center → Robot | 256 B – 1 KB | Low latency, zero-loss |
| **R2C** | Robot → Center | 1 – 4 MB | High throughput |
| **R2R** | Robot ↔ Robot | 16 – 256 KB | State synchronization |

---

## 🧪 Supported Test Scenarios

| # | Scenario | Stress Target | Representative Result |
|---|---|---|---|
| 1 | **End-to-end baseline** | DDS serialization + scheduling latency | 8.28 ms median latency at 50 Hz |
| 2 | **LOS vs NLOS** | Physical obstruction robustness | 35.2% packet loss under NLOS |
| 3 | **Dual-hop relay** | LOS restoration via relay topology | Packet loss reduced to 0.4% |
| 4 | **Payload stress** | Throughput saturation | Severe degradation at 4 MB payload |
| 5 | **QoS comparison** | Reliable vs BestEffort | Latency/packet-loss tradeoff observed |
| 6 | **Multi-node concurrency** | WiFi contention scaling | Critical degradation above 10 nodes |
| 7 | **PX4 closed-loop** | MAVROS ↔ PX4 bidirectional path | `AUTO.LOITER` mode verified |

---

## ⚡ Quick Start (TL;DR)

> ⚠️ **CRITICAL:** This section only provides a high-level overview of dependencies and core commands. For actual physical multi-node deployment—including router static IP setup, cross-version `ROS_DOMAIN_ID` discovery, FCU UART `udev` permissions, and hardware wiring—you **must** follow the comprehensive physical setup guide: **[Detailed Deployment Guide](docs/DEPLOYMENT.md)**.

### 🖥️ Hardware Platform

| Component | Platform | Environment |
|---|---|---|
| UAV Edge Node | NVIDIA Jetson Orin NX | Ubuntu 20.04 + ROS 2 Foxy |
| Flight Controller | Pixhawk 4 / CUAV V5+ | PX4 v1.13+ |
| Ground Control Station | VMware-based x86 Virtual Machine | Ubuntu 22.04 + ROS 2 Humble |
| Network Infrastructure | 2.4 GHz WiFi Router | Same subnet / Infrastructure mode |

---

## 🛠️ Software Dependencies

### UAV Edge Node (ROS 2 Foxy)

```bash
# Update package index
sudo apt update

# Fast DDS middleware
sudo apt install -y \
  ros-foxy-rmw-fastrtps-cpp

# MAVROS bridge for PX4 communication
sudo apt install -y \
  ros-foxy-mavros \
  ros-foxy-mavros-extras
```

### Ground Control Station (ROS 2 Humble)

```bash
# Update package index
sudo apt update

# ROS 2 analysis and visualization tools
sudo apt install -y \
  ros-humble-rmw-fastrtps-cpp \
  ros-humble-plotjuggler \
  ros-humble-rqt*
```

---

## 🔧 Workspace Build

```bash
# Create ROS 2 workspace
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws

# Clone repository
git clone https://github.com/your-org/multi-agent-comms-testbed.git \
src/comms_testbed

# Install dependencies
rosdep install --from-paths src --ignore-src -r -y

# Build workspace
colcon build --symlink-install

# Source environment
source install/setup.bash
```

---

## 🚁 PX4 Closed-loop Validation

### UAV Side — Launch MAVROS Bridge

```bash
ros2 launch mavros px4.launch \
  fcu_url:=/dev/ttyTHS0:921600 \
  namespace:=/uav1
```

### Ground Station — Verify Telemetry Stream

```bash
ros2 topic echo /uav1/mavros/imu/data
```

### Ground Station — Trigger PX4 Mode Switch

```bash
ros2 service call \
  /uav1/mavros/set_mode \
  mavros_msgs/srv/SetMode \
  "{custom_mode: 'AUTO.LOITER'}"
```

### Expected Validation Results

- IMU telemetry stream visible on ROS 2 topics
- PX4 flight mode successfully switches to `AUTO.LOITER`
- MAVROS ↔ PX4 bidirectional communication verified
- DDS communication path validated end-to-end

---

## 📊 Experimental Analysis

The framework provides automated analysis utilities for:

- End-to-end latency measurement
- Packet loss evaluation
- Jitter characterization
- QoS policy comparison
- Throughput benchmarking
- Multi-node contention analysis

### Generate Result Plots

```bash
python analysis_scripts/plot_latency.py
```

Generated figures are stored under:

```text
~/comms_testbed_data/
```

---

## 📂 Repository Layout

```text
.
├── comms_testbed/           # Core ROS 2 communication package
│   ├── src/                 # Communication and benchmark nodes
│   └── launch/              # Experiment launch configurations
│
├── scenarios/               # Scenario-specific parameter sets
│
├── analysis_scripts/        # Python-based analysis and plotting tools
│
├── config/                  # DDS QoS profiles and network configurations
│
├── assets/                  # Architecture diagrams, photos, result figures
│
└── README.md
```

---

## 📜 License

This project is licensed under the Apache License 2.0.

See the [LICENSE](./LICENSE) file for additional details.
