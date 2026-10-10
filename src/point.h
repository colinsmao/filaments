#pragma once
#include <glm/glm.hpp>
#include <cstddef>
#include <type_traits>

// The CPU/GPU interchange is six packed float32 values: x, y, z, r, g, b.
struct Point { glm::vec3 position; glm::vec3 color; };
static_assert(sizeof(float) == 4 && sizeof(Point) == 24 && offsetof(Point, color) == 12);
static_assert(std::is_trivially_copyable_v<Point>);
