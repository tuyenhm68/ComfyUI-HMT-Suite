"""
Auto-updater for ComfyUI-HMT-Suite
Automatically updates the custom node from git repository on startup
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Optional
from .downloader import log_to_console


class AutoUpdater:
    """
    Handles automatic updates from git repository
    """

    def __init__(self):
        self.root_dir = self._find_root_dir()
        self.config_file = self.root_dir / "config.json"
        self.config = self._load_config()

    def _find_root_dir(self) -> Path:
        """
        Find the root directory of this custom node
        """
        # current.parent = utils folder
        # current.parent.parent = ComfyUI-HMT-Suite root
        return Path(__file__).resolve().parent.parent

    def _load_config(self) -> Dict:
        """
        Load configuration from config.json

        Returns:
            Dict with configuration settings
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                log_to_console("Config file not found, using default settings", "WARNING")
                return {
                    "auto_update": {
                        "enabled": True,
                        "check_on_startup": True,
                        "show_notification": True
                    }
                }
        except Exception as e:
            log_to_console(f"Error loading config: {e}", "ERROR")
            return {
                "auto_update": {
                    "enabled": False,
                    "check_on_startup": False,
                    "show_notification": False
                }
            }

    def is_enabled(self) -> bool:
        """
        Check if auto-update is enabled

        Returns:
            True if auto-update is enabled
        """
        return self.config.get("auto_update", {}).get("enabled", False)

    def check_on_startup(self) -> bool:
        """
        Check if should check for updates on startup

        Returns:
            True if should check on startup
        """
        return self.config.get("auto_update", {}).get("check_on_startup", False)

    def show_notification(self) -> bool:
        """
        Check if should show notification

        Returns:
            True if should show notification
        """
        return self.config.get("auto_update", {}).get("show_notification", True)

    def _is_git_repository(self) -> bool:
        """
        Check if the current directory is a git repository

        Returns:
            True if it's a git repository
        """
        git_dir = self.root_dir / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def _has_local_changes(self) -> bool:
        """
        Check if there are local uncommitted changes

        Returns:
            True if there are local changes
        """
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=10
            )

            # If output is not empty, there are changes
            return bool(result.stdout.strip())
        except Exception as e:
            log_to_console(f"Error checking git status: {e}", "ERROR")
            return True  # Assume there are changes to be safe

    def _get_current_branch(self) -> Optional[str]:
        """
        Get the current git branch name

        Returns:
            Branch name or None if error
        """
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            log_to_console(f"Error getting branch name: {e}", "ERROR")
            return None

    def _fetch_updates(self) -> bool:
        """
        Fetch updates from remote repository

        Returns:
            True if fetch succeeded
        """
        try:
            log_to_console("Fetching updates from remote repository...", "INFO")

            result = subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                log_to_console("Fetch completed successfully", "SUCCESS")
                return True
            else:
                log_to_console(f"Fetch failed: {result.stderr}", "ERROR")
                return False
        except subprocess.TimeoutExpired:
            log_to_console("Fetch timed out after 60 seconds", "ERROR")
            return False
        except Exception as e:
            log_to_console(f"Error fetching updates: {e}", "ERROR")
            return False

    def _check_updates_available(self) -> bool:
        """
        Check if there are updates available

        Returns:
            True if updates are available
        """
        try:
            branch = self._get_current_branch()
            if not branch:
                return False

            # Compare local and remote commits
            result = subprocess.run(
                ['git', 'rev-list', f'HEAD..origin/{branch}', '--count'],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                commits_behind = int(result.stdout.strip())
                return commits_behind > 0
            return False
        except Exception as e:
            log_to_console(f"Error checking for updates: {e}", "ERROR")
            return False

    def _pull_updates(self) -> Dict:
        """
        Pull updates from remote repository

        Returns:
            Dict with success status and message
        """
        try:
            log_to_console("Pulling updates from remote repository...", "INFO")

            result = subprocess.run(
                ['git', 'pull', 'origin'],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                # Check if anything was updated
                if "Already up to date" in result.stdout or "Already up-to-date" in result.stdout:
                    log_to_console("ComfyUI-HMT-Suite is already up to date", "INFO")
                    return {
                        'success': True,
                        'updated': False,
                        'message': 'Already up to date'
                    }
                else:
                    log_to_console("ComfyUI-HMT-Suite updated successfully!", "SUCCESS")
                    log_to_console("Please restart ComfyUI to apply changes", "INFO")
                    return {
                        'success': True,
                        'updated': True,
                        'message': 'Updated successfully. Please restart ComfyUI.'
                    }
            else:
                error_msg = f"Git pull failed: {result.stderr}"
                log_to_console(error_msg, "ERROR")
                return {
                    'success': False,
                    'updated': False,
                    'message': error_msg
                }
        except subprocess.TimeoutExpired:
            error_msg = "Git pull timed out after 120 seconds"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'updated': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"Error pulling updates: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'updated': False,
                'message': error_msg
            }

    def update(self) -> Dict:
        """
        Perform auto-update if enabled and safe

        Returns:
            Dict with success status, updated flag, and message
        """
        try:
            # Check if auto-update is enabled
            if not self.is_enabled():
                log_to_console("Auto-update is disabled in config", "INFO")
                return {
                    'success': True,
                    'updated': False,
                    'message': 'Auto-update is disabled'
                }

            # Check if this is a git repository
            if not self._is_git_repository():
                log_to_console("Not a git repository, skipping auto-update", "WARNING")
                return {
                    'success': True,
                    'updated': False,
                    'message': 'Not a git repository'
                }

            # Check for local changes
            if self._has_local_changes():
                log_to_console("Local changes detected, skipping auto-update to avoid conflicts", "WARNING")
                log_to_console("Please commit or stash your changes to enable auto-update", "INFO")
                return {
                    'success': True,
                    'updated': False,
                    'message': 'Local changes detected, skipping update'
                }

            # Fetch updates
            if not self._fetch_updates():
                return {
                    'success': False,
                    'updated': False,
                    'message': 'Failed to fetch updates'
                }

            # Check if updates are available
            if not self._check_updates_available():
                log_to_console("ComfyUI-HMT-Suite is already up to date", "INFO")
                return {
                    'success': True,
                    'updated': False,
                    'message': 'Already up to date'
                }

            # Pull updates
            return self._pull_updates()

        except Exception as e:
            error_msg = f"Auto-update failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return {
                'success': False,
                'updated': False,
                'message': error_msg
            }

    def run_on_startup(self):
        """
        Run auto-update on startup if enabled
        """
        try:
            if not self.check_on_startup():
                return

            log_to_console("="*60, "INFO")
            log_to_console("ComfyUI-HMT-Suite Auto-Updater", "INFO")
            log_to_console("="*60, "INFO")

            result = self.update()

            if result['success'] and result.get('updated', False):
                if self.show_notification():
                    log_to_console("="*60, "SUCCESS")
                    log_to_console("*** UPDATE AVAILABLE ***", "SUCCESS")
                    log_to_console(result['message'], "SUCCESS")
                    log_to_console("="*60, "SUCCESS")

            log_to_console("="*60, "INFO")

        except Exception as e:
            log_to_console(f"Error during startup auto-update: {e}", "ERROR")


# Global instance
_updater = None

def get_updater() -> AutoUpdater:
    """
    Get or create the global updater instance

    Returns:
        AutoUpdater instance
    """
    global _updater
    if _updater is None:
        _updater = AutoUpdater()
    return _updater


def run_auto_update_on_startup():
    """
    Convenience function to run auto-update on startup
    """
    updater = get_updater()
    updater.run_on_startup()
