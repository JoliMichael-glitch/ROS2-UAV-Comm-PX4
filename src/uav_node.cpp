#include <chrono>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "uav_test/msg/uav_cmd.hpp"
#include "uav_test/msg/uav_status.hpp"

using namespace std::chrono_literals;

class UavNode : public rclcpp::Node {
 public:
  UavNode() : Node("uav_node") {
    this->declare_parameter<std::string>("uav_id", "uav");
    this->get_parameter("uav_id", uav_id_);

    status_pub_ = this->create_publisher<uav_test::msg::UAVStatus>("status", 10);
    cmd_sub_ = this->create_subscription<uav_test::msg::UAVCmd>(
        "cmd", 10,
        [this](const uav_test::msg::UAVCmd::SharedPtr msg) {
          if (msg->target_id == uav_id_) {
            RCLCPP_INFO(this->get_logger(), "\033[1;32m[UAV_%s] 收到中心机指令: %s\033[0m",
                        uav_id_.c_str(), msg->cmd_content.c_str());
          }
        });

    timer_ = this->create_wall_timer(2s, [this]() {
      uav_test::msg::UAVStatus msg;
      msg.header.stamp = this->now();
      msg.uav_id = uav_id_;
      status_pub_->publish(msg);
    });
  }

 private:
  std::string uav_id_;
  rclcpp::Publisher<uav_test::msg::UAVStatus>::SharedPtr status_pub_;
  rclcpp::Subscription<uav_test::msg::UAVCmd>::SharedPtr cmd_sub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<UavNode>());
  rclcpp::shutdown();
  return 0;
}
