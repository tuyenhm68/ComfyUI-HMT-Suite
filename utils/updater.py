"""
ComfyUI Updater Utility
Handles updating ComfyUI core and custom nodes using pygit2.
Based on ComfyUI's official update.py logic for portable compatibility.
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, List
from .downloader import log_to_console


class ComfyUIUpdater:
    """
    Handles updating ComfyUI core and custom nodes using pygit2.
    Compatible with both portable and git-installed versions.
    """

    def __init__(self):
        self.comfyui_root = self._find_comfyui_root()
        self.custom_nodes_dir = self.comfyui_root / "custom_nodes"
        self.python_executable = self._find_python_executable()

    def _find_comfyui_root(self) -> Path:
        current = Path(__file__).resolve()
        # utils -> ComfyUI-HMT-Suite -> custom_nodes -> ComfyUI
        comfyui_root = current.parent.parent.parent.parent
        if (comfyui_root / "custom_nodes").exists():
            return comfyui_root
        return Path.cwd()

    def _find_python_executable(self) -> Path:
        # Try python_embeded (Windows portable)
        for name in ["python_embeded", "python_embedded"]:
            python_exe = self.comfyui_root.parent / name / "python.exe"
            if python_exe.exists():
                return python_exe
        return Path(sys.executable)

    def _import_pygit2(self):
        """Import pygit2 with owner validation disabled."""
        try:
            import pygit2
            pygit2.option(pygit2.GIT_OPT_SET_OWNER_VALIDATION, 0)
            return pygit2
        except ImportError:
            raise RuntimeError(
                "pygit2 is not installed. "
                "Install it with: pip install pygit2"
            )

    def _pull(self, repo, remote_name='origin', branch='master'):
        """
        Pull latest changes from remote.
        Based on ComfyUI's official update.py pull() function.
        """
        pygit2 = self._import_pygit2()

        for remote in repo.remotes:
            if remote.name == remote_name:
                remote.fetch()
                try:
                    remote_ref = repo.lookup_reference(
                        f'refs/remotes/{remote_name}/{branch}'
                    )
                except KeyError:
                    raise RuntimeError(
                        f"Branch '{branch}' not found on remote '{remote_name}'"
                    )

                remote_target = remote_ref.target
                merge_result, _ = repo.merge_analysis(remote_target)

                if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                    return False  # Already up to date

                elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                    repo.checkout_tree(repo.get(remote_target))
                    try:
                        master_ref = repo.lookup_reference(
                            f'refs/heads/{branch}'
                        )
                        master_ref.set_target(remote_target)
                    except KeyError:
                        repo.create_branch(branch, repo.get(remote_target))
                    repo.head.set_target(remote_target)
                    return True  # Updated

                elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                    repo.merge(remote_target)
                    if repo.index.conflicts is not None:
                        for conflict in repo.index.conflicts:
                            log_to_console(
                                f"Conflict in: {conflict[0].path}", "WARNING"
                            )
                        repo.state_cleanup()
                        raise RuntimeError("Merge conflicts detected")

                    user = repo.default_signature
                    tree = repo.index.write_tree()
                    repo.create_commit(
                        'HEAD', user, user, 'Merge!',
                        tree, [repo.head.target, remote_target]
                    )
                    repo.state_cleanup()
                    return True  # Updated

                else:
                    raise RuntimeError("Unknown merge analysis result")

        return False

    def _stash_and_prepare(self, repo):
        """Stash current changes before pulling."""
        pygit2 = self._import_pygit2()
        ident = pygit2.Signature('comfyui-hmt', 'hmt@comfyui')

        try:
            repo.stash(ident)
            log_to_console("Stashed current changes", "INFO")
        except KeyError:
            log_to_console("Nothing to stash", "INFO")
        except Exception:
            log_to_console("Could not stash, cleaning index", "WARNING")
            try:
                repo.state_cleanup()
                repo.index.read_tree(repo.head.peel().tree)
                repo.index.write()
                repo.stash(ident)
            except KeyError:
                pass

    def _detect_default_branch(self, repo) -> str:
        """Detect the default branch name (master or main)."""
        for branch_name in ['master', 'main']:
            if repo.lookup_branch(branch_name) is not None:
                return branch_name
            try:
                repo.lookup_reference(f'refs/remotes/origin/{branch_name}')
                return branch_name
            except KeyError:
                continue
        return 'master'

    def _checkout_branch(self, repo, branch_name: str):
        """Checkout a branch, creating it if needed from remote."""
        pygit2 = self._import_pygit2()

        branch = repo.lookup_branch(branch_name)
        if branch is None:
            try:
                ref = repo.lookup_reference(
                    f'refs/remotes/origin/{branch_name}'
                )
            except KeyError:
                for remote in repo.remotes:
                    if remote.name == "origin":
                        remote.fetch()
                ref = repo.lookup_reference(
                    f'refs/remotes/origin/{branch_name}'
                )
            repo.checkout(ref)
            if repo.lookup_branch(branch_name) is None:
                repo.create_branch(branch_name, repo.get(ref.target))
        else:
            ref = repo.lookup_reference(branch.name)
            repo.checkout(ref)

    def _install_requirements(self, requirements_path: Path) -> bool:
        """Install pip requirements."""
        if not requirements_path.exists():
            return True

        try:
            cmd = [
                str(self.python_executable), '-s',
                '-m', 'pip', 'install', '-r', str(requirements_path)
            ]
            log_to_console(f"Installing requirements: {requirements_path}", "INFO")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                log_to_console("Requirements installed successfully", "SUCCESS")
                return True
            else:
                log_to_console(
                    f"Requirements install warnings: {result.stderr}", "WARNING"
                )
                return True  # Don't fail on partial installs
        except Exception as e:
            log_to_console(f"Requirements install failed: {e}", "ERROR")
            return False

    def _run_install_script(self, script_path: Path) -> bool:
        """Run install.py script for a custom node."""
        if not script_path.exists():
            return True

        try:
            cmd = [str(self.python_executable), '-s', str(script_path)]
            log_to_console(f"Running: {script_path.name}", "INFO")
            result = subprocess.run(
                cmd, cwd=str(script_path.parent),
                capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                log_to_console(f"{script_path.name} completed", "SUCCESS")
            else:
                log_to_console(
                    f"{script_path.name} warnings: {result.stderr}", "WARNING"
                )
            return True
        except Exception as e:
            log_to_console(f"{script_path.name} failed: {e}", "ERROR")
            return False

    def get_current_version(self) -> Dict:
        """Get current ComfyUI version info."""
        try:
            pygit2 = self._import_pygit2()
            repo = pygit2.Repository(str(self.comfyui_root))
            commit = repo.head.peel()
            return {
                "commit": str(commit.id)[:8],
                "message": commit.message.strip().split('\n')[0],
                "date": datetime.fromtimestamp(
                    commit.commit_time
                ).strftime('%Y-%m-%d %H:%M:%S'),
                "branch": repo.head.shorthand if not repo.head.is_detached else "detached"
            }
        except Exception as e:
            return {"error": str(e)}

    def check_update_available(self) -> Dict:
        """Check if ComfyUI update is available."""
        try:
            pygit2 = self._import_pygit2()
            repo = pygit2.Repository(str(self.comfyui_root))
            branch_name = self._detect_default_branch(repo)

            for remote in repo.remotes:
                if remote.name == "origin":
                    remote.fetch()

            local_commit = repo.head.peel()
            try:
                remote_ref = repo.lookup_reference(
                    f'refs/remotes/origin/{branch_name}'
                )
                remote_commit = repo.get(remote_ref.target)
            except KeyError:
                return {"available": False, "message": "Could not check remote"}

            if local_commit.id == remote_commit.id:
                return {"available": False, "message": "Already up to date"}

            return {
                "available": True,
                "current": str(local_commit.id)[:8],
                "latest": str(remote_commit.id)[:8],
                "message": remote_commit.message.strip().split('\n')[0]
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def update_comfyui(self, stable: bool = True) -> Dict:
        """
        Update ComfyUI core.
        Based on official update.py logic.
        """
        try:
            pygit2 = self._import_pygit2()
            repo = pygit2.Repository(str(self.comfyui_root))

            log_to_console("=" * 60, "INFO")
            log_to_console("ComfyUI Core Update - Starting", "INFO")
            log_to_console("=" * 60, "INFO")

            # Step 1: Stash changes
            self._stash_and_prepare(repo)

            # Step 2: Create backup branch
            backup_name = f'backup_{datetime.today().strftime("%Y%m%d_%H%M%S")}'
            try:
                repo.branches.local.create(backup_name, repo.head.peel())
                log_to_console(f"Created backup branch: {backup_name}", "INFO")
            except Exception:
                pass

            # Step 3: Checkout default branch
            branch_name = self._detect_default_branch(repo)
            log_to_console(f"Checking out {branch_name} branch", "INFO")
            self._checkout_branch(repo, branch_name)

            # Step 4: Pull latest
            log_to_console("Pulling latest changes...", "INFO")
            updated = self._pull(repo, branch=branch_name)

            # Step 5: Checkout stable tag if requested
            if stable:
                latest_tag = self._get_latest_tag(repo)
                if latest_tag is not None:
                    log_to_console(
                        f"Checking out stable tag: {latest_tag}", "INFO"
                    )
                    repo.checkout(latest_tag)

            # Step 6: Update requirements
            req_path = self.comfyui_root / "requirements.txt"
            self._install_requirements(req_path)

            # Get new version info
            commit = repo.head.peel()
            new_version = str(commit.id)[:8]

            if updated:
                msg = f"ComfyUI updated to {new_version}"
                log_to_console(msg, "SUCCESS")
            else:
                msg = f"ComfyUI already up to date ({new_version})"
                log_to_console(msg, "SUCCESS")

            log_to_console("=" * 60, "SUCCESS")

            return {
                "success": True,
                "updated": updated,
                "version": new_version,
                "message": msg
            }

        except Exception as e:
            error_msg = f"ComfyUI update failed: {str(e)}"
            log_to_console(error_msg, "ERROR")
            return {"success": False, "updated": False, "message": error_msg}

    def _get_latest_tag(self, repo) -> Optional[str]:
        """Get the latest stable tag."""
        versions = []
        for ref_name in repo.references:
            try:
                prefix = "refs/tags/v"
                if ref_name.startswith(prefix):
                    version_str = ref_name[len(prefix):]
                    parts = list(map(int, version_str.split(".")))
                    score = parts[0] * 10000000000 + parts[1] * 100000 + parts[2]
                    versions.append((score, ref_name))
            except (ValueError, IndexError):
                continue
        versions.sort()
        if versions:
            return versions[-1][1]
        return None

    def scan_updatable_nodes(self) -> List[Dict]:
        """Scan custom_nodes for git-managed nodes."""
        nodes = []
        if not self.custom_nodes_dir.exists():
            return nodes

        for item in self.custom_nodes_dir.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith(('.', '_')):
                continue

            git_dir = item / ".git"
            has_git = git_dir.exists()

            node_info = {
                "name": item.name,
                "path": str(item),
                "has_git": has_git,
                "has_requirements": (item / "requirements.txt").exists(),
                "has_install_script": (item / "install.py").exists(),
            }

            if has_git:
                try:
                    pygit2 = self._import_pygit2()
                    repo = pygit2.Repository(str(item))
                    commit = repo.head.peel()
                    node_info["commit"] = str(commit.id)[:8]
                    node_info["branch"] = (
                        repo.head.shorthand
                        if not repo.head.is_detached else "detached"
                    )
                except Exception:
                    node_info["commit"] = "unknown"
                    node_info["branch"] = "unknown"

            nodes.append(node_info)

        return nodes

    def update_single_node(self, node_path: Path) -> Dict:
        """Update a single custom node."""
        node_name = node_path.name
        git_dir = node_path / ".git"

        if not git_dir.exists():
            return {
                "name": node_name,
                "success": False,
                "updated": False,
                "message": f"'{node_name}' has no .git - cannot update (installed via zip/copy)"
            }

        try:
            pygit2 = self._import_pygit2()
            repo = pygit2.Repository(str(node_path))

            # Stash
            self._stash_and_prepare(repo)

            # Detect branch and checkout
            branch_name = self._detect_default_branch(repo)
            if not repo.head.is_detached:
                branch_name = repo.head.shorthand
            else:
                self._checkout_branch(repo, branch_name)

            # Pull
            updated = self._pull(repo, branch=branch_name)

            # Run install.py if exists and updated
            if updated:
                install_script = node_path / "install.py"
                self._run_install_script(install_script)

                # Install requirements if exists
                req_file = node_path / "requirements.txt"
                self._install_requirements(req_file)

            commit = repo.head.peel()
            version = str(commit.id)[:8]

            if updated:
                msg = f"'{node_name}' updated to {version}"
            else:
                msg = f"'{node_name}' already up to date ({version})"

            return {
                "name": node_name,
                "success": True,
                "updated": updated,
                "version": version,
                "message": msg
            }

        except Exception as e:
            return {
                "name": node_name,
                "success": False,
                "updated": False,
                "message": f"'{node_name}' update failed: {str(e)}"
            }

    def update_all_nodes(self) -> Dict:
        """Update all custom nodes that have .git."""
        log_to_console("=" * 60, "INFO")
        log_to_console("Custom Nodes Update - Starting", "INFO")
        log_to_console("=" * 60, "INFO")

        results = []
        updated_count = 0
        skipped_count = 0
        failed_count = 0

        nodes = self.scan_updatable_nodes()

        for node_info in nodes:
            node_path = Path(node_info["path"])

            if not node_info["has_git"]:
                log_to_console(
                    f"Skipping '{node_info['name']}' (no .git)", "WARNING"
                )
                skipped_count += 1
                results.append({
                    "name": node_info["name"],
                    "success": True,
                    "updated": False,
                    "message": "Skipped - no .git folder"
                })
                continue

            log_to_console(f"Updating '{node_info['name']}'...", "INFO")
            result = self.update_single_node(node_path)
            results.append(result)

            if result["success"] and result["updated"]:
                updated_count += 1
                log_to_console(result["message"], "SUCCESS")
            elif result["success"]:
                log_to_console(result["message"], "INFO")
            else:
                failed_count += 1
                log_to_console(result["message"], "ERROR")

        summary = (
            f"Update complete: {updated_count} updated, "
            f"{skipped_count} skipped, {failed_count} failed "
            f"(out of {len(nodes)} nodes)"
        )
        log_to_console(summary, "SUCCESS")
        log_to_console("=" * 60, "SUCCESS")

        return {
            "success": failed_count == 0,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "total": len(nodes),
            "message": summary,
            "details": results
        }

    @staticmethod
    def restart_comfyui(delay: int = 2):
        """Restart ComfyUI server."""
        python_exe = sys.executable
        args = sys.argv.copy()

        log_to_console(f"Restarting ComfyUI in {delay}s...", "INFO")
        sys.stdout.flush()
        sys.stderr.flush()

        if delay > 0:
            time.sleep(delay)

        log_to_console("Restarting now...", "SUCCESS")

        try:
            os.execv(python_exe, [python_exe] + args)
        except Exception as e:
            log_to_console(f"os.execv failed: {e}, trying subprocess", "WARNING")
            subprocess.Popen([python_exe] + args, cwd=os.getcwd())
            sys.exit(0)
