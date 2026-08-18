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

    @server.routes.get("/hmt/download/progress")
    async def get_download_progress_api(request):
        """
        GET /hmt/download/progress
        Tien do cua moi download dang chay.

        ModelDownloaderNode giu tien do trong dict _download_progress NOI BO tien
        trinh, khong co route nao phoi ra -- client buoc phai cao console log de
        biet %. Route nay tra thang dict do.
        """
        try:
            from .nodes.model_downloader import ModelDownloaderNode
            return web.json_response(ModelDownloaderNode.get_all_downloads())
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

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

    # --- Python Environment & Pip Management endpoints ---
    from .utils.python_env import get_env_info, check_package, pip_install
    import asyncio

    @server.routes.get("/hmt/env")
    async def get_environment_info(request):
        """
        GET /hmt/env
        Returns detailed Python environment info (sys.executable, versions, CUDA, portable flag, etc.)
        """
        try:
            info = get_env_info()
            return web.json_response(info)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @server.routes.post("/hmt/check-package")
    async def check_package_api(request):
        """
        POST /hmt/check-package
        Check if a Python package/module is installed.
        Body: {"package": "triton"}
        """
        try:
            body = await request.json() if request.body_exists else {}
            package_name = body.get("package", "")
            if not package_name:
                return web.json_response(
                    {"installed": False, "error": "Field 'package' is required in request body"},
                    status=400
                )
            result = check_package(package_name)
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"installed": False, "error": str(e)}, status=500)

    @server.routes.post("/hmt/pip-install")
    async def pip_install_api(request):
        """
        POST /hmt/pip-install
        Execute pip install in ComfyUI's active Python environment.
        Body: {
            "package": "triton-windows",
            "extra_args": ["--no-cache-dir"],
            "timeout": 300
        }
        """
        try:
            body = await request.json() if request.body_exists else {}
            package = body.get("package") or body.get("packages")
            if not package:
                return web.json_response(
                    {"success": False, "error": "Field 'package' or 'packages' is required"},
                    status=400
                )
            extra_args = body.get("extra_args", [])
            timeout = body.get("timeout", 300)

            # Run in thread pool to avoid blocking the aiohttp async event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: pip_install(package=package, extra_args=extra_args, timeout=timeout)
            )

            status_code = 200 if result.get("success") else 500
            return web.json_response(result, status=status_code)
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    print("[ComfyUI-HMT-Suite] API endpoints registered:")
    print("  - GET /hmt/models/list")
    print("  - GET /hmt/custom-nodes/list")
    print("  - GET /hmt/custom-nodes/mappings")
    print("  - GET /hmt/update/comfyui/check")
    print("  - GET /hmt/update/comfyui/version")
    print("  - POST /hmt/update/comfyui")
    print("  - GET /hmt/update/custom-nodes/list")
    print("  - POST /hmt/update/custom-nodes")
    print("  - GET /hmt/env")
    print("  - POST /hmt/check-package")
    print("  - POST /hmt/pip-install")



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
