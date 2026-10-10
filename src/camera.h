#pragma once
#include <algorithm>
#include <cmath>
#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>

// Orbit around target; fly controls translate target and eye together.
struct Camera {
    glm::vec3 target{0.0f};
    float yaw = 35.0f, pitch = 20.0f, distance = 18.0f;
    glm::vec3 forward() const {
        const float y = glm::radians(yaw), p = glm::radians(pitch);
        return {-std::cos(p) * std::sin(y), -std::sin(p), -std::cos(p) * std::cos(y)};
    }
    glm::vec3 right() const { return glm::normalize(glm::cross(forward(), glm::vec3(0, 1, 0))); }
    glm::vec3 up() const { return glm::cross(right(), forward()); }
    glm::vec3 eye() const { return target - forward() * distance; }
    glm::mat4 view() const { return glm::lookAt(eye(), target, up()); }
    glm::mat4 projection(float aspect, float magnification = 1.0f) const {
        const float fov = 2.0f * std::atan(std::tan(glm::radians(22.5f)) / magnification);
        return glm::perspective(fov, aspect, 0.01f, 10000.0f);
    }
    void rotate(float dx, float dy, bool fly = false, float sensitivity = 0.25f) {
        const auto oldEye = eye();
        yaw -= dx * sensitivity;
        pitch = std::clamp(pitch + dy * sensitivity, -89.0f, 89.0f);
        if (fly) target = oldEye + forward() * distance;
    }
    void zoom(float wheel) { distance = std::clamp(distance * std::exp(-wheel * 0.12f), 0.05f, 2000.0f); }
    void pan(float dx, float dy, float viewportHeight, float magnification = 1.0f) {
        const float units = 2.0f * distance * std::tan(glm::radians(22.5f)) / (std::max(viewportHeight, 1.0f) * magnification);
        target += (-right() * dx + up() * dy) * units;
    }
};
