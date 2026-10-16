#pragma once
#include "parts_renderer.h"
#include "camera.h"
#include "camera_controls.h"
#include "runtime_config.h"
#include <GLFW/glfw3.h>
#include <imgui.h>
#include <imgui_impl_glfw.h>
#include <imgui_impl_opengl3.h>
#include <cstdio>

inline std::vector<size_t> gallerySelection(const PartsDictionary& dictionary,int group,const std::string& colour,size_t selected) {
    std::vector<size_t> indices;
    for(size_t i=0;i<dictionary.parts.size();++i) {
        const auto& p=dictionary.parts[i];
        bool include=false;
        if(group==0) include=p.category=="reference" || (p.category=="core" && i<=6) ||
            (p.category=="glass" && (p.colour=="orange" || p.colour=="lime" || p.colour=="blue")) ||
            (p.category=="pane" && p.colour=="lime" && (p.connections==0 || p.connections==1 || p.connections==3 || p.connections==5 || p.connections==15)) ||
            (p.category=="fence" && p.connections==15);
        if(group==1) include=p.category=="pane" && p.colour==colour;
        if(group==2) include=p.category=="glass" || (p.category=="pane" && p.connections==5);
        if(group==3) include=p.category=="core";
        if(group==4) include=p.category=="fence";
        if(group==5) include=i==selected || p.category=="reference";
        if(include) indices.push_back(i);
    }
    return indices;
}

inline std::string galleryLabel(const PartDefinition& p) {
    return p.category=="reference"?"Unit cube":p.name + (p.connections>=0?" | "+partConnections(p.connections):"");
}

inline std::string galleryShortLabel(const PartDefinition& p,int group) {
    auto connection=partConnections(p.connections);
    connection.erase(std::remove(connection.begin(),connection.end(),' '),connection.end());
    if(p.category=="reference") return "Unit cube";
    if(p.category=="pane") return (group==1?std::string("Pane"):p.colour+" pane")+" / "+(p.connections==0?"none":connection);
    if(p.category=="glass") return p.colour+" glass";
    if(p.category=="fence") return "Fence / "+(p.connections==0?"none":connection);
    return p.name;
}

inline void saveGalleryPixels(const std::filesystem::path& file,int width,int height) {
    std::vector<unsigned char> pixels(size_t(width)*height*3);
    glPixelStorei(GL_PACK_ALIGNMENT,1); glReadPixels(0,0,width,height,GL_RGB,GL_UNSIGNED_BYTE,pixels.data());
    std::ofstream out(file,std::ios::binary);
    out<<"P6\n"<<width<<" "<<height<<"\n255\n";
    for(int y=height-1;y>=0;--y) out.write(reinterpret_cast<const char*>(pixels.data()+size_t(y)*width*3),width*3);
    if(!out) throw std::runtime_error("Could not save gallery render");
}

// Gallery state is intentionally local. It neither reads nor writes plot settings.
inline int renderPartsGallery(GLFWwindow* window,const std::filesystem::path& testOutput={}) {
    const bool test=!testOutput.empty();
    const auto dictionary=PartsDictionary::load(FILAMENTS_PARTS_DIRECTORY);
    PartsRenderer renderer(dictionary);
    Camera camera; camera.yaw=24; camera.pitch=12;
    CameraControls controls; controls.speed=4;
    int group=0,colourIndex=6,previousGroup=-1,frame=0;
    const char* colours[]={"clear","white","gray","orange","red","yellow","lime","blue","purple","pink"};
    size_t selected=0;
    bool night=false,labels=true,neutral=false,done=false,dirty=true;
    float background[3]={.018f,.022f,.035f};
    std::vector<PartInstance> instances;
    glm::vec3 center(0);
    float fitDistance=20;
    if(test) std::filesystem::create_directories(testOutput);
    glfwSwapInterval(test?0:1);
    while(!glfwWindowShouldClose(window) && !done) {
        glfwPollEvents(); controls.checkFocus(window);
        int width,height; glfwGetFramebufferSize(window,&width,&height);
        if(width==0 || height==0) { glfwWaitEventsTimeout(.05); continue; }
        ImGui_ImplOpenGL3_NewFrame(); ImGui_ImplGlfw_NewFrame(); ImGui::NewFrame();
        auto& io=ImGui::GetIO();
        if(test) {
            const int groups[]={0,1,2,3,4,5,5,2,5,5}; group=groups[frame];
            if(frame==5) { for(size_t i=0;i<dictionary.parts.size();++i) if(dictionary.parts[i].block=="lime_stained_glass_pane" && dictionary.parts[i].connections==1) selected=i; }
            if(frame==6) { for(size_t i=0;i<dictionary.parts.size();++i) if(dictionary.parts[i].block=="blue_glazed_terracotta") selected=i; }
            if(frame>=8) { for(size_t i=0;i<dictionary.parts.size();++i) if(dictionary.parts[i].block=="lime_stained_glass_pane" && dictionary.parts[i].connections==15) selected=i; }
            if(frame==8) { camera.yaw=90; camera.pitch=0; }
            if(frame==9) { camera.yaw=24; camera.pitch=-25; }
            neutral=frame==2; night=frame==7; dirty=true;
        }
        ImGui::SetNextWindowPos(ImVec2(12,12));
        ImGui::SetNextWindowSize(ImVec2(350,io.DisplaySize.y-24));
        ImGui::Begin("Block assets",nullptr,ImGuiWindowFlags_NoMove|ImGuiWindowFlags_NoResize);
        ImGui::TextWrapped("Block models used inside whole bodies and rings.");
        ImGui::TextDisabled("Source: Minecraft %s",dictionary.source.c_str());
        ImGui::Separator();
        if(ImGui::Combo("Show",&group,"Overview\0Pane connections\0Glass colours\0Core materials\0Fence connections\0Single part\0")) dirty=true;
        if(group==1 && ImGui::Combo("Glass colour",&colourIndex,colours,10)) dirty=true;
        if(group==5) {
            if(ImGui::BeginCombo("Part",galleryLabel(dictionary.parts.at(selected)).c_str())) {
                for(size_t i=0;i<dictionary.parts.size();++i) {
                    ImGui::PushID(int(i));
                    if(ImGui::Selectable(galleryLabel(dictionary.parts[i]).c_str(),i==selected)) { selected=i; dirty=true; }
                    ImGui::PopID();
                }
                ImGui::EndCombo();
            }
        }
        if(ImGui::Checkbox("Night + block lighting",&night)) dirty=true;
        ImGui::Checkbox("Names and dimensions",&labels);
        if(ImGui::Checkbox("Neutral background",&neutral)) {
            // Background only; lighting, part colour and alpha remain unchanged.
        }
        ImGui::ColorEdit3("Dark background",background);
        if(ImGui::Button("Fit parts")) { camera.target=center; camera.distance=fitDistance; }
        ImGui::SameLine();
        if(ImGui::Button("Front")) { camera.yaw=0; camera.pitch=0; }
        if(ImGui::Button("Side")) { camera.yaw=90; camera.pitch=0; }
        ImGui::SameLine();
        if(ImGui::Button("Below")) { camera.yaw=24; camera.pitch=-25; }
        ImGui::SameLine();
        if(ImGui::Button("Oblique")) { camera.yaw=24; camera.pitch=12; }
        ImGui::Separator();
        ImGui::TextWrapped("Click a part label to inspect it. Left drag: orbit. Middle drag: pan. Wheel: zoom. WASD / E / Q: move.");
        ImGui::TextWrapped("All panes stay upright. N/E/S/W are connections on the block grid; Y is vertical.");
        ImGui::TextWrapped("Dimensions below each part are actual mesh bounds in blocks (X x Y x Z), not its occupied cell count.");
        ImGui::Separator();
        ImGui::Text("%zu dictionary entries",dictionary.parts.size());
        ImGui::TextWrapped(night?"Night uses the existing light-colour formula and local emitting cores. No shadows or occlusion.":"Material inspection: texture colour with the existing block-face shading. Emission does not brighten neighbours in this mode.");
        ImGui::TextWrapped("Original texture alpha; nearest-pixel filtering. Animated textures show their first frame. No bloom.");
        if(group==5) {
            const auto& p=dictionary.parts.at(selected);
            ImGui::Separator(); ImGui::TextWrapped("%s",p.id.c_str());
            ImGui::Text("Emission: %d / 15",p.emission);
            ImGui::Text("Surface: %s",p.translucent?"Transparent":"Opaque");
            ImGui::Text("Faces: %zu",p.faces.size());
        }
        ImGui::Separator();
        if(ImGui::Button("Close gallery")) done=true;
        ImGui::End();
        if(dirty) {
            auto selection=gallerySelection(dictionary,group,colours[colourIndex],selected);
            instances.clear();
            const int columns=group==5?2:4;
            const int rows=(int(selection.size())+columns-1)/columns;
            for(size_t i=0;i<selection.size();++i) {
                glm::vec3 pos((float(i%columns)-(columns-1)*.5f)*3.2f,((rows-1)*.5f-float(i/columns))*3.0f,0);
                // In individual inspection, separate the reference vertically so
                // an exact side view cannot hide the part behind the reference.
                if(group==5) pos={0,selection.size()==1?0.0f:(dictionary.parts[selection[i]].category=="reference"?-1.6f:1.6f),0};
                instances.push_back({selection[i],pos});
            }
            center={0,-.3f,0};
            fitDistance=group==5?7.5f:std::max(16.0f,rows*4.7f);
            if(group!=previousGroup || test) { camera.target=center; camera.distance=fitDistance; }
            previousGroup=group;
            renderer.setScene(instances,night); dirty=false;
        }
        controls.update(window,camera,io);
        const float scale=float(width)/std::max(io.DisplaySize.x,1.0f);
        const int left=int(374*scale),sceneWidth=std::max(width-left,1);
        const auto projection=camera.projection(float(sceneWidth)/height,controls.zoomMultiplier());
        const auto view=camera.view(),matrix=projection*view;
        glViewport(0,0,width,height);
        if(neutral) glClearColor(.24f,.24f,.24f,1); else glClearColor(background[0],background[1],background[2],1);
        glDepthMask(GL_TRUE); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);
        glViewport(left,0,sceneWidth,height); renderer.draw(matrix,view);
        if(labels) {
            auto* draw=ImGui::GetBackgroundDrawList();
            draw->PushClipRect(ImVec2(374,0),io.DisplaySize,true);
            for(const auto& instance:instances) {
                const auto& p=dictionary.parts[instance.definition];
                const auto clip=matrix*glm::vec4(instance.position+glm::vec3(0,-.78f,0),1);
                if(clip.w<=0) continue;
                const glm::vec3 ndc=glm::vec3(clip)/clip.w;
                const ImVec2 screen((left+(ndc.x*.5f+.5f)*sceneWidth)/scale,(.5f-ndc.y*.5f)*height/scale);
                const auto label=galleryShortLabel(p,group);
                char dimensions[96]; std::snprintf(dimensions,sizeof(dimensions),"%.4gx%.4gx%.4g",p.dimensions.x,p.dimensions.y,p.dimensions.z);
                const float wrap=group==5?260.0f:112.0f;
                auto text=[&](const char* value,float dy,ImU32 colour) {
                    const auto extent=ImGui::CalcTextSize(value,nullptr,false,wrap); const ImVec2 pos(screen.x-extent.x*.5f,screen.y+dy);
                    draw->AddRectFilled(ImVec2(pos.x-3,pos.y-1),ImVec2(pos.x+extent.x+3,pos.y+extent.y+1),IM_COL32(0,0,0,160),2);
                    draw->AddText(ImGui::GetFont(),ImGui::GetFontSize(),pos,colour,value,nullptr,wrap);
                    return extent.y;
                };
                const float labelHeight=text(label.c_str(),0,IM_COL32(240,240,240,255));
                const float dimHeight=text(dimensions,labelHeight+3,IM_COL32(190,202,215,255));
                const ImVec2 hitLow(screen.x-wrap*.5f,screen.y),hitHigh(screen.x+wrap*.5f,screen.y+labelHeight+3+dimHeight);
                if(!io.WantCaptureMouse && ImGui::IsMouseHoveringRect(hitLow,hitHigh,false)) {
                    ImGui::BeginTooltip(); ImGui::TextWrapped("%s",p.id.c_str()); ImGui::Text("Emission: %d / 15",p.emission); ImGui::EndTooltip();
                    if(ImGui::IsMouseClicked(ImGuiMouseButton_Left)) { selected=instance.definition; group=5; dirty=true; }
                }
            }
            draw->PopClipRect();
        }
        if(test) {
            std::vector<unsigned char> pixels(size_t(sceneWidth)*height*3);
            glPixelStorei(GL_PACK_ALIGNMENT,1); glReadPixels(left,0,sceneWidth,height,GL_RGB,GL_UNSIGNED_BYTE,pixels.data());
            size_t distinct=0;
            const int r=neutral?61:int(background[0]*255),g=neutral?61:int(background[1]*255),b=neutral?61:int(background[2]*255);
            for(size_t i=0;i<pixels.size();i+=3) if(std::abs(int(pixels[i])-r)+std::abs(int(pixels[i+1])-g)+std::abs(int(pixels[i+2])-b)>35) ++distinct;
            if(distinct<400) throw std::runtime_error("Gallery scene is blank");
            std::printf("Gallery view %d: %zu parts, %zu visible pixels\n",frame,instances.size(),distinct);
        }
        glViewport(0,0,width,height); ImGui::Render(); ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        if(test) {
            saveGalleryPixels(testOutput/("gallery-"+std::to_string(frame)+".ppm"),width,height);
            if(glGetError()!=GL_NO_ERROR) throw std::runtime_error("OpenGL error in parts gallery");
            if(++frame==10) done=true;
        }
        glfwSwapBuffers(window);
    }
    controls.capture(window,false);
    return 0;
}
