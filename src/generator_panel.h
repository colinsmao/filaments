#pragma once
#include "generation.h"
#include <imgui.h>
#include <map>
#include <limits>
#include <random>

class GeneratorPanel {
public:
    GeneratorPanel() : runtime(GeneratorRuntime::defaults()), service(runtime), fingerprint(runtime.sourceFingerprint()) {
        queue();
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
            selected = result->metadata.at("generator").get<std::string>();
            // A job can finish while the user is still dragging a slider.
            // Normalize returned values only if no newer edits have occurred.
            if (result->request.value("ui_revision", 0ULL) == editRevision)
                parameters[selected] = result->metadata.at("params");
            mathMs = result->metadata.at("generation_ms").get<double>();
            totalMs = result->elapsedMs;
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
        bool edited = ImGui::SliderInt("Stars", &count, 1000, 1000000, "%d", ImGuiSliderFlags_Logarithmic);
        edited |= ImGui::InputInt("Seed", &seed);
        seed = std::max(seed, 0);
        for (const auto& item : catalog) {
            if (item.at("id") != selected) continue;
            auto& params = parameters[selected];
            for (const auto& entry : item.at("parameters")) {
                const auto key = entry.at("key").get<std::string>();
                const auto label = entry.at("label").get<std::string>() + "##" + key;
                if (!params.contains(key)) params[key] = entry.at("default");
                if (entry.at("type") == "int") {
                    int value = params[key].get<int>();
                    if (ImGui::SliderInt(label.c_str(), &value, entry.at("min").get<int>(), entry.at("max").get<int>())) {
                        params[key] = value; edited = true;
                    }
                } else {
                    float value = params[key].get<float>();
                    if (ImGui::SliderFloat(label.c_str(), &value, entry.at("min").get<float>(), entry.at("max").get<float>(), "%.3f")) {
                        params[key] = value; edited = true;
                    }
                }
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
