#include <fstream>
#include <memory>
#include <string>
#include <cstring>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/u_int8_multi_array.hpp"

class StableSubscriber : public rclcpp::Node {
public:
    StableSubscriber() : Node("DDS_Subscriber") {
        // 1. 参数声明
        this->declare_parameter<std::string>("file_name", "/home/ros2/rx_test.csv");
        this->get_parameter("file_name", file_name_);

        // 2. 初始化接收日志
        file_out_.open(file_name_, std::ios::out | std::ios::trunc);
        if (!file_out_.is_open()) {
            RCLCPP_ERROR(this->get_logger(), "无法打开接收日志: %s", file_name_.c_str());
            return;
        }
        file_out_ << "SN,RX_Time_s,RX_Time_ns\n";

        // 3. 创建订阅者
        sub_ = this->create_subscription<std_msgs::msg::UInt8MultiArray>(
            "uav_test_topic", 10, 
            std::bind(&StableSubscriber::topic_callback, this, std::placeholders::_1));
        
        RCLCPP_INFO(this->get_logger(), "接收端已启动，监听话题: uav_test_topic");
    }

    // 析构函数：确保对象销毁时关闭文件
    ~StableSubscriber() {
        if (file_out_.is_open()) {
            file_out_.close();
        }
    }

private:
    void topic_callback(const std_msgs::msg::UInt8MultiArray::SharedPtr msg) {
        auto now = this->get_clock()->now();
        
        int received_sn = 0;
        if (msg->data.size() >= sizeof(int)) {
            std::memcpy(&received_sn, &msg->data[0], sizeof(int));
        }

        file_out_ << received_sn << "," << now.seconds() << "," << now.nanoseconds() << "\n";
        // 如果想看实时反馈，可以取消下面这一行的注释
        // RCLCPP_INFO(this->get_logger(), "收到 SN: %d", received_sn);
    }

    std::string file_name_;
    std::ofstream file_out_;
    rclcpp::Subscription<std_msgs::msg::UInt8MultiArray>::SharedPtr sub_;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<StableSubscriber>());
    rclcpp::shutdown();
    return 0;
}
