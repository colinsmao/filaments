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
        points.setPoints({{{-0.8f, 0, -4}, {1, 0, 0}}, {{1.6f, 0, -8}, {0, 1, 0}}});
        int width, height;
        glfwGetFramebufferSize(window, &width, &height);
        glViewport(0, 0, width, height);
        glEnable(GL_PROGRAM_POINT_SIZE);
        glEnable(GL_DEPTH_TEST);
        glClearColor(0, 0, 0, 1);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        const auto projection = glm::perspective(glm::radians(45.0f), float(width) / height, 0.01f, 100.0f);
        points.draw(projection, 0.2f, height * 0.5f * projection[1][1], false);
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
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; result = 1; }
    glfwDestroyWindow(window);
    glfwTerminate();
    return result;
}
