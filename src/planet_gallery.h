#pragma once
#include "planet_parts.h"
#include "planet_generator.h"
#include "planet_families.h"
#include "parts_gallery.h"

struct PlanetDisplay {
    std::string name;
    PlanetAssembly assembly;
    glm::vec3 offset{};
    int component=-1,example=-1;
    int generated=-1;
    std::string materialLabel;
    int study=-1;
    size_t palette=0;
};

// Whole components are selected here; the old gallery remains a block-asset browser.
inline int renderPlanetGallery(GLFWwindow* window,const std::filesystem::path& testOutput={}) {
    const bool test=!testOutput.empty();
    const auto assets=PartsDictionary::load(FILAMENTS_PARTS_DIRECTORY);
    auto dictionary=PlanetDictionary::load(FILAMENTS_PLANET_DICTIONARY,assets);
    const auto generator=SmallPlanetGenerator::load(FILAMENTS_PLANET_DICTIONARY,dictionary,assets);
    const auto families=PlanetFamilies::load(FILAMENTS_PLANET_FAMILIES,dictionary,assets);
    PartsRenderer renderer(assets);
    Camera camera; camera.yaw=24; camera.pitch=-25;
    CameraControls controls; controls.speed=4;
    int mode=10,previousMode=-1,frame=0;
    int selectedStudy=0,selectedPalette=0,familyCount=6,dictionaryPage=0;
    bool includeEarlierComponents=false,includeEarlierStudies=false;
    std::vector<PlanetFamilyChoice> familyChoices;
    const int studyViewEnd=65+int(families.families.size())*4;
    const int studyPaletteEnd=studyViewEnd+int(families.families.size())*3;
    int seed=42,count=9,selectedGenerated=0;
    float ringChance=.8f,luminousChance=.5f;
    std::vector<SmallPlanetChoice> generated;
    size_t body=dictionary.find("body-pearl"); int ring=int(dictionary.find("ring-pink"));
    int component=int(body);
    bool night=false,neutral=false,labels=true,done=false,dirty=true,openAssets=false;
    bool showBody=true,showRing=true;
    float fitDistance=25; glm::vec3 center{};
    std::vector<PlanetDisplay> displays;
    std::vector<PartInstance> instances;
    nlohmann::json evidence=nlohmann::json::array();
    if(test) std::filesystem::create_directories(testOutput);
    glfwSwapInterval(test?0:1);
    while(!glfwWindowShouldClose(window) && !done) {
        glfwPollEvents(); controls.checkFocus(window);
        int width,height; glfwGetFramebufferSize(window,&width,&height);
        if(width==0 || height==0) { glfwWaitEventsTimeout(.05); continue; }
        ImGui_ImplOpenGL3_NewFrame(); ImGui_ImplGlfw_NewFrame(); ImGui::NewFrame();
        auto& io=ImGui::GetIO();
        if(test) {
            includeEarlierStudies=frame>=65 && frame<studyPaletteEnd;
            // Overview, body/ring dictionaries, controlled comparisons, each
            // assembled example from front/side/below/oblique, then body-only.
            if(frame<3) mode=frame;
            else if(frame<7) { mode=4; camera.yaw=24; camera.pitch=22; neutral=frame==4; night=frame==5; if(frame==6) camera.pitch=-25; }
            else if(frame<31) {
                mode=3; const auto& e=dictionary.examples[(frame-7)/4]; body=e.body; ring=e.ring;
                const int angle=(frame-7)%4;
                camera.yaw=angle==0?0:angle==1?90:24;
                camera.pitch=angle<2?0:angle==2?-25:22;
                neutral=false; night=false;
            } else if(frame==31) { mode=3; body=dictionary.find("body-stack"); ring=-1; camera.yaw=24; camera.pitch=22; }
            else if(frame<34) { mode=3; body=dictionary.find("body-cased"); ring=int(dictionary.find("ring-wide")); showBody=frame==33; showRing=frame==32; }
            else if(frame<36) { mode=5; component=int(dictionary.find(frame==34?"ring-wide":"ring-tall")); if(frame==35) { camera.yaw=0; camera.pitch=89; } }
            else if(frame<40) { mode=8; showBody=showRing=true; camera.yaw=frame==39?90:frame==37?0:24; camera.pitch=frame==38?-25:frame==37 || frame==39?0:22; }
            else if(frame<47) {
                mode=6; seed=frame==44?7:frame==45?12345:42; count=9; camera.yaw=24; camera.pitch=frame==43?-25:22;
                neutral=frame==41; night=frame==42 || frame==46; ringChance=.8f; luminousChance=frame==46?0:.5f;
            } else if(frame<56) {
                mode=7; seed=42; count=9; ringChance=.8f; luminousChance=.5f; selectedGenerated=frame-47;
                neutral=false; night=false; showBody=showRing=true; camera.yaw=24; camera.pitch=22;
            } else if(frame<60) {
                mode=9; neutral=false; night=false; camera.yaw=frame==57 || frame==59?0:24;
                camera.pitch=frame==57?0:frame==58?-25:frame==59?89:22;
            } else if(frame==60) {
                mode=6; seed=42; count=12; ringChance=.8f; luminousChance=.5f;
                neutral=false; night=false; camera.yaw=24; camera.pitch=22;
            } else if(frame<65) {
                mode=10; const int angle=(frame-61)%4;
                camera.yaw=angle==1?0:angle==2?90:24; camera.pitch=angle==1 || angle==2?0:angle==0?-25:22;
                neutral=false; night=false; showBody=showRing=true;
            } else if(frame<studyViewEnd) {
                mode=11; selectedStudy=(frame-65)/4; selectedPalette=0; const int angle=(frame-65)%4;
                camera.yaw=angle==1?0:angle==2?90:24; camera.pitch=angle==1 || angle==2?0:angle==0?-25:22;
                neutral=false; night=false; showBody=showRing=true;
            } else if(frame<studyPaletteEnd) {
                mode=11; selectedStudy=(frame-studyViewEnd)/3; selectedPalette=(frame-studyViewEnd)%3;
                neutral=false; night=true; showBody=showRing=true; camera.yaw=24; camera.pitch=-25;
            } else if(frame<studyPaletteEnd+4) {
                mode=13; const int angle=frame-studyPaletteEnd;
                camera.yaw=angle==1?0:angle==2?90:24; camera.pitch=angle==1 || angle==2?0:angle==0?-25:22;
                neutral=false; night=false; showBody=showRing=true;
            } else {
                mode=12; seed=frame==studyPaletteEnd+4?42:frame==studyPaletteEnd+5?7:12345; familyCount=6;
                neutral=false; night=false; showBody=showRing=true; camera.yaw=24; camera.pitch=-25;
            }
            dirty=true;
        }
        ImGui::SetNextWindowPos(ImVec2(12,12));
        ImGui::SetNextWindowSize(ImVec2(350,io.DisplaySize.y-24));
        ImGui::Begin("Planet parts",nullptr,ImGuiWindowFlags_NoMove|ImGuiWindowFlags_NoResize);
        ImGui::TextWrapped("A planet = one body + an optional ring.");
        if(ImGui::Combo("Show",&mode,"Earlier examples\0Body dictionary\0Ring dictionary\0Geometric assembly\0Earlier glass comparison\0Single component\0Earlier seeded combinations\0Inspect earlier result\0Tall-body ring comparison\0Pane attachment comparison\0Screenshot studies\0Inspect planet study\0Generated references\0Earlier stepped-ring comparison\0")) dirty=true;
        if(mode==10 || mode==11) {
            if(ImGui::Checkbox("Include earlier studies",&includeEarlierStudies)) {
                if(!includeEarlierStudies) { selectedStudy=int(families.eligible.front()); selectedPalette=int(families.families[selectedStudy].referencePalettes.front()); }
                dirty=true;
            }
        }
        if(mode==10) {
            ImGui::TextWrapped("Five screenshot examples: pink, slime, honey, yellow stack and blue stack. Invented larger shapes and unsupported colour swaps are historical only. Click a label for the exact source and assumptions.");
        }
        if(mode==11) {
            if(ImGui::BeginCombo("Study",families.families[selectedStudy].name.c_str())) {
                for(size_t i=0;i<families.families.size();++i) if(includeEarlierStudies || !families.families[i].referencePalettes.empty())
                    if(ImGui::Selectable(families.families[i].name.c_str(),selectedStudy==int(i))) { selectedStudy=int(i); selectedPalette=0; dirty=true; }
                ImGui::EndCombo();
            }
            const auto& f=families.families[selectedStudy];
            if(ImGui::BeginCombo("Palette",f.palettes[selectedPalette].name.c_str())) {
                for(size_t i=0;i<f.palettes.size();++i) if(includeEarlierStudies || !f.palettes[i].referenceCrop.empty())
                    if(ImGui::Selectable(f.palettes[i].name.c_str(),selectedPalette==int(i))) { selectedPalette=int(i); dirty=true; }
                ImGui::EndCombo();
            }
            if(ImGui::Checkbox("Show body",&showBody)) { if(!showBody && !showRing) showBody=true; dirty=true; }
            ImGui::SameLine(); if(ImGui::Checkbox("Show ring",&showRing)) { if(!showBody && !showRing) showBody=true; dirty=true; }
            ImGui::TextWrapped("%s. %s",f.basis.c_str(),f.verdict.c_str());
            const auto& palette=f.palettes[selectedPalette];
            if(ImGui::CollapsingHeader("Reference evidence and assumptions")) {
                ImGui::TextWrapped("Observed: %s",palette.observed.c_str()); ImGui::TextWrapped("Assumed: %s",palette.assumed.c_str());
                ImGui::TextWrapped("Reference crop: %s",palette.referenceCrop.empty()?"None; historical extension or colour swap":palette.referenceCrop.c_str());
            }
            ImGui::TextWrapped("Body: %s\nRing: %s",dictionary.components[f.body].name.c_str(),dictionary.components[f.ring].name.c_str());
            std::map<std::pair<std::string,int>,int> materials;
            for(const auto& b:families.assemble(assets,dictionary,{size_t(selectedStudy),size_t(selectedPalette)}).blocks) {
                const auto& a=assets.parts[b.definition];
                if(a.category=="core") ++materials[{a.block,a.emission}];
            }
            for(const auto& entry:materials) ImGui::TextWrapped("%d x %s; emits %d / 15",entry.second,entry.first.first.c_str(),entry.first.second);
            ImGui::TextWrapped("Ring: %s panes; emits 0",palette.ringColour.c_str());
            if(ImGui::Button("Back to planet studies")) { mode=10; dirty=true; }
        }
        if(mode==12) {
            if(ImGui::InputInt("Seed",&seed)) { seed=std::max(seed,0); dirty=true; }
            if(ImGui::Button("Next seed")) { seed=seed==2147483647?0:seed+1; dirty=true; }
            if(ImGui::SliderInt("Planets",&familyCount,3,6)) dirty=true;
            ImGui::TextWrapped("Seed chooses a screenshot-based family, then a palette tied to a specific source crop. Five examples across three pairings. No invented larger shapes or unsupported colour swaps.");
            if(families.eligible.empty()) { ImGui::TextWrapped("Family inspection is still pending."); mode=10; dirty=true; }
        }
        if(mode==1 || mode==2) {
            if(ImGui::Checkbox("Include earlier components",&includeEarlierComponents)) { dictionaryPage=0; dirty=true; }
            int total=0; for(size_t i=0;i<dictionary.components.size();++i) if((includeEarlierComponents || families.referenceComponents.count(i)) && dictionary.components[i].kind==(mode==1?"body":"ring")) ++total;
            dictionaryPage=std::min(dictionaryPage,(total-1)/6);
            if(ImGui::SliderInt("Dictionary page",&dictionaryPage,0,(total-1)/6)) dirty=true;
            ImGui::TextWrapped("%d whole components. Default dictionary shows only components used by the screenshot studies. Material changes do not count as new shapes.",total);
        }
        if(mode==6 || mode==7) {
            if(ImGui::InputInt("Seed",&seed)) { seed=std::max(seed,0); dirty=true; }
            if(ImGui::Button("Next seed")) { seed=seed==2147483647?0:seed+1; dirty=true; }
            if(ImGui::SliderInt("Planets",&count,3,12)) { selectedGenerated=std::min(selectedGenerated,count-1); dirty=true; }
            if(ImGui::SliderFloat("Ring chance",&ringChance,0,1,"%.2f")) dirty=true;
            if(ImGui::SliderFloat("Luminous bodies",&luminousChance,0,1,"%.2f")) dirty=true;
            ImGui::TextWrapped("Chances are 0-1 fractions, not quotas. Seed repeats the choices; increasing count keeps existing planets. Each ring has one colour. Click a label for full materials, bounds and block counts.");
            if(mode==7) {
                if(ImGui::SliderInt("Result index",&selectedGenerated,0,count-1)) dirty=true;
                if(ImGui::Checkbox("Show body",&showBody)) { if(!showBody && !showRing) showBody=true; dirty=true; }
                ImGui::SameLine(); if(ImGui::Checkbox("Show ring",&showRing)) { if(!showRing && !showBody) showBody=true; dirty=true; }
                if(!generated.empty() && selectedGenerated<int(generated.size())) {
                    const auto& p=generated[selectedGenerated];
                    ImGui::TextWrapped("Body: %s\nMaterial: %s\nRing: %s\nPane colour: %s\nEmission: %d / 15",p.bodyLabel.c_str(),p.bodyMaterial.c_str(),p.ringLabel.c_str(),p.ring<0?"none":p.ringColour.c_str(),p.emission);
                }
                if(ImGui::Button("Back to generated grid")) { mode=6; dirty=true; }
            }
        }
        if(mode==3) {
            ImGui::TextWrapped("This checks cell overlap only. Generated families use the separately inspected body/ring pairings.");
            if(ImGui::BeginCombo("Body",dictionary.components[body].name.c_str())) {
                for(size_t i=0;i<dictionary.components.size();++i) if(dictionary.components[i].kind=="body") {
                    if(ImGui::Selectable(dictionary.components[i].name.c_str(),body==i)) {
                        body=i; if(!dictionary.fits(body,ring)) ring=-1; dirty=true;
                    }
                }
                ImGui::EndCombo();
            }
            if(ImGui::BeginCombo("Ring",ring<0?"None":dictionary.components[ring].name.c_str())) {
                if(ImGui::Selectable("None",ring<0)) { ring=-1; dirty=true; }
                for(size_t i=0;i<dictionary.components.size();++i) if(dictionary.components[i].kind=="ring") {
                    const bool fits=dictionary.fits(body,int(i));
                    ImGui::BeginDisabled(!fits);
                    if(ImGui::Selectable((dictionary.components[i].name+(fits?"":" (overlaps body)")).c_str(),ring==int(i))) { ring=int(i); dirty=true; }
                    ImGui::EndDisabled();
                }
                ImGui::EndCombo();
            }
            if(ImGui::Checkbox("Show body",&showBody)) { if(!showBody && (!showRing || ring<0)) showBody=true; dirty=true; }
            ImGui::SameLine();
            if(ImGui::Checkbox("Show ring",&showRing)) { if(!showBody && !showRing) showBody=true; dirty=true; }
            ImGui::TextWrapped("%s",dictionary.components[body].description.c_str());
            if(ring>=0) ImGui::TextWrapped("%s",dictionary.components[ring].description.c_str());
            ImGui::TextDisabled("Origin: centre of the mounting block.");
        }
        if(mode==5) {
            if(ImGui::BeginCombo("Component",dictionary.components[component].name.c_str())) {
                for(size_t i=0;i<dictionary.components.size();++i) if(ImGui::Selectable(dictionary.components[i].name.c_str(),component==int(i))) { component=int(i); dirty=true; }
                ImGui::EndCombo();
            }
            ImGui::TextWrapped("%s",dictionary.components[component].description.c_str());
        }
        if(mode==4) ImGui::TextWrapped("Same pearl body and eight ring cells. Left: pink panes. Middle: gray/clear sections. Right: same colour layout in full glass. Orthographic view keeps angle and scale identical.");
        if(mode==8) ImGui::TextWrapped("Same two-block shroomlight body and yellow panes. Left: one-high ring around the lower block. Right: two-high surround. Only the ring's second row changes.");
        if(mode==9) ImGui::TextWrapped("Same eight white pane cells. Sea lantern accepts inward arms; jack-o'-lantern and honey do not. Pane-to-pane corners still connect. Attachment is block metadata, not a test of visible cube bounds.");
        if(mode==13) ImGui::TextWrapped("Same nineteen-block body and purple panes. Left: 4.125-block square belt. Right: 6.125-block stepped ring. Equal angle and scale; only ring geometry changes.");
        ImGui::Separator();
        if(ImGui::Checkbox("Night + block lighting",&night)) dirty=true;
        ImGui::Checkbox("Neutral background",&neutral);
        ImGui::Checkbox("Names and dimensions",&labels);
        if(ImGui::Button("Fit")) { camera.target=center; camera.distance=fitDistance; }
        ImGui::SameLine(); if(ImGui::Button("Front")) { camera.yaw=0; camera.pitch=0; }
        ImGui::SameLine(); if(ImGui::Button("Side")) { camera.yaw=90; camera.pitch=0; }
        if(ImGui::Button("Below")) { camera.yaw=24; camera.pitch=-25; }
        ImGui::SameLine(); if(ImGui::Button("Oblique")) { camera.yaw=24; camera.pitch=22; }
        ImGui::SameLine(); if(ImGui::Button("Top")) { camera.yaw=0; camera.pitch=89; }
        ImGui::Separator();
        ImGui::TextWrapped("Click a label to inspect. Left drag: orbit; middle drag: pan; wheel: zoom. Dimensions are mesh bounds in blocks: X x Y x Z.");
        ImGui::TextWrapped("Panes stay upright: each is 1 block tall, 0.125 thick. The two-high surround uses two rows.");
        ImGui::TextWrapped("Current screenshot studies have one- or two-block cores and single-colour surrounds. Larger layered reference bodies are not reconstructed yet.");
        ImGui::TextDisabled("Block assets: Minecraft %s",assets.source.c_str());
        ImGui::TextWrapped(night?"Existing light formula; each planet is lit separately for inspection. No shadows, bloom or occlusion.":"Material inspection uses texture colour and fixed face shading. Enable night lighting to inspect emission.");
        if(ImGui::Button("Inspect block assets")) openAssets=true;
        ImGui::SameLine(); if(ImGui::Button("Close")) done=true;
        ImGui::End();
        const float scale=float(width)/std::max(io.DisplaySize.x,1.0f);
        const int left=int(374*scale),sceneWidth=std::max(width-left,1);
        if(dirty) {
            displays.clear(); instances.clear();
            auto add=[&](std::string name,std::vector<size_t> selected,int c=-1,int e=-1) {
                displays.push_back({name,dictionary.assemble(assets,selected),{},c,e,-1,{},-1,0});
            };
            auto addGenerated=[&](const SmallPlanetChoice& p,int index,bool bodyVisible=true,bool ringVisible=true) {
                std::string material=p.bodyMaterial; std::replace(material.begin(),material.end(),'_',' ');
                if(mode==6) { const auto word=material.find("glazed "); if(word!=std::string::npos) material.erase(word,7); }
                std::string ringLabel=p.ringLabel;
                if(mode==6) { const auto word=ringLabel.find(" surround"); if(word!=std::string::npos) ringLabel.erase(word); if(ringLabel=="Upright frame") ringLabel="Upright"; }
                const std::string title=(index>=0?"#"+std::to_string(index+1)+" ":"")+p.bodyLabel+(mode==6?" / ":"\n")+ringLabel;
                const std::string label=material+"\n"+(mode==6?(p.ring<0?"":p.ringColour+" | "):
                    (p.ring<0?"no panes":p.ringColour+" panes")+" | ")+"emits "+std::to_string(p.emission);
                displays.push_back({title,generator.assemble(assets,dictionary,p,bodyVisible,ringVisible),{},-1,-1,index,label,-1,0});
            };
            auto addStudy=[&](PlanetFamilyChoice choice,bool bodyVisible=true,bool ringVisible=true) {
                const auto& f=families.families[choice.family]; const auto& p=f.palettes[choice.palette];
                displays.push_back({mode==10 || mode==12?p.name:f.name,families.assemble(assets,dictionary,choice,bodyVisible,ringVisible),{},-1,-1,-1,
                    mode==10 || mode==12?(p.referenceCrop.empty()?"Historical study":"Source: "+p.referenceCrop):f.basis+"\n"+p.name,int(choice.family),choice.palette});
            };
            if(mode==13) {
                for(const std::string id:{"study-wide-belt","study-stepped-belt"}) {
                    const auto b=dictionary.find("study-stepped"),r=dictionary.find(id);
                    displays.push_back({id=="study-wide-belt"?"Close square belt":"Wider stepped ring",dictionary.assemble(assets,{b,r},{{r,"purple_stained_glass_pane"}}),{},-1,-1,-1,{},-1,0});
                }
            } else if(mode==10) {
                for(size_t i=0;i<families.families.size();++i) {
                    if(includeEarlierStudies) addStudy({i,0});
                    else for(const auto p:families.families[i].referencePalettes) addStudy({i,p});
                }
            } else if(mode==11) addStudy({size_t(selectedStudy),size_t(selectedPalette)},showBody,showRing);
            else if(mode==12) {
                familyChoices.clear();
                for(int i=0;i<familyCount;++i) { const auto c=families.select(uint32_t(seed),uint32_t(i)); familyChoices.push_back(c); addStudy(c); }
            } else if(mode==6 || mode==7) {
                generated.clear();
                for(int i=0;i<count;++i) generated.push_back(generator.select(uint32_t(seed),uint32_t(i),ringChance,luminousChance));
                if(mode==6) { for(int i=0;i<count;++i) addGenerated(generated[i],i); }
                else { if(generated[selectedGenerated].ring<0) showBody=true; addGenerated(generated[selectedGenerated],selectedGenerated,showBody,showRing); }
            } else if(mode==8) {
                for(const std::string id:{"ring-pink","ring-double"}) {
                    SmallPlanetChoice p; p.body=dictionary.find("body-stack"); p.ring=int(dictionary.find(id));
                    p.bodyMaterial="shroomlight"; p.ringColour="yellow"; p.bodyLabel="Stack"; p.ringLabel=generator.ringLabels.at(p.ring); p.emission=15;
                    addGenerated(p,-1);
                }
            } else if(mode==9) {
                for(const std::string material:{"sea_lantern","jack_o_lantern","honey_block"}) {
                    SmallPlanetChoice p; p.body=dictionary.find("body-pearl"); p.ring=int(dictionary.find("ring-pink"));
                    p.bodyMaterial=material; p.ringColour="white"; p.bodyLabel="Cube";
                    p.ringLabel=material=="sea_lantern"?"Inward arms":"No inward arms"; p.emission=material=="honey_block"?0:15;
                    addGenerated(p,-1);
                }
            } else if(mode==0 || mode==4) {
                const size_t count=mode==4?3:dictionary.examples.size();
                for(size_t i=0;i<count;++i) { const auto& e=dictionary.examples[i]; std::vector<size_t> selected{e.body}; if(e.ring>=0) selected.push_back(e.ring); add(e.name,selected,-1,int(i)); }
            } else if(mode==1 || mode==2) {
                int index=0;
                for(size_t i=0;i<dictionary.components.size();++i) if((includeEarlierComponents || families.referenceComponents.count(i)) && dictionary.components[i].kind==(mode==1?"body":"ring")) {
                    if(index/6==dictionaryPage) add(dictionary.components[i].name,{i},int(i)); ++index;
                }
            } else if(mode==5) add(dictionary.components[component].name,{size_t(component)},component);
            else {
                if(!showBody && ring<0) showBody=true;
                std::vector<size_t> selected;
                if(showBody) selected.push_back(body);
                if(ring>=0 && showRing) selected.push_back(ring);
                std::string name=showBody?dictionary.components[body].name:"";
                if(ring>=0 && showRing) name+=(name.empty()?"":" + ")+dictionary.components[ring].name;
                add(name,selected);
            }
            const int columns=mode==4 || mode==6 || mode==9 || mode==10 || mode==12?3:displays.size()>1?2:1;
            const int rows=(int(displays.size())+columns-1)/columns;
            const float spacingX=mode==10 || mode==12 || mode==13?8.8f:6.2f;
            glm::vec3 low(10000),high(-10000);
            for(size_t i=0;i<displays.size();++i) {
                auto& d=displays[i];
                const glm::vec3 position((float(i%columns)-(columns-1)*.5f)*spacingX,((rows-1)*.5f-float(i/columns))*5.6f,0);
                d.offset=position-d.assembly.center();
                for(auto block:d.assembly.blocks) { block.position+=d.offset; block.lightGroup=int(i)+1; instances.push_back(block); }
                low=glm::min(low,d.assembly.low+d.offset-glm::vec3(0,1,0));
                high=glm::max(high,d.assembly.high+d.offset);
            }
            // One unscaled reference cube beneath every view.
            size_t reference=0; for(size_t i=0;i<assets.parts.size();++i) if(assets.parts[i].category=="reference") reference=i;
            const glm::vec3 refPos(columns>1?-3.1f:0,low.y-2.1f,0); instances.push_back({reference,refPos});
            low=glm::min(low,refPos-glm::vec3(.5f,1.0f,.5f)); high=glm::max(high,refPos+glm::vec3(.5f));
            center=(low+high)*.5f;
            const float radius=glm::length(high-low)*.5f;
            const float halfFov=std::atan(std::tan(glm::radians(22.5f))*std::min(1.0f,float(sceneWidth)/height));
            fitDistance=radius/std::sin(halfFov)*1.08f;
            if(mode==3 || mode==5 || mode==7 || mode==11) {
                center=glm::vec3(0);
                const float componentRadius=glm::length(displays.front().assembly.dimensions())*.5f;
                // Include the camera-plane reference and its label at any angle.
                fitDistance=std::max(fitDistance,(componentRadius+3.4f)/std::tan(halfFov)+componentRadius);
            }
            if(mode!=previousMode || test || mode==3 || mode==5 || mode==7 || mode==10 || mode==11 || mode==12) { camera.target=center; camera.distance=fitDistance; }
            previousMode=mode; renderer.setScene(instances,night); dirty=false;
        }
        controls.update(window,camera,io);
        if(mode==4 || mode==6 || mode==8 || mode==9 || mode==10 || mode==12 || mode==13) {
            // Place comparison centres on the same camera-depth plane. Geometry
            // retains its world orientation, so each slot has identical scale
            // and viewing angle even while orbiting. No per-item resizing.
            const size_t reference=instances.back().definition;
            instances.clear();
            const int columns=mode==8 || mode==13?2:3;
            const int rows=(int(displays.size())+columns-1)/columns;
            for(size_t i=0;i<displays.size();++i) {
                auto& d=displays[i];
                const float x=(float(i%columns)-(columns-1)*.5f)*(mode==10 || mode==12 || mode==13?8.8f:6.2f);
                const float y=((rows-1)*.5f-float(i/columns))*5.6f;
                d.offset=camera.right()*x+camera.up()*y-d.assembly.center();
                for(auto block:d.assembly.blocks) { block.position+=d.offset; block.lightGroup=int(i)+1; instances.push_back(block); }
            }
            instances.push_back({reference,-camera.up()*((rows-1)*2.8f+4.8f)});
            renderer.setScene(instances,night);
        }
        if(mode==3 || mode==5 || mode==7 || mode==11) {
            // Keep the scale reference clear of the selected component even
            // when looking straight down Y (a world-Y offset would overlap).
            instances.back().position=-camera.up()*(glm::length(displays.front().assembly.dimensions())*.5f+2.2f);
            renderer.setScene(instances,night);
        }
        const float aspect=float(sceneWidth)/height;
        const float halfHeight=camera.distance*std::tan(glm::radians(22.5f))/controls.zoomMultiplier();
        const bool orthographic=mode==4 || mode==6 || mode==8 || mode==9 || mode==10 || mode==12 || mode==13;
        const auto projection=orthographic?glm::ortho(-halfHeight*aspect,halfHeight*aspect,-halfHeight,halfHeight,camera.nearClip,camera.farClip):camera.projection(aspect,controls.zoomMultiplier());
        const auto view=camera.view(),matrix=projection*view;
        glViewport(0,0,width,height);
        if(neutral) glClearColor(.24f,.24f,.24f,1); else glClearColor(.018f,.022f,.035f,1);
        glDepthMask(GL_TRUE); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);
        glViewport(left,0,sceneWidth,height); renderer.draw(matrix,view);
        if(labels) {
            auto* draw=ImGui::GetBackgroundDrawList(); draw->PushClipRect(ImVec2(374,0),io.DisplaySize,true);
            auto project=[&](const glm::vec3& position) {
                const auto clip=matrix*glm::vec4(position,1); if(clip.w<=0) return ImVec2(-10000,-10000);
                const glm::vec3 ndc=glm::vec3(clip)/clip.w;
                return ImVec2((left+(ndc.x*.5f+.5f)*sceneWidth)/scale,(.5f-ndc.y*.5f)*height/scale);
            };
            auto label=[&](const ImVec2& screen,const std::string& name,const std::string& detail) {
                const float wrap=mode==6 || mode==10 || mode==12?std::max(80.f,std::min(220.f,(mode==6?6.2f:8.8f)*height/(2*halfHeight*scale)-12)):
                    mode==3 || mode==5 || mode==7 || mode==11?360.f:220.f;
                float dy=0;
                for(const auto& text:{name,detail}) {
                    const auto extent=ImGui::CalcTextSize(text.c_str(),nullptr,false,wrap);
                    const ImVec2 p(screen.x-extent.x*.5f,screen.y+dy);
                    draw->AddRectFilled(ImVec2(p.x-3,p.y-1),ImVec2(p.x+extent.x+3,p.y+extent.y+1),IM_COL32(0,0,0,175),2);
                    draw->AddText(ImGui::GetFont(),ImGui::GetFontSize(),p,dy==0?IM_COL32(240,240,240,255):IM_COL32(190,202,215,255),text.c_str(),nullptr,wrap);
                    dy+=extent.y+3;
                }
                return !io.WantCaptureMouse && ImGui::IsMouseHoveringRect(ImVec2(screen.x-wrap*.5f,screen.y),ImVec2(screen.x+wrap*.5f,screen.y+dy),false) && ImGui::IsMouseClicked(0);
            };
            for(const auto& d:displays) {
                const auto dim=d.assembly.dimensions(); char detail[128];
                std::snprintf(detail,sizeof(detail),"%.4gx%.4gx%.4g blocks\n%zu part%s / %zu blocks",dim.x,dim.y,dim.z,d.assembly.componentCount,d.assembly.componentCount==1?"":"s",d.assembly.blocks.size());
                if(mode==10) { for(char* c=detail;*c;++c) if(*c=='\n') { *c=0; break; } }
                ImVec2 anchor=project(d.offset+d.assembly.center());
                for(int bits=0;bits<8;++bits) {
                    glm::vec3 corner; for(int axis=0;axis<3;++axis) corner[axis]=bits&(1<<axis)?d.assembly.high[axis]:d.assembly.low[axis];
                    anchor.y=std::max(anchor.y,project(d.offset+corner).y+6);
                }
                if(label(anchor,d.name,mode==6 || mode==12?d.materialLabel:d.materialLabel.empty()?detail:d.materialLabel+"\n"+detail)) {
                    if(d.component>=0) { mode=5; component=d.component; }
                    if(d.example>=0) { mode=3; body=dictionary.examples[d.example].body; ring=dictionary.examples[d.example].ring; showBody=showRing=true; }
                    if(d.generated>=0) { mode=7; selectedGenerated=d.generated; showBody=showRing=true; }
                    if(d.study>=0) { mode=11; selectedStudy=d.study; selectedPalette=int(d.palette); showBody=showRing=true; }
                    dirty=true;
                }
            }
            auto refAnchor=project(instances.back().position);
            for(int bits=0;bits<8;++bits) {
                glm::vec3 corner; for(int axis=0;axis<3;++axis) corner[axis]=bits&(1<<axis)?.5f:-.5f;
                refAnchor.y=std::max(refAnchor.y,project(instances.back().position+corner).y+6);
            }
            label(refAnchor,"Reference cube","1x1x1 block");
            draw->PopClipRect();
        }
        if(test) {
            std::vector<unsigned char> pixels(size_t(sceneWidth)*height*3); glPixelStorei(GL_PACK_ALIGNMENT,1);
            glReadPixels(left,0,sceneWidth,height,GL_RGB,GL_UNSIGNED_BYTE,pixels.data());
            size_t visible=0; const int bg[3]={neutral?61:4,neutral?61:5,neutral?61:8};
            for(size_t i=0;i<pixels.size();i+=3) if(std::abs(int(pixels[i])-bg[0])+std::abs(int(pixels[i+1])-bg[1])+std::abs(int(pixels[i+2])-bg[2])>35) ++visible;
            if(visible<400) throw std::runtime_error("Blank planet gallery view");
            nlohmann::json record={{"frame",frame},{"mode",mode},{"night",night},{"neutral",neutral},{"yaw",camera.yaw},{"pitch",camera.pitch},{"distance",camera.distance},{"target",{camera.target.x,camera.target.y,camera.target.z}},{"visible_pixels",visible},{"exhibits",nlohmann::json::array()}};
            for(const auto& d:displays) { const auto v=d.assembly.dimensions(); record["exhibits"].push_back({{"name",d.name},{"components",d.assembly.componentCount},{"blocks",d.assembly.blocks.size()},{"dimensions",{v.x,v.y,v.z}}}); }
            record["projection"]=orthographic?"orthographic":"perspective";
            if(mode==10 || mode==11 || mode==12) {
                record["studies"]=nlohmann::json::array();
                for(const auto& d:displays) record["studies"].push_back(families.describe(dictionary,{size_t(d.study),d.palette}));
                if(mode==12) record["seed"]=seed;
            }
            if(mode==6 || mode==7) {
                record["seed"]=seed; record["ring_chance"]=ringChance; record["luminous_chance"]=luminousChance;
                record["choices"]=nlohmann::json::array();
                for(const auto& p:generated) record["choices"].push_back(SmallPlanetGenerator::describe(dictionary,p));
            }
            record["resolved_blocks"]=nlohmann::json::array();
            for(const auto& b:instances) record["resolved_blocks"].push_back({{"asset",assets.parts[b.definition].id},{"position",{b.position.x,b.position.y,b.position.z}},{"light_group",b.lightGroup}});
            evidence.push_back(record);
        }
        glViewport(0,0,width,height); ImGui::Render(); ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        if(test) {
            saveGalleryPixels(testOutput/("planet-"+std::to_string(frame)+".ppm"),width,height);
            if(glGetError()!=GL_NO_ERROR) throw std::runtime_error("OpenGL error in planet gallery");
            if(++frame==(families.eligible.empty()?studyPaletteEnd+4:studyPaletteEnd+7)) done=true;
        }
        glfwSwapBuffers(window);
        if(openAssets) { renderPartsGallery(window); openAssets=false; glfwSwapInterval(test?0:1); }
    }
    if(test) { std::ofstream out(testOutput/"views.json"); out<<evidence.dump(2)<<'\n'; }
    controls.capture(window,false); return 0;
}
