#pragma once
#include <GLFW/glfw3.h>
#include <imgui.h>
#include "camera.h"

class CameraControls {
public:
    enum Mode { Drag, FirstPerson };
    Mode mode = Drag;
    float sensitivity = 0.10f;
    float speed = 5.0f;
    float zoomFactor = 3.0f;

    float zoomMultiplier() const { return zoomHeld ? zoomFactor : 1.0f; }

    void updateZoom(bool rightDown, bool allowed) {
        if (!rightDown || !allowed) zoomHeld = false;
        else if (!rightWasDown) zoomHeld = true;
        rightWasDown = rightDown;
    }

    bool captured() const { return mouseCaptured; }

    void capture(GLFWwindow* window, bool enabled) {
        if (!enabled) zoomHeld = false;
        if (mouseCaptured == enabled) return;
        mouseCaptured = enabled;
        // Disabled cursor gives unbounded virtual coordinates; raw motion avoids
        // desktop mouse acceleration where supported. ImGui must not consume it.
        auto& io = ImGui::GetIO();
        if (enabled) io.ConfigFlags |= ImGuiConfigFlags_NoMouse;
        else io.ConfigFlags &= ~ImGuiConfigFlags_NoMouse;
        glfwSetInputMode(window, GLFW_CURSOR, enabled ? GLFW_CURSOR_DISABLED : GLFW_CURSOR_NORMAL);
        if (glfwRawMouseMotionSupported())
            glfwSetInputMode(window, GLFW_RAW_MOUSE_MOTION, enabled ? GLFW_TRUE : GLFW_FALSE);
        resetMouse = true;
        skipDragMouse = true;
    }

    void setMode(GLFWwindow* window, Mode next) {
        mode = next;
        capture(window, mode == FirstPerson && glfwGetWindowAttrib(window, GLFW_FOCUSED));
    }

    void checkFocus(GLFWwindow* window) {
        if (!glfwGetWindowAttrib(window, GLFW_FOCUSED)) capture(window, false);
    }

    // Always seed a fresh baseline on capture so cursor warps cannot turn the camera.
    void mouseLook(Camera& camera, double x, double y) {
        if (!resetMouse)
            camera.rotate(static_cast<float>(x - lastX), static_cast<float>(y - lastY), true, sensitivity / zoomMultiplier());
        lastX = x;
        lastY = y;
        resetMouse = false;
    }

    void update(GLFWwindow* window, Camera& camera, const ImGuiIO& io) {
        checkFocus(window);
        if (!glfwGetWindowAttrib(window, GLFW_FOCUSED)) { updateZoom(false, false); return; }
        const bool ignoreDragMouse = skipDragMouse;
        skipDragMouse = false;
        if (mouseCaptured || !io.WantCaptureKeyboard) {
            if (ImGui::IsKeyPressed(ImGuiKey_Escape, false)) {
                if (mode == FirstPerson) capture(window, false);
                else glfwSetWindowShouldClose(window, true);
                return;
            }
            if (ImGui::IsKeyPressed(ImGuiKey_F, false)) {
                setMode(window, mode == Drag ? FirstPerson : Drag);
                return;
            }
            if (mode == FirstPerson && ImGui::IsKeyPressed(ImGuiKey_Tab, false)) {
                capture(window, !mouseCaptured);
                return;
            }
        }
        updateZoom(glfwGetMouseButton(window, GLFW_MOUSE_BUTTON_RIGHT) == GLFW_PRESS,
                   mouseCaptured || (mode == Drag && !io.WantCaptureMouse && !ignoreDragMouse));
        if (mode == FirstPerson) {
            if (!mouseCaptured) {
                if (!io.WantCaptureMouse && ImGui::IsMouseClicked(ImGuiMouseButton_Left))
                    capture(window, true);
                return; // GUI interaction never moves the first-person camera.
            }
            double x, y;
            glfwGetCursorPos(window, &x, &y);
            mouseLook(camera, x, y);
        } else if (!io.WantCaptureMouse && !ignoreDragMouse) {
            if (ImGui::IsMouseDragging(ImGuiMouseButton_Left, 0.0f))
                camera.rotate(io.MouseDelta.x, io.MouseDelta.y, false, sensitivity / zoomMultiplier());
            if (ImGui::IsMouseDragging(ImGuiMouseButton_Middle, 0.0f))
                camera.pan(io.MouseDelta.x, io.MouseDelta.y, io.DisplaySize.y, zoomMultiplier());
            camera.zoom(io.MouseWheel);
        }
        if (mouseCaptured || !io.WantCaptureKeyboard) {
            glm::vec3 movement(0.0f);
            if (ImGui::IsKeyDown(ImGuiKey_W)) movement += camera.forward();
            if (ImGui::IsKeyDown(ImGuiKey_S)) movement -= camera.forward();
            if (ImGui::IsKeyDown(ImGuiKey_D)) movement += camera.right();
            if (ImGui::IsKeyDown(ImGuiKey_A)) movement -= camera.right();
            if (ImGui::IsKeyDown(ImGuiKey_Space) || ImGui::IsKeyDown(ImGuiKey_E)) movement.y += 1.0f;
            if (io.KeyShift || ImGui::IsKeyDown(ImGuiKey_Q)) movement.y -= 1.0f;
            if (glm::length(movement) > 0.0f)
                camera.target += glm::normalize(movement) * std::min(io.DeltaTime, 0.05f) * speed;
            if (ImGui::IsKeyPressed(ImGuiKey_R, false)) camera = Camera{};
        }
    }

private:
    bool mouseCaptured = false, resetMouse = true, skipDragMouse = false;
    bool zoomHeld = false, rightWasDown = false;
    double lastX = 0.0, lastY = 0.0;
};
