param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("compose", "contract-check")]
    [string]$Action
)

$sharedRoot = Resolve-Path "..\\Context Repository\\shared"

switch ($Action) {
    "compose" {
        docker compose -f "$sharedRoot\\docker-compose.yml" up --build
    }
    "contract-check" {
        powershell -ExecutionPolicy Bypass -File "$sharedRoot\\scripts\\check-contract-change.ps1"
    }
}
