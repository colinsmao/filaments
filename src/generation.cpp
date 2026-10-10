#include "generation.h"
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace {
struct Handle {
    HANDLE value = nullptr;
    explicit Handle(HANDLE handle = nullptr) : value(handle) {}
    ~Handle() { if (value && value != INVALID_HANDLE_VALUE) CloseHandle(value); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
};

struct JobDirectory {
    std::filesystem::path path;
    JobDirectory() {
        static std::atomic<unsigned> serial{0};
        const auto base = std::filesystem::temp_directory_path();
        for (int attempt = 0; attempt < 100; ++attempt) {
            auto candidate = base / ("filaments-job-" + std::to_string(GetCurrentProcessId()) + "-" +
                                    std::to_string(GetTickCount64()) + "-" + std::to_string(serial++));
            if (std::filesystem::create_directory(candidate)) { path = candidate; return; }
        }
        throw std::runtime_error("Cannot create a temporary generation directory");
    }
    ~JobDirectory() { std::error_code error; std::filesystem::remove_all(path, error); }
};

// Windows argv quoting, without a shell. Handles spaces, quotes and trailing slashes.
std::wstring quote(const std::wstring& argument) {
    std::wstring result = L"\"";
    size_t slashes = 0;
    for (wchar_t ch : argument) {
        if (ch == L'\\') { ++slashes; continue; }
        result.append(slashes * (ch == L'"' ? 2 : 1), L'\\');
        if (ch == L'"') result += L'\\';
        result += ch;
        slashes = 0;
    }
    result.append(slashes * 2, L'\\');
    return result + L'"';
}

std::string readLog(const std::filesystem::path& path) {
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file) return {};
    const auto size = static_cast<std::streamoff>(file.tellg());
    file.seekg(size > 8192 ? size - std::streamoff(8192) : std::streamoff(0));
    return std::string(std::istreambuf_iterator<char>(file), {});
}

void runPython(const GeneratorRuntime& runtime, const JobDirectory& directory,
               const std::shared_ptr<std::atomic_bool>& cancel) {
    SECURITY_ATTRIBUTES attributes{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
    Handle log(CreateFileW((directory.path / "python.log").c_str(), GENERIC_WRITE, FILE_SHARE_READ,
                           &attributes, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr));
    Handle input(CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                             &attributes, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr));
    if (log.value == INVALID_HANDLE_VALUE || input.value == INVALID_HANDLE_VALUE)
        throw std::runtime_error("Cannot create Python process IO handles");
    Handle job(CreateJobObjectW(nullptr, nullptr));
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!job.value || !SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &limits, sizeof(limits)))
        throw std::runtime_error("Cannot create a managed Python job");
    std::wstring command = quote(runtime.python.wstring()) + L" -B " + quote(runtime.worker.wstring()) +
        L" --request " + quote((directory.path / "request.json").wstring()) +
        L" --response " + quote((directory.path / "response.json").wstring()) +
        L" --points " + quote((directory.path / "points.bin").wstring()) +
        L" --generators " + quote(runtime.generators.wstring());
    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = input.value;
    startup.hStdOutput = startup.hStdError = log.value;
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(runtime.python.c_str(), command.data(), nullptr, nullptr, TRUE,
                        CREATE_NO_WINDOW | CREATE_SUSPENDED, nullptr, directory.path.c_str(), &startup, &process))
        throw std::runtime_error("Could not start Python (Windows error " + std::to_string(GetLastError()) +
                                 "). Check FILAMENTS_PYTHON and the NumPy installation.");
    Handle processHandle(process.hProcess), threadHandle(process.hThread);
    if (!AssignProcessToJobObject(job.value, process.hProcess)) {
        TerminateProcess(process.hProcess, 1);
        WaitForSingleObject(process.hProcess, 5000);
        throw std::runtime_error("Could not attach Python to its cancellation job");
    }
    if (ResumeThread(process.hThread) == static_cast<DWORD>(-1))
        throw std::runtime_error("Could not resume Python process");
    const auto started = std::chrono::steady_clock::now();
    while (true) {
        const auto wait = WaitForSingleObject(process.hProcess, 20);
        if (wait == WAIT_OBJECT_0) break;
        if (wait == WAIT_FAILED) throw std::runtime_error("Could not wait for Python process");
        const bool timedOut = std::chrono::steady_clock::now() - started > runtime.timeout;
        if (*cancel || timedOut) {
            TerminateJobObject(job.value, 1);
            WaitForSingleObject(process.hProcess, 5000);
            throw std::runtime_error(*cancel ? "Generation cancelled" : "Generation timed out (60 second default limit)");
        }
    }
    DWORD exitCode = 0;
    GetExitCodeProcess(process.hProcess, &exitCode);
    if (exitCode != 0)
        throw std::runtime_error("Python exited with code " + std::to_string(exitCode) + "\n" + readLog(directory.path / "python.log"));
}
}

GeneratorRuntime GeneratorRuntime::defaults() {
    GeneratorRuntime result;
    if (const char* python = std::getenv("FILAMENTS_PYTHON")) result.python = std::filesystem::u8path(python);
    if (const char* generators = std::getenv("FILAMENTS_GENERATORS")) result.generators = std::filesystem::u8path(generators);
    return result;
}

std::string GeneratorRuntime::sourceFingerprint() const {
    std::vector<std::string> entries;
    const auto add = [&](const std::filesystem::path& path) {
        std::error_code error;
        const auto stamp = std::filesystem::last_write_time(path, error);
        entries.push_back(path.u8string() + (error ? "missing" : std::to_string(static_cast<long long>(stamp.time_since_epoch().count()))));
    };
    add(worker);
    std::error_code error;
    for (std::filesystem::recursive_directory_iterator it(generators, error), end; !error && it != end; it.increment(error))
        if (it->path().extension() == ".py") add(it->path());
    std::sort(entries.begin(), entries.end());
    std::string result;
    for (const auto& entry : entries) result += entry + "\n";
    return result;
}

std::vector<Point> readPointFile(const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) throw std::runtime_error("Python returned no point buffer");
    const auto size = stream.tellg();
    stream.seekg(0);
    char magic[8]{};
    std::uint64_t count = 0;
    stream.read(magic, sizeof(magic));
    stream.read(reinterpret_cast<char*>(&count), sizeof(count));
    if (!stream || std::string(magic, 8) != "FSTAR001" || count == 0 || count > 1000000 ||
        size != std::streamoff(16 + count * sizeof(Point)))
        throw std::runtime_error("Invalid point buffer header, count or length");
    std::vector<Point> points(static_cast<size_t>(count));
    stream.read(reinterpret_cast<char*>(points.data()), static_cast<std::streamsize>(points.size() * sizeof(Point)));
    if (!stream) throw std::runtime_error("Incomplete point buffer");
    for (const auto& point : points) {
        for (int i = 0; i < 3; ++i) {
            if (!std::isfinite(point.position[i]) || std::abs(point.position[i]) > 1e6f ||
                !std::isfinite(point.color[i]) || point.color[i] < 0 || point.color[i] > 1)
                throw std::runtime_error("Invalid point coordinates or colors");
        }
    }
    return points;
}

GenerationResult runGeneration(const GeneratorRuntime& runtime, const nlohmann::json& request,
                               const std::shared_ptr<std::atomic_bool>& cancel) {
    GenerationResult result;
    result.request = request;
    const auto started = std::chrono::steady_clock::now();
    try {
        if (*cancel) throw std::runtime_error("Generation cancelled");
        JobDirectory directory;
        {
            std::ofstream file(directory.path / "request.json");
            file << request.dump();
            if (!file) throw std::runtime_error("Cannot write generation request");
        }
        runPython(runtime, directory, cancel);
        std::ifstream file(directory.path / "response.json");
        if (!file) throw std::runtime_error("Python returned no response\n" + readLog(directory.path / "python.log"));
        result.metadata = nlohmann::json::parse(file);
        if (!result.metadata.value("ok", false)) throw std::runtime_error(result.metadata.value("error", "Generation failed"));
        result.points = readPointFile(directory.path / "points.bin");
    } catch (const std::exception& error) { result.error = error.what(); }
    result.cancelled = *cancel;
    result.elapsedMs = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count();
    return result;
}

GenerationService::~GenerationService() {
    cancel();
    if (future_.valid()) future_.wait();
}

void GenerationService::request(nlohmann::json request) {
    ++revision_;
    pending_ = std::move(request);
    if (cancellation_) *cancellation_ = true;
}

void GenerationService::cancel() {
    ++revision_;
    pending_.reset();
    if (cancellation_) *cancellation_ = true;
}

std::optional<GenerationResult> GenerationService::poll() {
    std::optional<GenerationResult> completed;
    if (future_.valid() && future_.wait_for(std::chrono::seconds(0)) == std::future_status::ready) {
        auto result = future_.get();
        if (runningRevision_ == revision_ && !result.cancelled) completed = std::move(result);
    }
    if (!future_.valid() && pending_) {
        runningRevision_ = revision_;
        cancellation_ = std::make_shared<std::atomic_bool>(false);
        auto request = std::move(*pending_);
        pending_.reset();
        future_ = std::async(std::launch::async, [runtime = runtime_, request = std::move(request), cancel = cancellation_] {
            return runGeneration(runtime, request, cancel);
        });
    }
    return completed;
}
