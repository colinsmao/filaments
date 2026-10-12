#pragma once
#include "runtime_config.h"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <locale>
#include <sstream>
#include <string>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#endif

inline bool writeSettingsAtomically(const std::filesystem::path& path, const std::string& contents) {
    std::error_code error;
    if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path(), error);
    if (error) return false;
    auto temporary = path;
    temporary += ".tmp";
    std::ofstream file(temporary, std::ios::binary | std::ios::trunc);
    file << contents;
    file.close();
    bool ok = !file.fail();
    if (ok) {
#ifdef _WIN32
        ok = MoveFileExW(temporary.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
#else
        std::filesystem::rename(temporary, path, error);
        ok = !error;
#endif
    }
    if (!ok) std::filesystem::remove(temporary, error);
    return ok;
}

struct ControlSettings {
    int cameraMode = 0;
    float sensitivity = 0.10f;
    float moveSpeed = 5.0f;
    float zoomFactor = 3.0f;
    bool blockUnits = false;
};

inline std::filesystem::path controlSettingsPath() {
    return std::filesystem::path(FILAMENTS_SETTINGS_DIRECTORY) / "controls.ini";
}

inline ControlSettings loadControlSettings(const std::filesystem::path& path) {
    ControlSettings result;
    std::ifstream file(path);
    std::string line;
    while (std::getline(file, line)) {
        const auto equals = line.find('=');
        if (equals == std::string::npos) continue;
        const auto key = line.substr(0, equals);
        std::istringstream value(line.substr(equals + 1));
        value.imbue(std::locale::classic());
        float number;
        if (!(value >> number) || !std::isfinite(number)) continue;
        value >> std::ws;
        if (!value.eof()) continue;
        if (key == "camera_mode" && (number == 0.0f || number == 1.0f)) result.cameraMode = static_cast<int>(number);
        else if (key == "sensitivity") result.sensitivity = std::clamp(number, 0.02f, 0.5f);
        else if (key == "move_speed") result.moveSpeed = std::clamp(number, 0.1f, 6400.0f);
        else if (key == "zoom_factor") result.zoomFactor = std::clamp(number, 1.0f, 10.0f);
        else if (key == "block_units") result.blockUnits = number == 1;
    }
    return result;
}

inline bool saveControlSettings(const std::filesystem::path& path, const ControlSettings& settings) {
    std::ostringstream file;
    file.imbue(std::locale::classic());
    file << std::setprecision(std::numeric_limits<float>::max_digits10)
         << "camera_mode=" << settings.cameraMode << '\n'
         << "sensitivity=" << settings.sensitivity << '\n'
         << "move_speed=" << settings.moveSpeed << '\n'
         << "zoom_factor=" << settings.zoomFactor << '\n'
         << "block_units=" << settings.blockUnits << '\n';
    return writeSettingsAtomically(path, file.str());
}
