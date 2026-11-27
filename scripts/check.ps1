$ErrorActionPreference = "Stop"

Write-Host "Running mypy..."
uv run mypy src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running ruff..."
uv run ruff check src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running pytest..."
uv run pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "All checks passed."
