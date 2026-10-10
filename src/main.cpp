#include <glad/glad.h>
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_opengl3.h>
#include <glm/gtc/type_ptr.hpp>
#include "camera.h"
#include "camera_controls.h"
#include "settings.h"
#include <cstddef>
#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "point_renderer.h"
#include "generation.h"
#include "generator_panel.h"

int render(GLFWwindow* window, bool smoke) {
    if (smoke) std::fprintf(stderr, "Smoke: initializing renderers\n");
    PointRenderer cloud, axes;
    int pointCount = 0;
    auto plot = smoke ? PlotSettings{} : loadPlotSettings(plotSettingsPath());
    GeneratorPanel generator(plot.generator);
    if (smoke) std::fprintf(stderr, "Smoke: generator queued\n");
    glm::vec3 cloudCenter(0.0f);
    float cloudRadius = 5.0f;
    double uploadMs = 0;
    axes.setPoints({{{0,0,0},{1,0.3f,0.3f}},{{5,0,0},{1,0.3f,0.3f}},
                    {{0,0,0},{0.3f,1,0.5f}},{{0,5,0},{0.3f,1,0.5f}},
                    {{0,0,0},{0.4f,0.5f,1}},{{0,0,5},{0.4f,0.5f,1}}});
    Camera camera = plot.hasCamera ? plot.camera : Camera{};
    CameraControls controls;
    // Smoke tests use defaults and never read or overwrite personal preferences.
    const auto settingsPath = controlSettingsPath();
    if (!smoke) {
        const auto saved = loadControlSettings(settingsPath);
        controls.mode = static_cast<CameraControls::Mode>(saved.cameraMode);
        controls.sensitivity = saved.sensitivity;
        controls.speed = saved.moveSpeed;
        controls.zoomFactor = saved.zoomFactor;
        // A restored first-person mode starts with the mouse free for the GUI.
    }
    auto& size = plot.sizeScale;
    auto& showAxes = plot.showAxes;
    auto& round = plot.round;
    auto& vsync = plot.vsync;
    auto& background = plot.background;
    glfwSwapInterval(!smoke && vsync ? 1 : 0);
    glEnable(GL_DEPTH_TEST);
    glEnable(GL_PROGRAM_POINT_SIZE);
    int frame = 0;
    const double started = glfwGetTime();
    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();
        controls.checkFocus(window);
        if (auto points = generator.tick(glfwGetTime())) {
            const bool firstCloud = pointCount == 0;
            glm::vec3 low = points->front().position, high = low;
            for (const auto& point : *points) {
                low = glm::min(low, point.position);
                high = glm::max(high, point.position);
            }
            cloudCenter = (low + high) * 0.5f;
            cloudRadius = std::max(glm::length(high - low) * 0.5f, 0.1f);
            const double uploadStart = glfwGetTime();
            cloud.setPoints(*points);
            uploadMs = (glfwGetTime() - uploadStart) * 1000;
            pointCount = static_cast<int>(points->size());
            if (smoke) std::fprintf(stderr, "Smoke: uploaded %d stars\n", pointCount);
            if (firstCloud && !plot.hasCamera) { camera.target = cloudCenter; camera.distance = std::min(cloudRadius * 2.8f, 2000.0f); }
        }
        if (smoke && !generator.lastError().empty()) throw std::runtime_error(generator.lastError());
        if (smoke && glfwGetTime() - started > 30.0) throw std::runtime_error("Generator smoke test timed out");
        int width, height;
        glfwGetFramebufferSize(window, &width, &height);
        if (width == 0 || height == 0) { glfwWaitEventsTimeout(0.1); continue; }
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();
        auto& io = ImGui::GetIO();
        ImGui::SetNextWindowPos(ImVec2(16, 16), ImGuiCond_FirstUseEver);
        ImGui::SetNextWindowSize(ImVec2(380, 0), ImGuiCond_FirstUseEver);
        ImGui::SetNextWindowSizeConstraints(ImVec2(330, 100), ImVec2(440, std::max(100.0f, io.DisplaySize.y - 32)));
        ImGui::Begin("Filaments", nullptr, ImGuiWindowFlags_AlwaysAutoResize);
        ImGui::Text("%s", "3D point viewer / OpenGL 3.3");
        ImGui::Separator();
        const bool wasCaptured = controls.captured();
        ImGui::BeginDisabled(wasCaptured);
        generator.draw(glfwGetTime());
        ImGui::Separator();
        int mode = controls.mode;
        if (ImGui::Combo("Camera (F)", &mode, "Drag / orbit\0First person\0"))
            controls.setMode(window, static_cast<CameraControls::Mode>(mode));
        ImGui::SliderFloat("Sensitivity", &controls.sensitivity, 0.02f, 0.5f, "%.2f");
        ImGui::SliderFloat("Move speed", &controls.speed, 0.1f, 50.0f, "%.1f", ImGuiSliderFlags_Logarithmic);
        ImGui::SliderFloat("Right-click zoom", &controls.zoomFactor, 1.0f, 10.0f, "%.1fx", ImGuiSliderFlags_AlwaysClamp);
        ImGui::Separator();
        ImGui::Text("%d points | %.1f FPS", pointCount, io.Framerate);
        ImGui::Text("GPU point buffer: %.1f MiB", pointCount * sizeof(Point) / (1024.0 * 1024.0));
        ImGui::Text("Upload (CPU): %.1f ms", uploadMs);
        if (ImGui::CollapsingHeader("Display")) {
            ImGui::Combo("Draw as", &plot.renderMode, "Shaded cubes\0Points (fast)\0");
            ImGui::SliderFloat("Star size scale", &size, 0.05f, 20.0f, "%.2fx", ImGuiSliderFlags_Logarithmic);
            if (plot.renderMode == 1) ImGui::Checkbox("Round points", &round);
            ImGui::Checkbox("Axes", &showAxes);
            if (ImGui::Checkbox("VSync", &vsync)) glfwSwapInterval(vsync ? 1 : 0);
            ImGui::ColorEdit3("Background", background);
        }
        if (ImGui::Button("Reset camera (R)")) camera = Camera{};
        ImGui::SameLine();
        if (ImGui::Button("Fit cloud")) { camera.target = cloudCenter; camera.distance = std::min(cloudRadius * 2.8f, 2000.0f); }
        ImGui::EndDisabled();
        ImGui::TextDisabled("Plot and camera settings saved on exit");
        ImGui::Separator();
        if (controls.captured()) ImGui::TextUnformatted("Tab / Esc: release | G: new seed");
        if (ImGui::CollapsingHeader("Controls")) {
        if (controls.mode == CameraControls::FirstPerson) {
            ImGui::TextUnformatted(controls.captured() ? "Mouse captured: move to look" : "Mouse free: click scene to look");
            ImGui::TextUnformatted("Tab: capture / release\nEsc: release mouse\nF: switch to drag controls");
        } else {
            ImGui::TextUnformatted("Left drag: orbit\nMiddle drag: pan\nWheel: move closer / farther\nF: switch to first person\nEsc: quit");
        }
        ImGui::TextUnformatted("Hold right mouse: zoom in\nWASD: move | R: reset\nSpace / E: up | Shift / Q: down\nG: random seed + regenerate");
        }
        ImGui::End();
        // Draw over the scene, underneath GUI panels, in logical viewport pixels.
        const auto* viewport = ImGui::GetMainViewport();
        const ImVec2 center(std::floor(viewport->Pos.x + viewport->Size.x * 0.5f) + 0.5f,
                            std::floor(viewport->Pos.y + viewport->Size.y * 0.5f) + 0.5f);
        auto* overlay = ImGui::GetBackgroundDrawList();
        for (int outline = 1; outline >= 0; --outline) {
            const auto color = outline ? IM_COL32(0, 0, 0, 170) : IM_COL32(240, 240, 240, 230);
            const float thickness = outline ? 3.0f : 1.0f;
            overlay->AddLine(ImVec2(center.x - 5, center.y), ImVec2(center.x + 5, center.y), color, thickness);
            overlay->AddLine(ImVec2(center.x, center.y - 5), ImVec2(center.x, center.y + 5), color, thickness);
        }
        if (glfwGetWindowAttrib(window, GLFW_FOCUSED)) generator.handleShortcuts(controls.captured());
        controls.update(window, camera, io);
        if (smoke && pointCount > 0 && frame == 1) {
            // Verify capture flags, initial mouse rebasing, rotation and release.
            // The hidden test window is not focused, so explicitly exercise capture.
            Camera probe;
            const auto probeEye = probe.eye();
            const float initialYaw = probe.yaw;
            controls.setMode(window, CameraControls::FirstPerson);
            controls.capture(window, true);
            if (glfwGetInputMode(window, GLFW_CURSOR) != GLFW_CURSOR_DISABLED ||
                !(io.ConfigFlags & ImGuiConfigFlags_NoMouse))
                throw std::runtime_error("First-person capture failed");
            controls.mouseLook(probe, 4000, 3000);
            if (probe.yaw != initialYaw) throw std::runtime_error("Capture caused camera jump");
            controls.mouseLook(probe, 4040, 3020);
            if (probe.yaw >= initialYaw || glm::length(probe.eye() - probeEye) > 0.0001f)
                throw std::runtime_error("First-person look changed position or wrong direction");
            controls.capture(window, false);
            controls.capture(window, true);
            const float recaptureYaw = probe.yaw;
            controls.mouseLook(probe, -1000, -2000);
            if (probe.yaw != recaptureYaw) throw std::runtime_error("Recapture caused camera jump");
            controls.checkFocus(window);
            if (controls.captured()) throw std::runtime_error("Focus loss did not release mouse");
            controls.setMode(window, CameraControls::Drag);
            if (glfwGetInputMode(window, GLFW_CURSOR) != GLFW_CURSOR_NORMAL ||
                (io.ConfigFlags & ImGuiConfigFlags_NoMouse))
                throw std::runtime_error("Mouse release failed");
            std::printf("Smoke: first-person capture, look, recapture and focus release OK\n");
            // Exercise camera paths and resize, including non-square projection.
            const auto oldEye = camera.eye();
            camera.rotate(20.0f, -10.0f, true);
            if (glm::length(camera.eye() - oldEye) > 0.0001f) throw std::runtime_error("Fly rotation moved camera position");
            camera.rotate(-10.0f, 5.0f);
            camera.pan(4.0f, -2.0f, 600.0f);
            camera.zoom(1.0f);
            glfwSetWindowSize(window, 960, 640);
        }
        glViewport(0, 0, width, height);
        glClearColor(background[0], background[1], background[2], 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        const auto projection = camera.projection(float(width) / float(height), controls.zoomMultiplier());
        const auto matrix = projection * camera.view();
        const float projectionScale = 0.5f * float(height) * projection[1][1];
        if (plot.renderMode == 0) cloud.drawCubes(matrix, size);
        else cloud.draw(matrix, size, projectionScale, round);
        if (showAxes) axes.draw(matrix, size, projectionScale, false, GL_LINES);
        if (smoke && pointCount > 0 && frame == 3) {
            // Read before the GUI so a blank 3D scene cannot pass the smoke test.
            std::vector<unsigned char> pixels(static_cast<size_t>(width) * height * 3);
            glPixelStorei(GL_PACK_ALIGNMENT, 1);
            glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, pixels.data());
            size_t colored = 0;
            for (size_t i = 0; i < pixels.size(); i += 3)
                if (pixels[i] > 60 || pixels[i + 1] > 60 || pixels[i + 2] > 60) ++colored;
            if (colored < 1000) throw std::runtime_error("Point cloud did not render");
            std::printf("Smoke: %zu visible scene pixels, %d points, camera and resize OK\n", colored, pointCount);
        }
        ImGui::Render();
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        if (smoke && pointCount > 0 && frame == 3) {
            std::vector<unsigned char> pixels(static_cast<size_t>(width) * height * 3);
            glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, pixels.data());
            std::ofstream image("smoke.ppm", std::ios::binary);
            image << "P6\n" << width << ' ' << height << "\n255\n";
            for (int y = height - 1; y >= 0; --y)
                image.write(reinterpret_cast<const char*>(pixels.data() + static_cast<size_t>(y) * width * 3), width * 3);
            if (glGetError() != GL_NO_ERROR) throw std::runtime_error("OpenGL error during smoke test");
            glfwSetWindowShouldClose(window, true);
        }
        glfwSwapBuffers(window);
        if (pointCount > 0) ++frame;
    }
    controls.capture(window, false);
    if (!smoke) {
        plot.generator = generator.settings();
        plot.camera = camera;
        plot.hasCamera = true;
        if (!savePlotSettings(plotSettingsPath(), plot)) std::fprintf(stderr, "Could not save plot settings\n");
    }
    if (!smoke && !saveControlSettings(settingsPath, {controls.mode, controls.sensitivity, controls.speed, controls.zoomFactor}))
        std::fprintf(stderr, "Could not save camera control settings\n");
    return 0;
}

int main(int argc, char** argv) {
    const bool smoke = argc > 1 && std::string(argv[1]) == "--smoke-test";
    glfwSetErrorCallback([](int code, const char* description) { std::fprintf(stderr, "GLFW %d: %s\n", code, description); });
    if (!glfwInit()) return 1;
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
#ifdef __APPLE__
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GLFW_TRUE);
#endif
    if (smoke) glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE);
    GLFWwindow* window = glfwCreateWindow(1280, 800, "Filaments", nullptr, nullptr);
    if (!window) { glfwTerminate(); return 1; }
    glfwMakeContextCurrent(window);
    if (!gladLoadGLLoader(reinterpret_cast<GLADloadproc>(glfwGetProcAddress))) {
        std::fprintf(stderr, "OpenGL loader failed\n");
        glfwDestroyWindow(window); glfwTerminate(); return 1;
    }
    glfwSwapInterval(smoke ? 0 : 1);
    std::printf("GPU: %s\nDriver OpenGL: %s\nApplication baseline: OpenGL 3.3 / GLSL 330\n", glGetString(GL_RENDERER), glGetString(GL_VERSION));
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGui::GetIO().IniFilename = nullptr;
    ImGui::StyleColorsDark();
    if (!ImGui_ImplGlfw_InitForOpenGL(window, true) || !ImGui_ImplOpenGL3_Init("#version 330 core")) {
        std::fprintf(stderr, "ImGui backend initialization failed\n");
        ImGui::DestroyContext(); glfwDestroyWindow(window); glfwTerminate(); return 1;
    }
    int result = 0;
    try { result = render(window, smoke); }
    catch (const std::exception& error) { std::fprintf(stderr, "%s\n", error.what()); result = 1; }
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(window);
    glfwTerminate();
    return result;
}
