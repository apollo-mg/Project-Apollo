#!/usr/bin/env python3
"""
Driver-Kernel Alignment Check for ROCm/HIP

This script validates that the ROCm/HIP versions are properly aligned with the
kernel driver to prevent 'Ghost' configurations where hardware-software
compatibility is compromised.

Exit Codes:
    0: Success - versions aligned
    1: Ghost detected - versions not aligned
    2: Detection failed
"""

import subprocess
import sys
import os
import re
from typing import Optional, Tuple


class DriverKernelAlignmentCheck:
    """
    Validates alignment between ROCm/HIP versions and kernel drivers.
    """
    
    def __init__(self):
        self.rocm_version: Optional[str] = None
        self.hip_version: Optional[str] = None
        self.kernel_driver_version: Optional[str] = None
        self.alignment_status: str = "UNKNOWN"
        self.ghost_detected: bool = False
        
    def detect_rocm_version(self) -> Optional[str]:
        """
        Detect ROCm version from system.
        """
        try:
            # Method 1: Check via rocSmi
            result = subprocess.run(
                ['rocSmi', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Parse version from output
                match = re.search(r'ROCm\s+(\d+\.\d+\.\d+)', result.stdout)
                if match:
                    return match.group(1)
            
            # Method 2: Check via hipcc --version
            result = subprocess.run(
                ['hipcc', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                match = re.search(r'hipcc\s+(\d+\.\d+\.\d+)', result.stdout)
                if match:
                    return match.group(1)
            
            # Method 3: Check ROCm installation path
            rocm_path = os.environ.get('ROCM_PATH', '/opt/rocm')
            if os.path.exists(rocm_path):
                version_file = os.path.join(rocm_path, 'version.txt')
                if os.path.exists(version_file):
                    with open(version_file, 'r') as f:
                        return f.read().strip()
                        
        except (subprocess.SubprocessError, FileNotFoundError, TimeoutError):
            pass
            
        return None
    
    def detect_kernel_driver_version(self) -> Optional[str]:
        """
        Detect kernel driver version for GPU devices.
        """
        try:
            # Check via lspci for GPU devices
            result = subprocess.run(
                ['lspci', '-vvv', '-n'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Look for kernel driver version in output
                match = re.search(r'Kernel\s+Driver\s+Version\s+:\s+(\d+\.\d+\.\d+)', result.stdout)
                if match:
                    return match.group(1)
            
            # Alternative: Check via modinfo
            result = subprocess.run(
                ['modinfo', 'amdgpu'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                match = re.search(r'version\s+:\s+(\d+\.\d+\.\d+)', result.stdout)
                if match:
                    return match.group(1)
                    
        except (subprocess.SubprocessError, FileNotFoundError, TimeoutError):
            pass
            
        return None
    
    def detect_ghost_configuration(self) -> bool:
        """
        Detect if there is a 'Ghost' configuration where ROCm/HIP
        versions don't match the kernel driver.
        """
        rocm = self.rocm_version
        kernel = self.kernel_driver_version
        
        if not rocm or not kernel:
            return False
            
        # Check if versions are compatible
        # Ghost configuration: versions don't align
        if rocm != kernel:
            return True
            
        return False
    
    def run_check(self) -> int:
        """
        Run the alignment check.
        Returns:
            0: Success - versions aligned
            1: Ghost detected - versions not aligned
            2: Detection failed
        """
        # Detect versions
        self.rocm_version = self.detect_rocm_version()
        self.kernel_driver_version = self.detect_kernel_driver_version()
        
        # Check for ghost configuration
        self.ghost_detected = self.detect_ghost_configuration()
        
        # Set status
        if self.ghost_detected:
            self.alignment_status = "GHOST_DETECTED"
            print(f"ERROR: Ghost configuration detected!")
            print(f"  ROCm/HIP Version: {self.rocm_version}")
            print(f"  Kernel Driver Version: {self.kernel_driver_version}")
            print(f"  Status: MISMATCH - Hardware-Software compatibility compromised")
            return 1
            
        if self.rocm_version and self.kernel_driver_version:
            self.alignment_status = "ALIGNED"
            print(f"SUCCESS: Driver-Kernel Alignment verified")
            print(f"  ROCm/HIP Version: {self.rocm_version}")
            print(f"  Kernel Driver Version: {self.kernel_driver_version}")
            print(f"  Status: ALIGNED - Hardware-Software compatibility verified")
            return 0
            
        self.alignment_status = "DETECTION_FAILED"
        print(f"WARNING: Could not detect versions")
        print(f"  ROCm/HIP Version: {self.rocm_version}")
        print(f"  Kernel Driver Version: {self.kernel_driver_version}")
        return 2


def main():
    checker = DriverKernelAlignmentCheck()
    exit_code = checker.run_check()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
