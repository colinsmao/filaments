#pragma once
#include "camera.h"
#include "settings.h"
#include <nlohmann/json.hpp>

struct PlotSettings {
    nlohmann::json generator = {{"script", ""}, {"count", 100000}, {"seed", 42},
        {"parameters", nlohmann::json::object()}, {"auto_apply", true}, {"watch_files", true}};
    int renderMode = 0; // Shaded cubes; 1 = inexpensive point sprites.
    float sizeScale = 1.0f;
    bool round = true, showAxes = true, vsync = true, hasCamera = false;
    bool showCurves = true, showStars = true;
    float background[3] = {0.025f, 0.035f, 0.055f};
    Camera camera;
    bool blockUnits = false;
    float legacyDisplayScale = 16.0f;
};

inline std::filesystem::path plotSettingsPath() {
    return controlSettingsPath().parent_path() / "plot.json";
}

inline double plotNumber(const nlohmann::json& object, const char* key, double fallback, double lo, double hi) {
    const auto it = object.find(key);
    if (it == object.end() || !it->is_number()) return fallback;
    const double value = it->get<double>();
    return std::isfinite(value) ? std::clamp(value, lo, hi) : fallback;
}

inline bool plotBool(const nlohmann::json& object, const char* key, bool fallback) {
    const auto it = object.find(key);
    return it != object.end() && it->is_boolean() ? it->get<bool>() : fallback;
}

inline PlotSettings loadPlotSettings(const std::filesystem::path& path) {
    PlotSettings result;
    std::ifstream file(path);
    if (!file) return result;
    const auto json = nlohmann::json::parse(file, nullptr, false);
    if (!json.is_object()) return result;
    result.blockUnits = plotBool(json, "block_units", false);
    result.legacyDisplayScale = static_cast<float>(plotNumber(json, "legacy_display_scale", 16, 1, 128));
    const auto gen = json.find("generator");
    if (gen != json.end() && gen->is_object()) {
        if (gen->contains("script") && (*gen)["script"].is_string()) result.generator["script"] = (*gen)["script"];
        result.generator["count"] = static_cast<int>(plotNumber(*gen, "count", 100000, 1, 1000000));
        result.generator["seed"] = static_cast<int>(plotNumber(*gen, "seed", 42, 0, 2147483647));
        result.generator["auto_apply"] = plotBool(*gen, "auto_apply", true);
        result.generator["watch_files"] = plotBool(*gen, "watch_files", true);
        if (gen->contains("density_field") && (*gen)["density_field"].is_object()) {
            auto& field = result.generator["density_field"] = nlohmann::json::object();
            for (const auto& value : (*gen)["density_field"].items())
                if (value.value().is_number() && std::isfinite(value.value().get<double>()) &&
                    std::abs(value.value().get<double>()) <= 1e20) field[value.key()] = value.value();
        }
        const auto params = gen->find("parameters");
        if (params != gen->end() && params->is_object()) {
            for (const auto& script : params->items()) {
                if (!script.value().is_object()) continue;
                for (const auto& param : script.value().items()) {
                    if (param.value().is_number() && std::isfinite(param.value().get<double>()) &&
                        std::abs(param.value().get<double>()) <= 1e20)
                        result.generator["parameters"][script.key()][param.key()] = param.value();
                }
            }
        }
    }
    result.renderMode = static_cast<int>(plotNumber(json, "render_mode", 0, 0, 1));
    result.sizeScale = static_cast<float>(plotNumber(json, "size_scale", 1, 0.05, 20));
    result.round = plotBool(json, "round_points", true);
    result.showAxes = plotBool(json, "axes", true);
    result.showCurves = plotBool(json, "show_curves", true);
    result.showStars = plotBool(json, "show_stars", true);
    result.vsync = plotBool(json, "vsync", true);
    const auto bg = json.find("background");
    if (bg != json.end() && bg->is_array() && bg->size() == 3) {
        for (int i = 0; i < 3; ++i)
            if ((*bg)[i].is_number()) result.background[i] = static_cast<float>(std::clamp((*bg)[i].get<double>(), 0.0, 1.0));
    }
    const auto camera = json.find("camera");
    if (camera != json.end() && camera->is_object()) {
        result.camera.yaw = static_cast<float>(plotNumber(*camera, "yaw", 35, -36000, 36000));
        result.camera.pitch = static_cast<float>(plotNumber(*camera, "pitch", 20, -89, 89));
        result.camera.distance = static_cast<float>(plotNumber(*camera, "distance", 18, 0.05, 256000));
        result.camera.nearClip = static_cast<float>(plotNumber(*camera, "near_clip", .01, .001, 2));
        result.camera.farClip = static_cast<float>(plotNumber(*camera, "far_clip", 10000, 100, 1280000));
        const auto target = camera->find("target");
        if (target != camera->end() && target->is_array() && target->size() == 3 &&
            (*target)[0].is_number() && (*target)[1].is_number() && (*target)[2].is_number()) {
            for (int i = 0; i < 3; ++i) result.camera.target[i] = static_cast<float>(std::clamp((*target)[i].get<double>(), -1e6, 1e6));
            result.hasCamera = true;
        }
    }
    return result;
}

inline nlohmann::json plotSettingsJson(const PlotSettings& settings) {
    nlohmann::json json = {{"version", 1}, {"generator", settings.generator},
        {"block_units", settings.blockUnits}, {"legacy_display_scale", settings.legacyDisplayScale},
        {"render_mode", settings.renderMode}, {"size_scale", settings.sizeScale},
        {"round_points", settings.round}, {"axes", settings.showAxes}, {"vsync", settings.vsync},
        {"show_curves", settings.showCurves}, {"show_stars", settings.showStars},
        {"background", {settings.background[0], settings.background[1], settings.background[2]}}};
    if (settings.hasCamera) json["camera"] = {{"yaw", settings.camera.yaw}, {"pitch", settings.camera.pitch},
        {"distance", settings.camera.distance}, {"near_clip", settings.camera.nearClip}, {"far_clip", settings.camera.farClip},
        {"target", {settings.camera.target.x, settings.camera.target.y, settings.camera.target.z}}};
    return json;
}

inline void migrateWorldUnits(PlotSettings& plot, ControlSettings& controls) {
    if (!plot.blockUnits) {
        const auto selected = plot.generator.value("script", std::string{});
        const auto& presets = plot.generator["parameters"];
        float scale = 16;
        if (presets.contains(selected)) {
            const auto& params = presets[selected];
            scale = static_cast<float>(plotNumber(params, "pop_block_scale", 16, 0, 128));
            if (scale == 0) scale = 16;
        }
        plot.legacyDisplayScale = scale;
        plot.camera.target *= scale;
        plot.camera.distance *= scale;
        plot.camera.nearClip *= scale;
        plot.camera.farClip *= scale;
        plot.blockUnits = true;
    }
    // Separate file versions make either autosave order safe on interruption.
    if (!controls.blockUnits) {
        controls.moveSpeed *= plot.legacyDisplayScale;
        controls.blockUnits = true;
    }
}

inline bool savePlotSettings(const std::filesystem::path& path, const PlotSettings& settings) {
    return writeSettingsAtomically(path, plotSettingsJson(settings).dump(2) + '\n');
}
