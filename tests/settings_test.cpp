#include "settings.h"
#include "plot_settings.h"
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
        const ControlSettings original{1, 0.075f, 9.25f, 4.5f};
        require(saveControlSettings(path, original), "Could not save settings");
        const auto loaded = loadControlSettings(path);
        require(loaded.cameraMode == original.cameraMode && loaded.sensitivity == original.sensitivity &&
                loaded.moveSpeed == original.moveSpeed && loaded.zoomFactor == original.zoomFactor, "Saved settings did not round-trip");
        {
            std::ofstream file(path);
            file << "camera_mode=2\nsensitivity=nan\nmove_speed=oops\nzoom_factor=nan\nunknown=3\n";
        }
        const auto invalid = loadControlSettings(path);
        require(invalid.cameraMode == 0 && invalid.sensitivity == 0.10f && invalid.moveSpeed == 5.0f && invalid.zoomFactor == 3,
                "Malformed preferences must retain defaults");
        {
            std::ofstream file(path);
            file << "sensitivity=100\nmove_speed=-3\ncamera_mode=1junk\nzoom_factor=100\n";
        }
        const auto bounded = loadControlSettings(path);
        require(bounded.sensitivity == 0.5f && bounded.moveSpeed == 0.1f && bounded.cameraMode == 0 && bounded.zoomFactor == 10,
                "Preferences must enforce valid ranges and reject trailing garbage");
        require(!saveControlSettings(path / "invalid-child.ini", original), "Save failure should be reported");
        const auto plotPath = path.parent_path() / "plot.json";
        PlotSettings plot;
        plot.generator = {{"script", "filaments"}, {"count", 234567}, {"seed", 674},
            {"parameters", {{"galaxy", {{"arms", 7}, {"star_size", 0.06}}},
                            {"filaments", {{"width", 0.4}, {"nodes", 25}}}}},
            {"auto_apply", false}, {"watch_files", false}};
        plot.renderMode = 1;
        plot.sizeScale = 2.25f;
        plot.round = plot.showAxes = plot.vsync = false;
        plot.background[0] = 0.25f;
        plot.camera.target = {3, -4, 5};
        plot.camera.yaw = 160;
        plot.camera.pitch = -22;
        plot.camera.distance = 12;
        plot.hasCamera = true;
        require(savePlotSettings(plotPath, plot), "Could not save plot");
        const auto restored = loadPlotSettings(plotPath);
        require(restored.generator == plot.generator && restored.renderMode == 1 && restored.sizeScale == 2.25f &&
                !restored.round && !restored.showAxes && !restored.vsync && restored.background[0] == 0.25f &&
                restored.hasCamera && restored.camera.target == plot.camera.target && restored.camera.yaw == 160 &&
                restored.camera.pitch == -22 && restored.camera.distance == 12, "Plot configuration did not round-trip");
        std::ofstream(plotPath) << R"({"generator":{"script":"galaxy","count":2000000,"seed":-1,
            "parameters":{"galaxy":{"arms":4,"bad":"text"},"broken":[]}},"size_scale":-2,
            "background":"bad","camera":{"target":"bad"},"round_points":5})";
        const auto badPlot = loadPlotSettings(plotPath);
        require(badPlot.generator["count"] == 1000000 && badPlot.generator["seed"] == 0 &&
                badPlot.generator["parameters"]["galaxy"]["arms"] == 4 &&
                !badPlot.generator["parameters"]["galaxy"].contains("bad") && badPlot.sizeScale == 0.05f &&
                !badPlot.hasCamera && badPlot.round, "Plot settings must ignore malformed values and bound numbers");
        std::ofstream(plotPath) << "{truncated";
        require(loadPlotSettings(plotPath).generator["count"] == 100000, "Invalid JSON must use plot defaults");
        require(loadPlotSettings(plotPath.string() + ".missing").renderMode == 0, "Missing plot must default to cubes");
        require(!savePlotSettings(path / "invalid-child.json", plot), "Plot save failure should be reported");
        std::cout << "Settings round-trip, defaults, validation and save-error checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
