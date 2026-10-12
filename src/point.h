#pragma once
#include <glm/glm.hpp>
#include <cstddef>
#include <type_traits>

// FSTAR003/GPU layout: XYZ, RGB, world size, XYZ dimension multipliers.
// Legacy FSTAR002 records contain only the first seven floats.
struct Point {
    glm::vec3 position;
    glm::vec3 color;
    float size = 0.04f;
    glm::vec3 shape{1.0f};
};
static_assert(sizeof(float) == 4 && sizeof(Point) == 40 && offsetof(Point, color) == 12 &&
              offsetof(Point, size) == 24 && offsetof(Point, shape) == 28);
static_assert(std::is_trivially_copyable_v<Point>);
