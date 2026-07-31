# 🚁 ROS2-UAV-Comm-PX4

> Real-hardware ROS 2 communication benchmark framework for distributed UAV robotic systems.

ROS 2 Foxy/Humble-based distributed UAV communication testbed using PX4 and NVIDIA Jetson platforms. The project focuses on real-world communication performance evaluation, including multi-node coordination, QoS-aware networking, LOS/NLOS stress testing, payload-based load testing, relay communication, and PX4-MAVROS closed-loop validation.

[![ROS 2](https://img.shields.io/badge/ROS%202-Foxy%20%7C%20Humble-22303c?logo=ros)](https://docs.ros.org/)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04%20LTS-e95420?logo=ubuntu)](https://releases.ubuntu.com/20.04/)
[![Platform](https://img.shields.io/badge/Edge-Jetson%20Orin%20%7C%20Nano-76b900?logo=nvidia)](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/)
[![PX4](https://img.shields.io/badge/PX4-Autopilot-3d4db8)](https://px4.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)

---

## ✨ Core Features

- **Real-Hardware Communication Validation** — Real Jetson Orin NX (UAV) and Jetson Nano (UGV) nodes communicating over a 2.4 GHz WiFi infrastructure network.
- **Cross-Version ROS 2 Architecture** — DDS-based communication between ROS 2 Foxy/Ubuntu 20.04 edge nodes and a ROS 2 Humble/Ubuntu 22.04 ground station.
- **PX4 Closed-Loop Integration** — Bidirectional MAVROS-based communication between physical PX4 flight controllers and the ROS 2 network, including telemetry monitoring and flight-mode commands.
- **Communication Stress Testing** — Real-world LOS/NLOS evaluation, multi-node contention, payload stress testing, relay communication, and Reliable vs. BestEffort QoS comparison.

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
### Node Roles

- **UAV Node:** Provides onboard ROS 2 computing and interfaces with the PX4 flight controller through MAVROS.
- **UGV Node:** Provides an additional mobile edge node for heterogeneous multi-agent communication experiments.
- **Center Node:** Acts as the ground-side ROS 2 node for monitoring, command transmission, data collection, and communication performance analysis.
- **WiFi AP:** Provides the shared wireless infrastructure network connecting distributed nodes.
  
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

| Link | Direction | Typical Payload | Typical Application |
|---|---|---|---|
| **C2R** | Center → Robot | 256 B – 1 KB | Command / control messages |
| **R2C** | Robot → Center | 1 – 4 MB | Sensor / perception data |
| **R2R** | Robot ↔ Robot | 16 – 256 KB | State / coordination data |

> Payload sizes are representative experimental categories used in this project and should not be interpreted as strict requirements for all UAV communication systems.

---

## 🧪 Supported Test Scenarios

| # | Scenario                   | Main Metric             | Representative Result                                                                                    |
| - | -------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------- |
| 1 | **End-to-end baseline**    | Communication latency   | 8.28 ms median latency at 50 Hz                                                                          |
| 2 | **LOS vs NLOS**            | Packet loss             | 35.2% packet loss under the tested NLOS condition                                                        |
| 3 | **Dual-hop relay**         | Packet loss             | Packet loss reduced to 0.4% in the tested relay configuration                                            |
| 4 | **Payload stress**         | Latency / throughput    | Significant performance degradation observed at 4 MB payload                                             |
| 5 | **QoS comparison**         | Latency / packet loss   | Measurable trade-off between Reliable and BestEffort                                                     |
| 6 | **Multi-node concurrency** | Latency / packet loss   | Significant degradation observed beyond approximately 10 concurrent nodes under the tested configuration |
| 7 | **PX4 closed-loop**        | End-to-end connectivity | `AUTO.LOITER` mode successfully commanded through MAVROS                                                 |

---

## ⚡ Quick Start (TL;DR)

> ⚠️ **IMPORTANT:** This section provides a high-level overview of the hardware platform, software dependencies, and core validation commands. For actual physical multi-node deployment—including router static IP configuration, cross-version `ROS_DOMAIN_ID` discovery, FCU UART `udev` permissions, hardware wiring, and node-specific configuration—you **must** follow the comprehensive physical setup guide: **[Detailed Deployment Guide](docs/DEPLOYMENT.md)**.
>
> The commands below are intended to provide a quick overview of the experimental environment. Some parameters, device names, IP addresses, and topic namespaces may need to be adjusted according to the actual hardware configuration.

### 🖥️ Hardware Platform

| Component | Platform | Environment |
|---|---|---|
| UAV Edge Node | NVIDIA Jetson Orin NX | Ubuntu 20.04 + ROS 2 Foxy |
| Flight Controller | Pixhawk 4 / CUAV V5+ | PX4 v1.13+ |
| Ground Control Station | VMware-based x86 Virtual Machine | Ubuntu 22.04 + ROS 2 Humble |
| Network Infrastructure | 2.4 GHz WiFi Router | Same subnet / Infrastructure mode |

---

## 🛠️ Software Dependencies

### UAV Edge Node — ROS 2 Foxy

The UAV edge node runs ROS 2 Foxy on Ubuntu 20.04. Fast DDS is used as the ROS 2 middleware for distributed communication.

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

The ground station runs ROS 2 Humble on Ubuntu 22.04 and is primarily used for communication monitoring, data analysis, visualization, and experiment control.

```bash
# Update package index
sudo apt update

# ROS 2 analysis and visualization tools
sudo apt install -y \
  ros-humble-rmw-fastrtps-cpp \
  ros-humble-plotjuggler \
  ros-humble-rqt*
```
Note: ROS 2 Foxy and Humble are used on different nodes in the original experimental environment. Cross-distribution communication relies on compatible ROS 2 message definitions, DDS/RMW configuration, and QoS settings.
---

## 🔧 Workspace Build

Create a ROS 2 workspace and clone this repository:

```bash
# Create ROS 2 workspace
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws

# Clone this repository
git clone https://github.com/JoliMichael-glitch/ROS2-UAV-Comm-PX4.git \
src/ROS2-UAV-Comm-PX4

# Install dependencies
rosdep install --from-paths src --ignore-src -r -y

# Build workspace
colcon build --symlink-install

# Source the workspace
source install/setup.bash
```

> **Note:** The repository contains the implementation and experimental programs developed for the original undergraduate thesis. Depending on the selected experiment, additional configuration, launch files, or parameters may need to be adjusted according to the target node and hardware platform.

---

## 🚁 PX4–MAVROS Communication Validation

The PX4 integration validates the bidirectional communication path between the physical flight controller, the UAV edge computer, and the distributed ROS 2 network.

The basic communication path is:

```text
PX4 Flight Controller
        │
     MAVLink
        │
      UART
        │
      MAVROS
        │
     ROS 2
        │
   DDS / WiFi
        │
 Ground Station
```

### UAV Side — Launch MAVROS Bridge

On the UAV edge computer:

```bash
ros2 launch mavros px4.launch \
  fcu_url:=/dev/ttyTHS0:921600 \
  namespace:=/uav1
```

> **Note:** `/dev/ttyTHS0` is the UART device used in the original hardware configuration. The actual device name may differ depending on the Jetson platform, UART configuration, and `udev` rules. Refer to the **[Detailed Deployment Guide](docs/DEPLOYMENT.md)** before changing the hardware configuration.

### Ground Station — Verify Telemetry Stream

On the ground station:

```bash
ros2 topic echo /uav1/mavros/imu/data
```

A valid IMU data stream indicates that PX4 telemetry has been received by MAVROS and exposed through the ROS 2 communication layer.

### Ground Station — Trigger PX4 Mode Switch

The following command was used in the original validation experiment to test command transmission from ROS 2 to PX4:

```bash
ros2 service call \
  /uav1/mavros/set_mode \
  mavros_msgs/srv/SetMode \
  "{custom_mode: 'AUTO.LOITER'}"
```

### Expected Validation Results

A successful validation should demonstrate:

- PX4 IMU telemetry is available through ROS 2 topics
- The ground station can communicate with the UAV-side MAVROS node
- A PX4 flight-mode command can be transmitted through MAVROS
- PX4 successfully responds to the requested mode change
- Bidirectional communication between PX4, MAVROS, ROS 2, and the ground station is established

> **Safety note:** PX4 mode switching should only be performed when the flight controller and aircraft are in a safe test condition. The `AUTO.LOITER` command is used here as a communication validation example and should not be interpreted as a complete autonomous-flight procedure.

---

## 📊 Experimental Analysis

The repository contains analysis scripts developed for the communication experiments in the undergraduate thesis. Depending on the experiment, these scripts can be used to process communication logs and generate performance figures for:

- End-to-end latency measurement
- Packet loss evaluation
- Jitter characterization
- Reliable vs. BestEffort QoS comparison
- Payload-based communication stress testing
- Throughput evaluation
- Multi-node communication contention analysis
- Relay communication experiments

### Generate Result Plots

For example:

```bash
python analysis_scripts/plot_latency.py
```

> **Note:** The available analysis scripts correspond to different experiments and may require experiment-specific input files, parameters, or data paths. Please check the corresponding script before execution.

Generated figures and processed data are stored according to the output path configured by the individual analysis script.

For the original experimental workflow, generated data and figures were organized under:

```text
~/comms_testbed_data/
```

---

## 📂 Repository Layout

The repository is organized around the implementation, experimental programs, analysis scripts, and supporting configuration files used in the original undergraduate thesis project.

```text
ROS2-UAV-Comm-PX4/
├── src/                      # ROS 2 nodes and communication experiments
│   ├── center_node.cpp       # Ground/center-side communication node
│   ├── uav_node.cpp          # UAV-side communication node
│   ├── R1.cpp                # Relay/communication experiment node
│   ├── R2.cpp                # Relay node for multi-hop experiments
│   ├── C.cpp                 # Communication measurement/receiver node
│   └── ...                   # Other experimental source files
│
├── analysis_scripts/         # Python-based analysis and plotting tools
│   ├── plot_QoS.py
│   ├── cdf_plot.py
│   ├── plotgraph.py
│   └── ...
│
├── scripts/                  # Auxiliary monitoring and experiment scripts
│
├── config/                   # Configuration files used by experiments
│
├── assets/                   # Architecture diagrams, experiment photos,
│                             # and result figures
│
├── docs/
│   └── DEPLOYMENT.md         # Detailed physical deployment guide
│
├── README.md
└── LICENSE
```

> **Repository scope:** The current source code reflects the actual implementation and experimental configuration used during the undergraduate thesis. Some nodes and parameters are intentionally kept close to the original experimental setup to facilitate reproduction of the original experiments.

---

## 📜 License

This project is licensed under the Apache License 2.0.

See the [LICENSE](./LICENSE) file for additional details.
