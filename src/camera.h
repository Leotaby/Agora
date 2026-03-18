#pragma once
#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
#include <algorithm>

struct Camera {
    float distance = 18.0f;
    float yaw = 0.0f;
    float pitch = 0.45f;
    float auto_rotate_speed = 0.08f;
    bool dragging = false;
    double last_x = 0, last_y = 0;

    glm::vec3 eye() const {
        return glm::vec3(
            distance * cosf(pitch) * sinf(yaw),
            distance * sinf(pitch),
            distance * cosf(pitch) * cosf(yaw)
        );
    }

    glm::mat4 view() const {
        return glm::lookAt(eye(), glm::vec3(0.0f), glm::vec3(0, 1, 0));
    }

    glm::mat4 projection(float aspect) const {
        return glm::perspective(glm::radians(45.0f), aspect, 0.1f, 200.0f);
    }

    void drag(double dx, double dy) {
        yaw -= (float)dx * 0.005f;
        pitch += (float)dy * 0.005f;
        pitch = std::clamp(pitch, -1.2f, 1.4f);
    }

    void scroll(double y) {
        distance -= (float)y * 1.2f;
        distance = std::clamp(distance, 5.0f, 60.0f);
    }

    void update(float dt) {
        if (!dragging)
            yaw += auto_rotate_speed * dt;
    }
};
