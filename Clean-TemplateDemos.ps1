Write-Host "🧹 Cleaning Template Demos..." -ForegroundColor Cyan

$projectRoot = $PSScriptRoot

# 1. Delete the Device pages directory
$devicePagesPath = Join-Path $projectRoot "Pages\Device"
if (Test-Path $devicePagesPath) {
    Remove-Item -Recurse -Force $devicePagesPath
    Write-Host "Deleted Device Pages directory."
}

# 2. Delete specific hardware services to leave a clean slate
$servicesToRemove = @(
    "BatteryService.cs", "IBatteryService.cs",
    "BluetoothService.cs", "IBluetoothService.cs",
    "CameraService.cs", "ICameraService.cs",
    "GeolocationService.cs", "IGeolocationService.cs",
    "HapticsService.cs", "IHapticsService.cs",
    "MediaService.cs", "IMediaService.cs",
    "MotionService.cs", "IMotionService.cs",
    "NotificationService.cs", "INotificationService.cs",
    "ScreenService.cs", "IScreenService.cs",
    "ShareService.cs", "IShareService.cs"
)

foreach ($svc in $servicesToRemove) {
    $svcPath = Join-Path $projectRoot "Services\$svc"
    if (Test-Path $svcPath) {
        Remove-Item -Force $svcPath
    }
}
Write-Host "Deleted hardware services."

# 3. Clean up Program.cs
$programPath = Join-Path $projectRoot "Program.cs"
if (Test-Path $programPath) {
    $programContent = Get-Content $programPath
    $cleanProgram = $programContent | Where-Object { 
        $_ -notmatch "IGeolocationService" -and
        $_ -notmatch "ICameraService" -and
        $_ -notmatch "IMotionService" -and
        $_ -notmatch "IHapticsService" -and
        $_ -notmatch "IShareService" -and
        $_ -notmatch "INotificationService" -and
        $_ -notmatch "IBatteryService" -and
        $_ -notmatch "IMediaService" -and
        $_ -notmatch "IScreenService" -and
        $_ -notmatch "IBluetoothService"
    }
    Set-Content -Path $programPath -Value $cleanProgram
    Write-Host "Cleaned hardware dependency injections from Program.cs."
}

# 4. Clean up NavMenu.razor (remove all Device API links)
# This is a bit tricky with Regex in PS, so we'll just advise the AI/User to replace the NavMenu content.
$navMenuPath = Join-Path $projectRoot "Layout\NavMenu.razor"
if (Test-Path $navMenuPath) {
    $navContent = Get-Content $navMenuPath -Raw
    # We strip out the entire DEVICE APIS section using regex matching the HTML structure
    $navContent = $navContent -replace '(?s)<div class="nav-section-title">.*?DEVICE APIS.*?</ul>', ''
    Set-Content -Path $navMenuPath -Value $navContent
    Write-Host "Stripped Device APIs from NavMenu.razor."
}

Write-Host "✅ Slate cleaned! The app shell is ready for new logic." -ForegroundColor Green
