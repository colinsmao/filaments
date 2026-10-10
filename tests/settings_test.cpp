#include "settings.h"
#include <iostream>
#include <stdexcept>

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Expected a temporary settings file path");
        const std::filesystem::path path(argv[1]);
        const auto missing = loadControlSettings(path.string() + ".missing");
        require(missing.sensitivity == 0.10f && missing.cameraMode == 0, "Missing settings must use defaults");
        const ControlSettings original{1, 0.075f, 9.25f};
        require(saveControlSettings(path, original), "Could not save settings");
        const auto loaded = loadControlSettings(path);
        require(loaded.cameraMode == original.cameraMode && loaded.sensitivity == original.sensitivity &&
                loaded.moveSpeed == original.moveSpeed, "Saved settings did not round-trip");
        {
            std::ofstream file(path);
            file << "camera_mode=2\nsensitivity=nan\nmove_speed=oops\nunknown=3\n";
        }
        const auto invalid = loadControlSettings(path);
        require(invalid.cameraMode == 0 && invalid.sensitivity == 0.10f && invalid.moveSpeed == 5.0f,
                "Malformed preferences must retain defaults");
        {
            std::ofstream file(path);
            file << "sensitivity=100\nmove_speed=-3\ncamera_mode=1junk\n";
        }
        const auto bounded = loadControlSettings(path);
        require(bounded.sensitivity == 0.5f && bounded.moveSpeed == 0.1f && bounded.cameraMode == 0,
                "Preferences must enforce valid ranges and reject trailing garbage");
        require(!saveControlSettings(path / "invalid-child.ini", original), "Save failure should be reported");
        std::cout << "Settings round-trip, defaults, validation and save-error checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
