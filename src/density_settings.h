#pragma once
#include <nlohmann/json.hpp>
#include <map>
#include <string>
#include <vector>

// One upstream configuration. Legacy import runs once; consumers hold only local settings.
class DensitySettings {
public:
    nlohmann::json field = nlohmann::json::object();
    static bool participates(const std::string& script) {
        return script == "density_filament_curves" || script == "noise_filaments_branches" || script == "density_curve_corpus" || script == "density_filament_selection" || script == "density_population_selection";
    }

    void importLegacy(const std::string& script, const nlohmann::json& params,
                 bool blockUnits, double legacyScale) {
        if (!participates(script) || !params.is_object()) return;
        const bool curves = script == "density_filament_curves";
        const double scale = (script == "density_curve_corpus" || script == "density_filament_selection" || script == "density_population_selection") ? 1 : unitsScale(curves, params, blockUnits, legacyScale);
        for (const char* key : {"extent", "y_extent"})
            if (number(params, key)) field[key] = params[key].get<double>() * scale;
        if (!number(params, "y_extent") && number(params, "extent") && number(params, "y_scale"))
            field["y_extent"] = params["extent"].get<double>() * params["y_scale"].get<double>() * scale;
        if (number(params, "noise_scale"))
            field["noise_scale"] = params["noise_scale"].get<double>() * scale;
        else if (number(params, "extent") && number(params, "frequency") && params["frequency"].get<double>() > 0)
            field["noise_scale"] = params["extent"].get<double>() * scale / params["frequency"].get<double>();
        for (const char* key : scalarKeys())
            if (number(params, key)) field[key] = params[key];
        if (curves && number(params, "curve_resolution")) field["field_resolution"] = params["curve_resolution"];
    }

    // Migration only: remove old copies once the shared node owns these values.
    void removePresetFields(std::map<std::string, nlohmann::json>& presets) const {
        for (auto& [script, params] : presets) {
            if (!participates(script) || !params.is_object()) continue;
            for (const char* key : {"extent", "y_extent", "noise_scale", "frequency", "y_scale", "curve_resolution", "field_resolution"}) params.erase(key);
            for (const char* key : scalarKeys()) params.erase(key);
        }
    }

private:
    static double unitsScale(bool curves, const nlohmann::json& params, bool blockUnits, double legacyScale) {
        if (!blockUnits || params.value("_block_units", 0) == 1) return 1;
        if (!curves) return legacyScale;
        const double oldScale = params.value("pop_block_scale", 0.0);
        return oldScale > 0 ? oldScale : 16;
    }
    static bool number(const nlohmann::json& values, const char* key) {
        return values.contains(key) && values[key].is_number();
    }
    static const std::vector<const char*>& scalarKeys() {
        static const std::vector<const char*> keys = {"width", "octaves", "roughness", "clumping",
            "strand_continuity", "density_low", "density_mid", "density_high", "broad_strength", "broad_scale"};
        return keys;
    }
};
