#include <chrono>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "uav_test/msg/uav_cmd.hpp"
#include "uav_test/msg/uav_status.hpp"

using namespace std::chrono_literals;

class CenterNode : public rclcpp::Node {
 public:
  CenterNode() : Node("center_node"), index_(0) {
    status_subs_.push_back(this->create_subscription<uav_test::msg::UAVStatus>(
        "/uav1/status", 10,
        [this](const uav_test::msg::UAVStatus::SharedPtr msg) {
          RCLCPP_INFO(this->get_logger(), "[Center] 收到心跳 - 来自: %s", msg->uav_id.c_str());
        }));
    status_subs_.push_back(this->create_subscription<uav_test::msg::UAVStatus>(
        "/uav2/status", 10,
        [this](const uav_test::msg::UAVStatus::SharedPtr msg) {
          RCLCPP_INFO(this->get_logger(), "[Center] 收到心跳 - 来自: %s", msg->uav_id.c_str());
        }));
    status_subs_.push_back(this->create_subscription<uav_test::msg::UAVStatus>(
        "/uav3/status", 10,
        [this](const uav_test::msg::UAVStatus::SharedPtr msg) {
          RCLCPP_INFO(this->get_logger(), "[Center] 收到心跳 - 来自: %s", msg->uav_id.c_str());
        }));

    cmd_pubs_.push_back(
        this->create_publisher<uav_test::msg::UAVCmd>("/uav1/cmd", 10));
    cmd_pubs_.push_back(
        this->create_publisher<uav_test::msg::UAVCmd>("/uav2/cmd", 10));
    cmd_pubs_.push_back(
        this->create_publisher<uav_test::msg::UAVCmd>("/uav3/cmd", 10));

    targets_ = {"uav1", "uav2", "uav3"};

    timer_ = this->create_wall_timer(1s, [this]() {
      const std::size_t idx = index_ % cmd_pubs_.size();
      uav_test::msg::UAVCmd msg;
      msg.header.stamp = this->now();
      msg.target_id = targets_[idx];
      msg.cmd_content = "PING";
      cmd_pubs_[idx]->publish(msg);
      index_ = (index_ + 1) % cmd_pubs_.size();
    });
  }

 private:
  std::vector<rclcpp::Subscription<uav_test::msg::UAVStatus>::SharedPtr> status_subs_;
  std::vector<rclcpp::Publisher<uav_test::msg::UAVCmd>::SharedPtr> cmd_pubs_;
  std::vector<std::string> targets_;
  std::size_t index_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<CenterNode>());
  rclcpp::shutdown();
  return 0;
}
