$ErrorActionPreference = "Stop"

$project = if ($env:DOPPLER_PROJECT) { $env:DOPPLER_PROJECT } else { "all" }
$config = if ($env:DOPPLER_CONFIG) { $env:DOPPLER_CONFIG } else { "main" }
$missing = New-Object System.Collections.Generic.List[string]

$requiredSecrets = @(
    "CODECOV_TOKEN",
    "DOPPLER_GITHUB_SERVICE_TOKEN",
    "SAFETY_API_KEY"
)

foreach ($secretName in $requiredSecrets) {
    & doppler secrets get $secretName --plain --project $project --config $config *> $null
    if ($LASTEXITCODE -ne 0) {
        $missing.Add($secretName)
    }
}

if ($missing.Count -gt 0) {
    Write-Error "Missing Doppler secrets in ${project}/${config}: $($missing -join ', ')"
    exit 1
}

Write-Host "All required Doppler secrets from docs/doppler-setup.md are present in ${project}/${config}."
