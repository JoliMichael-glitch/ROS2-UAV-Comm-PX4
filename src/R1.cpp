/**
 * \class PublisherOneWay
 *
 * \brief R1 publisher node for one-way latency architecture
 * \date 2026
 */
#include <chrono>
#include <atomic>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "dds_study/msg/relay_packet.hpp"
#include "rclcpp/rclcpp.hpp"

using namespace std::chrono_literals;

class PublisherOneWay : public rclcpp::Node
{
private:
    using packet_msg_type = dds_study::msg::RelayPacket;

    rclcpp::Publisher<packet_msg_type>::SharedPtr pub_;
    rclcpp::TimerBase::SharedPtr message_timer_;
    rclcpp::TimerBase::SharedPtr end_timer_;

    std::atomic<uint32_t> publish_count_{0};
    uint32_t current_sequence_ = 0;

    std::string topic_ = "";
    int history_ = 10;
    int packets_to_send_ = 0;
    int publishing_period_ms_ = 1000;
    int payload_bytes_ = 0;
    bool use_volatile_ = true;
    bool use_mixed_qos_ = true;

    // Legacy arguments are still declared to keep old automation compatible.
    bool legacy_use_reliable_ = true;

    std::vector<uint8_t> constant_payload_;

    void end_callback()
    {
        RCLCPP_DEBUG(this->get_logger(), "Shutting down node");
        rclcpp::shutdown();
    }

    void initialize_ros_and_params()
    {
        this->declare_parameter<std::string>("ip_addr", "");
        this->declare_parameter<std::string>("file_name", "");
        this->declare_parameter<int>("port", 0);
        this->declare_parameter<int>("history", 10);
        this->declare_parameter<int>("packets_to_send", 0);
        this->declare_parameter<int>("payload_bytes", 0);
        this->declare_parameter<int>("publisher_period_ms", 1000);
        this->declare_parameter<std::string>("publisher_topic", "");
        this->declare_parameter<bool>("use_default_reliability", true);
        this->declare_parameter<bool>("use_default_volatibility", true);
        this->declare_parameter<bool>("use_mixed_qos", true);

        this->get_parameter_or<int>("history", history_, 10);
        this->get_parameter_or<int>("packets_to_send", packets_to_send_, 0);
        this->get_parameter_or<int>("payload_bytes", payload_bytes_, 0);
        this->get_parameter_or<int>("publisher_period_ms", publishing_period_ms_, 1000);
        this->get_parameter_or<std::string>("publisher_topic", topic_, "");
        this->get_parameter_or<bool>("use_default_reliability", legacy_use_reliable_, true);
        this->get_parameter_or<bool>("use_default_volatibility", use_volatile_, true);
        this->get_parameter_or<bool>("use_mixed_qos", use_mixed_qos_, true);

        if (topic_.empty())
        {
            RCLCPP_ERROR(this->get_logger(), "Publisher topic is empty");
            rclcpp::shutdown();
            return;
        }

        if (payload_bytes_ < 0)
        {
            payload_bytes_ = 0;
        }
        constant_payload_.assign(static_cast<size_t>(payload_bytes_), 0xA5);

        auto qos = rclcpp::QoS(static_cast<size_t>(history_));
        if (use_mixed_qos_)
        {
            qos.best_effort();
            RCLCPP_INFO(this->get_logger(), "R1 mixed QoS enabled: publisher uses Best Effort on topic %s", topic_.c_str());
        }
        else
        {
            qos.reliable();
            RCLCPP_INFO(this->get_logger(), "R1 mixed QoS disabled: publisher uses Reliable on topic %s", topic_.c_str());
        }

        if (!use_volatile_)
        {
            qos.transient_local();
        }

        pub_ = this->create_publisher<packet_msg_type>(topic_, qos);
        rclcpp::sleep_for(1s);
        message_timer_ = this->create_wall_timer(
            std::chrono::milliseconds(publishing_period_ms_),
            std::bind(&PublisherOneWay::message_timer_cb, this));
    }

    void message_timer_cb()
    {
        auto publish_index = ++publish_count_;
        const auto matched_subscribers = pub_->get_subscription_count();
        if (publish_index == 1 || (publish_index % 100) == 0)
        {
            RCLCPP_INFO(this->get_logger(), "Published packets: %u, matched DDS subscribers: %zu", publish_index, matched_subscribers);
        }
        if (matched_subscribers == 0 && (publish_index % 10) == 0)
        {
            RCLCPP_WARN(this->get_logger(), "No DDS subscriber matched on topic %s", topic_.c_str());
        }

        packet_msg_type ros_msg;
        ros_msg.header.stamp = this->now();
        ros_msg.header.frame_id = "R1";
        ros_msg.id = static_cast<int32_t>(current_sequence_);
        ros_msg.payload = constant_payload_;
        pub_->publish(ros_msg);

        current_sequence_++;
        if (packets_to_send_ > 0 && current_sequence_ >= static_cast<uint32_t>(packets_to_send_))
        {
            RCLCPP_DEBUG(this->get_logger(), "Packet limit reached.");
            end_timer_ = this->create_wall_timer(5s, std::bind(&PublisherOneWay::end_callback, this));
            message_timer_->cancel();
        }
    }

public:
    PublisherOneWay() : Node("DDS_Publisher_OneWay")
    {
        initialize_ros_and_params();
    }
};

int main(int argc, char *argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::sleep_for(2s);
    rclcpp::spin(std::make_shared<PublisherOneWay>());
    rclcpp::shutdown();
    return 0;
}
