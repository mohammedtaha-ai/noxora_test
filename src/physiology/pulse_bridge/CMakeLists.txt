cmake_minimum_required(VERSION 3.20)
if(POLICY CMP0144)
  cmake_policy(SET CMP0144 NEW)
endif()
project(nexora_pulse_bridge LANGUAGES CXX)

find_package(Pulse REQUIRED CONFIG)

add_executable(nexora_pulse_bridge main.cpp)
target_compile_features(nexora_pulse_bridge PRIVATE cxx_std_17)
target_link_libraries(nexora_pulse_bridge PRIVATE Pulse::Pulse)

target_compile_options(nexora_pulse_bridge PRIVATE -Wall -Wextra -Wpedantic)
