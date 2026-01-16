"""
Custom Node Installer Node for ComfyUI
Installs custom nodes from GitHub repositories
"""

import os
from pathlib import Path
from ..utils import CustomNodeInstaller
from ..utils.downloader import log_to_console


class CustomNodeInstallerNode:
    """
    ComfyUI Node for installing custom nodes from GitHub
    """
    
    # Global progress storage for API access
    _installation_progress = {}
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input parameters for the node"""
        return {
            "required": {
                "github_url": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "https://github.com/username/repo-name"
                }),
                "platform": (["auto", "windows", "linux"], {
                    "default": "auto"
                }),
            }
        }


    
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("status", "installation_path", "message")
    FUNCTION = "install_custom_node"
    CATEGORY = "HMT Suite/Utils"
    OUTPUT_NODE = True
    
    def __init__(self):
        self.installation_id = None
        self.current_percentage = 0
    
    def progress_callback(self, progress):
        """Callback to update global progress storage"""
        if self.installation_id:
            CustomNodeInstallerNode._installation_progress[self.installation_id] = progress.to_dict()
            self.current_percentage = progress.percentage
    
    def install_custom_node(
        self,
        github_url: str,
        platform: str = "auto"
    ):
        """
        Install a custom node from GitHub
        
        Args:
            github_url: GitHub repository URL
            platform: Target platform (auto, windows, linux)
        
        Returns:
            Tuple of (status, installation_path, message)
        """
        try:
            log_to_console("="*60, "INFO")
            log_to_console(f"Custom Node Installer - Starting installation", "INFO")
            log_to_console(f"URL: {github_url}", "INFO")
            
            # Validate inputs
            if not github_url or github_url.strip() == "":
                log_to_console("URL is required", "ERROR")
                return ("error", "", "URL is required")
            
            # Validate URL format (basic check)
            if not (github_url.startswith("http://") or github_url.startswith("https://")):
                log_to_console("Invalid URL format", "ERROR")
                return ("error", "", "Please provide a valid URL (http:// or https://)")
            
            # Generate unique installation ID for progress tracking
            import hashlib
            import time
            self.installation_id = hashlib.md5(f"{github_url}{time.time()}".encode()).hexdigest()
            
            # Initialize progress
            CustomNodeInstallerNode._installation_progress[self.installation_id] = {
                "status": "starting",
                "percentage": 0
            }
            
            # Create installer instance
            installer = CustomNodeInstaller()
            
            # Install custom node
            result = installer.install_custom_node(
                github_url=github_url,
                platform=platform,
                progress_callback=self.progress_callback
            )
            
            # Process result
            if result['success']:
                log_to_console("="*60, "SUCCESS")
                return ("success", result['path'], result['message'])
            else:
                log_to_console("="*60, "ERROR")
                return ("error", result.get('path', ''), result['message'])
        
        except Exception as e:
            error_msg = f"Installation failed: {str(e)}"
            log_to_console(f"Exception: {error_msg}", "ERROR")
            log_to_console("="*60, "ERROR")
            
            if self.installation_id:
                CustomNodeInstallerNode._installation_progress[self.installation_id] = {
                    "status": "error",
                    "error_message": error_msg
                }
            return ("error", "", error_msg)
    
    @classmethod
    def get_installation_progress(cls, installation_id: str):
        """Get progress for a specific installation (for API access)"""
        return cls._installation_progress.get(installation_id, {
            "status": "not_found",
            "message": "Installation ID not found"
        })
    
    @classmethod
    def get_all_installations(cls):
        """Get all installation progress (for API access)"""
        return cls._installation_progress
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Force re-execution on every run"""
        import time
        return time.time()


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HMT_CustomNodeInstaller": CustomNodeInstallerNode
}

# Display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    "HMT_CustomNodeInstaller": "Custom Node Installer"
}
