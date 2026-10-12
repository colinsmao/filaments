#pragma once
#include <imgui.h>
#include <algorithm>
#include <cmath>
#include <cstdio>

namespace ZoneSlider {
// Lower coordinate = -negative, upper = positive; either may cross zero.
// The saved fade reach is 1 - fade width.
inline void setReach(float& negative, float& positive, int side, float position,
                     bool linked, float negMin, float negMax, float posMin, float posMax) {
    if (linked) {
        negative = positive = std::clamp(std::abs(position), posMin, posMax);
    } else if (side < 0) {
        negative = std::clamp(-position, std::max(negMin, -positive), negMax);
    } else {
        positive = std::clamp(position, std::max(posMin, -negative), posMax);
    }
}

inline bool draw(const char* label, float& negative, float& positive, bool linked, bool fade,
                 bool negEnabled, bool posEnabled, float negMin, float negMax,
                 float posMin, float posMax, float halfExtent = 0, const char* units = "units") {
    ImGui::PushID(label);
    ImGui::TextUnformatted(label);
    ImGui::SameLine();
    ImGui::TextDisabled(linked ? "(linked)" : "(independent)");
    const float oldNeg = negative, oldPos = positive;
    const float width = std::max(120.0f, ImGui::GetContentRegionAvail().x);
    const ImVec2 origin = ImGui::GetCursorScreenPos();
    const float start = origin.x + 7, end = origin.x + width - 7;
    const auto x = [&](float value) { return start + (value + 1) * .5f * (end - start); };
    const ImGuiID sideId = ImGui::GetID("active-side");
    ImGui::BeginDisabled(!negEnabled && !posEnabled);
    ImGui::InvisibleButton("track", ImVec2(width, 30));
    if (ImGui::IsItemActivated()) {
        const float mouse = ImGui::GetIO().MousePos.x;
        int side = std::abs(mouse-x(-negative)) < std::abs(mouse-x(positive)) ? -1 : 1;
        if (-negative == positive) side = mouse < x(positive) ? -1 : 1;
        if (!negEnabled) side = 1;
        if (!posEnabled) side = -1;
        ImGui::GetStateStorage()->SetInt(sideId, side);
    }
    if (ImGui::IsItemActive() && ImGui::IsMouseDown(ImGuiMouseButton_Left)) {
        const float position = std::clamp(2*(ImGui::GetIO().MousePos.x-start)/(end-start)-1, -1.f, 1.f);
        setReach(negative, positive, ImGui::GetStateStorage()->GetInt(sideId, 1), position,
                 linked, negMin, negMax, posMin, posMax);
    }
    if (ImGui::IsItemHovered()) {
        ImGui::SetTooltip(fade
            ? "Handles mark where fading begins. Orange ends fade toward the boundary.\nA handle at its outer boundary disables fading at that end. Ctrl-click for exact entry."
            : "Seeds are allowed in the highlighted middle. Curves can grow beyond it.\nCtrl-click a number for exact entry.");
    }
    auto* draw = ImGui::GetWindowDrawList();
    const float top = origin.y+9, bottom = origin.y+21;
    const ImU32 base = ImGui::GetColorU32(ImGuiCol_FrameBg);
    const ImU32 seed = ImGui::GetColorU32(ImVec4(.24f, .68f, .78f, 1));
    const ImU32 amber = ImGui::GetColorU32(ImVec4(.95f, .62f, .22f, 1));
    draw->AddRectFilled(ImVec2(start, top), ImVec2(end, bottom), base, 3);
    if (fade) {
        if (negEnabled) draw->AddRectFilledMultiColor(ImVec2(start, top), ImVec2(x(-negative), bottom), base, amber, amber, base);
        if (posEnabled) draw->AddRectFilledMultiColor(ImVec2(x(positive), top), ImVec2(end, bottom), amber, base, base, amber);
    } else {
        draw->AddRectFilled(ImVec2(x(-negative), top), ImVec2(x(positive), bottom), seed, 2);
    }
    draw->AddLine(ImVec2(x(0), top-4), ImVec2(x(0), bottom+4), ImGui::GetColorU32(ImGuiCol_TextDisabled));
    for (int side : {-1, 1}) {
        const bool enabled = side < 0 ? negEnabled : posEnabled;
        const float location = x(side < 0 ? -negative : positive);
        draw->AddCircleFilled(ImVec2(location, origin.y+15), 6,
            ImGui::GetColorU32(enabled ? ImGuiCol_SliderGrabActive : ImGuiCol_TextDisabled));
        draw->AddCircle(ImVec2(location, origin.y+15), 6, ImGui::GetColorU32(ImGuiCol_Border));
    }
    ImGui::EndDisabled();
    // Positive lengths of the three regions, not signed boundary coordinates.
    // Percent fallback is relative to the full span, so these sum to 100%.
    const float lengthScale = halfExtent > 0 ? halfExtent : 50;
    const float lengths[] = {std::max(0.f, 1-negative)*lengthScale,
                             std::max(0.f, negative+positive)*lengthScale,
                             std::max(0.f, 1-positive)*lengthScale};
    const char* names[] = {fade ? "Lower fade" : "Lower excluded",
                           fade ? "Unfaded span" : "Seed span",
                           fade ? "Upper fade" : "Upper excluded"};
    ImGui::BeginDisabled(!negEnabled && !posEnabled);
    if (ImGui::BeginTable("region-lengths", 3, ImGuiTableFlags_SizingStretchSame)) {
        for (int i = 0; i < 3; ++i) {
            ImGui::TableNextColumn();
            ImGui::TextWrapped("%s", names[i]);
            ImGui::Text("%.1f %s", lengths[i], halfExtent > 0 ? units : "%");
        }
        ImGui::EndTable();
    }
    ImGui::EndDisabled();
    // Edit absolute coordinates when a physical half-extent is available.
    // Fractions remain the saved representation, and are also shown below.
    const float scale = halfExtent > 0 ? halfExtent : 100;
    char lowerFormat[48], upperFormat[48];
    std::snprintf(lowerFormat, sizeof(lowerFormat), "Lower: %%+.1f %s", halfExtent > 0 ? units : "%%");
    std::snprintf(upperFormat, sizeof(upperFormat), "Upper: %%+.1f %s", halfExtent > 0 ? units : "%%");
    float lower = -scale*negative, upper = scale*positive;
    ImGui::BeginDisabled(!negEnabled);
    ImGui::SetNextItemWidth((width-20)*.5f);
    if (ImGui::DragFloat("##lower", &lower, .1f, -scale*negMax, -scale*negMin, lowerFormat, ImGuiSliderFlags_AlwaysClamp))
        setReach(negative, positive, -1, lower/scale, linked, negMin, negMax, posMin, posMax);
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::TextDisabled("0");
    ImGui::SameLine();
    upper = scale*positive;
    ImGui::BeginDisabled(!posEnabled);
    ImGui::SetNextItemWidth(std::max(40.f, ImGui::GetContentRegionAvail().x));
    if (ImGui::DragFloat("##upper", &upper, .1f, scale*posMin, scale*posMax, upperFormat, ImGuiSliderFlags_AlwaysClamp))
        setReach(negative, positive, 1, upper/scale, linked, negMin, negMax, posMin, posMax);
    ImGui::EndDisabled();
    if (halfExtent > 0) {
        ImGui::TextDisabled("%+.1f%%", -100*negative);
        ImGui::SameLine(width*.5f);
        ImGui::TextDisabled("%+.1f%%", 100*positive);
    }
    ImGui::PopID();
    return negative != oldNeg || positive != oldPos;
}
}
