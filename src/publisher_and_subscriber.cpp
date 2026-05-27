/**
 * \class PublisherAndSubscriber
 *
 * \brief Combined publisher and subscriber executable.
 * \date 2026
 */
#include <chrono>
#include <array>
#include <atomic>
#include <cassert>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <memory>
#include <string>
#include <thread>

/* C headers for sockets. */
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/udp.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <unistd.h>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/u_int8_multi_array.hpp"

#define LOCALHOST 0x0100007F

using namespace std::chrono_literals;

class PubSubPublisher : public rclcpp::Node, public rclcpp::Context
{
private:
    typedef std_msgs::msg::UInt8MultiArray test_msg_type;

    bool use_file_;
    int udp_sock_ = -1;
    rclcpp::Publisher<test_msg_type>::SharedPtr pub_;
    rclcpp::TimerBase::SharedPtr message_timer_, end_timer_;
    uint32_t current_sequence;
    uint32_t ether_ip_addr_;

    std::ofstream file_handler_;
    std::thread *listener_thread_;
    std::atomic<bool> stop_thread_{false};
    std::atomic<uint32_t> feedback_count_{0};
    std::atomic<uint32_t> publish_count_{0};
    std::string topic_ = "";
    std_msgs::msg::UInt8MultiArray ros_msg;

    int history_ = 0;
    int packets_to_send_ = 0;
    int port_ = 0;
    bool use_reliable_;
    bool use_volatile_;
    std::string file_name_ = "";
    int publishing_period_ms_;
    int payload_bytes_;

    struct timespec diff_timespec(const struct timespec &time1, const struct timespec &time0)
    {
        struct timespec diff;
        diff.tv_sec = time1.tv_sec - time0.tv_sec;
        diff.tv_nsec = time1.tv_nsec - time0.tv_nsec;
        if (diff.tv_nsec < 0)
        {
            diff.tv_nsec += 1000000000;
            diff.tv_sec--;
        }
        return diff;
    }

    void end_callback(void)
    {
        file_handler_.close();
        RCLCPP_DEBUG(this->get_logger(), "Shutting down publisher node");
        rclcpp::shutdown();
    }

    int get_ethernet_addr(void)
    {
        FILE *fp;
        char path[1024];
        std::string temp_str;
        fp = popen("ip addr | grep inet | grep global | awk '{ print $2 }' | head -n 1", "r");
        if (fp == NULL)
        {
            RCLCPP_ERROR(this->get_logger(), "Failed to open system command");
            goto err;
        }
        if (fgets(path, sizeof(path), fp) == NULL)
        {
            RCLCPP_ERROR(this->get_logger(), "Failed to retrieve Ethernet address");
            goto err;
        }
        temp_str = path;
        temp_str.erase(temp_str.find('/'));
        RCLCPP_INFO(this->get_logger(), "Ethernet address from system script: %s", temp_str.c_str());
        if (inet_pton(AF_INET, temp_str.c_str(), &ether_ip_addr_) != 1)
        {
            RCLCPP_ERROR(this->get_logger(), "Failed to convert address to binary form");
            goto err;
        }
        pclose(fp);
        return 0;
    err:
        pclose(fp);
        return 1;
    }

    void initialize_ros_and_params(void)
    {
        this->declare_parameter<std::string>("ip_addr", "");
        this->declare_parameter<std::string>("file_name", "");
        this->declare_parameter<int>("history", 10);
        this->declare_parameter<int>("packets_to_send", 0);
        this->declare_parameter<int>("payload_bytes", 0);
        this->declare_parameter<int>("port", 0);
        this->declare_parameter<int>("publisher_period_ms", 1000);
        this->declare_parameter<std::string>("publisher_topic", "");
        this->declare_parameter<bool>("use_default_reliability", true);
        this->declare_parameter<bool>("use_default_volatibility", true);

        this->get_parameter<std::string>("file_name", file_name_);
        this->get_parameter_or<int>("history", history_, 10);
        this->get_parameter<int>("packets_to_send", packets_to_send_);
        this->get_parameter<int>("payload_bytes", payload_bytes_);
        this->get_parameter<int>("port", port_);
        this->get_parameter<int>("publisher_period_ms", publishing_period_ms_);
        this->get_parameter<std::string>("publisher_topic", topic_);
        this->get_parameter_or<bool>("use_default_reliability", use_reliable_, true);
        this->get_parameter_or<bool>("use_default_volatibility", use_volatile_, true);

        std::string ip_param;
        this->get_parameter<std::string>("ip_addr", ip_param);
        if (!ip_param.empty())
        {
            RCLCPP_INFO(this->get_logger(), "Using EXPLICIT IP from parameter: %s", ip_param.c_str());
            if (inet_pton(AF_INET, ip_param.c_str(), &ether_ip_addr_) != 1)
            {
                RCLCPP_ERROR(this->get_logger(), "Invalid explicit IP format");
            }
        }
        else
        {
            if (get_ethernet_addr() != 0)
            {
                RCLCPP_ERROR(this->get_logger(), "Failed to get ethernet, safely shutting down");
                rclcpp::shutdown();
            }
        }

        if (file_name_.empty())
        {
            use_file_ = false;
            RCLCPP_INFO(this->get_logger(), "No logfile path was provided. Not logging.");
        }
        else
        {
            use_file_ = true;
            RCLCPP_INFO(this->get_logger(), "Logging into: %s", file_name_.c_str());
        }

        current_sequence = 0;

        auto new_size = sizeof(uint32_t) + sizeof(uint32_t) + sizeof(time_t) + sizeof(long int) + payload_bytes_;
        ros_msg.data.resize(new_size);
        if (ros_msg.data.capacity() != new_size)
        {
            RCLCPP_ERROR(this->get_logger(), "Could not allocate memory for message");
            rclcpp::sleep_for(2s);
            rclcpp::shutdown();
        }

        memset(&ros_msg.data[new_size - payload_bytes_], 0xA5, payload_bytes_);

        auto qos = rclcpp::QoS((size_t)history_);
        if (!use_reliable_)
        {
            qos.best_effort();
        }
        if (!use_volatile_)
        {
            qos.transient_local();
        }

        pub_ = this->create_publisher<test_msg_type>(topic_, qos);
        rclcpp::sleep_for(1s);
        message_timer_ = this->create_wall_timer(std::chrono::milliseconds(publishing_period_ms_), std::bind(&PubSubPublisher::message_timer_cb, this));
    }

    void message_timer_cb(void)
    {
        auto publish_index = ++publish_count_;
        auto matched_subscribers = pub_->get_subscription_count();
        if (publish_index == 1 || (publish_index % 100) == 0)
        {
            RCLCPP_INFO(this->get_logger(), "Published packets: %u, matched DDS subscribers: %zu", publish_index, matched_subscribers);
        }

        if (matched_subscribers == 0 && (publish_index % 10) == 0)
        {
            RCLCPP_WARN(this->get_logger(), "No DDS subscriber matched on topic %s", topic_.c_str());
        }

        struct timespec rp;
        (void)clock_gettime(CLOCK_MONOTONIC, &rp);
        memcpy(&ros_msg.data[0], &current_sequence, sizeof(uint32_t));
        memcpy(&ros_msg.data[4], &ether_ip_addr_, sizeof(uint32_t));
        memcpy(&ros_msg.data[8], &rp.tv_sec, sizeof(time_t));
        memcpy(&ros_msg.data[8 + sizeof(time_t)], &rp.tv_nsec, sizeof(long int));

        pub_->publish(ros_msg);

        if (current_sequence == static_cast<uint32_t>(packets_to_send_))
        {
            RCLCPP_DEBUG(this->get_logger(), "Packet limit reached.");
            end_timer_ = this->create_wall_timer(5s, std::bind(&PubSubPublisher::end_callback, this));
            message_timer_->cancel();
        }
        current_sequence++;
    }

    void thread_func_(void)
    {
        int sock_;
        socklen_t len;
        struct sockaddr_in servaddr, cliaddr;

        if (use_file_)
        {
            file_handler_.open(file_name_, std::ios::out | std::ios::trunc);
            if (!file_handler_.is_open())
            {
                RCLCPP_ERROR(this->get_logger(), "Could not open file: exiting now");
                rclcpp::shutdown();
            }
            file_handler_ << "SN(Sequence Number)\t"
                          << "TX_s(Transmit Timestamp Seconds)\t"
                          << "TX_ns(Transmit Timestamp Nanoseconds)\t"
                          << "RX_s(Receive Timestamp Seconds)\t"
                          << "RX_ns(Receive Timestamp Nanoseconds)\t"
                          << "d_s(Delay Seconds)\t"
                          << "d_ns(Delay Nanoseconds)\t"
                          << "IP(Sender IPv4 Address)\n";
            file_handler_.flush();
        }

        if ((sock_ = socket(AF_INET, SOCK_DGRAM, 0)) < 0)
        {
            RCLCPP_ERROR(this->get_logger(), "Could not create socket");
            rclcpp::sleep_for(2s);
            rclcpp::shutdown();
        }
        udp_sock_ = sock_;

        assert(port_ < 0xFFFF);

        memset(&servaddr, 0, sizeof(servaddr));
        memset(&cliaddr, 0, sizeof(cliaddr));
        servaddr.sin_family = AF_INET;
        servaddr.sin_port = htons((uint16_t)port_);
        servaddr.sin_addr.s_addr = INADDR_ANY;

        if (bind(sock_, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0)
        {
            RCLCPP_ERROR(this->get_logger(), "Could bind socket to server address");
            rclcpp::sleep_for(2s);
            rclcpp::shutdown();
        }

        len = sizeof(cliaddr);
        char buffer[128];

        while (!stop_thread_)
        {
            size_t received_bytes = 0;
            ssize_t recv_len = 0;
            do
            {
                recv_len = recvfrom(sock_,
                                    &buffer[received_bytes],
                                    sizeof(buffer) - received_bytes,
                                    0,
                                    (struct sockaddr *)&cliaddr,
                                    &len);
                if (recv_len <= 0)
                {
                    break;
                }
                received_bytes += static_cast<size_t>(recv_len);
            } while (!stop_thread_ && received_bytes < (sizeof(struct timespec) + sizeof(uint32_t)));

            if (stop_thread_ || recv_len <= 0)
            {
                break;
            }

            if (cliaddr.sin_addr.s_addr == ether_ip_addr_)
            {
                cliaddr.sin_addr.s_addr = LOCALHOST;
            }

            struct timespec current_rp, past_rp;
            (void)clock_gettime(CLOCK_MONOTONIC, &current_rp);
            memset(&past_rp, 0, sizeof(past_rp));
            uint32_t sn = 0;
            memcpy(&sn, &buffer[0], sizeof(uint32_t));
            memcpy(&past_rp.tv_sec, &buffer[4], sizeof(time_t));
            memcpy(&past_rp.tv_nsec, &buffer[4 + sizeof(time_t)], sizeof(long int));

            auto current_count = ++feedback_count_;
            if (current_count == 1 || (current_count % 100) == 0)
            {
                RCLCPP_INFO(this->get_logger(), "Received UDP feedback packets: %u", current_count);
            }

            if (use_file_)
            {
                stream_to_file(file_handler_, sn, past_rp, current_rp, cliaddr.sin_addr.s_addr);
            }
        }

        close(sock_);
        file_handler_.close();
    }

    void stream_to_file(std::ofstream &fh, const uint32_t &sn, const struct timespec &tx_ts,
                        const struct timespec &rx_ts, const uint32_t &ip)
    {
        char ip_str[INET_ADDRSTRLEN];
        if (inet_ntop(AF_INET, (void *)&ip, ip_str, INET_ADDRSTRLEN) == nullptr)
        {
            RCLCPP_ERROR(this->get_logger(), "Error at converting IP from binary to text form");
            return;
        }
        auto diff = diff_timespec(rx_ts, tx_ts);
        fh << sn << "\t" << tx_ts.tv_sec << "\t" << tx_ts.tv_nsec << "\t" << rx_ts.tv_sec
           << "\t" << rx_ts.tv_nsec << "\t" << diff.tv_sec
           << "\t" << diff.tv_nsec << "\t" << ip_str << "\n";
        fh.flush();
    }

public:
    PubSubPublisher() : Node("DDS_Publisher")
    {
        initialize_ros_and_params();
        listener_thread_ = new std::thread(&PubSubPublisher::thread_func_, this);
    }

    ~PubSubPublisher()
    {
        stop_thread_ = true;
        if (udp_sock_ != -1)
        {
            close(udp_sock_);
        }
        if (listener_thread_ && listener_thread_->joinable())
        {
            listener_thread_->join();
        }
        file_handler_.close();
        delete listener_thread_;
    }
};

class PubSubSubscriber : public rclcpp::Node, public rclcpp::Context
{
private:
    int history_;
    bool use_reliable_;
    bool use_volatile_;
    int sub_sock_;
    int payload_bytes_;
    int port_;
    std::atomic<uint32_t> callback_count_{0};
    std::atomic<uint32_t> feedback_sent_count_{0};
    rclcpp::Subscription<std_msgs::msg::UInt8MultiArray>::SharedPtr sub_;
    socklen_t sub_len;
    std::string topic_ = "";
    struct sockaddr_in servaddr;

    void initialize_ros_and_params(void)
    {
        this->declare_parameter<int>("history", 10);
        this->declare_parameter<int>("payload_bytes", 0);
        this->declare_parameter<int>("port", 2077);
        this->declare_parameter<std::string>("publisher_topic", "");
        this->declare_parameter<std::string>("subscriber_topic", "");
        this->declare_parameter<bool>("use_default_reliability", true);
        this->declare_parameter<bool>("use_default_volatibility", true);

        this->get_parameter_or<int>("history", history_, 10);
        this->get_parameter<int>("payload_bytes", payload_bytes_);
        this->get_parameter_or<int>("port", port_, 2077);
        this->get_parameter_or<std::string>("subscriber_topic", topic_, "");
        if (topic_.empty())
        {
            this->get_parameter_or<std::string>("publisher_topic", topic_, "");
        }
        this->get_parameter_or<bool>("use_default_reliability", use_reliable_, true);
        this->get_parameter_or<bool>("use_default_volatibility", use_volatile_, true);

        auto qos = rclcpp::QoS((size_t)history_);
        if (!use_reliable_)
        {
            qos.best_effort();
        }
        if (!use_volatile_)
        {
            qos.transient_local();
        }

        sub_ = this->create_subscription<std_msgs::msg::UInt8MultiArray>(
            topic_, qos, std::bind(&PubSubSubscriber::msg_rx_callback, this, std::placeholders::_1));

        rclcpp::sleep_for(10s);
    }

    void initialize_subscriber_socket(void)
    {
        if ((sub_sock_ = socket(AF_INET, SOCK_DGRAM, 0)) < 0)
        {
            RCLCPP_ERROR(this->get_logger(), "Could not create socket");
            rclcpp::sleep_for(2s);
            rclcpp::shutdown();
        }

        assert(port_ < 0xFFFF);

        memset(&servaddr, 0, sizeof(servaddr));
        servaddr.sin_family = AF_INET;
        servaddr.sin_port = htons((uint16_t)port_);
        sub_len = sizeof(servaddr);
    }

    void msg_rx_callback(const std_msgs::msg::UInt8MultiArray::SharedPtr ros_data)
    {
        auto rx_count = ++callback_count_;
        if (rx_count == 1 || (rx_count % 100) == 0)
        {
            RCLCPP_INFO(this->get_logger(), "Subscriber callback count: %u", rx_count);
        }

        size_t header_size = sizeof(uint32_t) + sizeof(uint32_t) + sizeof(time_t) + sizeof(long int);
        size_t expected_bytes = payload_bytes_ + header_size;
        if (ros_data->data.size() < expected_bytes)
        {
            RCLCPP_INFO(this->get_logger(), "Size mismatch between expected to received bytes and actual data");
            return;
        }

        std::array<char, sizeof(uint32_t) + sizeof(time_t) + sizeof(long int)> buffer{};
        memcpy(buffer.data(), &ros_data->data[0], sizeof(uint32_t));
        memcpy(buffer.data() + sizeof(uint32_t), &ros_data->data[8], sizeof(time_t));
        memcpy(buffer.data() + sizeof(uint32_t) + sizeof(time_t), &ros_data->data[8 + sizeof(time_t)], sizeof(long int));

        memcpy(&servaddr.sin_addr.s_addr, &ros_data->data[4], sizeof(uint32_t));

        auto sent_bytes = sendto(sub_sock_, buffer.data(), buffer.size(), 0, (const struct sockaddr *)&servaddr, sub_len);
        if (sent_bytes != static_cast<ssize_t>(buffer.size()))
        {
            RCLCPP_WARN(this->get_logger(), "UDP feedback send mismatch: %ld/%zu", sent_bytes, buffer.size());
            return;
        }

        auto sent_count = ++feedback_sent_count_;
        if (sent_count == 1 || (sent_count % 100) == 0)
        {
            RCLCPP_INFO(this->get_logger(), "UDP feedback sent: %u", sent_count);
        }
    }

public:
    PubSubSubscriber() : Node("DDS_Subscriber")
    {
        initialize_ros_and_params();
        initialize_subscriber_socket();
    }
};

int main(int argc, char *argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::sleep_for(2s);

    auto publisher_node = std::make_shared<PubSubPublisher>();
    auto subscriber_node = std::make_shared<PubSubSubscriber>();

    rclcpp::executors::MultiThreadedExecutor executor;
    executor.add_node(publisher_node);
    executor.add_node(subscriber_node);
    executor.spin();

    rclcpp::shutdown();
    return 0;
}

