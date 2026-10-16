#pragma once
#include <nlohmann/json.hpp>
#include <glm/glm.hpp>
#include <array>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <set>
#include <cmath>
#include <stdexcept>

// Pure data loading; no renderer or viewer dependencies. Coordinates are blocks.
struct PartVertex {
    glm::vec3 position, normal;
    glm::vec2 uv;
    float texture;
};
struct PartDefinition {
    std::string id, name, block, category, colour;
    int connections = -1, emission = 0;
    bool translucent = false;
    bool paneAttach = false;
    glm::vec3 low{}, high{}, dimensions{};
    std::vector<std::array<PartVertex, 4>> faces;
    std::vector<glm::vec3> faceCull;
};
struct PartInstance { size_t definition; glm::vec3 position; int lightGroup=0; };
struct PartsDictionary {
    std::vector<PartDefinition> parts;
    std::array<glm::vec3, 16> lightColours;
    std::string source;
    int textureCount = 0;
    std::filesystem::path directory;

    static PartsDictionary load(const std::filesystem::path& directory) {
        std::ifstream stream(directory / "parts.json");
        if (!stream) throw std::runtime_error("Parts library is missing. Run scripts/build_parts_dictionary.py --jar <local Minecraft client.jar> first.");
        const auto json = nlohmann::json::parse(stream);
        if (json.at("version") != 1 || json.at("units") != "blocks") throw std::runtime_error("Unsupported parts dictionary");
        PartsDictionary result;
        result.directory = directory;
        result.source = json.at("source").at("jar").get<std::string>();
        result.textureCount = static_cast<int>(json.at("textures").size());
        if (result.textureCount < 1 || result.textureCount > 256) throw std::runtime_error("Invalid texture count");
        auto vec3 = [](const nlohmann::json& v) {
            if (!v.is_array() || v.size()!=3) throw std::runtime_error("Expected three coordinates");
            glm::vec3 p(v[0].get<float>(),v[1].get<float>(),v[2].get<float>());
            if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z)) throw std::runtime_error("Nonfinite part coordinates");
            return p;
        };
        for (int i=0;i<16;++i) result.lightColours[i]=vec3(json.at("light_colours").at(i));
        std::set<std::string> identifiers;
        for (const auto& p : json.at("parts")) {
            PartDefinition part;
            part.id=p.at("id"); part.name=p.at("name"); part.block=p.at("block"); part.category=p.at("category");
            part.colour=p.value("colour",std::string()); part.connections=p.value("connections",-1);
            part.emission=p.at("emission"); part.translucent=p.at("translucent");
            part.paneAttach=p.at("pane_attach");
            part.low=vec3(p.at("bounds").at(0)); part.high=vec3(p.at("bounds").at(1)); part.dimensions=vec3(p.at("dimensions"));
            if (!identifiers.insert(part.id).second || part.emission<0 || part.emission>15 || part.connections>15 || part.connections < -1)
                throw std::runtime_error("Invalid or duplicate part definition");
            glm::vec3 actualLow(10000),actualHigh(-10000);
            for (const auto& face : p.at("faces")) {
                if (face.size()!=4) throw std::runtime_error("Invalid part face");
                std::array<PartVertex,4> quad;
                for (int i=0;i<4;++i) {
                    if (face[i].size()!=9) throw std::runtime_error("Invalid part vertex");
                    const auto a=face[i].get<std::array<float,9>>();
                    for (float v:a) if (!std::isfinite(v)) throw std::runtime_error("Nonfinite part vertex");
                    quad[i]={{a[0],a[1],a[2]},{a[3],a[4],a[5]},{a[6],a[7]},a[8]};
                    if (a[8]<0 || a[8]>=result.textureCount || a[8]!=std::floor(a[8]) ||
                        std::abs(glm::length(quad[i].normal)-1)>0.001f) throw std::runtime_error("Invalid part normal or texture");
                    actualLow=glm::min(actualLow,quad[i].position); actualHigh=glm::max(actualHigh,quad[i].position);
                }
                part.faces.push_back(quad);
            }
            if (part.faces.empty() || glm::length(actualLow-part.low)>0.0001f || glm::length(actualHigh-part.high)>0.0001f ||
                glm::length(actualHigh-actualLow-part.dimensions)>0.0001f) throw std::runtime_error("Part bounds do not match actual mesh");
            for(const auto& c:p.at("face_cull")) {
                const auto direction=vec3(c);
                if(direction!=glm::vec3(0) && std::abs(direction.x)+std::abs(direction.y)+std::abs(direction.z)!=1) throw std::runtime_error("Invalid face cull direction");
                part.faceCull.push_back(direction);
            }
            if(part.faceCull.size()!=part.faces.size()) throw std::runtime_error("Face cull metadata does not match geometry");
            result.parts.push_back(std::move(part));
        }
        return result;
    }
};

inline std::string partConnections(int mask) {
    if (mask<0) return "";
    if (mask==0) return "No connections";
    std::string label;
    for (int i=0;i<4;++i) if (mask&(1<<i)) { if (!label.empty()) label+=" "; label+="NESW"[i]; }
    return label;
}
