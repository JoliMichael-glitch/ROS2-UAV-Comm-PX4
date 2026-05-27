import rclpy
from rclpy.node import Node
from dds_study.msg import RelayPacket
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
import time
import psutil
import threading
from collections import deque
import tkinter as tk

class FinalAcademicHUD(Node):
    def __init__(self):
        super().__init__('final_academic_hud')

        self.declare_parameter('subscriber_topic', '/hop2/rel')
        self.declare_parameter('use_mixed_qos', True)
        self.topic_name = self.get_parameter('subscriber_topic').value
        use_mixed_qos = self.get_parameter('use_mixed_qos').value
        self.window_sec = 2.0  
        self.data_buffer = deque()

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE if use_mixed_qos else ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.sub = self.create_subscription(RelayPacket, self.topic_name, self.callback, qos)

        # GUI 设计 - 高亮学术风格
        self.root = tk.Tk()
        self.root.title("SIAE UAV Link Monitor")
        self.root.geometry("420x550") 
        self.root.configure(bg="#1A1A1A") 
        self.root.attributes("-topmost", True)
        
        self.setup_ui()

    def setup_ui(self):
        # 颜色定义
        self.C_GREEN = "#00FF41"
        self.C_RED = "#FF3131"
        self.C_BLUE = "#00BFFF"
        
        header = tk.Frame(self.root, bg="#1A1A1A", height=60)
        header.pack(fill="x", pady=10)
        tk.Label(header, text="UAV LINK MONITOR", bg="#1A1A1A", fg="#FFFFFF", font=("Arial", 12, "bold")).pack(side="left", padx=25)
        self.status_led = tk.Label(header, text="● SYSTEM LIVE", bg="#1A1A1A", fg=self.C_GREEN, font=("Arial", 10, "bold"))
        self.status_led.pack(side="right", padx=25)

        self.ping_lbl = self.create_card("END-TO-END LATENCY", self.C_GREEN)
        self.loss_lbl = self.create_card("PACKET LOSS RATE", self.C_RED)
        self.flow_lbl = self.create_card("THROUGHPUT (FLOW)", self.C_BLUE)

        self.sys_info = tk.Label(self.root, text="CPU: --% | MEM: --%", bg="#1A1A1A", fg="#888", font=("Consolas", 12))
        self.sys_info.pack(side="bottom", pady=25)

    def create_card(self, title, val_color):
        frame = tk.Frame(self.root, bg="#2D2D2D", highlightbackground="#444", highlightthickness=1)
        frame.pack(fill="x", padx=25, pady=12)
        tk.Label(frame, text=title, bg="#2D2D2D", fg="#AAA", font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=(12, 0))
        label = tk.Label(frame, text="WAITING", bg="#2D2D2D", fg=val_color, font=("Consolas", 30, "bold"))
        label.pack(anchor="w", padx=15, pady=(5, 12))
        return label

    def callback(self, msg):
        try:
            now = time.time()
            sent_time = float(msg.header.stamp.sec) + float(msg.header.stamp.nanosec) / 1e9
            latency = now - sent_time
            if latency < 0:
                return

            payload_bytes = len(msg.payload)
            header_and_id_bytes = 4 + 4 + 4  # sec + nanosec + int32 id
            packet_bytes = payload_bytes + header_and_id_bytes

            self.data_buffer.append((now, latency, packet_bytes, int(msg.id)))
        except Exception:
            pass

    def update_hud(self):
        now = time.time()
        while self.data_buffer and (now - self.data_buffer[0][0]) > self.window_sec:
            self.data_buffer.popleft()

        if not self.data_buffer:
            self.ping_lbl.config(text="OFFLINE", fg="#666")
            self.loss_lbl.config(text="--- %", fg="#666")
            self.flow_lbl.config(text="0 B/s", fg="#666")
            self.status_led.config(fg="#666", text="● STANDBY")
        else:
            self.status_led.config(fg=self.C_GREEN, text="● SYSTEM LIVE")
            
            # 1. Latency (精确到 1 位小数)
            avg_p = sum(d[1] for d in self.data_buffer) / len(self.data_buffer)
            self.ping_lbl.config(text=f"{avg_p*1000.0:.1f} ms")

            # 2. Loss Rate
            sns = [d[3] for d in self.data_buffer]
            expected = max(sns) - min(sns) + 1
            actual = len(self.data_buffer)
            loss = max(0.0, (expected - actual) / expected * 100.0)
            self.loss_lbl.config(text=f"{loss:.1f} %", fg=self.C_GREEN if loss < 5 else self.C_RED)

            # 3. Flow
            total_b = sum(d[2] for d in self.data_buffer)
            self.flow_lbl.config(text=f"{total_b/self.window_sec:.1f} B/s")

        self.sys_info.config(text=f"CPU: {psutil.cpu_percent()}% | MEM: {psutil.virtual_memory().percent}%")
        self.root.after(200, self.update_hud)

if __name__ == '__main__':
    rclpy.init()
    node = FinalAcademicHUD()
    threading.Thread(target=lambda: rclpy.spin(node), daemon=True).start()
    node.update_hud()
    node.root.mainloop()
