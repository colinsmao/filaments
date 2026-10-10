#pragma once
#include "generation.h"
#include "plot_settings.h"
#include <imgui.h>
#include <map>
#include <limits>
#include <random>
#include <algorithm>
#include <vector>

class GeneratorPanel {
public:
    explicit GeneratorPanel(const nlohmann::json& saved = PlotSettings{}.generator)
        : runtime(GeneratorRuntime::defaults()), service(runtime), fingerprint(runtime.sourceFingerprint()) {
        selected = saved.at("script").get<std::string>();
        count = saved.at("count").get<int>();
        seed = saved.at("seed").get<int>();
        parameters = saved.at("parameters").get<std::map<std::string, nlohmann::json>>();
        autoApply = saved.at("auto_apply").get<bool>();
        watchFiles = saved.at("watch_files").get<bool>();
        queue();
    }

    nlohmann::json settings() const {
        return {{"script", selected}, {"count", count}, {"seed", seed}, {"parameters", parameters},
                {"auto_apply", autoApply}, {"watch_files", watchFiles}};
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
            if (!result->error.empty()) { error = result->error; return {}; }
            error.clear();
            // A job can finish while the user is still dragging a slider.
            // Normalize returned values only if no newer edits have occurred.
            if (result->request.value("ui_revision", 0ULL) == editRevision) {
                selected = result->metadata.at("generator").get<std::string>();
                parameters[selected] = result->metadata.at("params");
            }
            mathMs = result->metadata.at("generation_ms").get<double>();
            totalMs = result->elapsedMs;
            lines = result->metadata.value("primitive", std::string("points")) == "lines";
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
        bool selectedLines = false;
        for (const auto& item : catalog)
            if (item.at("id") == selected) selectedLines = item.value("primitive", std::string("points")) == "lines";
        bool edited = false;
        if (selectedLines) ImGui::TextUnformatted("Curve preview - no stars yet");
        else edited = ImGui::SliderInt("Stars", &count, 1000, 1000000, "%d", ImGuiSliderFlags_Logarithmic);
        edited |= ImGui::InputInt("Seed", &seed);
        seed = std::max(seed, 0);
        for (const auto& item : catalog) {
            if (item.at("id") != selected) continue;
            auto& params = parameters[selected];
            const auto drawParameter = [&](const nlohmann::json& entry) {
                const auto key = entry.at("key").get<std::string>();
                const auto label = entry.at("label").get<std::string>() + "##" + key;
                // Saved values may predate edits to a script's parameter schema.
                const double bounded = plotNumber(params, key.c_str(), entry.at("default").get<double>(),
                                                   entry.at("min").get<double>(), entry.at("max").get<double>());
                const auto enabledBy = entry.value("enabled_if", std::string{});
                const bool enabled = enabledBy.empty() || plotNumber(params, enabledBy.c_str(), 0, 0, 1) != 0;
                ImGui::BeginDisabled(!enabled);
                if (entry.value("toggle", false)) {
                    bool value = bounded != 0;
                    params[key] = value ? 1 : 0;
                    if (ImGui::Checkbox(label.c_str(), &value)) {
                        params[key] = value ? 1 : 0; edited = true;
                    }
                } else if (entry.at("type") == "int") {
                    int value = static_cast<int>(bounded);
                    params[key] = value;
                    if (ImGui::SliderInt(label.c_str(), &value, entry.at("min").get<int>(), entry.at("max").get<int>())) {
                        params[key] = value; edited = true;
                    }
                } else {
                    float value = static_cast<float>(bounded);
                    params[key] = value;
                    if (ImGui::SliderFloat(label.c_str(), &value, entry.at("min").get<float>(), entry.at("max").get<float>(), "%.3f")) {
                        params[key] = value; edited = true;
                    }
                }
                ImGui::EndDisabled();
            };
            for (const auto& entry : item.at("parameters"))
                if (entry.value("group", std::string{}).empty()) drawParameter(entry);
            if (!selectedLines && ImGui::CollapsingHeader("Postprocessing", ImGuiTreeNodeFlags_DefaultOpen)) {
                ImGui::Indent();
                std::vector<std::string> groups;
                for (const auto& entry : item.at("parameters")) {
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
    std::map<std::string, nlohmann::json> parameters;
    std::string selected, fingerprint, error, warnings;
    int count = 100000, seed = 42;
    bool watchFiles = true, autoApply = true, dirty = false;
    bool lines = false; // Describes the last successful buffer, not the pending selection.
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
        service.request({{"generator", selected}, {"count", count}, {"seed", seed}, {"params", params}, {"ui_revision", editRevision}});
    }
};
