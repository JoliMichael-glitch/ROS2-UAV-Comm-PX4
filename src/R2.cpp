/**
 * \class RelayOneWay
 *
 * \brief R2 relay for one-way latency architecture
 * \date 2026
 */
#include <chrono>
#include <atomic>
#include <functional>
#include <memory>
#include <string>

#include "dds_study/msg/relay_packet.hpp"
#include "rclcpp/rclcpp.hpp"

using namespace std::chrono_literals;

class RelayOneWay : public rclcpp::Node
{
private:
    using relay_msg_type = dds_study::msg::RelayPacket;

    int history_ = 10;
    int legacy_payload_bytes_ = 0;
    bool legacy_use_reliable_ = true;
    bool use_volatile_ = true;
    bool use_mixed_qos_ = true;
    std::string input_topic_ = "/hop1/rel";
    std::string output_topic_ = "/hop2/rel";

    std::atomic<uint32_t> rx_count_{0};
    std::atomic<uint32_t> forwarded_count_{0};

    rclcpp::Publisher<relay_msg_type>::SharedPtr pub_;
    rclcpp::Subscription<relay_msg_type>::SharedPtr sub_;

    void initialize_ros_and_params()
    {
        this->declare_parameter<int>("history", 10);
        this->declare_parameter<int>("payload_bytes", 0);
        this->declare_parameter<std::string>("relay_input_topic", "/hop1/rel");
        this->declare_parameter<std::string>("relay_output_topic", "/hop2/rel");
        this->declare_parameter<std::string>("publisher_topic", "/hop1/rel");
        this->declare_parameter<std::string>("subscriber_topic", "/hop2/rel");
        this->declare_parameter<bool>("use_default_reliability", true);
        this->declare_parameter<bool>("use_default_volatibility", true);
        this->declare_parameter<bool>("use_mixed_qos", true);

        this->get_parameter_or<int>("history", history_, 10);
        this->get_parameter_or<int>("payload_bytes", legacy_payload_bytes_, 0);
        this->get_parameter_or<bool>("use_default_reliability", legacy_use_reliable_, true);
        this->get_parameter_or<bool>("use_default_volatibility", use_volatile_, true);
        this->get_parameter_or<bool>("use_mixed_qos", use_mixed_qos_, true);

        std::string relay_input_topic;
        std::string relay_output_topic;
        std::string publisher_topic;
        std::string subscriber_topic;

        this->get_parameter_or<std::string>("relay_input_topic", relay_input_topic, "/hop1/rel");
        this->get_parameter_or<std::string>("relay_output_topic", relay_output_topic, "/hop2/rel");
        this->get_parameter_or<std::string>("publisher_topic", publisher_topic, "/hop1/rel");
        this->get_parameter_or<std::string>("subscriber_topic", subscriber_topic, "/hop2/rel");

        if (!relay_input_topic.empty())
        {
            input_topic_ = relay_input_topic;
        }
        else
        {
            input_topic_ = publisher_topic;
        }

        if (!relay_output_topic.empty())
        {
            output_topic_ = relay_output_topic;
        }
        else
        {
            output_topic_ = subscriber_topic;
        }

        if (input_topic_.empty() || output_topic_.empty())
        {
            RCLCPP_ERROR(this->get_logger(), "Relay topics are empty. Set relay_input_topic/relay_output_topic or publisher_topic/subscriber_topic");
            rclcpp::shutdown();
            return;
        }

        if (input_topic_ == output_topic_)
        {
            RCLCPP_ERROR(this->get_logger(), "Input and output topics are equal (%s). This would create a relay loop", input_topic_.c_str());
            rclcpp::shutdown();
            return;
        }

        auto sub_qos = rclcpp::QoS(static_cast<size_t>(history_));
        auto pub_qos = rclcpp::QoS(static_cast<size_t>(history_));

        if (use_mixed_qos_)
        {
            sub_qos.best_effort();
            pub_qos.reliable();
            RCLCPP_INFO(this->get_logger(), "R2 mixed QoS enabled: SUB Best Effort (%s) -> PUB Reliable (%s)", input_topic_.c_str(), output_topic_.c_str());
        }
        else
        {
            sub_qos.reliable();
            pub_qos.reliable();
            RCLCPP_INFO(this->get_logger(), "R2 mixed QoS disabled: SUB/PUB both Reliable (%s -> %s)", input_topic_.c_str(), output_topic_.c_str());
        }

        if (!use_volatile_)
        {
            sub_qos.transient_local();
            pub_qos.transient_local();
        }

        pub_ = this->create_publisher<relay_msg_type>(output_topic_, pub_qos);
        sub_ = this->create_subscription<relay_msg_type>(
            input_topic_,
            sub_qos,
            std::bind(&RelayOneWay::relay_callback, this, std::placeholders::_1));

        RCLCPP_INFO(this->get_logger(), "Relay is ready: %s -> %s", input_topic_.c_str(), output_topic_.c_str());
    }

    void relay_callback(const relay_msg_type::SharedPtr ros_data)
    {
        auto current_rx = ++rx_count_;
        if (current_rx == 1 || (current_rx % 100) == 0)
        {
            RCLCPP_INFO(this->get_logger(), "Relay received packets: %u", current_rx);
        }

        if (ros_data == nullptr)
        {
            RCLCPP_WARN(this->get_logger(), "Drop malformed packet: null pointer received");
            return;
        }

        relay_msg_type msg_out;
        msg_out.header = ros_data->header;
        msg_out.id = ros_data->id;
        msg_out.payload = ros_data->payload;
        pub_->publish(msg_out);

        auto current_forwarded = ++forwarded_count_;
        if (current_forwarded == 1 || (current_forwarded % 100) == 0)
        {
            RCLCPP_INFO(this->get_logger(), "Relay forwarded packets: %u", current_forwarded);
        }
    }

public:
    RelayOneWay() : Node("DDS_Relay_R2_OneWay")
    {
        initialize_ros_and_params();
    }
};

int main(int argc, char *argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::sleep_for(2s);

    rclcpp::spin(std::make_shared<RelayOneWay>());

    rclcpp::shutdown();
    return 0;
}
