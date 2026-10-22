# Source this file from the verified repository root before installing or testing.
task_storage_root="$(pwd -P)/.venv/.dev-storage"
export UV_CACHE_DIR="$task_storage_root/uv-cache"
export UV_PYTHON_INSTALL_DIR="$task_storage_root/uv-python"
export UV_PYTHON_BIN_DIR="$task_storage_root/uv-python-bin"
export UV_TOOL_DIR="$task_storage_root/uv-tool"
export UV_TOOL_BIN_DIR="$task_storage_root/uv-tool-bin"
export PIP_CACHE_DIR="$task_storage_root/pip-cache"
export XDG_CACHE_HOME="$task_storage_root/xdg-cache"
export XDG_DATA_HOME="$task_storage_root/xdg-data"
export TMPDIR="$task_storage_root/tmp/"
export HF_HOME="$task_storage_root/huggingface"
export TORCH_HOME="$task_storage_root/torch"
export MPLCONFIGDIR="$task_storage_root/matplotlib"
export PLAYWRIGHT_BROWSERS_PATH="$task_storage_root/playwright"
for task_env_path in "$UV_CACHE_DIR" "$UV_PYTHON_INSTALL_DIR" "$UV_PYTHON_BIN_DIR" \
    "$UV_TOOL_DIR" "$UV_TOOL_BIN_DIR" "$PIP_CACHE_DIR" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" \
    "$TMPDIR" "$HF_HOME" "$TORCH_HOME" "$MPLCONFIGDIR" "$PLAYWRIGHT_BROWSERS_PATH"; do
    mkdir -p "$task_env_path" || return 1
done
unset task_storage_root task_env_path
