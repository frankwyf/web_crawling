# Dot-source this file from the verified repository root before installing or testing.
$taskStorageRoot = Join-Path (Get-Location).ProviderPath '.venv/.dev-storage'
$taskStorageDirectories = @{
    UV_CACHE_DIR = 'uv-cache'; UV_PYTHON_INSTALL_DIR = 'uv-python'; UV_PYTHON_BIN_DIR = 'uv-python-bin'
    UV_TOOL_DIR = 'uv-tool'; UV_TOOL_BIN_DIR = 'uv-tool-bin'; PIP_CACHE_DIR = 'pip-cache'
    XDG_CACHE_HOME = 'xdg-cache'; XDG_DATA_HOME = 'xdg-data'; TMPDIR = 'tmp'
    HF_HOME = 'huggingface'; TORCH_HOME = 'torch'; MPLCONFIGDIR = 'matplotlib'
    PLAYWRIGHT_BROWSERS_PATH = 'playwright'
}
foreach ($taskStorageEntry in $taskStorageDirectories.GetEnumerator()) {
    $taskStoragePath = Join-Path $taskStorageRoot $taskStorageEntry.Value
    New-Item -ItemType Directory -Force -Path $taskStoragePath -ErrorAction Stop | Out-Null
    [Environment]::SetEnvironmentVariable($taskStorageEntry.Key, $taskStoragePath, 'Process')
}
# Python's tempfile uses TEMP/TMP on Windows before TMPDIR.
$env:TEMP = $env:TMPDIR
$env:TMP = $env:TMPDIR
Remove-Variable taskStorageRoot, taskStorageDirectories, taskStorageEntry, taskStoragePath
