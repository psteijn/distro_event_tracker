# Deployment script for Distro Event Tracker
# This script restarts the Windows Task Scheduler tasks to deploy the latest code.

$tasks = @(
    @{ Name = "DistroEventTracker"; Log = "distro_task_log.txt" },
    @{ Name = "OceanDistroEventTracker"; Log = "ocean_distro_task_log.txt" }
)

foreach ($task in $tasks) {
    $taskName = $task.Name
    $logFile = $task.Log
    Write-Host "--- Starting deployment for $taskName ---" -ForegroundColor Cyan
    
    # Check if task exists
    $scheduledTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -eq $scheduledTask) {
        Write-Warning "Task '$taskName' not found. Skipping."
        continue
    }

    # Stop the task if it's running
    if ($scheduledTask.State -ne "Ready") {
        Write-Host "Stopping task '$taskName'..."
        Stop-ScheduledTask -TaskName $taskName
        # Give it a moment to stop
        Start-Sleep -Seconds 2
    }

    # Clear log file to ensure we only see the current run's output
    if (Test-Path $logFile) {
        Clear-Content -Path $logFile
    }

    # Start the task
    Write-Host "Starting task '$taskName'..."
    Start-ScheduledTask -TaskName $taskName
    
    # Monitor log for success
    Write-Host "Verifying startup for $taskName (monitoring $logFile)..." -NoNewline
    $timeout = 60 # seconds
    $elapsed = 0
    $success = $false

    while ($elapsed -lt $timeout) {
        if (Test-Path $logFile) {
            $content = Get-Content -Path $logFile -Raw
            if ($content -like "*connected to Discord!*" -or $content -like "*Bot ready!*") {
                $success = $true
                break
            }
            if ($content -like "*Error:*") {
                Write-Host "`n[FAIL] Error detected in log for $taskName!" -ForegroundColor Red
                Write-Host ($content | Select-String -Pattern "Error:.*" | Select-Object -First 1)
                break
            }
        }
        
        Start-Sleep -Seconds 2
        $elapsed += 2
        Write-Host "." -NoNewline
    }

    if ($success) {
        Write-Host "`n[OK] $taskName is online and ready!" -ForegroundColor Green
    } else {
        Write-Host "`n[TIMEOUT] Could not verify $taskName startup within $timeout seconds." -ForegroundColor Yellow
        Write-Warning "Please check $logFile manually."
    }
}

Write-Host "`nDeployment process finished." -ForegroundColor Cyan
