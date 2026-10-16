#pragma once
#include "planet_generator.h"

// A family is an evaluated whole-planet pairing, with explicit palette choices.
// Component dictionaries still own all cell geometry. The old generator is kept.
struct PlanetFamilyPalette { std::string name,bodyMaterial,ringColour,referenceCrop,observed,assumed; };
struct PlanetFamily {
    std::string id,name,basis,observed,assumed,verdict,referenceCrop;
    size_t body=0,ring=0;
    bool selectable=false;
    std::vector<PlanetFamilyPalette> palettes;
    std::vector<size_t> referencePalettes;
};
struct PlanetFamilyChoice { size_t family=0,palette=0; };
struct PlanetFamilies {
    std::vector<PlanetFamily> families;
    std::vector<size_t> eligible;
    std::set<size_t> referenceComponents;
    size_t firstComponent=0;

    PlanetFamilyChoice select(uint32_t seed,uint32_t index) const {
        if(eligible.empty()) throw std::runtime_error("No planet families have completed inspection");
        const size_t f=eligible[SmallPlanetGenerator::random(seed,index,21)%eligible.size()];
        const auto& palettes=families[f].referencePalettes;
        return {f,palettes[SmallPlanetGenerator::random(seed,index,22)%palettes.size()]};
    }
    PlanetAssembly assemble(const PartsDictionary& assets,const PlanetDictionary& dictionary,
                            PlanetFamilyChoice choice,bool bodyVisible=true,bool ringVisible=true) const {
        const auto& f=families.at(choice.family); const auto& p=f.palettes.at(choice.palette);
        std::vector<size_t> selected; std::map<size_t,std::string> materials;
        if(bodyVisible) { selected.push_back(f.body); if(!p.bodyMaterial.empty()) materials[f.body]=p.bodyMaterial; }
        if(ringVisible) { selected.push_back(f.ring); materials[f.ring]=SmallPlanetGenerator::pane(p.ringColour); }
        return dictionary.assemble(assets,selected,materials);
    }
    nlohmann::json describe(const PlanetDictionary& dictionary,PlanetFamilyChoice c) const {
        const auto& f=families.at(c.family); const auto& p=f.palettes.at(c.palette);
        return {{"family",f.id},{"palette",p.name},{"body",dictionary.components[f.body].id},
                {"ring",dictionary.components[f.ring].id},{"body_material",p.bodyMaterial.empty()?nlohmann::json(nullptr):nlohmann::json(p.bodyMaterial)},
                {"ring_colour",p.ringColour},{"basis",f.basis},{"reference_crop",p.referenceCrop},{"verdict",f.verdict}};
    }
    static PlanetFamilies load(const std::filesystem::path& path,PlanetDictionary& dictionary,const PartsDictionary& assets) {
        const auto studies=PlanetDictionary::load(path,assets);
        PlanetFamilies result; result.firstComponent=dictionary.components.size();
        for(const auto& c:studies.components) {
            for(const auto& old:dictionary.components) if(c.id==old.id) throw std::runtime_error("Duplicate study component: "+c.id);
            if(c.kind=="ring") {
                std::array<int,3> low=c.cells.front().at,high=low;
                for(const auto& cell:c.cells) for(int a=0;a<3;++a) { low[a]=std::min(low[a],cell.at[a]); high[a]=std::max(high[a],cell.at[a]); }
                if(high[1]-low[1]>1 || high[0]==low[0] || high[2]==low[2]) throw std::runtime_error("Planet families require horizontal rings: "+c.id);
            }
            dictionary.components.push_back(c);
        }
        std::ifstream input(path); const auto doc=nlohmann::json::parse(input);
        std::set<std::string> ids;
        for(const auto& item:doc.at("families")) {
            PlanetFamily f;
            f.id=item.at("id"); f.name=item.at("name"); f.basis=item.at("basis");
            f.observed=item.at("observed"); f.assumed=item.at("assumed"); f.verdict=item.at("verdict");
            f.referenceCrop=item.at("reference_crop"); f.selectable=item.at("selectable");
            f.body=dictionary.find(item.at("body")); f.ring=dictionary.find(item.at("ring"));
            if(!ids.insert(f.id).second || !dictionary.fits(f.body,int(f.ring))) throw std::runtime_error("Invalid family pairing: "+f.id);
            for(const auto& p:item.at("palettes")) {
                PlanetFamilyPalette value{p.at("name"),p.at("body_material").is_null()?"":p.at("body_material").get<std::string>(),p.at("ring_colour"),
                    p.value("reference_crop",std::string()),p.value("observed",f.observed),p.value("assumed",f.assumed)};
                if(!value.referenceCrop.empty()) f.referencePalettes.push_back(f.palettes.size());
                f.palettes.push_back(value);
            }
            if(f.palettes.empty()) throw std::runtime_error("Family has no palette");
            result.families.push_back(f);
            const size_t fi=result.families.size()-1;
            for(size_t pi=0;pi<f.palettes.size();++pi) {
                const auto scene=result.assemble(assets,dictionary,{fi,pi});
                size_t panes=0;
                for(const auto& b:scene.blocks) {
                    const auto& a=assets.parts[b.definition];
                    if(a.category=="pane") { ++panes; if(a.block!=SmallPlanetGenerator::pane(f.palettes[pi].ringColour)) throw std::runtime_error("Mixed panes in family"); }
                    else if(a.category!="core") throw std::runtime_error("Family body requires core blocks");
                }
                if(panes!=dictionary.components[f.ring].cells.size()) throw std::runtime_error("Family ring is not entirely panes");
            }
            if(f.selectable) {
                if(f.verdict=="pending native inspection") throw std::runtime_error("Unreviewed family selected");
                if(f.referencePalettes.empty()) throw std::runtime_error("Selectable family has no screenshot-backed palette: "+f.id);
                result.eligible.push_back(fi);
            }
            if(!f.referencePalettes.empty()) { result.referenceComponents.insert(f.body); result.referenceComponents.insert(f.ring); }
        }
        if(result.families.empty()) throw std::runtime_error("No planet studies");
        return result;
    }
};
