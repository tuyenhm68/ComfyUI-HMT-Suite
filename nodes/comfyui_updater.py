"""
ComfyUI Updater Nodes
Provides nodes for updating ComfyUI core and custom nodes.
Automatically restarts ComfyUI after update completes.
"""

import time
from ..utils.updater import ComfyUIUpdater
from ..utils.downloader import log_to_console


class UpdateComfyUINode:
    """
    Node for updating ComfyUI core to the latest version.
    Uses pygit2 (compatible with portable installations).
    Automatically restarts ComfyUI after successful update.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "confirm_update": ("BOOLEAN", {
                    "default": False,
                    "label_on": "YES - Update Now",
                    "label_off": "NO - Don't Update"
                }),
                "stable_version": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Stable (recommended)",
                    "label_off": "Latest (development)"
                }),
                "auto_restart": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Auto restart after update",
                    "label_off": "Don't restart"
                }),
            },
            "optional": {
                "restart_delay": ("INT", {
                    "default": 3,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("status", "message")
    FUNCTION = "execute"
    CATEGORY = "HMT Suite/Utils"
    OUTPUT_NODE = True

    def execute(
        self,
        confirm_update: bool = False,
        stable_version: bool = True,
        auto_restart: bool = True,
        restart_delay: int = 3
    ):
        if not confirm_update:
            log_to_console("Update not confirmed. Set confirm_update to YES.", "WARNING")
            return ("cancelled", "Update cancelled. Set 'confirm_update' to YES.")

        try:
            updater = ComfyUIUpdater()

            # Show current version
            current = updater.get_current_version()
            log_to_console(f"Current version: {current}", "INFO")

            # Perform update
            result = updater.update_comfyui(stable=stable_version)

            if not result["success"]:
                return ("error", result["message"])

            if result["updated"] and auto_restart:
                log_to_console(
                    f"Update successful! Restarting in {restart_delay}s...",
                    "SUCCESS"
                )
                ComfyUIUpdater.restart_comfyui(delay=restart_delay)

            return ("success", result["message"])

        except Exception as e:
            error_msg = f"Update failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return ("error", error_msg)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return time.time()


class UpdateCustomNodesNode:
    """
    Node for updating all custom nodes (git-managed only).
    Automatically restarts ComfyUI after update completes.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "confirm_update": ("BOOLEAN", {
                    "default": False,
                    "label_on": "YES - Update All Nodes",
                    "label_off": "NO - Don't Update"
                }),
                "auto_restart": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Auto restart after update",
                    "label_off": "Don't restart"
                }),
            },
            "optional": {
                "node_filter": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Leave empty for all, or enter node name"
                }),
                "restart_delay": ("INT", {
                    "default": 3,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("status", "message")
    FUNCTION = "execute"
    CATEGORY = "HMT Suite/Utils"
    OUTPUT_NODE = True

    def execute(
        self,
        confirm_update: bool = False,
        auto_restart: bool = True,
        node_filter: str = "",
        restart_delay: int = 3
    ):
        if not confirm_update:
            log_to_console("Update not confirmed. Set confirm_update to YES.", "WARNING")
            return ("cancelled", "Update cancelled. Set 'confirm_update' to YES.")

        try:
            updater = ComfyUIUpdater()

            if node_filter and node_filter.strip():
                # Update a specific node
                from pathlib import Path
                node_path = updater.custom_nodes_dir / node_filter.strip()
                if not node_path.exists():
                    return ("error", f"Node '{node_filter}' not found")

                log_to_console(f"Updating single node: {node_filter}", "INFO")
                result = updater.update_single_node(node_path)

                if not result["success"]:
                    return ("error", result["message"])

                if result["updated"] and auto_restart:
                    log_to_console(
                        f"Update successful! Restarting in {restart_delay}s...",
                        "SUCCESS"
                    )
                    ComfyUIUpdater.restart_comfyui(delay=restart_delay)

                return ("success", result["message"])
            else:
                # Update all nodes
                result = updater.update_all_nodes()

                if result["updated_count"] > 0 and auto_restart:
                    log_to_console(
                        f"{result['updated_count']} node(s) updated! "
                        f"Restarting in {restart_delay}s...",
                        "SUCCESS"
                    )
                    ComfyUIUpdater.restart_comfyui(delay=restart_delay)

                return ("success", result["message"])

        except Exception as e:
            error_msg = f"Update failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return ("error", error_msg)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return time.time()


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HMT_UpdateComfyUI": UpdateComfyUINode,
    "HMT_UpdateCustomNodes": UpdateCustomNodesNode,
}

# Display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    "HMT_UpdateComfyUI": "Update ComfyUI",
    "HMT_UpdateCustomNodes": "Update Custom Nodes",
}
