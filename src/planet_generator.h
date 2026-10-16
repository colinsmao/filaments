#pragma once
#include "planet_parts.h"
#include <cstdint>

struct SmallPlanetChoice {
    size_t body=0;
    int ring=-1;
    std::string bodyMaterial,ringColour,bodyLabel,ringLabel;
    int emission=0;
};

// Data-only component selection. No renderer, placement, time or global RNG.
struct SmallPlanetGenerator {
    struct Body { size_t component; std::string label; std::vector<size_t> rings; };
    std::vector<Body> bodies;
    std::map<size_t,std::string> ringLabels;
    std::vector<std::string> luminous,unlit,colours;
    std::map<std::string,int> emissions;

    static uint64_t random(uint32_t seed,uint32_t index,uint32_t channel) {
        // Version-1 indexed SplitMix64: item count and unrelated choices cannot
        // shift the random stream for an existing item.
        uint64_t value=(uint64_t(seed)<<32)^uint64_t(index)^uint64_t(channel)*0x9e3779b97f4a7c15ULL;
        value=(value^(value>>30))*0xbf58476d1ce4e5b9ULL;
        value=(value^(value>>27))*0x94d049bb133111ebULL;
        return value^(value>>31);
    }
    static bool chance(uint64_t value,float probability) {
        return double(value>>11)*(1.0/9007199254740992.0)<probability;
    }
    static std::string pane(const std::string& colour) {
        return colour=="clear"?"glass_pane":colour+"_stained_glass_pane";
    }
    SmallPlanetChoice select(uint32_t seed,uint32_t index,float ringChance=.8f,float luminousChance=.5f) const {
        if(!std::isfinite(ringChance) || !std::isfinite(luminousChance) || ringChance<0 || ringChance>1 || luminousChance<0 || luminousChance>1)
            throw std::runtime_error("Planet probabilities must be between zero and one");
        const auto& b=bodies.at(random(seed,index,1)%bodies.size());
        SmallPlanetChoice result;
        result.body=b.component; result.bodyLabel=b.label;
        if(chance(random(seed,index,2),ringChance)) result.ring=int(b.rings.at(random(seed,index,3)%b.rings.size()));
        result.ringLabel=result.ring<0?"No ring":ringLabels.at(size_t(result.ring));
        const auto& materials=chance(random(seed,index,4),luminousChance)?luminous:unlit;
        result.bodyMaterial=materials.at(random(seed,index,5)%materials.size());
        result.ringColour=colours.at(random(seed,index,6)%colours.size());
        result.emission=emissions.at(result.bodyMaterial);
        return result;
    }
    PlanetAssembly assemble(const PartsDictionary& assets,const PlanetDictionary& dictionary,const SmallPlanetChoice& choice,
                            bool showBody=true,bool showRing=true) const {
        std::vector<size_t> selected;
        std::map<size_t,std::string> materials;
        if(showBody) { selected.push_back(choice.body); materials[choice.body]=choice.bodyMaterial; }
        if(showRing && choice.ring>=0) { selected.push_back(choice.ring); materials[size_t(choice.ring)]=pane(choice.ringColour); }
        return dictionary.assemble(assets,selected,materials);
    }
    static nlohmann::json describe(const PlanetDictionary& dictionary,const SmallPlanetChoice& p) {
        return {{"body",dictionary.components[p.body].id},{"ring",p.ring<0?nlohmann::json(nullptr):nlohmann::json(dictionary.components[p.ring].id)},
                {"body_material",p.bodyMaterial},{"ring_colour",p.ring<0?nlohmann::json(nullptr):nlohmann::json(p.ringColour)},
                {"emission",p.emission}};
    }
    static SmallPlanetGenerator load(const std::filesystem::path& path,const PlanetDictionary& dictionary,const PartsDictionary& assets) {
        std::ifstream stream(path); const auto doc=nlohmann::json::parse(stream).at("small_planets");
        if(doc.at("version")!=1) throw std::runtime_error("Unsupported small-planet generator version");
        SmallPlanetGenerator result;
        auto asset=[&](const std::string& block,int connections)->const PartDefinition& {
            for(const auto& p:assets.parts) if(p.block==block && p.connections==connections) return p;
            throw std::runtime_error("Missing generator material: "+block);
        };
        for(const auto& b:doc.at("bodies")) {
            const size_t index=dictionary.find(b.at("component"));
            const auto& component=dictionary.components[index];
            if(component.kind!="body" || component.cells.size()>2) throw std::runtime_error("Small bodies must contain one or two blocks");
            Body body{index,b.at("label"),{}};
            for(const auto& r:b.at("rings")) {
                const size_t ring=dictionary.find(r);
                if(!dictionary.fits(index,int(ring))) throw std::runtime_error("Generator lists an overlapping ring");
                const auto& recipe=dictionary.components[ring];
                std::set<std::string> materials;
                for(const auto& cell:recipe.cells) { if(asset(cell.block,0).category!="pane") throw std::runtime_error("Small rings must use panes"); materials.insert(cell.block); }
                if(materials.size()!=1) throw std::runtime_error("Small ring recipe must have one colour");
                body.rings.push_back(ring);
                result.ringLabels[ring]=doc.at("rings").at(recipe.id).get<std::string>();
            }
            if(body.rings.empty()) throw std::runtime_error("Small body has no ring options");
            result.bodies.push_back(body);
        }
        result.luminous=doc.at("luminous_materials").get<std::vector<std::string>>();
        result.unlit=doc.at("unlit_materials").get<std::vector<std::string>>();
        result.colours=doc.at("ring_colours").get<std::vector<std::string>>();
        if(result.bodies.empty() || result.luminous.empty() || result.unlit.empty() || result.colours.empty()) throw std::runtime_error("Empty small-planet selection pool");
        for(int lit=0;lit<2;++lit) for(const auto& name:lit?result.luminous:result.unlit) {
            const auto& p=asset(name,-1);
            if(p.translucent || p.category!="core" || p.low!=glm::vec3(-.5f) || p.high!=glm::vec3(.5f) || (p.emission>0)!=bool(lit))
                throw std::runtime_error("Body material must be a full opaque core with matching emission class");
            result.emissions[name]=p.emission;
        }
        for(const auto& colour:result.colours) for(int mask=0;mask<16;++mask)
            if(asset(pane(colour),mask).category!="pane") throw std::runtime_error("Invalid ring colour");
        return result;
    }
};
