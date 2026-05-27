cmake_minimum_required(VERSION 3.8)
project(dds_study)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# -------------------------------------------------------------------
# 1. 查找依赖
# -------------------------------------------------------------------
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

# -------------------------------------------------------------------
# 2. 生成自定义消息接口
# -------------------------------------------------------------------
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RelayPacket.msg"
  DEPENDENCIES std_msgs
)

# -------------------------------------------------------------------
# 3. 定义可执行文件与编译逻辑
# -------------------------------------------------------------------
set(dependencies "rclcpp" "std_msgs")

# 定义编译函数，减少重复代码
function(build_dds_node target_name source_file)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/${source_file})
        add_executable(${target_name} ${source_file})
        ament_target_dependencies(${target_name} ${dependencies})
        # 核心：将自定义消息接口链接到节点
        rosidl_target_interfaces(${target_name} ${PROJECT_NAME} "rosidl_typesupport_cpp")
        # 添加到安装列表
        install(TARGETS ${target_name} DESTINATION lib/${PROJECT_NAME})
    endif()
endfunction()

# --- 编译新节点 R1, R2, C (优先匹配新的 .cpp 文件) ---
# 请确保你的文件确实叫 R1.cpp 等，如果叫 publisher_oneway.cpp，函数会自动识别
build_dds_node(R1 src/R1.cpp)
if(NOT TARGET R1)
    build_dds_node(R1 src/publisher_oneway.cpp)
endif()

build_dds_node(R2 src/R2.cpp)
if(NOT TARGET R2)
    build_dds_node(R2 src/relay_oneway.cpp)
endif()

build_dds_node(C src/C.cpp)
if(NOT TARGET C)
    build_dds_node(C src/subscriber_oneway.cpp)
endif()

# --- 保留旧节点 (可选，如果不需要可以删掉) ---
build_dds_node(publisher src/publisher.cpp)
build_dds_node(subscriber src/subscriber.cpp)
build_dds_node(pub_sub src/publisher_and_subscriber.cpp)

# -------------------------------------------------------------------
# 4. 测试与导出
# -------------------------------------------------------------------
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
