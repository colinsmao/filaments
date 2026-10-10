$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$toolsDir = Join-Path $root '.tools'
New-Item -ItemType Directory -Force $toolsDir | Out-Null
function Install-Archive($url, $archiveName, $destination, $expected) {
    $stamp = Join-Path $toolsDir "$archiveName.installed"
    if ((Test-Path -LiteralPath $expected) -and (Test-Path -LiteralPath $stamp)) { return }
    $archive = Join-Path $toolsDir $archiveName
    Write-Host "Downloading $archiveName"
    & curl.exe -L --fail --silent --show-error $url -o $archive
    if ($LASTEXITCODE -ne 0) { throw "Download failed: $url" }
    Expand-Archive -LiteralPath $archive -DestinationPath $destination -Force
    if (!(Test-Path -LiteralPath $expected)) { throw "Missing tool after extraction: $expected" }
    Set-Content -LiteralPath $stamp -Value $url
}
Install-Archive 'https://github.com/mstorsjo/llvm-mingw/releases/download/20250305/llvm-mingw-20250305-ucrt-x86_64.zip' 'llvm-mingw.zip' $toolsDir "$toolsDir/llvm-mingw-20250305-ucrt-x86_64/bin/clang++.exe"
Install-Archive 'https://github.com/Kitware/CMake/releases/download/v3.31.6/cmake-3.31.6-windows-x86_64.zip' 'cmake.zip' $toolsDir "$toolsDir/cmake-3.31.6-windows-x86_64/bin/cmake.exe"
Install-Archive 'https://github.com/ninja-build/ninja/releases/download/v1.12.1/ninja-win.zip' 'ninja.zip' "$toolsDir/ninja" "$toolsDir/ninja/ninja.exe"
Write-Host 'Windows tools ready in .tools. No global settings changed.'
