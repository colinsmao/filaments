#include "camera_controls.h"
#include <iostream>
#include <stdexcept>

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

int main() {
    try {
        Camera camera;
        const auto eye = camera.eye();
        const auto base = camera.projection(1.5f);
        const auto zoomed = camera.projection(1.5f, 3);
        require(std::abs(zoomed[0][0] / base[0][0] - 3) < 0.0001f &&
                std::abs(zoomed[1][1] / base[1][1] - 3) < 0.0001f,
                "Zoom must magnify both screen dimensions by the configured factor");
        require(camera.eye() == eye, "FOV zoom must not move the camera");
        CameraControls controls;
        controls.zoomFactor = 4;
        controls.updateZoom(true, true);
        require(controls.zoomMultiplier() == 4, "Right press in scene should zoom");
        controls.updateZoom(true, true);
        require(controls.zoomMultiplier() == 4, "Holding right mouse should keep zoom");
        controls.updateZoom(false, true);
        require(controls.zoomMultiplier() == 1, "Release should restore normal FOV");
        controls.updateZoom(true, false);
        controls.updateZoom(true, true);
        require(controls.zoomMultiplier() == 1, "A press that started in the GUI must not zoom when dragged out");
        controls.updateZoom(false, true);
        controls.updateZoom(true, true);
        controls.updateZoom(true, false);
        require(controls.zoomMultiplier() == 1, "Losing camera interaction should release zoom");
        controls.updateZoom(false, true);
        controls.updateZoom(true, true);
        controls.mouseLook(camera, 100, 100);
        const float yaw = camera.yaw;
        controls.mouseLook(camera, 140, 100);
        require(std::abs(camera.yaw - (yaw - 40 * controls.sensitivity / 4)) < 0.0001f &&
                glm::length(camera.eye() - eye) < 0.0001f,
                "Zoomed mouse look should reduce sensitivity and preserve eye position");
        std::cout << "FOV zoom, hold/release, GUI gating and zoomed sensitivity passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
