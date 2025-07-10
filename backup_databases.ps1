# Create backup folder if it doesn't exist
$backupDir = Join-Path $PSScriptRoot "db_backups"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

# Set common values
$timestamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$dbUser = "user"
$dbPassword = "securepass123"  # match your docker-compose
$containerName = "ai-agent-dev-postgres-1"

# Set environment variable inside container for passwordless auth
$envCommand = "export PGPASSWORD=$dbPassword;"

# Back up chatbot_db
$chatbotFile = "chatbot_db_$timestamp.sql"
docker exec $containerName bash -c "$envCommand pg_dump -U $dbUser -d chatbot_db" > "$backupDir\$chatbotFile"

# Back up n8n_db
$n8nFile = "n8n_db_$timestamp.sql"
docker exec $containerName bash -c "$envCommand pg_dump -U $dbUser -d n8n_db" > "$backupDir\$n8nFile"

Write-Host "✅ Backups complete. Files saved to: $backupDir"
