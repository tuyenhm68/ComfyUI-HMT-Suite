"""
ComfyUI-HMT-Suite
Custom nodes suite for ComfyUI
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# Export for ComfyUI
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

# Version info
__version__ = "1.0.0"
__author__ = "HMT"
__description__ = "ComfyUI custom nodes suite"

# Run auto-update on startup
try:
    from .utils import run_auto_update_on_startup
    run_auto_update_on_startup()
except Exception as e:
    print(f"[ComfyUI-HMT-Suite] Auto-update error: {e}")
