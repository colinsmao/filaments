#pragma once
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

struct ControlSettings {
    int cameraMode = 0;
    float sensitivity = 0.10f;
    float moveSpeed = 5.0f;
};

inline std::filesystem::path controlSettingsPath() {
    if (const char* local = std::getenv("LOCALAPPDATA"))
        return std::filesystem::path(local) / "Filaments" / "controls.ini";
    if (const char* config = std::getenv("XDG_CONFIG_HOME"))
        return std::filesystem::path(config) / "filaments" / "controls.ini";
    if (const char* home = std::getenv("HOME"))
        return std::filesystem::path(home) / ".config" / "filaments" / "controls.ini";
    return "filaments-controls.ini";
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
        else if (key == "move_speed") result.moveSpeed = std::clamp(number, 0.1f, 50.0f);
    }
    return result;
}

inline bool saveControlSettings(const std::filesystem::path& path, const ControlSettings& settings) {
    std::error_code error;
    if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path(), error);
    if (error) return false;
    std::ofstream file(path, std::ios::trunc);
    file.imbue(std::locale::classic());
    file << std::setprecision(std::numeric_limits<float>::max_digits10)
         << "camera_mode=" << settings.cameraMode << '\n'
         << "sensitivity=" << settings.sensitivity << '\n'
         << "move_speed=" << settings.moveSpeed << '\n';
    file.close();
    return !file.fail();
}
