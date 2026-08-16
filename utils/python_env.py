"""
Python Environment & Package Management Utility for ComfyUI-HMT-Suite
Allows querying python environment details, checking installed packages,
and executing pip install into the active ComfyUI environment (Portable, Venv, Conda, System).
"""

import sys
import os
import platform
import subprocess
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Union


def find_comfyui_root() -> Path:
    """
    Find ComfyUI root directory.
    Assumes structure: ComfyUI/custom_nodes/ComfyUI-HMT-Suite/utils/python_env.py
    """
    current = Path(__file__).resolve()
    try:
        comfyui_root = current.parent.parent.parent.parent
        if (comfyui_root / "custom_nodes").exists():
            return comfyui_root
    except Exception:
        pass
    return Path.cwd()


def is_portable_environment() -> bool:
    """
    Check if running inside ComfyUI portable environment (python_embeded / python_embedded).
    """
    exe_str = str(Path(sys.executable).resolve()).lower()
    if "python_embeded" in exe_str or "python_embedded" in exe_str:
        return True

    comfyui_root = find_comfyui_root()
    # Check parent directory (standard portable layout: ComfyUI_windows_portable/python_embeded)
    for name in ["python_embeded", "python_embedded"]:
        if (comfyui_root.parent / name).is_dir():
            return True
        if (comfyui_root / name).is_dir():
            return True

    return False


def is_triton_installed() -> bool:
    """
    Fast check if triton module is importable.
    """
    try:
        import triton  # noqa: F401
        return True
    except Exception:
        return False


def get_cuda_version() -> Optional[str]:
    """
    Get CUDA version from PyTorch if available.
    """
    try:
        import torch
        if hasattr(torch, "version") and hasattr(torch.version, "cuda"):
            return torch.version.cuda
    except Exception:
        pass
    return None


def get_torch_version() -> Optional[str]:
    """
    Get PyTorch version if available.
    """
    try:
        import torch
        return getattr(torch, "__version__", None)
    except Exception:
        pass
    return None


def get_env_info() -> Dict[str, Any]:
    """
    Retrieve comprehensive Python environment information for ComfyUI.
    """
    executable_path = str(Path(sys.executable).resolve()).replace("\\", "/")
    
    return {
        "executable": executable_path,
        "python_version": platform.python_version(),
        "python_version_tuple": list(sys.version_info[:3]),
        "cuda_version": get_cuda_version(),
        "torch_version": get_torch_version(),
        "platform": sys.platform,
        "is_portable": is_portable_environment(),
        "installed_triton": is_triton_installed(),
    }


def check_package(package_name: str) -> Dict[str, Any]:
    """
    Check if a Python package/module is installed.
    Supports package names (e.g. 'triton-windows', 'opencv-python') and module names (e.g. 'triton', 'cv2').

    Returns:
        {"installed": True, "version": "...", "module_path": "..."}
        or
        {"installed": False, "error": "No module named '...'"}
    """
    if not package_name or not isinstance(package_name, str) or not package_name.strip():
        return {
            "installed": False,
            "error": "Invalid or empty package name provided"
        }

    pkg = package_name.strip()
    module_name = pkg.replace("-", "_")

    version = None
    module_path = None

    # 1. Try importlib.metadata for distribution package version & metadata
    try:
        import importlib.metadata as meta
        try:
            version = meta.version(pkg)
        except meta.PackageNotFoundError:
            try:
                version = meta.version(module_name)
            except meta.PackageNotFoundError:
                pass
    except Exception:
        pass

    # 2. Try find_spec to locate module file path
    spec = None
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is None and module_name != pkg:
            spec = importlib.util.find_spec(pkg)
    except Exception:
        pass

    if spec is not None:
        if spec.origin:
            module_path = str(Path(spec.origin).resolve()).replace("\\", "/")
        elif spec.submodule_search_locations:
            locs = list(spec.submodule_search_locations)
            if locs:
                module_path = str(Path(locs[0]).resolve()).replace("\\", "/")

        # If version not found via metadata, try importing module to read __version__
        if not version:
            try:
                mod = importlib.import_module(spec.name)
                mod_ver = getattr(mod, "__version__", None) or getattr(mod, "VERSION", None)
                if mod_ver is not None:
                    version = str(mod_ver)
                if not module_path and hasattr(mod, "__file__") and mod.__file__:
                    module_path = str(Path(mod.__file__).resolve()).replace("\\", "/")
            except Exception:
                pass

        return {
            "installed": True,
            "version": str(version) if version else "unknown",
            "module_path": str(module_path) if module_path else "built-in/namespace"
        }

    # 3. If spec was not found but metadata package exists
    if version is not None:
        return {
            "installed": True,
            "version": str(version),
            "module_path": "site-packages"
        }

    # 4. Fallback: try direct import
    try:
        mod = importlib.import_module(module_name)
        mod_ver = getattr(mod, "__version__", None) or getattr(mod, "VERSION", None)
        mod_path = getattr(mod, "__file__", None)
        return {
            "installed": True,
            "version": str(mod_ver) if mod_ver else (str(version) if version else "unknown"),
            "module_path": str(Path(mod_path).resolve()).replace("\\", "/") if mod_path else "built-in/namespace"
        }
    except Exception:
        pass

    return {
        "installed": False,
        "error": f"No module named '{pkg}'"
    }


def pip_install(
    package: Union[str, List[str]],
    extra_args: Optional[List[str]] = None,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Execute pip install into the current Python environment using sys.executable.

    Args:
        package: Package name string (e.g. 'triton-windows') or list of package strings.
        extra_args: Optional list of additional pip flags (e.g. ['--no-cache-dir']).
        timeout: Execution timeout in seconds (default: 300).

    Returns:
        Dictionary with success status, stdout, stderr, returncode, etc.
    """
    if isinstance(package, str):
        packages = [p.strip() for p in package.split() if p.strip()]
    elif isinstance(package, list):
        packages = [str(p).strip() for p in package if str(p).strip()]
    else:
        return {
            "success": False,
            "error": "Package parameter must be a string or list of strings",
            "returncode": -1,
            "stdout": "",
            "stderr": ""
        }

    if not packages:
        return {
            "success": False,
            "error": "No valid packages specified for installation",
            "returncode": -1,
            "stdout": "",
            "stderr": ""
        }

    cmd = [sys.executable, "-m", "pip", "install"]
    if extra_args and isinstance(extra_args, list):
        for arg in extra_args:
            if isinstance(arg, str) and arg.strip():
                cmd.append(arg.strip())
    
    cmd.extend(packages)

    try:
        # Run pip install subprocess with safe encoding
        env = os.environ.copy()
        # Force UTF-8 encoding for Python sub-processes
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=env
        )

        return {
            "success": result.returncode == 0,
            "package": " ".join(packages) if len(packages) > 1 else packages[0],
            "command": " ".join(cmd),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "error": None if result.returncode == 0 else f"pip install exited with code {result.returncode}"
        }
    except subprocess.TimeoutExpired as te:
        return {
            "success": False,
            "package": " ".join(packages) if len(packages) > 1 else packages[0],
            "command": " ".join(cmd),
            "stdout": te.stdout if hasattr(te, "stdout") and te.stdout else "",
            "stderr": te.stderr if hasattr(te, "stderr") and te.stderr else "",
            "returncode": -1,
            "error": f"pip install timed out after {timeout} seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "package": " ".join(packages) if len(packages) > 1 else packages[0],
            "command": " ".join(cmd),
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "error": f"Execution failed: {str(e)}"
        }
