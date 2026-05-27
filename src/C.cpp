/**
 * \class SubscriberOneWay
 * \brief C-side subscriber node - Strict Header & Raw Difference Format
 */
#include <chrono>
#include <atomic>
#include <fstream>
#include <functional>
#include <memory>
#include <string>
#include <sys/types.h>
#include <ifaddrs.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#include "dds_study/msg/relay_packet.hpp"
#include "rclcpp/rclcpp.hpp"

using namespace std::chrono_literals;

class SubscriberOneWay : public rclcpp::Node
{
private:
    using relay_msg_type = dds_study::msg::RelayPacket;

    bool use_file_ = false;
    std::string file_name_ = "";
    std::string topic_ = "";
    std::string local_ip_ = "0.0.0.0";
    std::ofstream file_handler_;
    std::atomic<uint32_t> callback_count_{0};
    rclcpp::Subscription<relay_msg_type>::SharedPtr sub_;

    // 获取本机 IP 地址
    void get_local_ip() {
        struct ifaddrs *ifAddrStruct = NULL;
        struct ifaddrs *ifa = NULL;
        void *tmpAddrPtr = NULL;
        getifaddrs(&ifAddrStruct);
        for (ifa = ifAddrStruct; ifa != NULL; ifa = ifa->ifa_next) {
            if (!ifa->ifa_addr) continue;
            if (ifa->ifa_addr->sa_family == AF_INET) { // 检查是 IPv4
                tmpAddrPtr = &((struct sockaddr_in *)ifa->ifa_addr)->sin_addr;
                char addressBuffer[INET_ADDRSTRLEN];
                inet_ntop(AF_INET, tmpAddrPtr, addressBuffer, INET_ADDRSTRLEN);
                std::string ifName = ifa->ifa_name;
                if (ifName != "lo") { // 排除本地回环
                    local_ip_ = addressBuffer;
                    break;
                }
            }
        }
        if (ifAddrStruct != NULL) freeifaddrs(ifAddrStruct);
    }

    void initialize_ros_and_params()
    {
        this->declare_parameter<std::string>("file_name", "");
        this->declare_parameter<std::string>("subscriber_topic", "/hop2/rel");

        this->get_parameter_or<std::string>("file_name", file_name_, "");
        this->get_parameter_or<std::string>("subscriber_topic", topic_, "/hop2/rel");

        get_local_ip();

        if (!file_name_.empty())
        {
            file_handler_.open(file_name_, std::ios::out | std::ios::trunc);
            if (file_handler_.is_open())
            {
                use_file_ = true;
                // --- 严格按照你的要求：表头一字不变 ---
                file_handler_ << "id,TX_s,TX_ns,RX_s,RX_ns,d_s,d_ns,IP\n";
                file_handler_.flush();
            }
        }

        // 接收端 QoS 设为 BestEffort 兼容性最强
        auto qos = rclcpp::QoS(10).best_effort();
        sub_ = this->create_subscription<relay_msg_type>(
            topic_, qos, std::bind(&SubscriberOneWay::msg_rx_callback, this, std::placeholders::_1));
        
        RCLCPP_INFO(this->get_logger(), "Subscriber started on %s, Logging to %s", topic_.c_str(), file_name_.c_str());
    }

    void msg_rx_callback(const relay_msg_type::SharedPtr ros_data)
    {
        if (ros_data == nullptr) return;

        // 获取发送时间 (TX)
        const rclcpp::Time tx_time(ros_data->header.stamp);
        int64_t tx_s = tx_time.nanoseconds() / 1000000000LL;
        int64_t tx_ns = tx_time.nanoseconds() % 1000000000LL;

        // 获取接收时间 (RX)
        const rclcpp::Time rx_time = this->now();
        int64_t rx_s = rx_time.nanoseconds() / 1000000000LL;
        int64_t rx_ns = rx_time.nanoseconds() % 1000000000LL;

        // --- 计算两列差值 ---
        // d_s 代表秒的差值，d_ns 代表纳秒部分的原始差值
        int64_t d_s = rx_s - tx_s;
        int64_t d_ns = rx_ns - tx_ns;

        callback_count_++;

        if (use_file_ && file_handler_.is_open())
        {
            // 严格按照表格顺序写入
            file_handler_ << ros_data->id << ","
                          << tx_s << ","
                          << tx_ns << ","
                          << rx_s << ","
                          << rx_ns << ","
                          << d_s << ","
                          << d_ns << ","
                          << local_ip_ << "\n";
            
            if (callback_count_ % 10 == 0) file_handler_.flush();
        }
    }

public:
    SubscriberOneWay() : Node("DDS_Subscriber_OneWay") {
        initialize_ros_and_params();
    }

    ~SubscriberOneWay() override {
        if (file_handler_.is_open()) file_handler_.close();
    }
};

int main(int argc, char *argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SubscriberOneWay>());
    rclcpp::shutdown();
    return 0;
}
