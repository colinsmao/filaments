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

inline GLuint renderProgram(const char* vs, const char* fs) {
    const GLuint vertex = shader(GL_VERTEX_SHADER, vs);
    const GLuint fragment = shader(GL_FRAGMENT_SHADER, fs);
    const GLuint program = glCreateProgram();
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
    return program;
}

// Points and instanced cubes share one star buffer; switching mode never uploads it again.
class PointRenderer {
    GLuint vao = 0, vbo = 0, program = 0;
    GLuint cubeVao = 0, cubeMesh = 0, cubeProgram = 0;
    GLint cubeMatrixLocation = -1, cubeScaleLocation = -1;
    GLint matrixLocation = -1, sizeLocation = -1, roundLocation = -1;
    GLint projectionScaleLocation = -1, sizeLimitsLocation = -1;
    float sizeLimits[2] = {1.0f, 1.0f};
    GLsizei count = 0;
public:
    PointRenderer() {
        const char* vs = R"(#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec3 color;
layout(location=2) in float starSize;
uniform mat4 viewProjection;
uniform float pointSize;
uniform float projectionScale;
uniform vec2 sizeLimits;
out vec3 vertexColor;
void main() {
    gl_Position = viewProjection * vec4(position, 1.0);
    // Each star's world-space diameter is multiplied by the display scale.
    // clip.w is positive camera depth
    // for visible points in our perspective projection.
    float pixels = starSize * pointSize * projectionScale / max(gl_Position.w, 0.0001);
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
        program = renderProgram(vs, fs);
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
        glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, sizeof(Point), reinterpret_cast<void*>(offsetof(Point, size)));
        glEnableVertexAttribArray(0);
        glEnableVertexAttribArray(1);
        glEnableVertexAttribArray(2);

        cubeProgram = renderProgram(R"(#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec3 color;
layout(location=2) in float starSize;
layout(location=3) in vec3 corner;
layout(location=4) in vec3 normal;
uniform mat4 viewProjection;
uniform float sizeScale;
out vec3 vertexColor;
void main() {
    gl_Position = viewProjection * vec4(position + corner * starSize * sizeScale, 1.0);
    // Fixed block-face tones: opposite horizontal faces have identical shading.
    // X = east/west, Z = north/south, Y = top/bottom. No directional light.
    float light = abs(normal.x) > 0.5 ? 0.82
                : abs(normal.z) > 0.5 ? 0.92
                : normal.y > 0.0 ? 1.0 : 0.85;
    vertexColor = color * light;
})", R"(#version 330 core
in vec3 vertexColor;
out vec4 fragColor;
void main() {
    fragColor = vec4(vertexColor, 1.0);
})");
        cubeMatrixLocation = glGetUniformLocation(cubeProgram, "viewProjection");
        cubeScaleLocation = glGetUniformLocation(cubeProgram, "sizeScale");
        // A reusable unit cube: two triangles per face, with flat normals.
        struct Vertex { glm::vec3 position, normal; };
        std::vector<Vertex> vertices;
        for (int axis = 0; axis < 3; ++axis) {
            for (float sign : {-1.0f, 1.0f}) {
                glm::vec3 normal(0), u(0), v(0);
                normal[axis] = sign;
                u[(axis + 1) % 3] = 1;
                v[(axis + 2) % 3] = sign;
                const glm::vec2 corners[] = {{0,0}, {1,0}, {1,1}, {0,1}};
                for (int index : {0, 1, 2, 0, 2, 3}) {
                    const auto uv = corners[index];
                    vertices.push_back({normal * 0.5f + u * (uv.x - 0.5f) + v * (uv.y - 0.5f), normal});
                }
            }
        }
        glGenVertexArrays(1, &cubeVao);
        glBindVertexArray(cubeVao);
        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(Point), reinterpret_cast<void*>(offsetof(Point, position)));
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(Point), reinterpret_cast<void*>(offsetof(Point, color)));
        glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, sizeof(Point), reinterpret_cast<void*>(offsetof(Point, size)));
        for (GLuint i = 0; i < 3; ++i) { glEnableVertexAttribArray(i); glVertexAttribDivisor(i, 1); }
        glGenBuffers(1, &cubeMesh);
        glBindBuffer(GL_ARRAY_BUFFER, cubeMesh);
        glBufferData(GL_ARRAY_BUFFER, static_cast<GLsizeiptr>(vertices.size() * sizeof(Vertex)), vertices.data(), GL_STATIC_DRAW);
        glVertexAttribPointer(3, 3, GL_FLOAT, GL_FALSE, sizeof(Vertex), reinterpret_cast<void*>(offsetof(Vertex, position)));
        glVertexAttribPointer(4, 3, GL_FLOAT, GL_FALSE, sizeof(Vertex), reinterpret_cast<void*>(offsetof(Vertex, normal)));
        for (GLuint i = 3; i < 5; ++i) glEnableVertexAttribArray(i);
        glBindVertexArray(0);
    }
    ~PointRenderer() {
        glDeleteBuffers(1, &vbo);
        glDeleteVertexArrays(1, &vao);
        glDeleteProgram(program);
        glDeleteBuffers(1, &cubeMesh);
        glDeleteVertexArrays(1, &cubeVao);
        glDeleteProgram(cubeProgram);
    }
    PointRenderer(const PointRenderer&) = delete;
    PointRenderer& operator=(const PointRenderer&) = delete;
    void setPoints(const std::vector<Point>& points) {
        count = static_cast<GLsizei>(points.size());
        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glBufferData(GL_ARRAY_BUFFER, static_cast<GLsizeiptr>(points.size() * sizeof(Point)), points.data(), GL_STATIC_DRAW);
    }
    void draw(const glm::mat4& matrix, float size, float projectionScale, bool round = true, GLenum mode = GL_POINTS) const {
        // The Python worker may not have uploaded a buffer yet. Some drivers
        // still touch enabled attributes during an otherwise empty draw.
        if (count == 0) return;
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

    void drawCubes(const glm::mat4& matrix, float sizeScale) const {
        if (count == 0) return;
        glUseProgram(cubeProgram);
        glUniformMatrix4fv(cubeMatrixLocation, 1, GL_FALSE, glm::value_ptr(matrix));
        glUniform1f(cubeScaleLocation, sizeScale);
        glEnable(GL_CULL_FACE);
        glBindVertexArray(cubeVao);
        glDrawArraysInstanced(GL_TRIANGLES, 0, 36, count);
        glBindVertexArray(0);
        glDisable(GL_CULL_FACE);
    }
};

