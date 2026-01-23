"""
Custom Node Installer for ComfyUI
Handles installation of custom nodes from GitHub repositories
"""

import os
import subprocess
import sys
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Callable
from .downloader import log_to_console, DownloadProgress


class CustomNodeInstaller:
    """
    Handler for installing ComfyUI custom nodes from GitHub
    """
    
    def __init__(self):
        self.comfyui_root = self._find_comfyui_root()
        self.custom_nodes_dir = self.comfyui_root / "custom_nodes"
        self.python_executable = self._find_python_executable()
        self.detected_platform = self._detect_platform()
    
    def _find_comfyui_root(self) -> Path:
        """
        Find ComfyUI root directory
        Assumes we're in ComfyUI/custom_nodes/ComfyUI-HMT-Suite
        """
        current = Path(__file__).resolve()
        
        # Go up from utils -> ComfyUI-HMT-Suite -> custom_nodes -> ComfyUI
        try:
            # current.parent = utils folder
            # current.parent.parent = ComfyUI-HMT-Suite folder
            # current.parent.parent.parent = custom_nodes folder
            # current.parent.parent.parent.parent = ComfyUI root folder
            comfyui_root = current.parent.parent.parent.parent
            
            log_to_console(f"Detected ComfyUI root: {comfyui_root}", "INFO")
            
            # Verify this is ComfyUI root by checking for key directories
            if (comfyui_root / "custom_nodes").exists():
                log_to_console(f"Verified ComfyUI root (custom_nodes exists)", "INFO")
                return comfyui_root
            else:
                log_to_console(f"Warning: custom_nodes not found at {comfyui_root}", "WARNING")
        except Exception as e:
            log_to_console(f"Error detecting ComfyUI root: {e}", "WARNING")
        
        # Fallback: use current working directory
        log_to_console(f"Using fallback: current working directory", "WARNING")
        return Path.cwd()
    
    def _find_python_executable(self) -> Path:
        """
        Find Python executable
        Tries to find python_embeded first, then falls back to system python
        """
        # Try python_embeded (Windows portable version)
        python_embedded = self.comfyui_root / "python_embeded" / "python.exe"
        if python_embedded.exists():
            return python_embedded
        
        # Try python_embedded (alternative spelling)
        python_embedded_alt = self.comfyui_root / "python_embedded" / "python.exe"
        if python_embedded_alt.exists():
            return python_embedded_alt
        
        # Fallback to system python
        return Path(sys.executable)
    
    def _detect_platform(self) -> str:
        """
        Detect the current platform
        
        Returns:
            'windows' or 'linux'
        """
        import platform
        system = platform.system().lower()
        
        if 'windows' in system:
            return 'windows'
        elif 'linux' in system:
            return 'linux'
        else:
            # Default to linux for other Unix-like systems (macOS, BSD, etc.)
            return 'linux'
    
    def install_custom_node(
        self,
        github_url: str,
        platform: str = "auto",
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Install a custom node from GitHub
        
        Args:
            github_url: GitHub repository URL
            platform: Target platform ('auto', 'windows', 'linux')
            progress_callback: Optional callback for progress updates
        
        Returns:
            Dict with success status, message, and installation path
        """
        try:
            # Determine actual platform to use
            if platform == "auto":
                actual_platform = self.detected_platform
                log_to_console(f"Auto-detected platform: {actual_platform}", "INFO")
            else:
                actual_platform = platform
                log_to_console(f"Using specified platform: {actual_platform}", "INFO")
            

            # Detect URL type: zip file or GitHub repository
            is_zip_file = github_url.lower().endswith('.zip')
            
            if is_zip_file:
                log_to_console("Detected ZIP file URL", "INFO")
                # Extract node name from URL
                # Example: https://cdn.comfy.org/city96/ComfyUI-GGUF/1.1.10/node.zip
                # We need to extract "ComfyUI-GGUF" from the path
                url_parts = github_url.rstrip('/').split('/')
                # Try to find a part that looks like a node name (contains "ComfyUI" or similar)
                node_name = None
                for part in url_parts:
                    if 'ComfyUI' in part or 'comfyui' in part:
                        node_name = part
                        break
                
                # If not found, use the filename without .zip
                if not node_name:
                    filename = url_parts[-1]
                    node_name = filename.replace('.zip', '')
            else:
                log_to_console("Detected GitHub repository URL", "INFO")
                # Extract repo name from GitHub URL
                node_name = github_url.rstrip('/').split('/')[-1]
                if node_name.endswith('.git'):
                    node_name = node_name[:-4]
            
            # Build destination path
            dest_path = self.custom_nodes_dir / node_name
            
            log_to_console(f"Installing custom node: {node_name}", "INFO")
            log_to_console(f"From: {github_url}", "INFO")
            log_to_console(f"To: {dest_path}", "INFO")
            
            # Check if already exists
            if dest_path.exists():
                log_to_console(f"Custom node folder already exists: {dest_path}", "WARNING")
                return {
                    'success': False,
                    'message': f"Custom node '{node_name}' already exists. Please remove it first or use a different name.",
                    'path': str(dest_path)
                }
            
            # Update progress
            if progress_callback:
                progress = DownloadProgress()
                progress.status = "starting"
                progress.percentage = 10
                progress.downloaded = 0
                progress.total_size = 0
                progress_callback(progress)
            
            # Branch based on URL type
            if is_zip_file:
                # Step 1: Download and extract ZIP file
                log_to_console("Step 1: Downloading and extracting ZIP file...", "INFO")
                extract_result = self._download_and_extract_zip(github_url, dest_path, progress_callback)
                
                if not extract_result['success']:
                    return extract_result
            else:
                # Step 1: Clone repository (existing logic)
                log_to_console("Step 1: Cloning repository...", "INFO")
                clone_result = self._clone_repository(github_url, dest_path)
                
                if not clone_result['success']:
                    return clone_result
            
            # Update progress
            if progress_callback:
                progress = DownloadProgress()
                progress.status = "cloned"
                progress.percentage = 50
                progress.downloaded = 0
                progress.total_size = 0
                progress_callback(progress)



            # Step 2: Check for and run installation scripts
            # Priority order: install.py > install.bat/sh > setup.bat/sh

            # First check for install.py (cross-platform Python script)
            install_py = dest_path / "install.py"

            if install_py.exists():
                log_to_console("Step 2: Found install.py, running Python installation script...", "INFO")

                if progress_callback:
                    progress = DownloadProgress()
                    progress.status = "running_install_py"
                    progress.percentage = 55
                    progress.downloaded = 0
                    progress.total_size = 0
                    progress_callback(progress)

                script_result = self._run_python_script(install_py)

                if not script_result['success']:
                    log_to_console(
                        f"Warning: install.py execution had issues: {script_result['message']}",
                        "WARNING"
                    )
            else:
                # No install.py, check for platform-specific scripts
                if actual_platform == "windows":
                    # Windows: check for .bat files
                    install_script = dest_path / "install.bat"
                    setup_script = dest_path / "setup.bat"
                    script_type = "bat"
                else:
                    # Linux: check for .sh files
                    install_script = dest_path / "install.sh"
                    setup_script = dest_path / "setup.sh"
                    script_type = "sh"

                if install_script.exists():
                    log_to_console(f"Step 2: Found {install_script.name}, running installation script...", "INFO")

                    if progress_callback:
                        progress = DownloadProgress()
                        progress.status = "running_install_script"
                        progress.percentage = 55
                        progress.downloaded = 0
                        progress.total_size = 0
                        progress_callback(progress)

                    script_result = self._run_script(install_script, script_type)

                    if not script_result['success']:
                        log_to_console(
                            f"Warning: {install_script.name} execution had issues: {script_result['message']}",
                            "WARNING"
                        )
                elif setup_script.exists():
                    log_to_console(f"Step 2: Found {setup_script.name}, running setup script...", "INFO")

                    if progress_callback:
                        progress = DownloadProgress()
                        progress.status = "running_setup_script"
                        progress.percentage = 55
                        progress.downloaded = 0
                        progress.total_size = 0
                        progress_callback(progress)

                    script_result = self._run_script(setup_script, script_type)

                    if not script_result['success']:
                        log_to_console(
                            f"Warning: {setup_script.name} execution had issues: {script_result['message']}",
                            "WARNING"
                        )

            
            # Step 3: Check for and install requirements.txt automatically
            requirements_file = dest_path / "requirements.txt"
            
            if requirements_file.exists():
                log_to_console("Step 3: Found requirements.txt, installing dependencies...", "INFO")
                
                if progress_callback:
                    progress = DownloadProgress()
                    progress.status = "installing"
                    progress.percentage = 70
                    progress.downloaded = 0
                    progress.total_size = 0
                    progress_callback(progress)
                
                install_result = self._install_requirements(requirements_file)
                
                if not install_result['success']:
                    log_to_console(
                        f"Warning: Requirements installation had issues: {install_result['message']}", 
                        "WARNING"
                    )
            else:
                log_to_console("No requirements.txt found, skipping dependency installation", "INFO")

            
            # Update progress
            if progress_callback:
                progress = DownloadProgress()
                progress.status = "completed"
                progress.percentage = 100
                progress.downloaded = 0
                progress.total_size = 0
                progress_callback(progress)
            
            log_to_console(f"Custom node '{node_name}' installed successfully!", "SUCCESS")
            log_to_console("Please restart ComfyUI to load the new custom node.", "INFO")
            
            return {
                'success': True,
                'message': f"Custom node '{node_name}' installed successfully. Please restart ComfyUI.",
                'path': str(dest_path)
            }
        
        except Exception as e:
            error_msg = f"Installation failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg,
                'path': ''
            }
    
    def _download_and_extract_zip(
        self, 
        zip_url: str, 
        dest_path: Path,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Download and extract a ZIP file
        
        Args:
            zip_url: URL to the ZIP file
            dest_path: Destination path for extraction
            progress_callback: Optional callback for progress updates
        
        Returns:
            Dict with success status and message
        """
        try:
            # Ensure custom_nodes directory exists
            self.custom_nodes_dir.mkdir(parents=True, exist_ok=True)
            
            # Create temporary file path for download
            zip_filename = zip_url.split('/')[-1]
            temp_zip_path = self.custom_nodes_dir / zip_filename
            
            log_to_console(f"Downloading: {zip_url}", "INFO")
            log_to_console(f"To: {temp_zip_path}", "INFO")
            
            # Download ZIP file
            if progress_callback:
                progress = DownloadProgress()
                progress.status = "downloading"
                progress.percentage = 20
                progress.downloaded = 0
                progress.total_size = 0
                progress_callback(progress)
            
            urllib.request.urlretrieve(zip_url, str(temp_zip_path))
            
            log_to_console("Download completed", "SUCCESS")
            
            # Extract ZIP file
            if progress_callback:
                progress = DownloadProgress()
                progress.status = "extracting"
                progress.percentage = 40
                progress.downloaded = 0
                progress.total_size = 0
                progress_callback(progress)
            
            log_to_console(f"Extracting to: {dest_path}", "INFO")
            
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(str(dest_path))
            
            # Clean up temporary ZIP file
            temp_zip_path.unlink()
            
            log_to_console("Extraction completed successfully", "SUCCESS")
            return {
                'success': True,
                'message': 'ZIP file downloaded and extracted successfully'
            }
        
        except urllib.error.URLError as e:
            error_msg = f"Failed to download ZIP file: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }
        except zipfile.BadZipFile:
            error_msg = "Downloaded file is not a valid ZIP file"
            log_to_console(error_msg, "ERROR")
            # Clean up bad file
            if temp_zip_path.exists():
                temp_zip_path.unlink()
            return {
                'success': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"ZIP download/extraction failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            # Clean up on error
            if 'temp_zip_path' in locals() and temp_zip_path.exists():
                temp_zip_path.unlink()
            return {
                'success': False,
                'message': error_msg
            }
    
    def _clone_repository(self, github_url: str, dest_path: Path) -> Dict:
        """
        Clone a GitHub repository using git
        Git will automatically use the repository name as the folder name
        
        Args:
            github_url: GitHub repository URL
            dest_path: Expected destination path (for verification only)
        
        Returns:
            Dict with success status and message
        """
        try:
            # Ensure custom_nodes directory exists
            self.custom_nodes_dir.mkdir(parents=True, exist_ok=True)
            
            # Build git clone command - don't specify destination, let git use default name
            cmd = [
                'git',
                'clone',
                github_url
            ]
            
            log_to_console(f"Running: {' '.join(cmd)}", "INFO")
            
            # Execute git clone in custom_nodes directory
            result = subprocess.run(
                cmd,
                cwd=str(self.custom_nodes_dir),  # Run in custom_nodes dir
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                log_to_console("Repository cloned successfully", "SUCCESS")
                return {
                    'success': True,
                    'message': 'Repository cloned successfully'
                }
            else:
                error_msg = f"Git clone failed: {result.stderr}"
                log_to_console(error_msg, "ERROR")
                return {
                    'success': False,
                    'message': error_msg
                }
        
        except subprocess.TimeoutExpired:
            error_msg = "Git clone timed out after 5 minutes"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }
        except FileNotFoundError:
            error_msg = "Git is not installed or not in PATH"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"Clone failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }
    
    def _install_requirements(self, requirements_file: Path) -> Dict:
        """
        Install requirements from requirements.txt
        
        Args:
            requirements_file: Path to requirements.txt
        
        Returns:
            Dict with success status and message
        """
        try:
            # Build pip install command
            cmd = [
                str(self.python_executable),
                '-s',
                '-m',
                'pip',
                'install',
                '-r',
                str(requirements_file)
            ]
            
            log_to_console(f"Running: {' '.join(cmd)}", "INFO")
            
            # Execute pip install
            result = subprocess.run(
                cmd,
                cwd=str(self.comfyui_root),
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
            
            if result.returncode == 0:
                log_to_console("Requirements installed successfully", "SUCCESS")
                return {
                    'success': True,
                    'message': 'Requirements installed successfully'
                }
            else:
                error_msg = f"Pip install had errors: {result.stderr}"
                log_to_console(error_msg, "WARNING")
                # Don't fail completely, as some requirements might have installed
                return {
                    'success': True,
                    'message': f'Requirements partially installed. Check logs for details.'
                }
        
        except subprocess.TimeoutExpired:
            error_msg = "Pip install timed out after 10 minutes"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"Requirements installation failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }
    
    
    def _run_python_script(self, script_path: Path) -> Dict:
        """
        Run a Python installation script (install.py)

        Args:
            script_path: Path to the Python script

        Returns:
            Dict with success status and message
        """
        try:
            log_to_console(f"Running: {script_path.name}", "INFO")

            # Build command to run Python script
            cmd = [
                str(self.python_executable),
                '-s',
                str(script_path)
            ]

            log_to_console(f"Command: {' '.join(cmd)}", "INFO")

            # Execute script from the script's directory so relative paths work correctly
            result = subprocess.run(
                cmd,
                cwd=str(script_path.parent),
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )

            if result.returncode == 0:
                log_to_console(f"{script_path.name} executed successfully", "SUCCESS")
                if result.stdout:
                    log_to_console(f"Output: {result.stdout}", "INFO")
                return {
                    'success': True,
                    'message': f'{script_path.name} executed successfully'
                }
            else:
                error_msg = f"{script_path.name} execution had errors: {result.stderr}"
                log_to_console(error_msg, "WARNING")
                if result.stdout:
                    log_to_console(f"Output: {result.stdout}", "INFO")
                # Don't fail completely, as the script might have partially succeeded
                return {
                    'success': True,
                    'message': f'{script_path.name} completed with warnings. Check logs for details.'
                }

        except subprocess.TimeoutExpired:
            error_msg = f"{script_path.name} timed out after 10 minutes"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"{script_path.name} execution failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }

    def _run_script(self, script_path: Path, script_type: str) -> Dict:
        """
        Run an installation script (.bat for Windows, .sh for Linux)

        Args:
            script_path: Path to the script
            script_type: Type of script ('bat' or 'sh')

        Returns:
            Dict with success status and message
        """
        try:
            log_to_console(f"Running: {script_path.name}", "INFO")

            # Prepare command based on script type
            if script_type == "sh":
                # For .sh files, make executable first and run with bash
                try:
                    # Make script executable
                    os.chmod(script_path, 0o755)
                except:
                    pass  # Ignore chmod errors on Windows

                cmd = ['bash', str(script_path)]
                use_shell = False
            else:
                # For .bat files on Windows
                cmd = [str(script_path)]
                use_shell = True

            # Execute script
            # Run from the script's directory so relative paths work correctly
            result = subprocess.run(
                cmd,
                cwd=str(script_path.parent),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes timeout
                shell=use_shell
            )

            if result.returncode == 0:
                log_to_console(f"{script_path.name} executed successfully", "SUCCESS")
                return {
                    'success': True,
                    'message': f'{script_path.name} executed successfully'
                }
            else:
                error_msg = f"{script_path.name} execution had errors: {result.stderr}"
                log_to_console(error_msg, "WARNING")
                # Don't fail completely, as the script might have partially succeeded
                return {
                    'success': True,
                    'message': f'{script_path.name} completed with warnings. Check logs for details.'
                }

        except subprocess.TimeoutExpired:
            error_msg = f"{script_path.name} timed out after 10 minutes"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"{script_path.name} execution failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'message': error_msg
            }
