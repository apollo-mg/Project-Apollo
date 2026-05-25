#!/usr/bin/env python3
"""Agent initialization with Model-to-Hardware Alignment (MHA) logic."""

import os
import sys
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelResourceRequirements:
    """Defines the hardware requirements for a specific model."""
    
    model_name: str
    required_vram_gb: float
    required_memory_gb: float
    required_compute_flops: Optional[float] = None  # TFLOPS
    min_driver_version: Optional[str] = None
    
    def __post_init__(self):
        if self.required_vram_gb < 0:
            raise ValueError("VRAM requirement cannot be negative")
        if self.required_memory_gb < 0:
            raise ValueError("Memory requirement cannot be negative")


class HardwareResourceChecker:
    """Checks available hardware resources against model requirements."""
    
    def __init__(self):
        self.available_vram_gb: Optional[float] = None
        self.available_memory_gb: Optional[float] = None
        self.gpu_model: Optional[str] = None
        self.driver_version: Optional[str] = None
        self._detect_hardware()
    
    def _detect_hardware(self):
        """Detect available hardware resources."""
        try:
            # Attempt to detect GPU via nvidia-smi or nvidia-smi equivalent
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu', 'name,driverVersion', '--format=csv'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    self.gpu_model = lines[0].strip()
                    self.driver_version = lines[1].strip()
                    # Estimate VRAM from GPU model (simplified heuristic)
                    self._estimate_vram_from_model()
            
            # Fallback: Check via environment variables or OS-specific methods
            if self.available_vram_gb is None:
                # Check if VRAM is specified via environment
                vram_env = os.environ.get('APOLLO_VRAM_GB')
                if vram_env:
                    self.available_vram_gb = float(vram_env)
                else:
                    # Default to a conservative estimate if undetected
                    self.available_vram_gb = 8.0  # Conservative default
                    
        except Exception as e:
            # Hardware detection failed, use conservative defaults
            self.available_vram_gb = 8.0
            self.available_memory_gb = 16.0
    
    def _estimate_vram_from_model(self):
        """Estimate VRAM based on GPU model name."""
        # Simplified heuristic for common GPU models
        model_lower = self.gpu_model.lower() if self.gpu_model else ''
        if 'rtx 3090' in model_lower or 'a100' in model_lower:
            self.available_vram_gb = 80.0
        elif 'rtx 3080' in model_lower:
            self.available_vram_gb = 10.0
        elif 'rtx 4090' in model_lower:
            self.available_vram_gb = 16.0
        elif 'a10' in model_lower:
            self.available_vram_gb = 40.0
        elif 'v100' in model_lower:
            self.available_vram_gb = 32.0
        else:
            self.available_vram_gb = 8.0  # Conservative default
    
    def check_alignment(self, requirements: ModelResourceRequirements) -> Dict[str, Any]:
        """
        Check if hardware can support the model requirements.
        
        Returns:
            Dict with 'aligned' (bool) and 'details' (dict) explaining the check.
        """
        details = {
            'model_name': requirements.model_name,
            'required_vram_gb': requirements.required_vram_gb,
            'available_vram_gb': self.available_vram_gb,
            'required_memory_gb': requirements.required_memory_gb,
            'available_memory_gb': self.available_memory_gb,
            'gpu_model': self.gpu_model,
            'driver_version': self.driver_version,
            'aligned': False,
            'warnings': []
        }
        
        # Check VRAM
        if self.available_vram_gb is None:
            details['warnings'].append('VRAM not detected, assuming sufficient')
            details['aligned'] = True  # Assume aligned if undetected
        elif self.available_vram_gb < requirements.required_vram_gb:
            details['warnings'].append(
                f"Insufficient VRAM: {self.available_vram_gb:.1f}GB available, "
                f"{requirements.required_vram_gb:.1f}GB required for "
                f"{requirements.model_name}"
            )
            details['aligned'] = False
        else:
            details['aligned'] = True
        
        # Check system memory
        if self.available_memory_gb and self.available_memory_gb < requirements.required_memory_gb:
            details['warnings'].append(
                f"Insufficient system memory: {self.available_memory_gb:.1f}GB available, "
                f"{requirements.required_memory_gb:.1f}GB required"
            )
            details['aligned'] = False
        
        # Check driver version if specified
        if requirements.min_driver_version and self.driver_version:
            if self._compare_versions(self.driver_version, requirements.min_driver_version) < 0:
                details['warnings'].append(
                    f"Driver version {self.driver_version} is below minimum "
                    f"{requirements.min_driver_version}"
                )
                details['aligned'] = False
        
        return {'aligned': details['aligned'], 'details': details}
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1."""
        try:
            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]
            if v1_parts < v2_parts:
                return -1
            elif v1_parts > v2_parts:
                return 1
            return 0
        except:
            return 0  # Assume equal if parsing fails


class Agent:
    """Agent with MHA (Model-to-Hardware Alignment) initialization."""
    
    def __init__(self, model_requirements: ModelResourceRequirements, 
                 strict_mode: bool = True):
        """
        Initialize agent with hardware alignment checks.
        
        Args:
            model_requirements: The resource requirements for the model to be loaded.
            strict_mode: If True, raise exception if hardware cannot support model.
                       If False, log warning but proceed.
        """
        self.model_requirements = model_requirements
        self.strict_mode = strict_mode
        self.hardware_checker = HardwareResourceChecker()
        self._mha_result: Optional[Dict[str, Any]] = None
        
        # Perform MHA check during initialization
        self._perform_mha_check()
    
    def _perform_mha_check(self):
        """Perform Model-to-Hardware Alignment check."""
        result = self.hardware_checker.check_alignment(self.model_requirements)
        self._mha_result = result
        
        if not result['aligned'] and self.strict_mode:
            raise HardwareAlignmentError(
                f"MHA check failed for {self.model_requirements.model_name}: "
                f"{result['details']['warnings']}"
            )
        elif not result['aligned'] and not self.strict_mode:
            import warnings
            warnings.warn(
                f"MHA check failed for {self.model_requirements.model_name}: "
                f"{result['details']['warnings']}"
            )
    
    def get_mha_status(self) -> Dict[str, Any]:
        """Return the MHA check result."""
        return self._mha_result
    
    def can_load_model(self) -> bool:
        """Check if current hardware can load the model."""
        return self._mha_result['aligned'] if self._mha_result else False


class HardwareAlignmentError(Exception):
    """Raised when hardware cannot support the requested model."""
    pass


# Example usage and testing
if __name__ == "__main__":
    # Test the MHA logic
    print("Testing MHA (Model-to-Hardware Alignment) logic...")
    
    # Create requirements for a large model
    requirements = ModelResourceRequirements(
        model_name="LLAMA-70B",
        required_vram_gb=80.0,
        required_memory_gb=64.0,
        required_compute_flops=1000.0,
        min_driver_version="550.00"
    )
    
    # Initialize agent with MHA check
    try:
        agent = Agent(model_requirements=requirements, strict_mode=False)
        status = agent.get_mha_status()
        print(f"MHA Status: {status}")
        print(f"Can load model: {agent.can_load_model()}")
    except HardwareAlignmentError as e:
        print(f"Hardware alignment failed: {e}")
