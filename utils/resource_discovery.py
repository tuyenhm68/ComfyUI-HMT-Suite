"""
Resource Discovery API
Provides endpoints for Komfy Studio to check installed models and custom nodes
"""

import os
import sys
from pathlib import Path


def get_all_models():
    """
    Get all installed models from ComfyUI, grouped by categories.
    Automatically discovers ALL model types dynamically from folder_paths.

    Returns:
        dict: Dictionary with model categories as keys and list of filenames as values
    """
    try:
        import folder_paths
    except ImportError:
        print("[HMT Resource Discovery] Warning: folder_paths not available")
        return _get_models_from_filesystem()

    result = {}

    # Auto-discover ALL folder types from folder_paths (no hardcoded list!)
    try:
        if hasattr(folder_paths, 'folder_names_and_paths'):
            # Get all registered folder types dynamically
            model_types = list(folder_paths.folder_names_and_paths.keys())
            print(f"[HMT Resource Discovery] Auto-discovered {len(model_types)} model types")
        else:
            print("[HMT Resource Discovery] folder_names_and_paths not available, using filesystem scan")
            return _get_models_from_filesystem()
    except Exception as e:
        print(f"[HMT Resource Discovery] Error accessing folder_paths: {e}")
        return _get_models_from_filesystem()

    # Get models for each discovered type
    for model_type in model_types:
        try:
            models = folder_paths.get_filename_list(model_type)
            # Only include non-empty categories or include empty ones for completeness
            result[model_type] = list(models) if models else []
        except Exception as e:
            # If error getting this specific type, skip it silently
            pass

    return result


def _get_models_from_filesystem():
    """
    Fallback method: Scan models directory directly from filesystem.
    Used when folder_paths is not available.

    Returns:
        dict: Dictionary with model categories as keys and list of filenames as values
    """
    result = {}

    try:
        # Try to find ComfyUI models directory
        # Assuming structure: ComfyUI/custom_nodes/ComfyUI-HMT-Suite/utils/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        comfyui_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        models_dir = os.path.join(comfyui_dir, "models")

        if not os.path.exists(models_dir) or not os.path.isdir(models_dir):
            print(f"[HMT Resource Discovery] Models directory not found: {models_dir}")
            return {}

        print(f"[HMT Resource Discovery] Scanning models directory: {models_dir}")

        # Scan all subdirectories in models/
        for category in os.listdir(models_dir):
            category_path = os.path.join(models_dir, category)

            # Skip files, only process directories
            if not os.path.isdir(category_path):
                continue

            # Skip hidden directories
            if category.startswith('.'):
                continue

            # Get all files in this category
            files = []
            for item in os.listdir(category_path):
                item_path = os.path.join(category_path, item)
                if os.path.isfile(item_path):
                    files.append(item)

            result[category] = sorted(files)

        print(f"[HMT Resource Discovery] Found {len(result)} categories via filesystem scan")

    except Exception as e:
        print(f"[HMT Resource Discovery] Error scanning filesystem: {e}")

    return result


def get_installed_custom_nodes():
    """
    Get list of installed custom nodes (only scan level 1 folders)

    Returns:
        dict: Dictionary with 'installed_packages' (list) and 'total' (int)
    """
    try:
        # Get ComfyUI's custom_nodes directory
        # Assuming this file is in ComfyUI/custom_nodes/ComfyUI-HMT-Suite/utils/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        custom_nodes_dir = os.path.join(current_dir, "..", "..", "..")
        custom_nodes_dir = os.path.abspath(custom_nodes_dir)

        # If path doesn't end with custom_nodes, try alternative path
        if not custom_nodes_dir.endswith("custom_nodes"):
            # Try to find custom_nodes directory
            parts = current_dir.split(os.sep)
            if "custom_nodes" in parts:
                idx = parts.index("custom_nodes")
                custom_nodes_dir = os.sep.join(parts[:idx+1])

        installed = []

        if os.path.exists(custom_nodes_dir) and os.path.isdir(custom_nodes_dir):
            for item in os.listdir(custom_nodes_dir):
                item_path = os.path.join(custom_nodes_dir, item)

                # Only get directories at level 1
                if not os.path.isdir(item_path):
                    continue

                # Skip __pycache__ and system folders
                if item.startswith("__") or item.startswith("."):
                    continue

                # Add to list (no need to check __init__.py)
                installed.append(item)

        return {
            "installed_packages": sorted(installed),
            "total": len(installed)
        }

    except Exception as e:
        print(f"[HMT Resource Discovery] Error getting custom nodes: {e}")
        return {
            "installed_packages": [],
            "total": 0
        }


def get_node_mappings():
    """
    Get mapping between node class types and the custom node packages that provide them

    Returns:
        dict: Dictionary mapping node class names to list of packages (or ["built-in"])
    """
    try:
        import nodes
    except ImportError:
        print("[HMT Resource Discovery] Warning: nodes module not available")
        return {}

    result = {}

    try:
        # Get all registered nodes
        if hasattr(nodes, 'NODE_CLASS_MAPPINGS'):
            for node_class, node_obj in nodes.NODE_CLASS_MAPPINGS.items():
                try:
                    # Get the module where this node is defined
                    module = node_obj.__module__ if hasattr(node_obj, '__module__') else ""

                    if 'custom_nodes' in module:
                        # Extract package name: custom_nodes.PackageName.module -> PackageName
                        parts = module.split('.')
                        if len(parts) >= 2:
                            idx = parts.index('custom_nodes')
                            if idx + 1 < len(parts):
                                package = parts[idx + 1]
                                result[node_class] = [package]
                            else:
                                result[node_class] = ["unknown"]
                        else:
                            result[node_class] = ["unknown"]
                    else:
                        # Built-in ComfyUI node
                        result[node_class] = ["built-in"]
                except Exception as e:
                    # If error processing this node, mark as unknown
                    result[node_class] = ["unknown"]

    except Exception as e:
        print(f"[HMT Resource Discovery] Error getting node mappings: {e}")

    return result


# For testing
if __name__ == "__main__":
    print("Testing Resource Discovery...")

    print("\n=== Models ===")
    models = get_all_models()
    for category, files in models.items():
        if files:
            print(f"{category}: {len(files)} files")

    print("\n=== Custom Nodes ===")
    custom_nodes = get_installed_custom_nodes()
    print(f"Total: {custom_nodes['total']}")
    for pkg in custom_nodes['installed_packages']:
        print(f"  - {pkg}")

    print("\n=== Node Mappings ===")
    mappings = get_node_mappings()
    print(f"Total nodes: {len(mappings)}")
