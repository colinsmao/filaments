#pragma once
#include "point.h"
#include "runtime_config.h"
#include <nlohmann/json.hpp>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <future>
#include <memory>
#include <optional>
#include <string>
#include <vector>

struct GeneratorRuntime {
    std::filesystem::path python = FILAMENTS_PYTHON;
    std::filesystem::path worker = FILAMENTS_WORKER;
    std::filesystem::path generators = FILAMENTS_GENERATORS;
    std::chrono::milliseconds timeout{60000};
    static GeneratorRuntime defaults();
    std::string sourceFingerprint() const;
};

struct GenerationResult {
    nlohmann::json request;
    nlohmann::json metadata = nlohmann::json::object();
    std::vector<Point> points;
    std::vector<Point> stars; // Optional population layer accompanying line geometry.
    std::string error;
    double elapsedMs = 0;
    bool cancelled = false;
};

std::vector<Point> readPointFile(const std::filesystem::path& path, bool allowEmpty = false);
GenerationResult runGeneration(const GeneratorRuntime& runtime, const nlohmann::json& request,
                               const std::shared_ptr<std::atomic_bool>& cancel);

// Latest request wins. Python/file IO run on a worker thread; OpenGL stays on
// the main thread. Polling never waits for a running process.
class GenerationService {
public:
    explicit GenerationService(GeneratorRuntime runtime) : runtime_(std::move(runtime)) {}
    ~GenerationService();
    void request(nlohmann::json request);
    void cancel();
    std::optional<GenerationResult> poll();
    bool busy() const { return future_.valid() || pending_.has_value(); }
private:
    GeneratorRuntime runtime_;
    std::future<GenerationResult> future_;
    std::shared_ptr<std::atomic_bool> cancellation_;
    std::optional<nlohmann::json> pending_;
    unsigned long long revision_ = 0, runningRevision_ = 0;
};
