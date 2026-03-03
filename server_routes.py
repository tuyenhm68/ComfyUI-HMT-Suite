"""
Server Routes for ComfyUI-HMT-Suite
Registers API endpoints with ComfyUI's PromptServer
"""

import json
from aiohttp import web


def register_routes(server):
    """
    Register HMT Suite API routes with ComfyUI's PromptServer

    Args:
        server: ComfyUI's PromptServer instance
    """
    from .utils.resource_discovery import (
        get_all_models,
        get_installed_custom_nodes,
        get_node_mappings
    )

    @server.routes.get("/hmt/models/list")
    async def get_models_list(request):
        """
        GET /hmt/models/list
        Returns all installed models grouped by categories
        """
        try:
            models = get_all_models()
            return web.json_response(models)
        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    @server.routes.get("/hmt/custom-nodes/list")
    async def get_custom_nodes_list(request):
        """
        GET /hmt/custom-nodes/list
        Returns all installed custom nodes
        """
        try:
            custom_nodes = get_installed_custom_nodes()
            return web.json_response(custom_nodes)
        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    @server.routes.get("/hmt/custom-nodes/mappings")
    async def get_node_mappings_api(request):
        """
        GET /hmt/custom-nodes/mappings
        Returns mapping between node class types and packages
        """
        try:
            mappings = get_node_mappings()
            return web.json_response(mappings)
        except Exception as e:
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    # --- Update endpoints ---
    from .utils.updater import ComfyUIUpdater

    @server.routes.get("/hmt/update/comfyui/check")
    async def check_comfyui_update(request):
        """
        GET /hmt/update/comfyui/check
        Check if ComfyUI update is available
        """
        try:
            updater = ComfyUIUpdater()
            result = updater.check_update_available()
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @server.routes.post("/hmt/update/comfyui")
    async def update_comfyui(request):
        """
        POST /hmt/update/comfyui
        Update ComfyUI core. Body: {"stable": true, "auto_restart": true}
        """
        try:
            body = await request.json() if request.body_exists else {}
            stable = body.get("stable", True)
            auto_restart = body.get("auto_restart", True)
            restart_delay = body.get("restart_delay", 3)

            updater = ComfyUIUpdater()
            result = updater.update_comfyui(stable=stable)

            if result["success"] and result["updated"] and auto_restart:
                import asyncio
                async def delayed_restart():
                    await asyncio.sleep(restart_delay)
                    ComfyUIUpdater.restart_comfyui(delay=0)
                asyncio.ensure_future(delayed_restart())
                result["restarting"] = True

            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @server.routes.get("/hmt/update/custom-nodes/list")
    async def list_updatable_nodes(request):
        """
        GET /hmt/update/custom-nodes/list
        List all custom nodes with their update status
        """
        try:
            updater = ComfyUIUpdater()
            nodes = updater.scan_updatable_nodes()
            return web.json_response({"nodes": nodes})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @server.routes.post("/hmt/update/custom-nodes")
    async def update_custom_nodes(request):
        """
        POST /hmt/update/custom-nodes
        Update custom nodes. Body: {"node_filter": "", "auto_restart": true}
        """
        try:
            body = await request.json() if request.body_exists else {}
            node_filter = body.get("node_filter", "")
            auto_restart = body.get("auto_restart", True)
            restart_delay = body.get("restart_delay", 3)

            updater = ComfyUIUpdater()

            if node_filter and node_filter.strip():
                from pathlib import Path
                node_path = updater.custom_nodes_dir / node_filter.strip()
                if not node_path.exists():
                    return web.json_response(
                        {"error": f"Node '{node_filter}' not found"},
                        status=404
                    )
                result = updater.update_single_node(node_path)
                has_updates = result.get("updated", False)
            else:
                result = updater.update_all_nodes()
                has_updates = result.get("updated_count", 0) > 0

            if has_updates and auto_restart:
                import asyncio
                async def delayed_restart():
                    await asyncio.sleep(restart_delay)
                    ComfyUIUpdater.restart_comfyui(delay=0)
                asyncio.ensure_future(delayed_restart())
                result["restarting"] = True

            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @server.routes.get("/hmt/update/comfyui/version")
    async def get_comfyui_version(request):
        """
        GET /hmt/update/comfyui/version
        Get current ComfyUI version info
        """
        try:
            updater = ComfyUIUpdater()
            version = updater.get_current_version()
            return web.json_response(version)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    print("[ComfyUI-HMT-Suite] API endpoints registered:")
    print("  - GET /hmt/models/list")
    print("  - GET /hmt/custom-nodes/list")
    print("  - GET /hmt/custom-nodes/mappings")
    print("  - GET /hmt/update/comfyui/check")
    print("  - GET /hmt/update/comfyui/version")
    print("  - POST /hmt/update/comfyui")
    print("  - GET /hmt/update/custom-nodes/list")
    print("  - POST /hmt/update/custom-nodes")


def setup_routes():
    """
    Setup routes by getting PromptServer instance and registering routes
    """
    try:
        from server import PromptServer
        server = PromptServer.instance
        register_routes(server)
    except ImportError:
        print("[ComfyUI-HMT-Suite] Warning: PromptServer not available, API routes not registered")
    except Exception as e:
        print(f"[ComfyUI-HMT-Suite] Error registering API routes: {e}")
