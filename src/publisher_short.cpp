#include <chrono>
#include <fstream>
#include <memory>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/u_int8_multi_array.hpp"

using namespace std::chrono_literals;

class StablePublisher : public rclcpp::Node {
public:
    StablePublisher() : Node("DDS_Publisher"), current_sequence(0) {
        // 声明参数
        this->declare_parameter<std::string>("file_name", "/home/ros2/test.csv");
        this->declare_parameter<int>("payload_bytes", 256);
        this->declare_parameter<int>("publisher_period_ms", 50);
        this->declare_parameter<int>("packets_to_send", 500);

        // 获取参数
        this->get_parameter("file_name", file_name_);
        this->get_parameter("payload_bytes", payload_bytes_);
        this->get_parameter("publisher_period_ms", period_ms_);
        this->get_parameter("packets_to_send", packets_to_send_);

        // 打开文件
        file_out_.open(file_name_, std::ios::out | std::ios::trunc);
        if (!file_out_.is_open()) {
            RCLCPP_ERROR(this->get_logger(), "无法打开文件: %s", file_name_.c_str());
            return;
        }
        file_out_ << "SN,Time_s,Time_ns\n";

        // 准备消息
        msg_.data.resize(payload_bytes_ + 16); // 预留点空间给Header

        pub_ = this->create_publisher<std_msgs::msg::UInt8MultiArray>("uav_test_topic", 10);
        
        RCLCPP_INFO(this->get_logger(), "开始实验，记录至: %s", file_name_.c_str());
        
        timer_ = this->create_wall_timer(
            std::chrono::milliseconds(period_ms_), 
            std::bind(&StablePublisher::timer_callback, this));
    }

private:
   void timer_callback() {
    if (current_sequence >= packets_to_send_) {
        RCLCPP_INFO(this->get_logger(), "测试完成！");
        file_out_.close();
        timer_->cancel();
        rclcpp::shutdown();
        return;
    }

    auto now = this->get_clock()->now();
    
    // --- 核心修改：将序号 SN 写入数据包的前 4 字节 ---
    // 使用 memcpy 将 current_sequence 这个整数拷贝进 msg_.data
    std::memcpy(&msg_.data[0], &current_sequence, sizeof(int));
    
    // 记录发送日志
    file_out_ << current_sequence << "," << now.seconds() << "," << now.nanoseconds() << "\n";
    
    pub_->publish(msg_);
    current_sequence++;
}

    std::string file_name_;
    int payload_bytes_, period_ms_, packets_to_send_;
    int current_sequence;
    std::ofstream file_out_;
    rclcpp::Publisher<std_msgs::msg::UInt8MultiArray>::SharedPtr pub_;
    rclcpp::TimerBase::SharedPtr timer_;
    std_msgs::msg::UInt8MultiArray msg_;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<StablePublisher>());
    rclcpp::shutdown();
    return 0;
}
