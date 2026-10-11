#include "generator_panel.h"
#include <iostream>
#include <thread>

void checkStartup(const nlohmann::json& saved, bool lines = false, bool population = false) {
    GeneratorPanel panel(saved);
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
            return;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    throw std::runtime_error("Generator panel startup timed out");
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
        std::cout << "Default and restored generator startup/UI frames passed without a window\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; result = 1; }
    ImGui::DestroyContext();
    return result;
}
