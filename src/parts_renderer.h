#pragma once
#include "parts_dictionary.h"
#include "point_renderer.h"
#include <algorithm>
#include <cstdint>
#include <numeric>

class PartsRenderer {
    struct Vertex { PartVertex part; glm::vec3 light; };
    struct Face { std::array<Vertex,4> vertices; glm::vec3 center; };
    GLuint vao=0,vbo=0,program=0,texture=0;
    std::vector<Vertex> opaque;
    std::vector<Face> transparent;
    const PartsDictionary& dictionary;
public:
    explicit PartsRenderer(const PartsDictionary& dictionary) : dictionary(dictionary) {
        std::ifstream input(dictionary.directory/"textures.rgba",std::ios::binary);
        char magic[4]; uint32_t w=0,h=0,layers=0;
        input.read(magic,4); input.read(reinterpret_cast<char*>(&w),4); input.read(reinterpret_cast<char*>(&h),4); input.read(reinterpret_cast<char*>(&layers),4);
        if (!input || std::string(magic,4)!="PTEX" || w!=16 || h!=16 || layers!=uint32_t(dictionary.textureCount))
            throw std::runtime_error("Invalid parts texture array");
        std::vector<unsigned char> pixels(size_t(w)*h*layers*4);
        input.read(reinterpret_cast<char*>(pixels.data()),pixels.size());
        if (!input || input.peek()!=std::char_traits<char>::eof()) throw std::runtime_error("Truncated or oversized parts texture array");
        program=renderProgram(R"(#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec3 normal;
layout(location=2) in vec2 uv;
layout(location=3) in float layer;
layout(location=4) in vec3 illumination;
uniform mat4 matrix;
out vec3 texcoord;
out vec3 light;
void main() {
    gl_Position=matrix*vec4(position,1);
    texcoord=vec3(uv,layer);
    float face=abs(normal.x)>.5?.82:abs(normal.z)>.5?.92:normal.y>0?1:.85;
    light=illumination*face;
})",R"(#version 330 core
uniform sampler2DArray atlas;
in vec3 texcoord;
in vec3 light;
out vec4 fragColor;
void main() {
    vec4 tex=texture(atlas,texcoord);
    if(tex.a<.01) discard;
    fragColor=vec4(tex.rgb*light,tex.a);
})");
        glGenVertexArrays(1,&vao); glGenBuffers(1,&vbo); glBindVertexArray(vao); glBindBuffer(GL_ARRAY_BUFFER,vbo);
        const int counts[]={3,3,2,1,3};
        const size_t offsets[]={offsetof(Vertex,part)+offsetof(PartVertex,position),offsetof(Vertex,part)+offsetof(PartVertex,normal),
            offsetof(Vertex,part)+offsetof(PartVertex,uv),offsetof(Vertex,part)+offsetof(PartVertex,texture),offsetof(Vertex,light)};
        for(GLuint i=0;i<5;++i) { glEnableVertexAttribArray(i); glVertexAttribPointer(i,counts[i],GL_FLOAT,GL_FALSE,sizeof(Vertex),reinterpret_cast<void*>(offsets[i])); }
        glGenTextures(1,&texture); glBindTexture(GL_TEXTURE_2D_ARRAY,texture);
        glTexImage3D(GL_TEXTURE_2D_ARRAY,0,GL_RGBA8,w,h,layers,0,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());
        glTexParameteri(GL_TEXTURE_2D_ARRAY,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D_ARRAY,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D_ARRAY,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D_ARRAY,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
        glBindVertexArray(0);
    }
    ~PartsRenderer() { glDeleteTextures(1,&texture); glDeleteBuffers(1,&vbo); glDeleteVertexArrays(1,&vao); glDeleteProgram(program); }
    PartsRenderer(const PartsRenderer&)=delete;
    PartsRenderer& operator=(const PartsRenderer&)=delete;
    size_t transparentFaceCount() const { return transparent.size(); }

    void setScene(const std::vector<PartInstance>& instances,bool night) {
        opaque.clear(); transparent.clear();
        for (const auto& instance:instances) {
            const auto& part=dictionary.parts.at(instance.definition);
            float level=0;
            for(const auto& source:instances) {
                if(source.lightGroup!=instance.lightGroup) continue;
                const auto delta=glm::abs(instance.position-source.position);
                level=std::max(level,float(dictionary.parts.at(source.definition).emission)-delta.x-delta.y-delta.z);
            }
            level=std::clamp(level,0.0f,15.0f);
            const int lo=int(level),hi=std::min(lo+1,15);
            const auto light=night?glm::mix(dictionary.lightColours[lo],dictionary.lightColours[hi],level-lo):glm::vec3(1);
            for (size_t faceIndex=0;faceIndex<part.faces.size();++faceIndex) {
                const auto& quad=part.faces[faceIndex];
                // Connected full-glass blocks of the same material have no
                // interior surface. Keep boundaries between different colours.
                bool internal=false;
                if(part.category=="glass") {
                    const auto normal=quad[0].normal;
                    const auto adjacent=instance.position+normal;
                    for(const auto& other:instances) {
                        const auto& neighbor=dictionary.parts.at(other.definition);
                        if(neighbor.block==part.block && glm::length(other.position-adjacent)<.00001f) { internal=true; break; }
                    }
                }
                if(part.category=="pane" && part.faceCull[faceIndex]!=glm::vec3(0)) {
                    // Source models mark connected arm end caps for culling.
                    // Unmarked faces (including pane top/bottom) stay literal.
                    const auto direction=part.faceCull[faceIndex];
                    const auto adjacent=instance.position+direction;
                    const int bit=direction.z<0?0:direction.x>0?1:direction.z>0?2:3;
                    for(const auto& other:instances) {
                        const auto& neighbor=dictionary.parts.at(other.definition);
                        if(neighbor.block==part.block && glm::length(other.position-adjacent)<.00001f &&
                           (part.connections&(1<<bit)) && (neighbor.connections&(1<<((bit+2)%4)))) { internal=true; break; }
                    }
                }
                if(internal) continue;
                Face face{};
                for(int i=0;i<4;++i) { face.vertices[i]={quad[i],light}; face.vertices[i].part.position+=instance.position; face.center+=face.vertices[i].part.position*.25f; }
                if(part.translucent) transparent.push_back(face);
                else for(int i:{0,1,2,0,2,3}) opaque.push_back(face.vertices[i]);
            }
        }
    }
    void draw(const glm::mat4& matrix,const glm::mat4& view) {
        glEnable(GL_DEPTH_TEST); glEnable(GL_CULL_FACE); glDepthMask(GL_TRUE); glDisable(GL_BLEND);
        glUseProgram(program); glUniformMatrix4fv(glGetUniformLocation(program,"matrix"),1,GL_FALSE,glm::value_ptr(matrix));
        glUniform1i(glGetUniformLocation(program,"atlas"),0);
        glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D_ARRAY,texture); glBindVertexArray(vao); glBindBuffer(GL_ARRAY_BUFFER,vbo);
        auto drawVertices=[&](const std::vector<Vertex>& vertices) {
            if(vertices.empty()) return;
            glBufferData(GL_ARRAY_BUFFER,vertices.size()*sizeof(Vertex),vertices.data(),GL_STREAM_DRAW);
            glDrawArrays(GL_TRIANGLES,0,static_cast<GLsizei>(vertices.size()));
        };
        drawVertices(opaque);
        // Sort faces, not whole parts: front/back surfaces of glass can interleave.
        // Recipes use nonoverlapping cells. Intersecting transparent meshes would
        // require splitting/order-independent transparency, not this face sort.
        std::vector<size_t> order(transparent.size()); std::iota(order.begin(),order.end(),0);
        std::sort(order.begin(),order.end(),[&](size_t a,size_t b) {
            const auto& first=transparent[a]; const auto& second=transparent[b];
            const float za=(view*glm::vec4(first.center,1)).z,zb=(view*glm::vec4(second.center,1)).z;
            if(za!=zb) return za<zb;
            // Equal-depth pane faces need a geometry/material tie-breaker too.
            // Keeping input order here causes one-level rounding differences
            // when an otherwise identical assembly is submitted in reverse.
            auto key=[](const Vertex& v) {
                return std::array<float,12>{v.part.position.x,v.part.position.y,v.part.position.z,
                    v.part.normal.x,v.part.normal.y,v.part.normal.z,v.part.uv.x,v.part.uv.y,
                    v.part.texture,v.light.x,v.light.y,v.light.z};
            };
            for(int i=0;i<4;++i) {
                const auto ka=key(first.vertices[i]),kb=key(second.vertices[i]);
                if(ka!=kb) return ka<kb;
            }
            return false;
        });
        std::vector<Vertex> sorted; sorted.reserve(order.size()*6);
        for(size_t index:order) for(int i:{0,1,2,0,2,3}) sorted.push_back(transparent[index].vertices[i]);
        glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA); glDepthMask(GL_FALSE);
        drawVertices(sorted);
        glDepthMask(GL_TRUE); glDisable(GL_BLEND); glDisable(GL_CULL_FACE); glBindVertexArray(0);
    }
};
