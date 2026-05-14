# Deployment script for Distro Event Tracker
# This script restarts the Windows Task Scheduler tasks to deploy the latest code.

$tasks = @("DistroEventTracker", "OceanDistroEventTracker")

foreach ($taskName in $tasks) {
    Write-Host "Restarting task: $taskName"
    
    # Check if task exists
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Warning "Task '$taskName' not found. Skipping."
        continue
    }

    # Stop the task if it's running
    if ($task.State -ne "Ready") {
        Write-Host "Stopping task '$taskName'..."
        Stop-ScheduledTask -TaskName $taskName
        # Give it a moment to stop
        Start-Sleep -Seconds 2
    }

    # Start the task
    Write-Host "Starting task '$taskName'..."
    Start-ScheduledTask -TaskName $taskName
    
    Write-Host "Task '$taskName' restarted successfully."
}

Write-Host "`nDeployment complete!"
