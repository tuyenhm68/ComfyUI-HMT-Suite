"""
Model Downloader Node for ComfyUI
Downloads models from direct URLs or GitHub with progress tracking
"""

import os
import folder_paths
from pathlib import Path
from ..utils import FileDownloader, GitHubHandler
from ..utils.downloader import log_to_console


class ModelDownloaderNode:
    """
    ComfyUI Node for downloading models from internet
    Supports direct file URLs and GitHub URLs
    """
    
    # Global progress storage for API access
    _download_progress = {}
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input parameters for the node"""
        return {
            "required": {
                "download_type": (["file", "github"], {
                    "default": "file"
                }),
                "url": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
                "destination_folder": ("STRING", {
                    "default": "checkpoints",
                    "multiline": False
                }),
                "filename": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
                "overwrite": ("BOOLEAN", {
                    "default": False
                }),
            },
            "optional": {
                "hf_token": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "hf_xxxxx (optional, for private/gated models)"
                }),
                "extract_repo": ("BOOLEAN", {
                    "default": True
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("status", "file_path", "message", "progress_percentage")
    FUNCTION = "download_model"
    CATEGORY = "HMT Suite/Utils"
    OUTPUT_NODE = True
    
    def __init__(self):
        self.download_id = None
        self.current_percentage = 0
    
    def progress_callback(self, progress):
        """Callback to update global progress storage and current percentage"""
        if self.download_id:
            ModelDownloaderNode._download_progress[self.download_id] = progress.to_dict()
            self.current_percentage = progress.percentage
    
    def download_model(
        self,
        download_type: str,
        url: str,
        destination_folder: str,
        filename: str = "",
        overwrite: bool = False,
        hf_token: str = "",
        extract_repo: bool = True
    ):
        """
        Download model from URL

        Args:
            download_type: "file" or "github"
            url: Source URL
            destination_folder: Destination folder relative to ComfyUI/models/
            filename: Optional custom filename (auto-detect if empty)
            overwrite: Whether to overwrite existing files
            hf_token: Optional Hugging Face token for private/gated models
            extract_repo: Whether to extract GitHub repository (only for repo downloads)

        Returns:
            Tuple of (status, file_path, message, progress_percentage)
        """
        try:
            log_to_console("="*60, "INFO")
            log_to_console(f"Model Downloader - Starting new download", "INFO")
            log_to_console(f"Type: {download_type}", "INFO")
            log_to_console(f"URL: {url}", "INFO")
            
            # Validate inputs
            if not url or url.strip() == "":
                log_to_console("URL is required", "ERROR")
                return ("error", "", "URL is required", 0)
            
            # Get ComfyUI models directory
            # Try to get from folder_paths, fallback to relative path
            try:
                models_dir = folder_paths.models_dir
            except:
                # Fallback: assume we're in custom_nodes/ComfyUI-HMT-Suite
                models_dir = Path(__file__).parent.parent.parent.parent / "models"
            
            # Build full destination path
            dest_path = Path(models_dir) / destination_folder
            
            log_to_console(f"Destination: {dest_path}", "INFO")
            
            # Generate unique download ID for progress tracking
            import hashlib
            import time
            self.download_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()
            
            # Initialize progress
            ModelDownloaderNode._download_progress[self.download_id] = {
                "status": "starting",
                "percentage": 0,
                "downloaded": 0,
                "total_size": 0
            }
            
            # Download based on type
            if download_type == "file":
                downloader = FileDownloader()
                result = downloader.download(
                    url=url,
                    destination_folder=str(dest_path),
                    filename=filename if filename.strip() else None,
                    overwrite=overwrite,
                    progress_callback=self.progress_callback,
                    auth_token=hf_token if hf_token.strip() else None
                )
            
            elif download_type == "github":
                github_handler = GitHubHandler()
                
                # Check if it's a repository or file
                parsed = github_handler.parse_github_url(url)
                
                if parsed['type'] == 'repository':
                    result = github_handler.download_repository(
                        url=url,
                        destination_folder=str(dest_path),
                        extract=extract_repo,
                        progress_callback=self.progress_callback
                    )
                else:
                    result = github_handler.download_file(
                        url=url,
                        destination_folder=str(dest_path),
                        filename=filename if filename.strip() else None,
                        overwrite=overwrite,
                        progress_callback=self.progress_callback,
                        auth_token=hf_token if hf_token.strip() else None
                    )
            
            else:
                return ("error", "", f"Invalid download type: {download_type}", 0)
            
            # Process result
            if result['success']:
                file_path = result.get('file_path', result.get('extracted_to', ''))
                log_to_console("="*60, "SUCCESS")
                return ("success", file_path, result['message'], 100)
            else:
                log_to_console("="*60, "ERROR")
                return ("error", "", result['message'], self.current_percentage)
        
        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            log_to_console(f"Exception: {error_msg}", "ERROR")
            log_to_console("="*60, "ERROR")
            
            if self.download_id:
                ModelDownloaderNode._download_progress[self.download_id] = {
                    "status": "error",
                    "error_message": error_msg
                }
            return ("error", "", error_msg, self.current_percentage)
    
    @classmethod
    def get_download_progress(cls, download_id: str):
        """Get progress for a specific download (for API access)"""
        return cls._download_progress.get(download_id, {
            "status": "not_found",
            "message": "Download ID not found"
        })
    
    @classmethod
    def get_all_downloads(cls):
        """Get all download progress (for API access)"""
        return cls._download_progress
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Force re-execution on every run"""
        import time
        return time.time()


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HMT_ModelDownloader": ModelDownloaderNode
}

# Display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    "HMT_ModelDownloader": "Model Downloader"
}
