#include "generation.h"
#include <cstring>
#include <fstream>
#include <iostream>
#include <thread>

void require(bool ok, const std::string& message) { if (!ok) throw std::runtime_error(message); }
nlohmann::json request(const std::string& name, int count = 1000, int seed = 42) {
    return {{"generator", name}, {"count", count}, {"seed", seed}, {"params", nlohmann::json::object()}};
}
GenerationResult run(const GeneratorRuntime& runtime, const std::string& name, int count = 1000) {
    return runGeneration(runtime, request(name, count), std::make_shared<std::atomic_bool>(false));
}
void write(const std::filesystem::path& path, const std::string& source) { std::ofstream(path) << source; }

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Expected temporary test directory");
        if (std::string(argv[1]) == "--benchmark") {
            for (const auto& mode : {"galaxy", "filaments"}) {
                for (int count : {100000, 1000000}) {
                    auto result = run(GeneratorRuntime::defaults(), mode, count);
                    require(result.error.empty(), result.error);
                    std::cout << mode << ": " << count << " stars, math/packing "
                              << result.metadata.at("generation_ms") << " ms, subprocess + transfer "
                              << result.elapsedMs << " ms\n";
                }
            }
            return 0;
        }
        const auto root = std::filesystem::path(argv[1]) /
            ("source with spaces " + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
        std::filesystem::create_directories(root);
        auto runtime = GeneratorRuntime::defaults();
        for (const auto& item : std::filesystem::directory_iterator(runtime.generators))
            if (item.path().extension() == ".py") std::filesystem::copy_file(item.path(), root / item.path().filename());
        runtime.generators = root;
        auto galaxy = run(runtime, "galaxy");
        require(galaxy.error.empty(), galaxy.error);
        require(galaxy.points.size() == 1000 && galaxy.metadata.at("catalog").size() >= 2, "Galaxy or catalog missing");
        auto repeated = run(runtime, "galaxy");
        require(repeated.error.empty() && repeated.points.size() == galaxy.points.size() &&
                std::memcmp(repeated.points.data(), galaxy.points.data(), galaxy.points.size() * sizeof(Point)) == 0,
                "Fixed seed should reproduce point bytes");
        auto filaments = run(runtime, "filaments");
        require(filaments.error.empty() && filaments.points.size() == 1000, "Filament generation failed: " + filaments.error);
        auto curves = run(runtime, "grown_filaments", 1);
        require(curves.error.empty(), curves.error);
        require(curves.metadata.at("primitive") == "lines" && curves.points.size() > 2 && curves.points.size() % 2 == 0,
                "Curve preview must transfer complete endpoint pairs independently of star count");
        const auto before = runtime.sourceFingerprint();
        const auto hot = root / "hot.py";
        const std::string prefix = "import numpy as np\ndef generate(count, seed):\n    return np.full((count,3), ";
        write(hot, prefix + "1), np.ones((count,3))\n");
        require(before != runtime.sourceFingerprint(), "New script not detected by file watcher");
        auto first = run(runtime, "hot");
        require(first.error.empty() && first.points.front().position.x == 1, "New script not discovered");
        require(first.points.front().size == 0.04f, "Legacy scripts should receive default star sizes");
        const auto stamp = std::filesystem::last_write_time(hot);
        write(hot, prefix + "2), np.ones((count,3))\n");
        std::filesystem::last_write_time(hot, stamp); // same timestamp and size: no stale bytecode allowed
        auto second = run(runtime, "hot");
        require(second.error.empty() && second.points.front().position.x == 2, "Script reload reused stale source");
        write(hot, "def generate(:\n");
        auto broken = run(runtime, "hot");
        require(!broken.error.empty() && broken.points.empty(), "Syntax error must not publish points");
        auto other = run(runtime, "galaxy");
        require(other.error.empty() && !other.metadata.at("warnings").empty(), "Broken script must not disable other modes");
        write(hot, prefix + "3), np.ones((count,3))\n");
        auto repaired = run(runtime, "hot");
        require(repaired.error.empty() && repaired.points.front().position.x == 3, "Script repair did not recover");
        write(root / "sized.py", prefix + "0), np.ones((count,3)), np.linspace(0.02, 0.2, count)\n");
        const auto sized = run(runtime, "sized");
        require(sized.error.empty() && sized.points.front().size == 0.02f && sized.points.back().size == 0.2f,
                "Individual star sizes did not survive the Python/C++ transfer");
        write(root / "invalid.py", prefix + "np.nan), np.ones((count,3))\n");
        require(!run(runtime, "invalid").error.empty(), "NaN points must be rejected");
        write(root / "slow.py", "import time\nimport numpy as np\ndef generate(count, seed):\n    time.sleep(10)\n    return np.zeros((count,3)), np.ones((count,3))\n");
        {
            GenerationService service(runtime);
            service.request(request("slow"));
            service.poll();
            std::this_thread::sleep_for(std::chrono::milliseconds(300));
            const auto start = std::chrono::steady_clock::now();
            service.request(request("hot"));
            std::optional<GenerationResult> latest;
            while (!(latest = service.poll()) && std::chrono::steady_clock::now() - start < std::chrono::seconds(5))
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            require(latest && latest->error.empty() && latest->metadata.at("generator") == "hot", "Latest request did not replace slow job");
            require(latest->points.front().position.x == 3, "Stale result was published");
        }
        runtime.timeout = std::chrono::milliseconds(300);
        require(run(runtime, "slow").error.find("timed out") != std::string::npos, "Runaway generator should time out");
        runtime.timeout = std::chrono::milliseconds(60000);
        runtime.python = root / "missing python.exe";
        require(run(runtime, "galaxy").error.find("Could not start Python") != std::string::npos, "Missing interpreter needs a clear error");
        write(root / "corrupt.bin", "not a point buffer");
        bool rejected = false;
        try { readPointFile(root / "corrupt.bin"); } catch (const std::exception&) { rejected = true; }
        require(rejected, "Corrupt binary data must be rejected");
        std::filesystem::remove_all(root); // only this test's freshly created unique directory
        std::cout << "Python bridge, seed reproducibility, reload/repair, validation, cancellation and timeout checks passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
