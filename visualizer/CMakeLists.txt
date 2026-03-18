cmake_minimum_required(VERSION 3.20)
project(agora-viz LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenGL REQUIRED)
find_package(glfw3 3.3 REQUIRED)
find_package(glm REQUIRED)
find_package(nlohmann_json 3.11 REQUIRED)
find_package(CURL REQUIRED)

add_executable(agora-viz
    src/main.cpp
    src/network.cpp
    src/renderer.cpp
)

target_include_directories(agora-viz PRIVATE src)

target_link_libraries(agora-viz PRIVATE
    OpenGL::GL
    glfw
    glm::glm
    nlohmann_json::nlohmann_json
    CURL::libcurl
)

if(APPLE)
    target_compile_definitions(agora-viz PRIVATE GL_SILENCE_DEPRECATION)
endif()
