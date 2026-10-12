#pragma once
#include "plot_settings.h"

// Observe actual settings rather than generation jobs: edits must persist even
// when auto-apply is off, a job is cancelled, or Python returns an error.
class SettingsAutosave {
public:
    SettingsAutosave(std::filesystem::path plotPath, std::filesystem::path controlsPath,
                     const PlotSettings& plot, const ControlSettings& controls)
        : plotPath(std::move(plotPath)), controlsPath(std::move(controlsPath)),
          saved(snapshot(plot, controls)), observed(saved) {}

    void tick(double now, const PlotSettings& plot, const ControlSettings& controls, bool force = false) {
        const auto current = snapshot(plot, controls);
        if (current != observed) { observed = current; lastChange = now; }
        if (current == saved) { firstPending = -1; saveFailed = false; return; }
        if (firstPending < 0) firstPending = now;
        // Save 350 ms after an edit ends, or every 2 s during continuous movement.
        if (!force && (now < retryAfter || (now - lastChange < 0.35 && now - firstPending < 2.0))) return;
        bool ok = true;
        if (current["plot"] != saved["plot"]) {
            if (savePlotSettings(plotPath, plot)) saved["plot"] = current["plot"];
            else ok = false;
        }
        if (current["controls"] != saved["controls"]) {
            if (saveControlSettings(controlsPath, controls)) saved["controls"] = current["controls"];
            else ok = false;
        }
        saveFailed = !ok;
        if (ok) firstPending = -1;
        else retryAfter = now + 1.0;
    }

    bool pending() const { return firstPending >= 0; }
    bool failed() const { return saveFailed; }

private:
    static nlohmann::json snapshot(const PlotSettings& plot, const ControlSettings& controls) {
        return {{"plot", plotSettingsJson(plot)}, {"controls", {
            {"mode", controls.cameraMode}, {"sensitivity", controls.sensitivity},
            {"speed", controls.moveSpeed}, {"zoom", controls.zoomFactor}, {"block_units", controls.blockUnits}}}};
    }
    std::filesystem::path plotPath, controlsPath;
    nlohmann::json saved, observed;
    double firstPending = -1, lastChange = 0, retryAfter = 0;
    bool saveFailed = false;
};
