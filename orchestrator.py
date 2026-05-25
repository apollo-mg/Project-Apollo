#!/usr/bin/env python3
"""
Sovereign Entity Architecture - Centralized Orchestration System

This script manages model profiles, ports, and environment variables through a centralized
profiles.json schema. It deprecates the legacy start_*.sh scripts by providing a
unified interface for launching AI services.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional


class ServiceOrchestrator:
    """
    Centralized orchestration system for managing AI model services.
    
    Reads configuration from profiles.json and manages:
    - Model profiles (architect, turbo, whisper, bonsai)
    - Port allocation and conflict resolution
    - Environment variable injection (HSA_OVERRIDE_GFX_VERSION, etc.)
    - Process lifecycle management
    """
    
    def __init__(self, profiles_path: Optional[str] = None):
        """
        Initialize the orchestrator with the profiles configuration.
        
        Args:
            profiles_path: Path to profiles.json. Defaults to ./profiles.json
        """
        self.profiles_path = Path(profiles_path) if profiles_path else Path("./profiles.json")
        self.profiles: Dict[str, Any] = {}
        self._load_profiles()
        
    def _load_profiles(self) -> None:
        """
        Load and parse the profiles.json configuration file.
        """
        if not self.profiles_path.exists():
            raise FileNotFoundError(f"Profiles file not found: {self.profiles_path}")
        
        with open(self.profiles_path, "r") as f:
            self.profiles = json.load(f)
    
    def get_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Retrieve a specific profile configuration.
        
        Args:
            profile_name: Name of the profile (e.g., 'architect', 'turbo')
            
        Returns:
            Dictionary containing profile configuration
        """
        if profile_name not in self.profiles.get("profiles", {}):
            raise ValueError(f"Unknown profile: {profile_name}")
        return self.profiles["profiles"][profile_name]
    
    def list_profiles(self) -> None:
        """
        List all available profiles with their configurations.
        """
        print("Available Profiles:")
        print("-" * 60)
        for name, config in self.profiles["profiles"].items():
            print(f"  {name}:")
            print(f"    Port: {config.get('port', 'N/A')}")
            print(f"    Model: {config.get('model', 'N/A')}")
            print(f"    Description: {config.get('description', 'N/A')}")
            print()
    
    def launch(self, profile_name: str, foreground: bool = False) -> int:
        """
        Launch a service based on the specified profile.
        
        Args:
            profile_name: Name of the profile to launch
            foreground: If True, run in foreground (wait for process). If False, background.
            
        Returns:
            Exit code of the launched process
        """
        profile = self.get_profile(profile_name)
        
        # Build environment variables
        env = os.environ.copy()
        env.update(profile.get("env", {}))
        
        # Build command
        server_bin = profile.get("server", "")
        if not server_bin:
            print(f"Error: No server binary specified for {profile_name}")
            return 1
        
        # Construct command based on profile type
        cmd = [server_bin]
        
        # Add model path
        model_path = profile.get("model", "")
        if model_path:
            cmd.extend(["-m", model_path])
        
        # Add port
        port = profile.get("port")
        if port:
            cmd.extend(["--port", str(port)])
        
        # Add host
        host = profile.get("args", {}).get("host")
        if host:
            cmd.extend(["--host", host])
        
        # Add other arguments
        args = profile.get("args", {})
        for key, value in args.items():
            if value is not None:
                if isinstance(value, bool):
                    cmd.append(str(value).lower())
                else:
                    cmd.extend([key, str(value)])
        
        print(f"[*] Launching {profile_name}...")
        print(f"[*] Port: {port}")
        print(f"[*] Model: {model_path}")
        if profile.get("env"):
            print(f"[*] Environment: {profile['env']}")
        print(f"[*] Command: {' '.join(cmd)}")
        
        # Execute
        try:
            if foreground:
                result = subprocess.run(cmd, env=env)
                return result.returncode
            else:
                # Background process
                process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"[+] Process started with PID: {process.pid}")
                return 0
        except Exception as e:
            print(f"Error launching {profile_name}: {e}")
            return 1
    
    def stop(self, profile_name: str) -> int:
        """
        Stop a service by name or port.
        
        Args:
            profile_name: Name of the profile or port number
            
        Returns:
            Exit code
        """
        # Find process by port or name
        port = profile_name
        if not profile_name.isdigit():
            # It's a name, get the port
            try:
                port = self.get_profile(profile_name)["port"]
            except:
                print(f"Unknown profile: {profile_name}")
                return 1
        
        # Kill process on port
        cmd = ["fuser", "-k", f"{port}/tcp"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[+] Stopped service on port {port}")
            return 0
        else:
            print(f"[-] Could not stop service on port {port}")
            return 1
    
    def status(self, profile_name: str) -> int:
        """
        Check status of a service.
        
        Args:
            profile_name: Name of the profile or port number
            
        Returns:
            Exit code
        """
        port = profile_name
        if not profile_name.isdigit():
            try:
                port = self.get_profile(profile_name)["port"]
            except:
                print(f"Unknown profile: {profile_name}")
                return 1
        
        # Check if port is in use
        cmd = ["fuser", "-v", f"{port}/tcp"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[+] Service running on port {port}")
            return 0
        else:
            print(f"[-] Service not running on port {port}")
            return 1


def main():
    """
    Main entry point for the orchestrator CLI.
    """
    orchestrator = ServiceOrchestrator()
    
    if len(sys.argv) < 2:
        print("Usage: orchestrator.py <command> <profile>")
        print("Commands: list, launch, stop, status")
        print("Profiles: architect, turbo, whisper, bonsai")
        sys.exit(1)
    
    command = sys.argv[1]
    profile = sys.argv[2] if len(sys.argv) > 2 else None
    
    if command == "list":
        orchestrator.list_profiles()
    elif command == "launch":
        if not profile:
            print("Error: Profile name required for launch")
            sys.exit(1)
        orchestrator.launch(profile, foreground=True)
    elif command == "stop":
        if not profile:
            print("Error: Profile name or port required for stop")
            sys.exit(1)
        orchestrator.stop(profile)
    elif command == "status":
        if not profile:
            print("Error: Profile name or port required for status")
            sys.exit(1)
        orchestrator.status(profile)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
