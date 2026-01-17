"""
ComfyUI Restart Node
Safely restarts the ComfyUI server with all original arguments preserved
"""

import os
import sys
import time
from pathlib import Path
from ..utils.downloader import log_to_console


class ComfyUIRestartNode:
    """
    ComfyUI Node for restarting the server
    Useful after installing custom nodes or changing configurations
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input parameters for the node"""
        return {
            "required": {
                "restart_delay": ("INT", {
                    "default": 2,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "display": "number"
                }),
                "confirm_restart": ("BOOLEAN", {
                    "default": False,
                    "label_on": "YES - Restart Now",
                    "label_off": "NO - Don't Restart"
                }),
            },
            "optional": {
                "show_info": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Show restart info",
                    "label_off": "Hide info"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("status", "message", "restart_command")
    FUNCTION = "restart_server"
    CATEGORY = "HMT Suite/Utils"
    OUTPUT_NODE = True
    
    def restart_server(
        self,
        restart_delay: int = 2,
        confirm_restart: bool = False,
        show_info: bool = True
    ):
        """
        Restart ComfyUI server
        
        Args:
            restart_delay: Delay in seconds before restarting (0-10)
            confirm_restart: Must be True to actually restart
            show_info: Show detailed restart information
        
        Returns:
            Tuple of (status, message, restart_command)
        """
        try:
            # Get current Python executable
            python_exe = sys.executable
            
            # Get command line arguments
            args = sys.argv.copy()
            
            # Get current working directory
            cwd = os.getcwd()
            
            # Build restart command for display
            restart_cmd = f"{python_exe} {' '.join(args)}"
            
            # Log restart information
            log_to_console("=" * 60, "INFO")
            log_to_console("ComfyUI Restart Node - Information", "INFO")
            log_to_console("=" * 60, "INFO")
            
            if show_info:
                log_to_console(f"Python Executable: {python_exe}", "INFO")
                log_to_console(f"Working Directory: {cwd}", "INFO")
                log_to_console(f"Command Arguments:", "INFO")
                for i, arg in enumerate(args):
                    log_to_console(f"  [{i}] {arg}", "INFO")
                log_to_console(f"Restart Delay: {restart_delay} seconds", "INFO")
            
            # Check if restart is confirmed
            if not confirm_restart:
                log_to_console("Restart NOT confirmed (confirm_restart = False)", "WARNING")
                log_to_console("Set 'confirm_restart' to True to actually restart", "WARNING")
                log_to_console("=" * 60, "WARNING")
                
                return (
                    "cancelled",
                    "Restart cancelled. Set 'confirm_restart' to True to restart.",
                    restart_cmd
                )
            
            # Restart is confirmed
            log_to_console("Restart CONFIRMED - Server will restart!", "SUCCESS")
            log_to_console(f"Restarting in {restart_delay} seconds...", "SUCCESS")
            log_to_console("=" * 60, "SUCCESS")
            
            # Flush all output buffers
            sys.stdout.flush()
            sys.stderr.flush()
            
            # Wait for delay
            if restart_delay > 0:
                time.sleep(restart_delay)
            
            # Perform restart
            log_to_console("Restarting ComfyUI now...", "INFO")
            
            # Use os.execv to replace current process
            # This will restart ComfyUI with the same Python and arguments
            try:
                if os.name == 'nt':  # Windows
                    os.execv(python_exe, [python_exe] + args)
                else:  # Linux/Mac
                    os.execv(python_exe, [python_exe] + args)
            except Exception as exec_error:
                # If os.execv fails, try alternative method
                log_to_console(f"os.execv failed: {exec_error}", "ERROR")
                log_to_console("Trying alternative restart method...", "WARNING")
                
                import subprocess
                subprocess.Popen([python_exe] + args, cwd=cwd)
                
                # Exit current process
                log_to_console("Exiting current process...", "INFO")
                sys.exit(0)
            
            # This line should never be reached if restart is successful
            return (
                "restarting",
                f"ComfyUI is restarting with delay of {restart_delay}s...",
                restart_cmd
            )
        
        except Exception as e:
            error_msg = f"Restart failed: {str(e)}"
            log_to_console(f"Exception: {error_msg}", "ERROR")
            log_to_console("=" * 60, "ERROR")
            
            return (
                "error",
                error_msg,
                "N/A"
            )
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Force re-execution on every run"""
        return time.time()


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HMT_ComfyUIRestart": ComfyUIRestartNode
}

# Display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    "HMT_ComfyUIRestart": "ComfyUI Restart"
}
