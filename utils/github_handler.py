"""
GitHub Handler Utility
Supports downloading files and repositories from GitHub with progress tracking
"""

import os
import re
import zipfile
import requests
from pathlib import Path
from typing import Optional, Callable, Dict
from urllib.parse import urlparse
from .downloader import DownloadProgress, FileDownloader, log_to_console


class GitHubHandler:
    """Handle GitHub downloads (files, repos, releases)"""
    
    def __init__(self):
        self.progress = DownloadProgress()
        self.file_downloader = FileDownloader()
    
    def parse_github_url(self, url: str) -> Dict:
        """
        Parse GitHub URL to determine type and extract info
        
        Supported formats:
        - https://github.com/user/repo
        - https://github.com/user/repo/blob/branch/path/to/file
        - https://github.com/user/repo/releases/download/tag/file
        - https://raw.githubusercontent.com/user/repo/branch/path/to/file
        """
        parsed = urlparse(url)
        
        # Raw GitHub content
        if 'raw.githubusercontent.com' in parsed.netloc:
            parts = parsed.path.strip('/').split('/')
            if len(parts) >= 4:
                return {
                    'type': 'raw_file',
                    'user': parts[0],
                    'repo': parts[1],
                    'branch': parts[2],
                    'file_path': '/'.join(parts[3:]),
                    'download_url': url
                }
        
        # Regular GitHub URL
        if 'github.com' in parsed.netloc:
            parts = parsed.path.strip('/').split('/')
            
            if len(parts) >= 2:
                user = parts[0]
                repo = parts[1]
                
                # Release download
                if len(parts) >= 5 and parts[2] == 'releases' and parts[3] == 'download':
                    return {
                        'type': 'release_file',
                        'user': user,
                        'repo': repo,
                        'tag': parts[4],
                        'filename': parts[5] if len(parts) > 5 else None,
                        'download_url': url
                    }
                
                # File in repository
                if len(parts) >= 5 and parts[2] == 'blob':
                    branch = parts[3]
                    file_path = '/'.join(parts[4:])
                    raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{file_path}"
                    return {
                        'type': 'repo_file',
                        'user': user,
                        'repo': repo,
                        'branch': branch,
                        'file_path': file_path,
                        'download_url': raw_url
                    }
                
                # Repository (clone/download)
                return {
                    'type': 'repository',
                    'user': user,
                    'repo': repo,
                    'download_url': f"https://github.com/{user}/{repo}/archive/refs/heads/main.zip"
                }
        
        return {
            'type': 'unknown',
            'error': 'Unable to parse GitHub URL'
        }
    
    def download_file(
        self,
        url: str,
        destination_folder: str,
        filename: Optional[str] = None,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        auth_token: Optional[str] = None
    ) -> Dict:
        """
        Download a single file from GitHub

        Args:
            url: GitHub URL (raw, blob, or release)
            destination_folder: Folder to save file
            filename: Optional custom filename
            overwrite: Whether to overwrite existing file
            progress_callback: Optional callback for progress updates
            auth_token: Optional authentication token (for private repos or rate limiting)

        Returns:
            Dictionary with download status and info
        """
        try:
            log_to_console(f"Parsing GitHub URL: {url}", "INFO")
            
            # Parse GitHub URL
            parsed = self.parse_github_url(url)
            
            if parsed['type'] == 'unknown':
                log_to_console(f"Invalid GitHub URL: {parsed.get('error', 'Unknown error')}", "ERROR")
                return {
                    "success": False,
                    "message": parsed.get('error', 'Invalid GitHub URL'),
                    "progress": self.progress.to_dict()
                }
            
            log_to_console(f"GitHub URL type: {parsed['type']}", "INFO")
            
            # Get download URL
            download_url = parsed.get('download_url')
            
            if not download_url:
                log_to_console("Could not determine download URL", "ERROR")
                return {
                    "success": False,
                    "message": "Could not determine download URL",
                    "progress": self.progress.to_dict()
                }
            
            # Use FileDownloader for actual download
            result = self.file_downloader.download(
                url=download_url,
                destination_folder=destination_folder,
                filename=filename,
                overwrite=overwrite,
                progress_callback=progress_callback,
                auth_token=auth_token
            )
            
            # Update our progress from file_downloader
            self.progress = self.file_downloader.progress
            
            return result
            
        except Exception as e:
            self.progress.status = "error"
            self.progress.error_message = str(e)
            
            log_to_console(f"GitHub download error: {str(e)}", "ERROR")
            
            if progress_callback:
                progress_callback(self.progress)
            
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "progress": self.progress.to_dict()
            }
    
    def download_repository(
        self,
        url: str,
        destination_folder: str,
        extract: bool = True,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> Dict:
        """
        Download entire GitHub repository as ZIP
        
        Args:
            url: GitHub repository URL
            destination_folder: Folder to save/extract repository
            extract: Whether to extract ZIP file
            progress_callback: Optional callback for progress updates
        
        Returns:
            Dictionary with download status and info
        """
        try:
            log_to_console(f"Parsing repository URL: {url}", "INFO")
            
            parsed = self.parse_github_url(url)
            
            if parsed['type'] != 'repository':
                log_to_console(f"URL is not a repository: {parsed['type']}", "ERROR")
                return {
                    "success": False,
                    "message": "URL is not a repository",
                    "progress": self.progress.to_dict()
                }
            
            log_to_console(f"Repository: {parsed['user']}/{parsed['repo']}", "INFO")
            
            # Check if repository folder already exists (when extracting)
            if extract:
                extract_path = Path(destination_folder)
                # Check for extracted repository folder (GitHub adds -main or -master suffix)
                possible_folders = [
                    extract_path / f"{parsed['repo']}-main",
                    extract_path / f"{parsed['repo']}-master",
                    extract_path / parsed['repo']
                ]
                
                for folder in possible_folders:
                    if folder.exists() and folder.is_dir():
                        # Count files in directory
                        try:
                            file_count = len(list(folder.rglob('*')))
                            log_to_console(f"Repository folder already exists: {folder}", "WARNING")
                            log_to_console(f"Contains {file_count} files/folders", "INFO")
                            log_to_console("Skipping download (folder exists)", "INFO")
                            
                            self.progress.status = "completed"
                            self.progress.percentage = 100
                            
                            return {
                                "success": True,
                                "message": "Repository folder already exists, skipped download",
                                "extracted_to": str(folder),
                                "skipped": True,
                                "progress": self.progress.to_dict()
                            }
                        except Exception as e:
                            log_to_console(f"Error checking folder: {e}", "WARNING")
            
            # Download ZIP file
            zip_filename = f"{parsed['repo']}.zip"
            
            log_to_console(f"Downloading repository as ZIP: {zip_filename}", "INFO")
            
            download_result = self.file_downloader.download(
                url=parsed['download_url'],
                destination_folder=destination_folder,
                filename=zip_filename,
                overwrite=True,
                progress_callback=progress_callback
            )
            
            if not download_result['success']:
                return download_result
            
            # Extract if requested
            if extract:
                log_to_console("Extracting repository...", "INFO")
                
                self.progress.status = "extracting"
                if progress_callback:
                    progress_callback(self.progress)
                
                zip_path = Path(download_result['file_path'])
                extract_path = Path(destination_folder)
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                log_to_console(f"Extracted to: {extract_path}", "SUCCESS")
                
                # Remove ZIP file after extraction
                zip_path.unlink()
                log_to_console("Removed ZIP file", "INFO")
                
                self.progress.status = "completed"
                if progress_callback:
                    progress_callback(self.progress)
                
                return {
                    "success": True,
                    "message": "Repository downloaded and extracted successfully",
                    "extracted_to": str(extract_path),
                    "progress": self.progress.to_dict()
                }
            
            return download_result
            
        except Exception as e:
            self.progress.status = "error"
            self.progress.error_message = str(e)
            
            log_to_console(f"Repository download error: {str(e)}", "ERROR")
            
            if progress_callback:
                progress_callback(self.progress)
            
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "progress": self.progress.to_dict()
            }
    
    def get_progress(self) -> Dict:
        """Get current download progress"""
        return self.progress.to_dict()
