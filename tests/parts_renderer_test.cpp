#include "parts_renderer.h"
#include "planet_parts.h"
#include "planet_generator.h"
#include "planet_families.h"
#include "runtime_config.h"
#include <GLFW/glfw3.h>
#include <glm/gtc/matrix_transform.hpp>
#include <iostream>

int main() {
    if(!glfwInit()) return 1;
    glfwWindowHint(GLFW_VISIBLE,GLFW_FALSE);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR,3); glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR,3);
    glfwWindowHint(GLFW_OPENGL_PROFILE,GLFW_OPENGL_CORE_PROFILE);
    auto* window=glfwCreateWindow(320,240,"Parts test",nullptr,nullptr);
    if(!window) { glfwTerminate(); return 1; }
    glfwMakeContextCurrent(window);
    if(!gladLoadGLLoader(reinterpret_cast<GLADloadproc>(glfwGetProcAddress))) return 1;
    int result=0;
    try {
        const auto dict=PartsDictionary::load(FILAMENTS_PARTS_DIRECTORY);
        PartsRenderer renderer(dict);
        auto find=[&](const std::string& block,int connections=-1) {
            for(size_t i=0;i<dict.parts.size();++i) if(dict.parts[i].block==block && dict.parts[i].connections==connections) return i;
            throw std::runtime_error("Missing test part");
        };
        const auto white=find("white_concrete"),blue=find("blue_stained_glass"),clear=find("glass"),lamp=find("shroomlight");
        auto view=glm::lookAt(glm::vec3(0,0,5),glm::vec3(0),glm::vec3(0,1,0));
        auto matrix=glm::perspective(glm::radians(45.0f),320.f/240.f,.01f,100.f)*view;
        auto capture=[&](const std::vector<PartInstance>& scene,bool night=false) {
            renderer.setScene(scene,night);
            glViewport(0,0,320,240); glClearColor(.02f,.02f,.02f,1); glDepthMask(GL_TRUE);
            glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT); renderer.draw(matrix,view);
            std::vector<unsigned char> pixels(320*240*3); glPixelStorei(GL_PACK_ALIGNMENT,1);
            glReadPixels(0,0,320,240,GL_RGB,GL_UNSIGNED_BYTE,pixels.data());
            if(glGetError()!=GL_NO_ERROR) throw std::runtime_error("Parts OpenGL failure");
            return pixels;
        };
        auto center=[](const std::vector<unsigned char>& pixels) { const size_t i=(120*320+160)*3; return glm::vec3(pixels[i],pixels[i+1],pixels[i+2]); };
        const auto plain=capture({{white,{0,0,0}}});
        const auto throughClear=capture({{white,{0,0,0}},{clear,{0,0,1}}});
        if(glm::length(center(plain)-center(throughClear))>3) throw std::runtime_error("Clear glass lost texture transparency");
        const auto throughBlue=capture({{white,{0,0,0}},{blue,{0,0,1}}});
        if(center(throughBlue).r>=center(plain).r-10 || center(throughBlue).r<50) throw std::runtime_error("Blue glass did not tint a visible opaque core");
        if(throughBlue!=capture({{blue,{0,0,1}},{white,{0,0,0}}})) throw std::runtime_error("Transparency depends on part submission order");
        if(glm::length(center(capture({{white,{0,0,1}},{blue,{0,0,0}}}))-center(capture({{white,{0,0,1}}})))>3)
            throw std::runtime_error("Glass behind an opaque block incorrectly blended over it");
        const auto dark=center(capture({{white,{0,0,0}}},true));
        const auto lit=center(capture({{white,{0,0,0}},{lamp,{4,0,0}}},true));
        if(lit.r<dark.r+10) throw std::runtime_error("Emitting part did not illuminate the nearby receiver");
        const auto isolated=center(capture({{white,{0,0,0},1},{lamp,{4,0,0},2}},true));
        if(glm::length(isolated-dark)>1) throw std::runtime_error("Separate gallery planets leak block light between exhibits");
        auto greenCount=[](const std::vector<unsigned char>& pixels) {
            size_t count=0; for(size_t i=0;i<pixels.size();i+=3) if(pixels[i+1]>pixels[i]+10 && pixels[i+1]>pixels[i+2]+10) ++count; return count;
        };
        const auto thin=greenCount(capture({{find("lime_stained_glass_pane",1),{0,0,0}}}));
        const auto cross=greenCount(capture({{find("lime_stained_glass_pane",15),{0,0,0}}}));
        if(thin<10 || cross<thin*3) throw std::runtime_error("Pane connection states did not change the rendered silhouette");
        const size_t east=find("lime_stained_glass_pane",2),west=find("lime_stained_glass_pane",8);
        renderer.setScene({{east,{0,0,0}},{west,{1,0,0}}},false);
        if(renderer.transparentFaceCount()!=dict.parts[east].faces.size()+dict.parts[west].faces.size()-2)
            throw std::runtime_error("Connected panes retained their touching end caps");
        const auto planets=PlanetDictionary::load(FILAMENTS_PLANET_DICTIONARY,dict);
        for(const auto& example:planets.examples) {
            std::vector<size_t> selected{example.body}; if(example.ring>=0) selected.push_back(example.ring);
            auto scene=planets.assemble(dict,selected).blocks;
            const auto original=capture(scene);
            std::reverse(scene.begin(),scene.end());
            if(original!=capture(scene)) throw std::runtime_error("Assembled glass depends on block submission order: "+example.name);
        }
        const auto generator=SmallPlanetGenerator::load(FILAMENTS_PLANET_DICTIONARY,planets,dict);
        for(uint32_t i=0;i<12;++i) {
            auto scene=generator.assemble(dict,planets,generator.select(42,i)).blocks;
            const auto original=capture(scene,true); std::reverse(scene.begin(),scene.end());
            const auto reversed=capture(scene,true);
            if(original!=reversed) {
                size_t changed=0; int maxDelta=0;
                for(size_t p=0;p<original.size();++p) if(original[p]!=reversed[p]) { ++changed; maxDelta=std::max(maxDelta,std::abs(int(original[p])-int(reversed[p]))); }
                throw std::runtime_error("Generated planet blending depends on submission order: index="+std::to_string(i)+", channels="+std::to_string(changed)+", max delta="+std::to_string(maxDelta));
            }
        }
        auto studyDictionary=planets;
        const auto families=PlanetFamilies::load(FILAMENTS_PLANET_FAMILIES,studyDictionary,dict);
        for(int angle=0;angle<2;++angle) {
          view=glm::lookAt(angle?glm::vec3(8,-6,12):glm::vec3(0,0,10),glm::vec3(0),glm::vec3(0,1,0));
          matrix=glm::perspective(glm::radians(45.0f),320.f/240.f,.01f,100.f)*view;
          for(size_t fi=0;fi<families.families.size();++fi) for(size_t pi=0;pi<families.families[fi].palettes.size();++pi) {
            auto scene=families.assemble(dict,studyDictionary,{fi,pi}).blocks;
            const auto original=capture(scene,true); std::reverse(scene.begin(),scene.end());
            if(original!=capture(scene,true)) throw std::runtime_error("Study blending depends on block order: "+families.families[fi].id);
          }
        }
        std::cout<<"Parts: clear/tinted alpha, depth occlusion, order invariance, local light and pane silhouette passed; thin="<<thin<<", cross="<<cross<<"\n";
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; result=1; }
    glfwDestroyWindow(window); glfwTerminate(); return result;
}
