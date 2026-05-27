cmake_minimum_required(VERSION 3.5)
project(uav_test)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

set(msg_files
  "msg/UAVStatus.msg"
  "msg/UAVCmd.msg"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${msg_files}
  DEPENDENCIES std_msgs
)

add_executable(uav_node src/uav_node.cpp)
ament_target_dependencies(uav_node rclcpp std_msgs)
rosidl_target_interfaces(uav_node ${PROJECT_NAME} "rosidl_typesupport_cpp")

add_executable(center_node src/center_node.cpp)
ament_target_dependencies(center_node rclcpp std_msgs)
rosidl_target_interfaces(center_node ${PROJECT_NAME} "rosidl_typesupport_cpp")

install(TARGETS
  uav_node
  center_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY msg
  DESTINATION share/${PROJECT_NAME}
)

ament_export_dependencies(rosidl_default_runtime)

ament_package()
