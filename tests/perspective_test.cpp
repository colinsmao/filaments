#include "point_renderer.h"
#include <GLFW/glfw3.h>
#include <glm/gtc/matrix_transform.hpp>
#include <iostream>

int main() {
    if (!glfwInit()) return 1;
    glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    GLFWwindow* window = glfwCreateWindow(320, 240, "Perspective test", nullptr, nullptr);
    if (!window) { glfwTerminate(); return 1; }
    glfwMakeContextCurrent(window);
    if (!gladLoadGLLoader(reinterpret_cast<GLADloadproc>(glfwGetProcAddress))) {
        glfwDestroyWindow(window); glfwTerminate(); return 1;
    }
    int result = 0;
    try {
        PointRenderer points;
        // Startup can render frames before the Python worker uploads any stars.
        points.drawCubes(glm::mat4(1), 1);
        points.draw(glm::mat4(1), 1, 120);
        glFinish();
        if (glGetError() != GL_NO_ERROR) throw std::runtime_error("Empty startup draw caused an OpenGL error");
        points.setPoints({{{-0.8f, 0, -4}, {1, 0, 0}, 0.2f}, {{1.6f, 0, -8}, {0, 1, 0}, 0.2f}});
        int width, height;
        glfwGetFramebufferSize(window, &width, &height);
        glViewport(0, 0, width, height);
        glEnable(GL_PROGRAM_POINT_SIZE);
        glEnable(GL_DEPTH_TEST);
        glClearColor(0, 0, 0, 1);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        const auto projection = glm::perspective(glm::radians(45.0f), float(width) / height, 0.01f, 100.0f);
        points.draw(projection, 1.0f, height * 0.5f * projection[1][1], false);
        std::vector<unsigned char> pixels(static_cast<size_t>(width) * height * 3);
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, pixels.data());
        size_t nearPixels = 0, farPixels = 0;
        for (size_t i = 0; i < pixels.size(); i += 3) {
            if (pixels[i] > 200 && pixels[i + 1] < 20) ++nearPixels;
            if (pixels[i + 1] > 200 && pixels[i] < 20) ++farPixels;
        }
        // Twice the depth means half the diameter and roughly one quarter area.
        if (farPixels < 16 || nearPixels < 3 * farPixels || nearPixels > 5 * farPixels)
            throw std::runtime_error("Near/far point footprints do not follow perspective");
        if (glGetError() != GL_NO_ERROR) throw std::runtime_error("OpenGL error in perspective test");
        std::cout << "Perspective verified: near " << nearPixels << " pixels, far " << farPixels << " pixels\n";
        const auto read = [&]() {
            glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, pixels.data());
        };
        const auto checkSizeRatio = [&]() {
            read();
            size_t red = 0, green = 0;
            for (size_t i = 0; i < pixels.size(); i += 3) {
                if (pixels[i] > 40 && pixels[i + 1] == 0) ++red;
                if (pixels[i + 1] > 40 && pixels[i] == 0) ++green;
            }
            if (green < 16 || red < 3 * green || red > 5 * green)
                throw std::runtime_error("Individual star sizes did not control their visible footprints");
        };
        points.setPoints({{{-0.8f, 0, -4}, {1, 0, 0}, 0.4f}, {{0.8f, 0, -4}, {0, 1, 0}, 0.2f}});
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        points.draw(projection, 1, height * 0.5f * projection[1][1], false);
        checkSizeRatio();
        // Same buffer, different VAO/program: tests per-instance offsets and sizes.
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        points.drawCubes(projection, 1);
        checkSizeRatio();

        points.setPoints({{{0, 0, 0}, {1, 1, 1}, 1}});
        // Turning to the opposite horizontal faces must keep the same block tones.
        for (float side : {1.0f, -1.0f}) {
            const auto view = glm::lookAt(glm::vec3(3 * side, 2, 4 * side), glm::vec3(0), glm::vec3(0, 1, 0));
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
            points.drawCubes(projection * view, 1);
            read();
            size_t dark = 0, medium = 0, bright = 0;
            for (size_t i = 0; i < pixels.size(); i += 3) {
                const int light = pixels[i];
                if (light >= 207 && light <= 211) ++dark;
                if (light >= 233 && light <= 237) ++medium;
                if (light >= 253) ++bright;
            }
            if (dark < 100 || medium < 100 || bright < 100)
                throw std::runtime_error("Cube faces are missing or do not have distinct lighting");
        }
        // Drawing the farther star last must still leave the near star in front.
        points.setPoints({{{0, 0, -4}, {1, 0, 0}, 0.8f}, {{0, 0, -6}, {0, 1, 0}, 0.8f}});
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        points.drawCubes(projection, 1);
        read();
        const auto center = (static_cast<size_t>(height / 2) * width + width / 2) * 3;
        if (pixels[center] < 150 || pixels[center + 1] != 0)
            throw std::runtime_error("Overlapping cubes did not respect depth");
        if (glGetError() != GL_NO_ERROR) throw std::runtime_error("OpenGL error in cube test");
        std::cout << "Per-star point/cube sizes, shaded faces, instancing and overlap depth verified\n";
        std::vector<Point> largeCloud(100000);
        for (size_t i = 0; i < largeCloud.size(); ++i) {
            largeCloud[i] = {{float(i % 100) * 0.04f - 2, float((i / 100) % 100) * 0.04f - 2,
                             -4.0f - float(i / 10000) * 0.04f}, {1, 0.8f, 0.5f}, 0.04f};
        }
        points.setPoints(largeCloud);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        points.drawCubes(projection, 1);
        glFinish();
        if (glGetError() != GL_NO_ERROR) throw std::runtime_error("Large instanced draw failed");
        std::cout << "100,000-star cube draw passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; result = 1; }
    glfwDestroyWindow(window);
    glfwTerminate();
    return result;
}
