#pragma once
#include "generation.h"
#include "plot_settings.h"
#include "density_settings.h"
#include "zone_slider.h"
#include <imgui.h>
#include <map>
#include <limits>
#include <random>
#include <algorithm>
#include <vector>

class GeneratorPanel {
public:
    explicit GeneratorPanel(const nlohmann::json& saved = PlotSettings{}.generator,
                            bool blockUnits = false, float legacyDisplayScale = 16)
        : runtime(GeneratorRuntime::defaults()), service(runtime), fingerprint(runtime.sourceFingerprint()),
          blockUnits(blockUnits), legacyDisplayScale(legacyDisplayScale) {
        selected = saved.at("script").get<std::string>();
        count = saved.at("count").get<int>();
        seed = saved.at("seed").get<int>();
        parameters = saved.at("parameters").get<std::map<std::string, nlohmann::json>>();
        autoApply = saved.at("auto_apply").get<bool>();
        watchFiles = saved.at("watch_files").get<bool>();
        if (saved.contains("density_field") && saved["density_field"].is_object()) {
            densitySettings.field = saved["density_field"];
            if (!densitySettings.field.contains("field_resolution") && parameters.count("density_filament_curves") &&
                parameters["density_filament_curves"].contains("curve_resolution"))
                densitySettings.field["field_resolution"] = parameters["density_filament_curves"]["curve_resolution"];
        } else {
            // The requested initial copy is curves -> direct density. Once saved,
            // the shared field is authoritative regardless of selected script.
            const auto source = parameters.count("density_filament_curves") ? "density_filament_curves" : "noise_filaments_branches";
            if (parameters.count(source)) densitySettings.importLegacy(source, parameters[source], blockUnits, legacyDisplayScale);
        }
        if (blockUnits) densitySettings.removePresetFields(parameters);
        queue();
    }

    nlohmann::json settings() const {
        return {{"script", selected}, {"count", count}, {"seed", seed}, {"parameters", parameters},
                {"auto_apply", autoApply}, {"watch_files", watchFiles}, {"density_field", densitySettings.field}};
    }

    std::optional<std::vector<Point>> tick(double now) {
        if (now - lastScan > 0.5) {
            lastScan = now;
            auto current = runtime.sourceFingerprint();
            if (current != fingerprint) {
                fingerprint = std::move(current);
                if (watchFiles) { dirty = true; lastEdit = now; }
            }
        }
        if (dirty && now - lastEdit >= 0.35) { queue(); dirty = false; }
        if (auto result = service.poll()) {
            if (result->metadata.contains("catalog")) catalog = result->metadata["catalog"];
            warnings.clear();
            for (const auto& warning : result->metadata.value("warnings", nlohmann::json::array()))
                warnings += warning.get<std::string>() + "\n";
            if (result->request.value("ui_revision", 0ULL) == editRevision &&
                result->metadata.contains("params") && result->metadata.contains("generator")) {
                selected = result->metadata.at("generator").get<std::string>();
                parameters[selected] = result->metadata.at("params");
                if (result->metadata.contains("density_field"))
                    densitySettings.field = result->metadata["density_field"];
            }
            if (!result->error.empty()) { error = result->error; return {}; }
            selectionStats = result->metadata.value("selection_stats", nlohmann::json::object());
            error.clear();
            mathMs = result->metadata.at("generation_ms").get<double>();
            totalMs = result->elapsedMs;
            lines = result->metadata.value("primitive", std::string("points")) == "lines";
            population = result->metadata.value("population", false);
            populationLimited = result->metadata.value("population_limited", false);
            starLayer = std::move(result->stars);
            return std::move(result->points);
        }
        return {};
    }

    void draw(double now) {
        const std::string label = selected.empty() ? "Loading generators..." : selected + ".py";
        if (ImGui::BeginCombo("Script", label.c_str())) {
            for (const auto& item : catalog) {
                const auto id = item.at("id").get<std::string>();
                if (ImGui::Selectable((id + ".py").c_str(), id == selected)) {
                    selected = id;
                    ++editRevision;
                    queue();
                    dirty = false;
                }
            }
            ImGui::EndCombo();
        }
        bool selectedLines = false, selectedPopulation = false;
        for (const auto& item : catalog)
            if (item.at("id") == selected) {
                selectedLines = item.value("primitive", std::string("points")) == "lines";
                selectedPopulation = item.value("population", false);
            }
        bool edited = false;
        if (selectedLines) ImGui::TextUnformatted(selectedPopulation ? "Curves + star population" : "Curve preview");
        else edited = ImGui::SliderInt("Stars", &count, 1000, 1000000, "%d", ImGuiSliderFlags_Logarithmic);
        edited |= ImGui::InputInt("Seed", &seed);
        seed = std::max(seed, 0);
        for (const auto& item : catalog) {
            if (item.at("id") != selected) continue;
            auto& params = parameters[selected];
            if (!params.is_object()) params = nlohmann::json::object();
            if (blockUnits && DensitySettings::participates(selected) && params.value("_block_units", 0) != 1) {
                ImGui::TextUnformatted("Converting saved settings to blocks...");
                continue;
            }
            const auto drawParameter = [&](const nlohmann::json& entry) {
                if (entry.value("zone_hidden", false)) return;
                auto& values = entry.value("scope", std::string{}) == "density_field" ? densitySettings.field : params;
                const auto key = entry.at("key").get<std::string>();
                const auto label = entry.at("label").get<std::string>() + "##" + key;
                if (entry.contains("zone_kind")) {
                    const auto pair = entry.value("zone_pair", key);
                    const auto* other = &entry;
                    for (const auto& candidate : item.at("parameters"))
                        if (candidate.at("key") == pair) { other = &candidate; break; }
                    const bool fade = entry.at("zone_kind") == "fade";
                    const auto reach = [fade](float value) { return fade ? 1-value : value; };
                    const auto value = [&](const nlohmann::json& e) {
                        return static_cast<float>(plotNumber(values, e.at("key").get<std::string>().c_str(),
                            e.at("default").get<double>(), e.at("min").get<double>(), e.at("max").get<double>()));
                    };
                    const auto enabled = [&](const nlohmann::json& e) {
                        const auto toggle = e.value("enabled_if", std::string{});
                        return toggle.empty() || plotNumber(values, toggle.c_str(), 0, 0, 1) != 0;
                    };
                    float negative = reach(value(*other)), positive = reach(value(entry));
                    float halfExtent = 0;
                    const auto extentKey = entry.value("zone_extent", std::string{});
                    for (const auto& candidate : item.at("parameters")) {
                        if (candidate.at("key") != extentKey) continue;
                        const auto& extentValues = candidate.value("scope", std::string{}) == "density_field"
                            ? densitySettings.field : params;
                        halfExtent = static_cast<float>(plotNumber(extentValues, extentKey.c_str(),
                            candidate.at("default").get<double>(), 0, 1e6));
                        break;
                    }
                    const char* units = blockUnits && DensitySettings::participates(selected) ? "blocks" : "units";
                    ImGui::PushID(key.c_str());
                    if (ZoneSlider::draw(entry.at("zone_label").get<std::string>().c_str(),
                        negative, positive, pair == key, fade, enabled(*other), enabled(entry),
                        reach(other->at(fade ? "max" : "min").get<float>()),
                        reach(other->at(fade ? "min" : "max").get<float>()),
                        reach(entry.at(fade ? "max" : "min").get<float>()),
                        reach(entry.at(fade ? "min" : "max").get<float>()), halfExtent, units)) {
                        values[pair] = reach(negative);
                        values[key] = reach(positive);
                        edited = true;
                    }
                    ImGui::PopID();
                    return;
                }
                double minimum = entry.at("min").get<double>(), maximum = entry.at("max").get<double>();
                if (DensitySettings::participates(selected) &&
                    (key == "extent" || key == "y_extent" || key == "noise_scale" || key == "frequency") &&
                    values.contains(key) && values[key].is_number()) {
                    const double inherited = values[key].get<double>();
                    if (std::isfinite(inherited) && inherited > 0 && inherited <= 1e6) {
                        minimum = std::min(minimum, inherited);
                        maximum = std::max(maximum, inherited);
                    }
                }
                // Saved values may predate edits to a script's parameter schema.
                const double bounded = plotNumber(values, key.c_str(), entry.at("default").get<double>(),
                                                   minimum, maximum);
                const auto enabledBy = entry.value("enabled_if", std::string{});
                const bool enabled = enabledBy.empty() || plotNumber(values, enabledBy.c_str(), 0, 0, 1) != 0;
                ImGui::BeginDisabled(!enabled);
                if (entry.value("toggle", false)) {
                    bool value = bounded != 0;
                    values[key] = value ? 1 : 0;
                    if (ImGui::Checkbox(label.c_str(), &value)) {
                        values[key] = value ? 1 : 0; edited = true;
                    }
                } else if (entry.at("type") == "int") {
                    int value = static_cast<int>(bounded);
                    values[key] = value;
                    if (ImGui::SliderInt(label.c_str(), &value, entry.at("min").get<int>(), entry.at("max").get<int>())) {
                        values[key] = value; edited = true;
                    }
                } else {
                    float value = static_cast<float>(bounded);
                    values[key] = value;
                    const ImGuiSliderFlags flags = entry.value("logarithmic", false)
                        ? ImGuiSliderFlags_Logarithmic : ImGuiSliderFlags_None;
                    const float sliderMaximum = entry.value("slider_max", static_cast<float>(maximum));
                    if (ImGui::SliderFloat(label.c_str(), &value, static_cast<float>(minimum), sliderMaximum, "%.3f", flags)) {
                        values[key] = value; edited = true;
                    }
                }
                ImGui::EndDisabled();
                if (entry.contains("description") && ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
                    ImGui::BeginTooltip();
                    ImGui::PushTextWrapPos(ImGui::GetFontSize() * 32.f);
                    ImGui::TextUnformatted(entry.at("description").get<std::string>().c_str());
                    ImGui::PopTextWrapPos();
                    ImGui::EndTooltip();
                }
            };
            if (blockUnits && DensitySettings::participates(selected) && ImGui::CollapsingHeader("Noise / density field", ImGuiTreeNodeFlags_DefaultOpen)) {
                for (const auto& entry : item.at("parameters"))
                    if (entry.value("scope", std::string{}) == "density_field") drawParameter(entry);
            }
            if (!selectedPopulation || ImGui::CollapsingHeader("Curve generation", ImGuiTreeNodeFlags_DefaultOpen)) {
                for (const auto& entry : item.at("parameters"))
                    if (entry.value("group", std::string{}).empty()) drawParameter(entry);
            }
            bool hasSelection = false;
            for (const auto& entry : item.at("parameters"))
                hasSelection |= entry.value("section", std::string{}) == "selection";
            if (hasSelection && ImGui::CollapsingHeader("Curve selection", ImGuiTreeNodeFlags_DefaultOpen)) {
                for (const auto& entry : item.at("parameters"))
                    if (entry.value("section", std::string{}) == "selection") drawParameter(entry);
                if (!selectionStats.empty())
                    ImGui::Text("%d candidates -> %d candle / %d rod curves", selectionStats.value("candidates", 0),
                                selectionStats.value("candles", 0), selectionStats.value("rods", 0));
            }
            if (selectedPopulation && ImGui::CollapsingHeader("Star population", ImGuiTreeNodeFlags_DefaultOpen)) {
                for (const auto& entry : item.at("parameters"))
                    if (entry.value("section", std::string{}) == "population") drawParameter(entry);
                if (populationLimited) ImGui::TextWrapped("Star limit reached; density reduced to fit 1,000,000 stars.");
            }
            if ((!selectedLines || selectedPopulation) && ImGui::CollapsingHeader("Postprocessing", ImGuiTreeNodeFlags_DefaultOpen)) {
                ImGui::Indent();
                std::vector<std::string> groups;
                for (const auto& entry : item.at("parameters")) {
                    if (entry.value("section", std::string{}) == "population" || entry.value("section", std::string{}) == "field" || entry.value("section", std::string{}) == "selection") continue;
                    const auto group = entry.value("group", std::string{});
                    if (!group.empty() && std::find(groups.begin(), groups.end(), group) == groups.end())
                        groups.push_back(group);
                }
                for (const auto& group : groups) {
                    if (ImGui::TreeNodeEx(group.c_str(), ImGuiTreeNodeFlags_DefaultOpen)) {
                        for (const auto& entry : item.at("parameters"))
                            if (entry.value("group", std::string{}) == group) drawParameter(entry);
                        ImGui::TreePop();
                    }
                }
                ImGui::Unindent();
            }
        }
        if (edited) {
            ++editRevision;
            if (autoApply) { dirty = true; lastEdit = now; }
        }
        if (ImGui::Button("Generate / reload")) { queue(); dirty = false; }
        if (service.busy()) {
            ImGui::SameLine();
            if (ImGui::Button("Cancel")) { service.cancel(); dirty = false; error = "Generation cancelled; previous cloud retained."; }
        }
        if (ImGui::Button("Random seed + regenerate (G)")) regenerateRandom();
        ImGui::Checkbox("Auto-apply parameters", &autoApply);
        ImGui::Checkbox("Reload on script save", &watchFiles);
        ImGui::TextUnformatted(service.busy() ? "Generating in Python..." : dirty ? "Waiting for edits..." : "Ready");
        ImGui::Text("Math + packing: %.0f ms | Total: %.0f ms", mathMs, totalMs);
        if (!error.empty()) {
            ImGui::TextColored(ImVec4(1, 0.5f, 0.4f, 1), "Generation failed; keeping previous cloud");
            if (ImGui::CollapsingHeader("Error details", ImGuiTreeNodeFlags_DefaultOpen)) {
                ImGui::BeginChild("generation-error", ImVec2(0, 100), ImGuiChildFlags_Borders);
                ImGui::TextWrapped("%s", error.c_str());
                ImGui::EndChild();
            }
        }
        if (!warnings.empty() && ImGui::CollapsingHeader("Script warnings")) ImGui::TextWrapped("%s", warnings.c_str());
    }

    bool busy() const { return service.busy() || dirty; }
    bool drawsLines() const { return lines; }
    bool hasPopulation() const { return population; }
    std::vector<Point> takeStarLayer() { return std::move(starLayer); }
    void handleShortcuts(bool cameraCaptured) {
        const auto& io = ImGui::GetIO();
        if ((cameraCaptured || (!io.WantCaptureKeyboard && !io.WantTextInput)) &&
            ImGui::IsKeyPressed(ImGuiKey_G, false)) regenerateRandom();
    }
    const std::string& lastError() const { return error; }
    double mathMs = 0, totalMs = 0;

private:
    GeneratorRuntime runtime;
    GenerationService service;
    nlohmann::json catalog = nlohmann::json::array();
    nlohmann::json selectionStats = nlohmann::json::object();
    std::map<std::string, nlohmann::json> parameters;
    DensitySettings densitySettings;
    std::string selected, fingerprint, error, warnings;
    int count = 100000, seed = 42;
    bool watchFiles = true, autoApply = true, dirty = false;
    bool lines = false; // Describes the last successful buffer, not the pending selection.
    bool population = false, populationLimited = false;
    bool blockUnits = false;
    float legacyDisplayScale = 16;
    std::vector<Point> starLayer;
    double lastScan = 0, lastEdit = 0;
    unsigned long long editRevision = 0;
    std::mt19937 random{std::random_device{}()};

    void regenerateRandom() {
        std::uniform_int_distribution<int> distribution(0, std::numeric_limits<int>::max());
        const int previous = seed;
        do { seed = distribution(random); } while (seed == previous);
        ++editRevision;
        dirty = false;
        queue();
    }

    void queue() {
        auto params = selected.empty() ? nlohmann::json::object() : parameters[selected];
        if (params.is_null()) params = nlohmann::json::object();
        service.request({{"generator", selected}, {"count", count}, {"seed", seed}, {"params", params},
                         {"ui_revision", editRevision}, {"world_units", blockUnits ? "blocks" : "legacy"},
                         {"density_graph", blockUnits}, {"density_field", densitySettings.field},
                         {"legacy_display_scale", legacyDisplayScale}});
    }
};
