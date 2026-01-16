"""
File Downloader Utility
Supports downloading files with progress tracking, cross-platform compatible
"""

import os
import sys
import requests
import hashlib
from pathlib import Path
from typing import Optional, Callable, Dict
from urllib.parse import urlparse, unquote


def log_to_console(message: str, level: str = "INFO"):
    """Log message to console with color coding"""
    colors = {
        "INFO": "\033[94m",      # Blue
        "SUCCESS": "\033[92m",   # Green
        "WARNING": "\033[93m",   # Yellow
        "ERROR": "\033[91m",     # Red
        "RESET": "\033[0m"
    }
    
    color = colors.get(level, colors["INFO"])
    reset = colors["RESET"]
    print(f"{color}[Model Downloader - {level}]{reset} {message}", flush=True)


class DownloadProgress:
    """Track download progress"""
    def __init__(self):
        self.total_size = 0
        self.downloaded = 0
        self.percentage = 0
        self.status = "pending"  # pending, downloading, completed, error
        self.error_message = None
        self.filename = None
        self.destination = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            "total_size": self.total_size,
            "downloaded": self.downloaded,
            "percentage": self.percentage,
            "status": self.status,
            "error_message": self.error_message,
            "filename": self.filename,
            "destination": self.destination
        }


class FileDownloader:
    """Download files from direct URLs with progress tracking"""
    
    def __init__(self, chunk_size: int = 8192):
        self.chunk_size = chunk_size
        self.progress = DownloadProgress()
    
    def get_filename_from_url(self, url: str, response: Optional[requests.Response] = None) -> str:
        """Extract filename from URL or Content-Disposition header"""
        # Try to get from Content-Disposition header
        if response and 'Content-Disposition' in response.headers:
            content_disp = response.headers['Content-Disposition']
            if 'filename=' in content_disp:
                filename = content_disp.split('filename=')[1].strip('"\'')
                return unquote(filename)
        
        # Extract from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        # Decode URL encoding
        filename = unquote(filename)
        
        # If no filename found, generate one
        if not filename or filename == '':
            filename = f"downloaded_file_{hashlib.md5(url.encode()).hexdigest()[:8]}"
        
        return filename
    
    def download(
        self,
        url: str,
        destination_folder: str,
        filename: Optional[str] = None,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> Dict:
        """
        Download file from URL
        
        Args:
            url: Direct download URL
            destination_folder: Folder to save file (will be created if not exists)
            filename: Optional custom filename (auto-detect if None)
            overwrite: Whether to overwrite existing file
            progress_callback: Optional callback function for progress updates
        
        Returns:
            Dictionary with download status and info
        """
        try:
            self.progress.status = "downloading"
            
            log_to_console(f"Starting download from: {url}", "INFO")
            
            # Create destination folder (cross-platform)
            dest_path = Path(destination_folder)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            log_to_console(f"Destination folder: {dest_path}", "INFO")
            
            # Make initial request to get file info
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get filename
            if not filename:
                filename = self.get_filename_from_url(url, response)
            
            self.progress.filename = filename
            log_to_console(f"Filename: {filename}", "INFO")
            
            # Full file path
            file_path = dest_path / filename
            self.progress.destination = str(file_path)
            
            # Check if file exists
            if file_path.exists():
                if not overwrite:
                    existing_size = file_path.stat().st_size
                    existing_size_mb = existing_size / (1024 * 1024)
                    
                    self.progress.status = "completed"
                    self.progress.percentage = 100
                    self.progress.total_size = existing_size
                    self.progress.downloaded = existing_size
                    
                    log_to_console(f"File already exists: {file_path}", "WARNING")
                    log_to_console(f"Existing file size: {existing_size_mb:.2f} MB", "INFO")
                    log_to_console("Skipping download (overwrite=False)", "INFO")
                    
                    return {
                        "success": True,
                        "message": "File already exists, skipped download",
                        "file_path": str(file_path),
                        "skipped": True,
                        "progress": self.progress.to_dict()
                    }
                else:
                    log_to_console(f"File exists, will overwrite: {file_path}", "WARNING")
            
            # Get total file size
            self.progress.total_size = int(response.headers.get('content-length', 0))
            
            if self.progress.total_size > 0:
                size_mb = self.progress.total_size / (1024 * 1024)
                log_to_console(f"File size: {size_mb:.2f} MB", "INFO")
            
            log_to_console("Downloading...", "INFO")
            
            # Download file
            last_log_percentage = -1  # Track last logged percentage
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        self.progress.downloaded += len(chunk)
                        
                        # Calculate percentage
                        if self.progress.total_size > 0:
                            self.progress.percentage = int(
                                (self.progress.downloaded / self.progress.total_size) * 100
                            )
                            
                            # Update progress on same line (every 1%)
                            if self.progress.percentage != last_log_percentage:
                                downloaded_mb = self.progress.downloaded / (1024 * 1024)
                                total_mb = self.progress.total_size / (1024 * 1024)
                                # Use \r to overwrite the same line
                                print(f"\r\033[94m[Model Downloader - INFO]\033[0m Progress: {self.progress.percentage}% ({downloaded_mb:.2f}/{total_mb:.2f} MB)", end='', flush=True)
                                last_log_percentage = self.progress.percentage
                        
                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(self.progress)
            
            # Print newline after progress completes
            print()  # Move to next line
            
            # Mark as completed
            self.progress.status = "completed"
            self.progress.percentage = 100
            
            log_to_console(f"Download completed: {file_path}", "SUCCESS")
            
            if progress_callback:
                progress_callback(self.progress)
            
            return {
                "success": True,
                "message": "Download completed successfully",
                "file_path": str(file_path),
                "file_size": self.progress.total_size,
                "progress": self.progress.to_dict()
            }
            
        except requests.exceptions.RequestException as e:
            self.progress.status = "error"
            self.progress.error_message = f"Network error: {str(e)}"
            
            log_to_console(f"Download failed: {str(e)}", "ERROR")
            
            if progress_callback:
                progress_callback(self.progress)
            
            return {
                "success": False,
                "message": f"Download failed: {str(e)}",
                "progress": self.progress.to_dict()
            }
        
        except Exception as e:
            self.progress.status = "error"
            self.progress.error_message = str(e)
            
            log_to_console(f"Error: {str(e)}", "ERROR")
            
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
