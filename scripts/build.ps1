param(
    [ValidateSet('Debug', 'Release')][string]$Configuration = 'Release',
    [switch]$Run,
    [switch]$Test
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& "$PSScriptRoot/setup.ps1"
$toolBin = "$root/.tools/llvm-mingw-20250305-ucrt-x86_64/bin"
$cmake = "$root/.tools/cmake-3.31.6-windows-x86_64/bin/cmake.exe"
$ninja = "$root/.tools/ninja/ninja.exe"
$build = "$root/build/$Configuration"
$originalPath = $env:PATH
try {
    $env:PATH = "$toolBin;$env:PATH"
    & $cmake -S $root -B $build -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" "-DCMAKE_C_COMPILER=$toolBin/clang.exe" "-DCMAKE_CXX_COMPILER=$toolBin/clang++.exe" "-DCMAKE_BUILD_TYPE=$Configuration"
    if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed' }
    & $cmake --build $build --parallel
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    if ($Test) {
        & "$root/.tools/cmake-3.31.6-windows-x86_64/bin/ctest.exe" --test-dir $build --output-on-failure
        if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    }
    if ($Run) { & "$build/filaments.exe" }
} finally { $env:PATH = $originalPath }
