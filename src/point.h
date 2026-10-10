#pragma once
#include <glm/glm.hpp>
#include <cstddef>
#include <type_traits>

// Seven packed float32 values: x, y, z, r, g, b, size (world units).
struct Point { glm::vec3 position; glm::vec3 color; float size = 0.04f; };
static_assert(sizeof(float) == 4 && sizeof(Point) == 28 && offsetof(Point, color) == 12 && offsetof(Point, size) == 24);
static_assert(std::is_trivially_copyable_v<Point>);
