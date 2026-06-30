param (
    [Parameter(Mandatory=$true)]
    [string]$NewAppName,

    [Parameter(Mandatory=$true)]
    [string]$Destination
)

$sourceDir = $PSScriptRoot

if (Test-Path $Destination) {
    Write-Host "Destination already exists. Please choose a new folder." -ForegroundColor Red
    exit 1
}

Write-Host "🚀 Scaffolding Antigravity App Factory Template..." -ForegroundColor Cyan
Write-Host "Target: $NewAppName at $Destination" -ForegroundColor DarkGray

# 1. Copy everything except .git, bin, obj, publish_temp, dist, output
Write-Host "Copying files..."
New-Item -ItemType Directory -Path $Destination | Out-Null
Get-ChildItem -Path $sourceDir -Exclude ".git","bin","obj","publish_temp","dist","output" | Copy-Item -Destination $Destination -Recurse

# 2. Rename the .csproj file
$oldProjectFile = Join-Path $Destination "BlazorPwaTemplate.csproj"
$newProjectFile = Join-Path $Destination "$NewAppName.csproj"
if (Test-Path $oldProjectFile) {
    Rename-Item -Path $oldProjectFile -NewName "$NewAppName.csproj"
    Write-Host "Renamed project file to $NewAppName.csproj"
}

# 3. Find and Replace Namespaces and Project Names
Write-Host "Updating namespaces and references to '$NewAppName'..."
$filesToProcess = Get-ChildItem -Path $Destination -Include *.cs, *.razor, *.csproj, *.html, *.json, *.toml, *.md, *.ps1, *.sh -Recurse -File

foreach ($file in $filesToProcess) {
    # Skip this scaffold script itself if it was copied
    if ($file.Name -eq "Scaffold.ps1" -or $file.Name -eq "Clean-TemplateDemos.ps1") { continue }
    
    $content = Get-Content $file.FullName -Raw
    if ($content -match "BlazorPwaTemplate" -or $content -match "blazorpwatemplate") {
        # Case sensitive replacements
        $content = $content -replace "BlazorPwaTemplate", $NewAppName
        $content = $content -replace "blazorpwatemplate", $NewAppName.ToLower()
        Set-Content -Path $file.FullName -Value $content
    }
}

Write-Host "✅ Done! Your new app is ready at $Destination" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  cd $Destination"
Write-Host "  ./Clean-TemplateDemos.ps1 (optional, to strip device demos)"
Write-Host "  dotnet watch"
