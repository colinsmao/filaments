#pragma once
#include "point.h"
#include <glad/glad.h>
#include <glm/gtc/type_ptr.hpp>
#include <vector>
#include <stdexcept>

inline GLuint shader(GLenum type, const char* source) {
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
    GLint projectionScaleLocation = -1, sizeLimitsLocation = -1;
    float sizeLimits[2] = {1.0f, 1.0f};
    GLsizei count = 0;
public:
    PointRenderer() {
        const char* vs = R"(#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec3 color;
uniform mat4 viewProjection;
uniform float pointSize;
uniform float projectionScale;
uniform vec2 sizeLimits;
out vec3 vertexColor;
void main() {
    gl_Position = viewProjection * vec4(position, 1.0);
    // pointSize is a world-space diameter. clip.w is positive camera depth
    // for visible points in our perspective projection.
    float pixels = pointSize * projectionScale / max(gl_Position.w, 0.0001);
    gl_PointSize = clamp(pixels, sizeLimits.x, sizeLimits.y);
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
        projectionScaleLocation = glGetUniformLocation(program, "projectionScale");
        sizeLimitsLocation = glGetUniformLocation(program, "sizeLimits");
        glGetFloatv(GL_POINT_SIZE_RANGE, sizeLimits);
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
    void draw(const glm::mat4& matrix, float size, float projectionScale, bool round = true, GLenum mode = GL_POINTS) const {
        glUseProgram(program);
        glUniformMatrix4fv(matrixLocation, 1, GL_FALSE, glm::value_ptr(matrix));
        glUniform1f(sizeLocation, size);
        glUniform1f(projectionScaleLocation, projectionScale);
        glUniform2fv(sizeLimitsLocation, 1, sizeLimits);
        glUniform1i(roundLocation, round);
        glBindVertexArray(vao);
        glDrawArrays(mode, 0, count);
        glBindVertexArray(0);
    }
};

