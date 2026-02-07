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

    print("[ComfyUI-HMT-Suite] API endpoints registered:")
    print("  - GET /hmt/models/list")
    print("  - GET /hmt/custom-nodes/list")
    print("  - GET /hmt/custom-nodes/mappings")


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
