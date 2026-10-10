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
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

struct Point { glm::vec3 position; glm::vec3 color; };

GLuint shader(GLenum type, const char* source) {
    const GLuint id = glCreateShader(type);
    glShaderSource(id, 1, &source, nullptr);
    glCompileShader(id);
    GLint ok = 0;
    glGetShaderiv(id, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[4096]{};
        glGetShaderInfoLog(id, sizeof(log), nullptr, log);
        glDeleteShader(id);
        throw std::runtime_error(log);
    }
    return id;
}

// One position/color buffer and one draw call, independent of point count.
class PointRenderer {
    GLuint vao = 0, vbo = 0, program = 0;
    GLint matrixLocation = -1, sizeLocation = -1, roundLocation = -1;
    GLsizei count = 0;
public:
    PointRenderer() {
        const char* vs = R"(#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec3 color;
uniform mat4 viewProjection;
uniform float pointSize;
out vec3 vertexColor;
void main() {
    gl_Position = viewProjection * vec4(position, 1.0);
    gl_PointSize = pointSize;
    vertexColor = color;
})";
        const char* fs = R"(#version 330 core
in vec3 vertexColor;
uniform bool roundPoints;
out vec4 fragColor;
void main() {
    if (roundPoints) {
        vec2 p = gl_PointCoord * 2.0 - 1.0;
        if (dot(p, p) > 1.0) discard;
    }
    fragColor = vec4(vertexColor, 1.0);
})";
        const GLuint vertex = shader(GL_VERTEX_SHADER, vs);
        const GLuint fragment = shader(GL_FRAGMENT_SHADER, fs);
        program = glCreateProgram();
        glAttachShader(program, vertex);
        glAttachShader(program, fragment);
        glLinkProgram(program);
        glDeleteShader(vertex);
        glDeleteShader(fragment);
        GLint ok = 0;
        glGetProgramiv(program, GL_LINK_STATUS, &ok);
        if (!ok) {
            char log[4096]{};
            glGetProgramInfoLog(program, sizeof(log), nullptr, log);
            glDeleteProgram(program);
            throw std::runtime_error(log);
        }
        matrixLocation = glGetUniformLocation(program, "viewProjection");
        sizeLocation = glGetUniformLocation(program, "pointSize");
        roundLocation = glGetUniformLocation(program, "roundPoints");
        glGenVertexArrays(1, &vao);
        glGenBuffers(1, &vbo);
        glBindVertexArray(vao);
        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(Point), reinterpret_cast<void*>(offsetof(Point, position)));
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(Point), reinterpret_cast<void*>(offsetof(Point, color)));
        glEnableVertexAttribArray(0);
        glEnableVertexAttribArray(1);
        glBindVertexArray(0);
    }
    ~PointRenderer() {
        glDeleteBuffers(1, &vbo);
        glDeleteVertexArrays(1, &vao);
        glDeleteProgram(program);
    }
    PointRenderer(const PointRenderer&) = delete;
    PointRenderer& operator=(const PointRenderer&) = delete;
    void setPoints(const std::vector<Point>& points) {
        count = static_cast<GLsizei>(points.size());
        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glBufferData(GL_ARRAY_BUFFER, static_cast<GLsizeiptr>(points.size() * sizeof(Point)), points.data(), GL_STATIC_DRAW);
    }
    void draw(const glm::mat4& matrix, float size, bool round = true, GLenum mode = GL_POINTS) const {
        glUseProgram(program);
        glUniformMatrix4fv(matrixLocation, 1, GL_FALSE, glm::value_ptr(matrix));
        glUniform1f(sizeLocation, size);
        glUniform1i(roundLocation, round);
        glBindVertexArray(vao);
        glDrawArrays(mode, 0, count);
        glBindVertexArray(0);
    }
};

std::vector<Point> makeCloud(int count) {
    std::vector<Point> points;
    points.reserve(count);
    std::mt19937 rng(42);
    std::uniform_real_distribution<float> uniform(0.0f, 1.0f);
    std::normal_distribution<float> noise(0.0f, 0.14f);
    for (int i = 0; i < count; ++i) {
        const float t = uniform(rng), angle = t * 28.0f + float(i % 3) * 2.0944f;
        const float radius = 2.2f + 0.8f * std::sin(t * 10.0f);
        const glm::vec3 p(radius * std::cos(angle) + noise(rng), (t - 0.5f) * 10.0f + noise(rng), radius * std::sin(angle) + noise(rng));
        const glm::vec3 c = glm::mix(glm::vec3(0.2f, 0.75f, 1.0f), glm::vec3(1.0f, 0.48f, 0.2f), t);
        points.push_back({p, c});
    }
    return points;
}

int render(GLFWwindow* window, bool smoke) {
    PointRenderer cloud, axes;
    int requestedCount = 100000, pointCount = requestedCount;
    cloud.setPoints(makeCloud(pointCount));
    axes.setPoints({{{0,0,0},{1,0.3f,0.3f}},{{5,0,0},{1,0.3f,0.3f}},
                    {{0,0,0},{0.3f,1,0.5f}},{{0,5,0},{0.3f,1,0.5f}},
                    {{0,0,0},{0.4f,0.5f,1}},{{0,0,5},{0.4f,0.5f,1}}});
    Camera camera;
    CameraControls controls;
    // Smoke tests use defaults and never read or overwrite personal preferences.
    const auto settingsPath = controlSettingsPath();
    if (!smoke) {
        const auto saved = loadControlSettings(settingsPath);
        controls.mode = static_cast<CameraControls::Mode>(saved.cameraMode);
        controls.sensitivity = saved.sensitivity;
        controls.speed = saved.moveSpeed;
        // A restored first-person mode starts with the mouse free for the GUI.
    }
    float size = 2.0f;
    bool showAxes = true, round = true, vsync = true;
    float background[3] = {0.025f, 0.035f, 0.055f};
    float sizeRange[2]{};
    glGetFloatv(GL_POINT_SIZE_RANGE, sizeRange);
    glEnable(GL_DEPTH_TEST);
    glEnable(GL_PROGRAM_POINT_SIZE);
    int frame = 0;
    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();
        controls.checkFocus(window);
        int width, height;
        glfwGetFramebufferSize(window, &width, &height);
        if (width == 0 || height == 0) { glfwWaitEventsTimeout(0.1); continue; }
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();
        auto& io = ImGui::GetIO();
        ImGui::SetNextWindowPos(ImVec2(16, 16), ImGuiCond_FirstUseEver);
        ImGui::SetNextWindowSize(ImVec2(300, 0), ImGuiCond_FirstUseEver);
        ImGui::Begin("Filaments", nullptr, ImGuiWindowFlags_AlwaysAutoResize);
        ImGui::Text("%s", "3D point viewer / OpenGL 3.3");
        ImGui::Separator();
        const bool wasCaptured = controls.captured();
        ImGui::BeginDisabled(wasCaptured);
        int mode = controls.mode;
        if (ImGui::Combo("Camera (F)", &mode, "Drag / orbit\0First person\0"))
            controls.setMode(window, static_cast<CameraControls::Mode>(mode));
        ImGui::SliderFloat("Sensitivity", &controls.sensitivity, 0.02f, 0.5f, "%.2f");
        ImGui::SliderFloat("Move speed", &controls.speed, 0.1f, 50.0f, "%.1f", ImGuiSliderFlags_Logarithmic);
        ImGui::Separator();
        ImGui::Text("%d points | %.1f FPS", pointCount, io.Framerate);
        ImGui::Text("GPU point buffer: %.1f MiB", pointCount * sizeof(Point) / (1024.0 * 1024.0));
        ImGui::SliderInt("Points", &requestedCount, 1000, 1000000, "%d", ImGuiSliderFlags_Logarithmic);
        if (ImGui::Button("Generate sample")) {
            cloud.setPoints(makeCloud(requestedCount));
            pointCount = requestedCount;
        }
        ImGui::SliderFloat("Point size", &size, std::max(1.0f, sizeRange[0]), std::min(12.0f, sizeRange[1]), "%.1f px");
        ImGui::Checkbox("Round points", &round);
        ImGui::Checkbox("Axes", &showAxes);
        if (ImGui::Checkbox("VSync", &vsync)) glfwSwapInterval(vsync ? 1 : 0);
        ImGui::ColorEdit3("Background", background);
        if (ImGui::Button("Reset camera (R)")) camera = Camera{};
        ImGui::EndDisabled();
        ImGui::Separator();
        if (controls.mode == CameraControls::FirstPerson) {
            ImGui::TextUnformatted(controls.captured() ? "Mouse captured: move to look" : "Mouse free: click scene to look");
            ImGui::TextUnformatted("Tab: capture / release\nEsc: release mouse\nF: switch to drag controls");
        } else {
            ImGui::TextUnformatted("Left drag: orbit\nMiddle drag: pan\nRight drag: look\nWheel: zoom\nF: switch to first person\nEsc: quit");
        }
        ImGui::TextUnformatted("WASD: move | R: reset\nSpace / E: up | Shift / Q: down");
        ImGui::End();
        controls.update(window, camera, io);
        if (smoke && frame == 1) {
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
        const auto matrix = camera.projection(float(width) / float(height)) * camera.view();
        cloud.draw(matrix, size, round);
        if (showAxes) axes.draw(matrix, 1.0f, false, GL_LINES);
        if (smoke && frame == 3) {
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
        if (smoke && frame == 3) {
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
        ++frame;
    }
    controls.capture(window, false);
    if (!smoke && !saveControlSettings(settingsPath, {controls.mode, controls.sensitivity, controls.speed}))
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
