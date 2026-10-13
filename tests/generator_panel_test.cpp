#include "generator_panel.h"
#include <iostream>
#include <thread>

void checkZoneSlider() {
    float negative = .4f, positive = .6f;
    ZoneSlider::setReach(negative, positive, -1, -.8f, false, 0, 1, 0, 1);
    if (negative != .8f || positive != .6f) throw std::runtime_error("Asymmetric zone moved the other side");
    ZoneSlider::setReach(negative, positive, 1, .2f, true, 0, 1, 0, 1);
    if (negative != .2f || positive != .2f) throw std::runtime_error("Symmetric zone did not mirror");
    ZoneSlider::setReach(negative, positive, -1, .1f, false, -1, 1, -1, 1);
    if (negative != -.1f || positive != .2f) throw std::runtime_error("Zone handle could not cross center");
    ZoneSlider::setReach(negative, positive, -1, .5f, false, -1, 1, -1, 1);
    if (negative != -.2f || positive != .2f) throw std::runtime_error("Lower handle crossed the upper handle");
    ZoneSlider::setReach(negative, positive, 1, 1, true, 0, .95f, 0, .95f);
    if (negative != .95f || positive != .95f) throw std::runtime_error("Fade start escaped schema bounds");

    auto& io = ImGui::GetIO();
    float trackStart = 0, trackEnd = 0, trackY = 0;
    negative = .4f; positive = .6f;
    const auto frame = [&](bool linked) {
        ImGui::NewFrame();
        ImGui::SetNextWindowPos(ImVec2(0, 0));
        ImGui::SetNextWindowSize(ImVec2(500, 300));
        ImGui::Begin("Zone interaction", nullptr, ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize);
        const auto cursor = ImGui::GetCursorScreenPos();
        trackStart = cursor.x + 7;
        trackEnd = cursor.x + ImGui::GetContentRegionAvail().x - 7;
        trackY = cursor.y + ImGui::GetTextLineHeightWithSpacing() + 15;
        ZoneSlider::draw("Y seed region", negative, positive, linked, false, true, true,
                         linked ? 0 : -1, 1, linked ? 0 : -1, 1);
        ImGui::End();
        ImGui::Render();
    };
    frame(false);
    const auto mouse = [&](float location) {
        io.AddMousePosEvent(trackStart+(location+1)*.5f*(trackEnd-trackStart), trackY);
    };
    mouse(.6f); frame(false);
    io.AddMouseButtonEvent(0, true); frame(false);
    mouse(.85f); frame(false);
    if (std::abs(positive-.85f) > .006f || negative != .4f)
        throw std::runtime_error("Dragging positive zone handle failed: " + std::to_string(negative) + ", " + std::to_string(positive));
    mouse(-.2f); frame(false);
    if (std::abs(positive+.2f) > .006f || negative != .4f)
        throw std::runtime_error("Dragging upper handle across zero failed");
    mouse(-.6f); frame(false);
    if (positive != -.4f || negative != .4f)
        throw std::runtime_error("Upper handle crossed the lower handle");
    io.AddMouseButtonEvent(0, false); frame(false);
    mouse(-.4f); frame(true);
    io.AddMouseButtonEvent(0, true); frame(true);
    mouse(-.7f); frame(true);
    if (std::abs(positive-.7f) > .006f || std::abs(negative-.7f) > .006f)
        throw std::runtime_error("Dragging symmetric zone handle failed");
    io.AddMouseButtonEvent(0, false); frame(true);
}

nlohmann::json checkStartup(const nlohmann::json& saved, bool lines = false, bool population = false, bool blockUnits = false) {
    GeneratorPanel panel(saved, blockUnits);
    const auto started = std::chrono::steady_clock::now();
    bool loaded = false;
    while (std::chrono::steady_clock::now() - started < std::chrono::seconds(10)) {
        const double now = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        if (auto points = panel.tick(now)) {
            if (points->empty()) throw std::runtime_error("Empty startup cloud");
            loaded = true;
        }
        ImGui::NewFrame();
        ImGui::Begin("Generator startup");
        panel.draw(now);
        ImGui::End();
        ImGui::Render();
        if (!panel.lastError().empty()) throw std::runtime_error(panel.lastError());
        if (loaded) {
            if (panel.drawsLines() != lines)
                throw std::runtime_error("Wrong primitive for uploaded geometry");
            if (panel.hasPopulation() != population || panel.takeStarLayer().empty() == population)
                throw std::runtime_error("Wrong star layer for uploaded geometry");
            if (panel.settings().at("script").get<std::string>().empty())
                throw std::runtime_error("Generator selection missing after startup");
            return panel.settings();
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    throw std::runtime_error("Generator panel startup timed out: " + saved.dump());
}

int main() {
    ImGui::CreateContext();
    auto& io = ImGui::GetIO();
    io.IniFilename = nullptr;
    io.DisplaySize = ImVec2(800, 1000);
    io.DeltaTime = 1.0f / 60;
    unsigned char* pixels;
    int width, height;
    io.Fonts->GetTexDataAsRGBA32(&pixels, &width, &height);
    int result = 0;
    try {
        checkZoneSlider();
        checkStartup(PlotSettings{}.generator);
        auto saved = PlotSettings{}.generator;
        saved["script"] = "filaments";
        saved["count"] = 1234;
        saved["parameters"] = {{"filaments", {{"nodes", 25}, {"star_size", 0.1}}}};
        checkStartup(saved);
        saved["script"] = "grown_filaments";
        checkStartup(saved, true);
        saved["script"] = "stochastic_filaments";
        saved["parameters"]["stochastic_filaments"] = {{"seed_count", 1}, {"length", 2}, {"curves_per_seed", 1}};
        checkStartup(saved, true, true);
        saved["script"] = "density_filament_curves";
        saved["parameters"]["density_filament_curves"] = {{"pop_block_scale", 16}, {"curve_resolution", 24}};
        checkStartup(saved, true, true, true);
        saved["parameters"].erase("density_filament_curves");
        checkStartup(saved, true, true, true);
        saved["script"] = "density_curve_corpus";
        saved["density_field"] = {{"extent", 128}, {"y_extent", 32}, {"noise_scale", 64}, {"field_resolution", 24}};
        saved["parameters"]["density_curve_corpus"] = {{"corpus_span", 64}, {"corpus_copies", 4}, {"select_count", 24}};
        const auto corpus = checkStartup(saved, true, true, true);
        if (corpus["parameters"]["density_curve_corpus"]["corpus_span"] != 64 ||
            corpus["density_field"]["extent"] != 128 || !DensitySettings::participates("density_curve_corpus"))
            throw std::runtime_error("Independent corpus units or shared density panel failed");
        saved["script"] = "density_filament_selection";
        saved["parameters"]["density_filament_selection"] = {{"seed_rate", 12}, {"strand_length", 100}};
        const auto selection = checkStartup(saved, true, true, true);
        if (selection["parameters"]["density_filament_selection"]["strand_length"] != 100 ||
            selection["density_field"]["extent"] != 128 || !DensitySettings::participates("density_filament_selection"))
            throw std::runtime_error("Curve selection units or shared density panel failed");
        saved["script"] = "density_population_selection";
        saved["parameters"]["density_population_selection"] = {{"seed_rate", 20}, {"strand_length", 80},
            {"seed_y_neg", .9}, {"seed_y_pos", .9}, {"select_density", 0}};
        const auto populationSelection = checkStartup(saved, true, true, true);
        const auto selectedPreset = populationSelection["parameters"]["density_population_selection"];
        if (selectedPreset["strand_length"] != 80 || selectedPreset["select_budget"] != 5 ||
            selectedPreset["short_curve_fraction"] != .75 || selectedPreset["short_curve_length"] != 24 ||
            selectedPreset["short_growth_response"] != 2 || selectedPreset.value("short_growth_wander", 0.f) != .8f ||
            selectedPreset["select_short_rod_penalty"] != .5 ||
            selectedPreset.value("select_isolation", 0.f) != .9f || selectedPreset["select_isolation_distance"] != 8 ||
            selectedPreset.contains("pop_candle_weight") || populationSelection["density_field"]["extent"] != 128 ||
            !DensitySettings::participates("density_population_selection"))
            throw std::runtime_error("Population selection controls or shared density panel failed");
        {
            saved["script"] = "noise_filaments_branches";
            saved["parameters"] = {
                {"density_filament_curves", {{"_block_units", 1}, {"extent", 256}, {"y_extent", 64},
                    // This fixture checks shared settings, not thousands of long curves.
                    // Mean-normalized rate 500 made it exceed the startup time limit.
                    {"noise_scale", 128}, {"width", .05}, {"curve_resolution", 24}, {"strand_length", 300},
                    {"seed_rate", 5}, {"fade_y_pos", 1}}},
                {"noise_filaments_branches", {{"extent", 6}, {"frequency", 3}, {"star_size", .03}, {"fade_y", 0}}}};
            saved.erase("density_field");
            const auto migrated = checkStartup(saved, false, false, true);
            if (migrated["density_field"]["noise_scale"] != 128 ||
                migrated["density_field"]["extent"] != 256 ||
                migrated["density_field"]["field_resolution"] != 24)
                throw std::runtime_error("Upstream configuration migration failed");
            for (const char* script : {"density_filament_curves", "noise_filaments_branches"})
                for (const char* key : {"extent", "noise_scale", "frequency", "width", "curve_resolution"})
                    if (migrated["parameters"][script].contains(key))
                        throw std::runtime_error("Shared field was duplicated in a consumer preset");
            if (std::abs(migrated["parameters"]["noise_filaments_branches"]["star_size"].get<double>() - .48) > 1e-6 ||
                migrated["parameters"]["noise_filaments_branches"]["fade_y"] != 0 ||
                migrated["parameters"]["density_filament_curves"]["strand_length"] != 300)
                throw std::runtime_error("Consumer-local controls lost or incorrectly migrated");
            auto changed = migrated;
            changed["density_field"]["noise_scale"] = 80;
            changed["script"] = "density_filament_curves";
            auto curves = checkStartup(changed, true, true, true);
            curves["script"] = "noise_filaments_branches";
            auto direct = checkStartup(curves, false, false, true);
            if (curves["density_field"] != direct["density_field"] || direct["density_field"]["noise_scale"] != 80)
                throw std::runtime_error("Consumers did not preserve the same upstream configuration");
        }
        std::cout << "Default and restored generator startup/UI frames passed without a window\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; result = 1; }
    ImGui::DestroyContext();
    return result;
}
