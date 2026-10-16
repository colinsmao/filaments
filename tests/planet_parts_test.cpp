#include "planet_parts.h"
#include "planet_generator.h"
#include "planet_families.h"
#include "runtime_config.h"
#include <iostream>

int main() {
    try {
        const auto assets=PartsDictionary::load(FILAMENTS_PARTS_DIRECTORY);
        const auto dict=PlanetDictionary::load(FILAMENTS_PLANET_DICTIONARY,assets);
        auto require=[](bool ok,const char* reason) { if(!ok) throw std::runtime_error(reason); };
        auto dimensions=[&](const std::string& id,glm::vec3 expected) {
            require(glm::length(dict.assemble(assets,{dict.find(id)}).dimensions()-expected)<.00001f,"Wrong assembled mesh bounds");
        };
        dimensions("body-pearl",{1,1,1}); dimensions("body-stack",{1,2,1}); dimensions("body-cased",{3,3,3});
        dimensions("ring-pink",{2.125,1,2.125}); dimensions("ring-broken",{2.125,1,2.125});
        dimensions("ring-glass",{3,1,3}); dimensions("ring-tall",{2.125,3,.125}); dimensions("ring-wide",{4.125,1,4.125});
        dimensions("ring-double",{2.125,2,2.125}); dimensions("ring-upright",{2.125,3,.125});
        require(dict.components.size()==11 && dict.examples.size()==6,"Incomplete component dictionary");
        size_t combinations=0;
        for(size_t b=0;b<dict.components.size();++b) if(dict.components[b].kind=="body") {
            require(dict.fits(b,-1),"Ring must be optional");
            for(size_t r=0;r<dict.components.size();++r) if(dict.components[r].kind=="ring" && dict.fits(b,int(r))) {
                const auto a=dict.assemble(assets,{b,r});
                require(a.componentCount==2 && a.blocks.size()==dict.components[b].cells.size()+dict.components[r].cells.size(),"Assembly lost blocks or component identity");
                ++combinations;
            }
        }
        require(combinations==20,"Compatibility matrix changed");
        const auto pearl=dict.find("body-pearl"),pink=dict.find("ring-pink");
        auto connections=[&](const PlanetAssembly& a,glm::vec3 at) {
            for(const auto& block:a.blocks) if(block.position==at) return assets.parts[block.definition].connections;
            throw std::runtime_error("Missing expected cell");
        };
        require(connections(dict.assemble(assets,{pink}),{0,0,-1})==10,"Standalone ring has wrong EW arm connections");
        require(connections(dict.assemble(assets,{pearl,pink}),{0,0,-1})==14,"Combined ring must connect to the body on its south face");
        for(const std::string material:{"honey_block","jack_o_lantern","pumpkin"}) {
            const auto assembled=dict.assemble(assets,{pearl,pink},{{pearl,material}});
            require(connections(assembled,{0,0,-1})==10,"Pane incorrectly attaches to a nonattachable body");
            require(connections(assembled,{-1,0,-1})==6,"Body exception broke pane-to-pane corner connections");
        }
        for(const std::string material:{"sea_lantern","moss_block","glass","slime_block"})
            require(connections(dict.assemble(assets,{pearl,pink},{{pearl,material}}),{0,0,-1})==14,"Pane lost a valid body connection");
        require(!dict.fits(dict.find("body-stack"),int(dict.find("ring-tall"))),"Stack clips the upright frame");
        bool rejected=false;
        try { dict.assemble(assets,{dict.find("body-stack"),dict.find("ring-tall")}); } catch(const std::exception&) { rejected=true; }
        require(rejected,"Clipping combination was assembled");
        auto duplicate=dict; duplicate.components[pearl].cells.push_back(duplicate.components[pearl].cells.front());
        rejected=false; try { duplicate.assemble(assets,{pearl}); } catch(const std::exception&) { rejected=true; }
        require(rejected,"Duplicate occupied cells accepted");
        const auto& plain=dict.components[pink].cells;
        const auto& mixed=dict.components[dict.find("ring-broken")].cells;
        const auto& full=dict.components[dict.find("ring-glass")].cells;
        require(plain.size()==mixed.size() && plain.size()==full.size(),"Comparison layout counts differ");
        for(size_t i=0;i<plain.size();++i) {
            require(plain[i].at==mixed[i].at && mixed[i].at==full[i].at,"Comparison positions changed");
            require(mixed[i].block.substr(0,mixed[i].block.size()-5)==full[i].block,"Full-glass comparison changes colours");
        }
        const auto generator=SmallPlanetGenerator::load(FILAMENTS_PLANET_DICTIONARY,dict,assets);
        std::set<std::string> seenBodies,seenRings,seenMaterials,seenColours;
        int ringless=0,emitting=0,dark=0;
        nlohmann::json seed42=nlohmann::json::array();
        for(uint32_t seed=0;seed<1000;++seed) for(uint32_t i=0;i<12;++i) {
            const auto p=generator.select(seed,i);
            require(SmallPlanetGenerator::describe(dict,p)==SmallPlanetGenerator::describe(dict,generator.select(seed,i)),"Seeded result is not repeatable");
            require(dict.fits(p.body,p.ring),"Generated components collide");
            const auto assembled=generator.assemble(assets,dict,p);
            require(assembled.componentCount==(p.ring<0?1u:2u),"Generated component count changed");
            const size_t bodyCount=dict.components[p.body].cells.size();
            size_t countedBody=0,countedPane=0;
            for(const auto& instance:assembled.blocks) {
                const auto& a=assets.parts[instance.definition];
                require(a.category!="glass","Full glass leaked into small planets");
                if(a.category=="pane") {
                    ++countedPane;
                    require(a.block==SmallPlanetGenerator::pane(p.ringColour),"Ring has mixed pane colours");
                    require(a.emission==0,"Pane colour incorrectly changes emission");
                } else {
                    ++countedBody;
                    require(a.block==p.bodyMaterial && a.emission==p.emission,"Body material or emission lost during assembly");
                }
            }
            require(countedBody==bodyCount,"Body block count changed");
            require(countedPane==(p.ring<0?0:dict.components[p.ring].cells.size()),"Ring block count changed");
            const auto noRing=generator.select(seed,i,0,.5f),allRing=generator.select(seed,i,1,.5f);
            require(noRing.ring<0 && allRing.ring>=0,"Ring chance endpoints failed");
            require(noRing.body==p.body && allRing.body==p.body && noRing.bodyMaterial==p.bodyMaterial && allRing.bodyMaterial==p.bodyMaterial && allRing.ringColour==p.ringColour,"Ring chance changed independent choices");
            const auto unlit=generator.select(seed,i,.8f,0),lit=generator.select(seed,i,.8f,1);
            require(unlit.emission==0 && lit.emission>0,"Luminous chance endpoints failed");
            require(unlit.body==p.body && lit.body==p.body && unlit.ring==p.ring && lit.ring==p.ring && lit.ringColour==p.ringColour,"Luminous chance changed geometry or pane colour");
            seenBodies.insert(dict.components[p.body].id); seenMaterials.insert(p.bodyMaterial);
            if(p.ring>=0) { seenRings.insert(dict.components[p.ring].id); seenColours.insert(p.ringColour); } else ++ringless;
            if(p.emission) ++emitting; else ++dark;
            if(seed==42 && i<9) seed42.push_back(SmallPlanetGenerator::describe(dict,p));
        }
        require(seenBodies.size()==2 && seenRings.size()==3 && seenMaterials.size()==12 && seenColours.size()==9 && ringless>0 && emitting>0 && dark>0,"Selection pools were not exercised");
        // Evaluate a longer batch out of order: preexisting indices must remain unchanged.
        for(int i=11;i>=0;--i) if(i<9) require(seed42[i]==SmallPlanetGenerator::describe(dict,generator.select(42,uint32_t(i))),"Count or evaluation order changes existing results");
        std::cout<<"11 whole components, 20 geometric pairs, 12000 generated planets: repeatability, independent controls, single-colour panes, emission and compatibility passed\n";
        std::cout<<"Seed 42: "<<seed42.dump()<<'\n';
        auto studyDictionary=dict;
        const auto families=PlanetFamilies::load(FILAMENTS_PLANET_FAMILIES,studyDictionary,assets);
        require(families.families.size()==6 && studyDictionary.components.size()==21,"Study component inventory changed");
        require(families.eligible.size()==3 && families.referenceComponents.size()==4,"Screenshot scope changed");
        size_t paletteCount=0;
        for(size_t fi=0;fi<families.families.size();++fi) {
            const auto& f=families.families[fi];
            require(studyDictionary.fits(f.body,int(f.ring)),"Study body/ring overlaps");
            for(size_t pi=0;pi<f.palettes.size();++pi) {
                ++paletteCount;
                const auto scene=families.assemble(assets,studyDictionary,{fi,pi});
                require(scene.componentCount==2,"Whole study component identity lost");
                require(scene.blocks.size()==studyDictionary.components[f.body].cells.size()+studyDictionary.components[f.ring].cells.size(),"Study geometry was cut to fit");
                require(families.assemble(assets,studyDictionary,{fi,pi},false,true).componentCount==1,"Ring-only inspection failed");
                require(families.assemble(assets,studyDictionary,{fi,pi},true,false).componentCount==1,"Body-only inspection failed");
            }
        }
        require(paletteCount==18,"Study palette inventory changed");
        auto studyDimensions=[&](const std::string& id,glm::vec3 expected) {
            require(glm::length(studyDictionary.assemble(assets,{studyDictionary.find(id)}).dimensions()-expected)<.00001f,"Wrong study mesh bounds");
        };
        studyDimensions("study-bar",{3,1,1}); studyDimensions("study-disc",{3,1,3}); studyDimensions("study-stepped",{3,3,3});
        studyDimensions("study-long-belt",{4.125,1,2.125}); studyDimensions("study-wide-belt",{4.125,1,4.125});
        studyDimensions("study-stepped-belt",{6.125,1,6.125});
        require(studyDictionary.components[studyDictionary.find("study-stepped")].cells.size()==19,"Stepped body lost its corner cuts");
        // The tall reference palette retains an unlit upper pumpkin and luminous
        // lower jack-o'-lantern. A single whole-body override would lose this.
        const auto tall=families.assemble(assets,studyDictionary,{2,0});
        int sources=0;
        for(const auto& b:tall.blocks) if(assets.parts[b.definition].emission) ++sources;
        require(sources==1,"Authored tall-body emission arrangement lost");
        const auto honey=families.assemble(assets,studyDictionary,{1,0});
        require(connections(honey,{0,0,-1})==10,"Detached belt acquired an inward arm");
        if(!families.eligible.empty()) {
            std::set<size_t> selectedFamilies;
            for(uint32_t seed=0;seed<1000;++seed) for(uint32_t i=0;i<12;++i) {
                const auto c=families.select(seed,i);
                require(families.families[c.family].selectable,"Unreviewed family selected");
                require(!families.families[c.family].palettes[c.palette].referenceCrop.empty(),"Unsupported palette entered screenshot generation");
                require(families.describe(studyDictionary,c)==families.describe(studyDictionary,families.select(seed,i)),"Family result depends on evaluation order");
                require(families.assemble(assets,studyDictionary,c).componentCount==2,"Generated family changed pairing");
                selectedFamilies.insert(c.family);
            }
            require(selectedFamilies.size()==families.eligible.size(),"Family selection did not exercise all eligible shapes");
        }
        std::cout<<"Six horizontal studies / five body shapes / five rings / 18 palettes: geometry, mounting, source arrangement and family selection passed\n";
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
