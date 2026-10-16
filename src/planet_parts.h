#pragma once
#include "parts_dictionary.h"
#include <map>

// A component is an authored whole body or ring. Block assets remain below it.
struct PlanetCell { std::array<int,3> at; std::string block; };
struct PlanetComponent {
    std::string id, kind, name, description;
    std::vector<PlanetCell> cells;
};
struct PlanetExample { std::string name; size_t body; int ring=-1; };
struct PlanetAssembly {
    std::vector<PartInstance> blocks;
    glm::vec3 low{10000},high{-10000};
    size_t componentCount=0;
    glm::vec3 dimensions() const { return high-low; }
    glm::vec3 center() const { return (high+low)*.5f; }
};
struct PlanetDictionary {
    std::vector<PlanetComponent> components;
    std::vector<PlanetExample> examples;

    size_t find(const std::string& id) const {
        for(size_t i=0;i<components.size();++i) if(components[i].id==id) return i;
        throw std::runtime_error("Unknown planet component: "+id);
    }
    // Any occupied-cell overlap is rejected; never clip or resize a component.
    bool fits(size_t body,int ring) const {
        if(components.at(body).kind!="body") return false;
        if(ring<0) return true;
        if(components.at(ring).kind!="ring") return false;
        for(const auto& a:components[body].cells) for(const auto& b:components[ring].cells) if(a.at==b.at) return false;
        return true;
    }
    PlanetAssembly assemble(const PartsDictionary& assets,const std::vector<size_t>& selected,
                            const std::map<size_t,std::string>& materials={}) const {
        if(selected.empty() || selected.size()>2) throw std::runtime_error("Select one component, or a body and ring");
        if(selected.size()==2 && !fits(selected[0],int(selected[1]))) throw std::runtime_error("Body and ring overlap or have invalid roles");
        std::map<std::array<int,3>,std::string> cells;
        for(size_t index:selected) for(const auto& c:components.at(index).cells) {
            const auto replacement=materials.find(index);
            if(!cells.emplace(c.at,replacement==materials.end()?c.block:replacement->second).second) throw std::runtime_error("Overlapping planet cells");
        }
        auto asset=[&](const std::string& block,int mask)->size_t {
            for(size_t i=0;i<assets.parts.size();++i) if(assets.parts[i].block==block && assets.parts[i].connections==mask) return i;
            throw std::runtime_error("Missing planet block asset: "+block);
        };
        PlanetAssembly result; result.componentCount=selected.size();
        const int directions[4][3]={{0,0,-1},{1,0,0},{0,0,1},{-1,0,0}};
        for(const auto& [position,block]:cells) {
            const bool pane=block=="glass_pane" || block.find("_glass_pane")!=std::string::npos;
            int mask=-1;
            if(pane) {
                mask=0;
                for(int d=0;d<4;++d) {
                    auto adjacent=position;
                    for(int a=0;a<3;++a) adjacent[a]+=directions[d][a];
                    const auto neighbor=cells.find(adjacent);
                    if(neighbor!=cells.end()) {
                        // Attachment is a block rule, not a cube-bounds test:
                        // pumpkins/jack-o-lanterns are exceptions; honey's support
                        // face is too small. Glass panes attach to each other.
                        const auto& name=neighbor->second;
                        const bool neighborPane=name=="glass_pane" || name.find("_glass_pane")!=std::string::npos;
                        const auto& def=assets.parts[asset(name,neighborPane?0:-1)];
                        if(def.paneAttach) mask|=1<<d;
                    }
                }
            }
            const size_t definition=asset(block,mask);
            const glm::vec3 p(position[0],position[1],position[2]);
            const auto& def=assets.parts[definition];
            result.blocks.push_back({definition,p});
            result.low=glm::min(result.low,p+def.low); result.high=glm::max(result.high,p+def.high);
        }
        return result;
    }
    static PlanetDictionary load(const std::filesystem::path& path,const PartsDictionary& assets) {
        std::ifstream stream(path);
        if(!stream) throw std::runtime_error("Missing planet component dictionary: "+path.string());
        const auto doc=nlohmann::json::parse(stream);
        if(doc.at("version")!=1 || doc.at("units")!="blocks") throw std::runtime_error("Unsupported planet dictionary");
        PlanetDictionary result;
        std::set<std::string> ids;
        for(const auto& item:doc.at("components")) {
            PlanetComponent c;
            c.id=item.at("id"); c.kind=item.at("kind"); c.name=item.at("name"); c.description=item.at("description");
            if(c.id.empty() || !ids.insert(c.id).second || (c.kind!="body" && c.kind!="ring")) throw std::runtime_error("Invalid planet component identity");
            for(const auto& cell:item.at("cells")) {
                if(!cell.is_array() || cell.size()!=4) throw std::runtime_error("Invalid planet cell");
                PlanetCell value;
                for(int axis=0;axis<3;++axis) {
                    if(!cell[axis].is_number_integer() || std::abs(cell[axis].get<double>())>64) throw std::runtime_error("Planet cells must be integer block centres within 64 blocks");
                    value.at[axis]=cell[axis].get<int>();
                }
                value.block=cell[3].get<std::string>(); c.cells.push_back(value);
            }
            if(c.cells.empty() || c.cells.size()>4096) throw std::runtime_error("Invalid planet component size");
            result.components.push_back(c);
            result.assemble(assets,{result.components.size()-1});
        }
        for(const auto& item:doc.at("examples")) {
            PlanetExample example{item.at("name"),result.find(item.at("body")),item.contains("ring")?int(result.find(item.at("ring"))):-1};
            if(!result.fits(example.body,example.ring)) throw std::runtime_error("Invalid planet example");
            result.examples.push_back(example);
        }
        if(result.examples.empty()) throw std::runtime_error("Planet dictionary has no examples");
        return result;
    }
};
