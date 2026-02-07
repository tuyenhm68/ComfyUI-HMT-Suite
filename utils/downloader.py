"""
File Downloader Utility
Supports downloading files with progress tracking, cross-platform compatible.
Enhanced with multi-threaded parallel downloading for maximum speed.
Version 2.0: Added file integrity validation and disk space checking.
"""

import os
import sys
import requests
import hashlib
import time
import shutil
import concurrent.futures
import threading
from pathlib import Path
from typing import Optional, Callable, Dict
from urllib.parse import urlparse, unquote
from threading import Lock

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


def check_disk_space(path: Path, required_bytes: int) -> bool:
    """Check if there's enough disk space available"""
    try:
        stat = shutil.disk_usage(path.parent if path.is_file() else path)
        available = stat.free
        # Add 10% buffer for safety
        required_with_buffer = int(required_bytes * 1.1)
        return available >= required_with_buffer
    except Exception as e:
        log_to_console(f"Could not check disk space: {e}", "WARNING")
        return True  # Assume OK if we can't check


def verify_file_size(file_path: Path, expected_size: int, tolerance: int = 0) -> bool:
    """
    Verify downloaded file size matches expected size

    Args:
        file_path: Path to downloaded file
        expected_size: Expected file size in bytes
        tolerance: Allowed size difference in bytes (default: 0 for exact match)

    Returns:
        True if size matches (within tolerance), False otherwise
    """
    if not file_path.exists():
        return False

    actual_size = file_path.stat().st_size
    size_diff = abs(actual_size - expected_size)

    if size_diff <= tolerance:
        return True
    else:
        log_to_console(
            f"File size mismatch! Expected: {expected_size:,} bytes, "
            f"Got: {actual_size:,} bytes, Diff: {size_diff:,} bytes",
            "ERROR"
        )
        return False


def verify_part_size(part_path: Path, expected_size: int) -> bool:
    """Verify a downloaded part has the correct size"""
    if not part_path.exists():
        log_to_console(f"Part file missing: {part_path}", "ERROR")
        return False

    actual_size = part_path.stat().st_size
    if actual_size != expected_size:
        log_to_console(
            f"Part size mismatch: {part_path.name} - "
            f"Expected: {expected_size:,}, Got: {actual_size:,}",
            "ERROR"
        )
        return False
    return True


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
        self._lock = Lock()
    
    def update(self, downloaded_delta: int):
        """Thread-safe update of downloaded bytes"""
        with self._lock:
            self.downloaded += downloaded_delta
            if self.total_size > 0:
                self.percentage = int((self.downloaded / self.total_size) * 100)
    
    def set_total(self, total: int):
        with self._lock:
            self.total_size = total

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        with self._lock:
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
    """Download files from direct URLs with multi-threaded progress tracking"""
    
    def __init__(self, chunk_size: int = 1024 * 1024, max_workers: int = 16, min_part_size: int = 1024 * 1024 * 10):
        self.chunk_size = chunk_size  # 1MB default
        self.max_workers = max_workers
        self.min_part_size = min_part_size # 10MB min
        self.progress = DownloadProgress()
        self.session = requests.Session()
        self.auth_headers = {}  # Store authentication headers

        # Configure connection pool to support all workers
        # pool_connections: number of pools to cache (one per host)
        # pool_maxsize: maximum connections per pool
        # Set pool_maxsize to max_workers + buffer to avoid "pool is full" warnings
        adapter = requests.adapters.HTTPAdapter(
            max_retries=3,
            pool_connections=10,
            pool_maxsize=max(max_workers + 5, 20)  # Add buffer for parallel requests
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
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
    
    def _download_part(self, url: str, start: int, end: int, part_path: Path, progress_callback: Optional[Callable] = None):
        """Download a specific part of the file with retry logic"""
        headers = {'Range': f'bytes={start}-{end}'}
        # Merge with authentication headers if present
        headers.update(self.auth_headers)

        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                # Increase timeout: 60s connection + 120s read
                with self.session.get(url, headers=headers, stream=True, timeout=(60, 120)) as response:
                    response.raise_for_status()
                    with open(part_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if chunk:
                                f.write(chunk)
                                size = len(chunk)
                                self.progress.update(size)
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    log_to_console(f"Part download failed ({start}-{end}), retrying ({attempt+1}/{max_retries}): {e}", "WARNING")
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    log_to_console(f"Part download failed ({start}-{end}) after {max_retries} attempts: {e}", "ERROR")
                    return False

    def download(
        self,
        url: str,
        destination_folder: str,
        filename: Optional[str] = None,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        auth_token: Optional[str] = None
    ) -> Dict:
        """
        Download file from URL with parallel support

        Args:
            url: URL to download from
            destination_folder: Folder to save the file
            filename: Optional custom filename
            overwrite: Whether to overwrite existing files
            progress_callback: Callback function for progress updates
            auth_token: Optional authentication token (e.g., Hugging Face token)
        """
        try:
            self.progress = DownloadProgress() # Reset progress
            self.progress.status = "downloading"

            # Set authentication headers if token provided
            self.auth_headers = {}
            if auth_token and auth_token.strip():
                self.auth_headers['Authorization'] = f'Bearer {auth_token.strip()}'
                log_to_console("Authentication token provided", "INFO")

            log_to_console(f"Starting download from: {url}", "INFO")
            
            # Create destination folder
            dest_path = Path(destination_folder)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            # Initial Request to get metadata
            head_resp = None
            try:
                head_resp = self.session.head(url, allow_redirects=True, timeout=30, headers=self.auth_headers)
                # If HEAD fails (some servers deny it), try GET with stream
                if head_resp.status_code >= 400:
                     head_resp = self.session.get(url, stream=True, timeout=30, headers=self.auth_headers)
                     head_resp.close() # Close immediately, we just want headers
            except:
                # Fallback to simple get if head fails
                head_resp = None

            # Determine filename
            if not filename:
                if head_resp:
                    filename = self.get_filename_from_url(url, head_resp)
                else:
                     filename = self.get_filename_from_url(url)
            
            self.progress.filename = filename
            log_to_console(f"Filename: {filename}", "INFO")
            
            file_path = dest_path / filename
            self.progress.destination = str(file_path)
            
            # Check existing
            if file_path.exists():
                if not overwrite:
                    existing_size = file_path.stat().st_size
                    self.progress.status = "completed"
                    self.progress.percentage = 100
                    self.progress.total_size = existing_size
                    self.progress.downloaded = existing_size
                    log_to_console(f"File exists: {file_path} ({existing_size/(1024*1024):.2f} MB). Skipping.", "WARNING")
                    return {
                        "success": True,
                        "message": "File already exists, skipped download",
                        "file_path": str(file_path),
                        "skipped": True,
                        "progress": self.progress.to_dict()
                    }
                else:
                    log_to_console(f"File exists, overwriting...", "WARNING")
            
            # Get content length and accept-ranges
            total_size = 0
            accept_ranges = False
            
            if head_resp:
                total_size = int(head_resp.headers.get('content-length', 0))
                
                # Check accept-ranges header properly (case-insensitive)
                accept_ranges_header = head_resp.headers.get('Accept-Ranges', '').lower()
                if 'bytes' in accept_ranges_header:
                    accept_ranges = True
            else:
                # Fallback to GET to find size
                 with self.session.get(url, stream=True, timeout=30, headers=self.auth_headers) as r:
                     total_size = int(r.headers.get('content-length', 0))
                     accept_ranges_header = r.headers.get('Accept-Ranges', '').lower()
                     if 'bytes' in accept_ranges_header:
                         accept_ranges = True

            self.progress.set_total(total_size)

            if total_size > 0:
                log_to_console(f"File size: {total_size / (1024*1024):.2f} MB", "INFO")

                # Check disk space
                if not check_disk_space(dest_path, total_size):
                    available_mb = shutil.disk_usage(dest_path).free / (1024*1024)
                    required_mb = total_size / (1024*1024)
                    raise Exception(
                        f"Insufficient disk space. Required: {required_mb:.2f} MB, "
                        f"Available: {available_mb:.2f} MB"
                    )
                log_to_console("Disk space check: OK", "SUCCESS")
            else:
                log_to_console("File size unknown. Skipping disk space check.", "WARNING")

            # DECIDE STRATEGY
            use_parallel = False
            if accept_ranges and total_size > self.min_part_size:
                use_parallel = True
                log_to_console("Server supports parallel download. Accelerating...", "SUCCESS")
            else:
                log_to_console("Using single-threaded download.", "INFO")

            start_time = time.time()
            
            if use_parallel:
                # Calculate parts
                num_workers = self.max_workers
                part_size = total_size // num_workers
                
                # Adjust if part size is too small
                if part_size < self.min_part_size:
                    num_workers = max(1, total_size // self.min_part_size)
                    part_size = total_size // num_workers
                
                log_to_console(f"Splitting into {num_workers} parts...", "INFO")
                
                ranges = []
                for i in range(num_workers):
                    start = i * part_size
                    end = start + part_size - 1
                    if i == num_workers - 1:
                        end = total_size - 1
                    ranges.append((start, end))
                
                # Temp directory for parts
                temp_dir = dest_path / f".tmp_{filename}_{int(time.time())}"
                temp_dir.mkdir(exist_ok=True)
                
                part_files = []
                futures = []
                
                monitor_thread = None
                stop_monitor = False

                def monitor_progress():
                    last_pct = -1
                    while not stop_monitor:
                        pct = self.progress.percentage
                        if pct != last_pct and pct >= 0:
                            downloaded_mb = self.progress.downloaded / (1024 * 1024)
                            total_mb = self.progress.total_size / (1024 * 1024)
                            print(f"\r\033[94m[Model Downloader - INFO]\033[0m Progress: {pct}% ({downloaded_mb:.2f}/{total_mb:.2f} MB)", end='', flush=True)
                            last_pct = pct
                            if progress_callback:
                                try:
                                    progress_callback(self.progress)
                                except:
                                    pass
                        time.sleep(0.5)

                try:
                    # Start Monitor
                    monitor_thread = threading.Thread(target=monitor_progress)
                    monitor_thread.daemon = True # Ensure thread dies if main dies
                    monitor_thread.start()

                    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                        for i, (start, end) in enumerate(ranges):
                            p_path = temp_dir / f"part_{i}"
                            part_files.append(p_path)
                            futures.append(executor.submit(self._download_part, url, start, end, p_path))
                        
                        # Wait for valid completion
                        for future in concurrent.futures.as_completed(futures):
                            if not future.result():
                                raise Exception("One or more parts failed to download")
                    
                    stop_monitor = True
                    monitor_thread.join(timeout=1.0) # Wait a bit but don't hang
                    print() # Newline

                    # Verify all parts before merging
                    log_to_console("Verifying downloaded parts...", "INFO")
                    all_parts_valid = True
                    for i, (p_path, (start, end)) in enumerate(zip(part_files, ranges)):
                        expected_part_size = end - start + 1
                        if not verify_part_size(p_path, expected_part_size):
                            all_parts_valid = False
                            break

                    if not all_parts_valid:
                        raise Exception("Part verification failed. Download incomplete.")

                    log_to_console("All parts verified successfully", "SUCCESS")

                    # Combine parts to temporary file first (atomic write pattern)
                    temp_output = file_path.with_suffix(file_path.suffix + '.tmp')
                    log_to_console("Merging parts...", "INFO")
                    with open(temp_output, 'wb') as outfile:
                        for p_path in part_files:
                            with open(p_path, 'rb') as infile:
                                shutil.copyfileobj(infile, outfile)

                    # Verify merged file size
                    if not verify_file_size(temp_output, total_size, tolerance=0):
                        temp_output.unlink()  # Delete corrupted file
                        raise Exception(
                            f"Merged file size verification failed. "
                            f"Expected: {total_size:,} bytes"
                        )

                    log_to_console("File integrity verified", "SUCCESS")

                    # Atomic rename: move temp file to final destination
                    if file_path.exists():
                        file_path.unlink()  # Remove old file if exists
                    temp_output.rename(file_path)

                    # Cleanup temp dir
                    try:
                        shutil.rmtree(temp_dir)
                    except:
                        pass # Ignore cleanup errors

                except Exception as e:
                    stop_monitor = True
                    if monitor_thread and monitor_thread.is_alive():
                        monitor_thread.join(timeout=1.0)
                    print()
                    # Cleanup
                    if temp_dir.exists():
                        try:
                            shutil.rmtree(temp_dir)
                        except:
                            pass
                    raise e

            else:
                # Single threaded fallback - use atomic write pattern
                temp_output = file_path.with_suffix(file_path.suffix + '.tmp')

                # Increase timeout: 60s connection + 120s read
                with self.session.get(url, stream=True, timeout=(60, 120), headers=self.auth_headers) as response:
                    response.raise_for_status()

                    last_log_percentage = -1
                    with open(temp_output, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            if chunk:
                                f.write(chunk)
                                self.progress.update(len(chunk))

                                # Log
                                if self.progress.percentage != last_log_percentage:
                                    downloaded_mb = self.progress.downloaded / (1024 * 1024)
                                    total_mb = (self.progress.total_size / (1024 * 1024)) if self.progress.total_size else 0
                                    print(f"\r\033[94m[Model Downloader - INFO]\033[0m Progress: {self.progress.percentage}% ({downloaded_mb:.2f}/{total_mb:.2f} MB)", end='', flush=True)
                                    last_log_percentage = self.progress.percentage

                                    if progress_callback:
                                        try:
                                            progress_callback(self.progress)
                                        except:
                                            pass
                    print() # Newline

                # Verify file size if known
                if total_size > 0:
                    log_to_console("Verifying file integrity...", "INFO")
                    if not verify_file_size(temp_output, total_size, tolerance=0):
                        temp_output.unlink()  # Delete corrupted file
                        raise Exception(
                            f"Downloaded file size verification failed. "
                            f"Expected: {total_size:,} bytes"
                        )
                    log_to_console("File integrity verified", "SUCCESS")

                # Atomic rename: move temp file to final destination
                if file_path.exists():
                    file_path.unlink()
                temp_output.rename(file_path)

            elapsed = time.time() - start_time
            avg_speed = (self.progress.total_size / (1024*1024)) / elapsed if elapsed > 0 else 0

            # Final verification
            final_size = file_path.stat().st_size
            final_size_mb = final_size / (1024*1024)

            self.progress.status = "completed"
            self.progress.percentage = 100

            log_to_console(f"Download completed: {file_path}", "SUCCESS")
            log_to_console(f"Final file size: {final_size_mb:.2f} MB ({final_size:,} bytes)", "SUCCESS")
            log_to_console(f"Average Speed: {avg_speed:.2f} MB/s", "SUCCESS")
            
            if progress_callback:
                progress_callback(self.progress)
            
            return {
                "success": True,
                "message": "Download completed successfully",
                "file_path": str(file_path),
                "file_size": self.progress.total_size,
                "progress": self.progress.to_dict()
            }

        except Exception as e:
            self.progress.status = "error"
            self.progress.error_message = str(e)
            log_to_console(f"Download failed: {str(e)}", "ERROR")

            # Cleanup: remove temporary files
            try:
                temp_output = file_path.with_suffix(file_path.suffix + '.tmp')
                if temp_output.exists():
                    log_to_console("Cleaning up temporary file...", "INFO")
                    temp_output.unlink()
            except:
                pass

            if progress_callback:
                progress_callback(self.progress)

            return {
                "success": False,
                "message": f"Download failed: {str(e)}",
                "progress": self.progress.to_dict()
            }
    
    def get_progress(self) -> Dict:
        """Get current download progress"""
        return self.progress.to_dict()
