#!/usr/bin/env python3
"""Auto-Fallback mechanism for Model-to-Hardware Alignment (MHA).

This module provides automatic fallback logic that switches to hardware-aligned models
(e.g., SDXL-Turbo) when VRAM margins are breached.
"""

import os
import sys
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from pathlib import Path
import threading
import time


@dataclass
class FallbackModelConfig:
    """Configuration for a fallback model."""
    model_name: str
    required_vram_gb: float
    required_memory_gb: float
    priority: int  # Lower is better (higher priority)
    
    def __post_init__(self):
        if self.required_vram_gb < 0:
            raise ValueError("VRAM requirement cannot be negative")
        if self.required_memory_gb < 0:
            raise ValueError("Memory requirement cannot be negative")


class FallbackModelRegistry:
    """Registry mapping heavy models to lighter hardware-aligned alternatives."""
    
    def __init__(self):
        self._registry: Dict[str, List[FallbackModelConfig]] = {}
        self._register_default_fallbacks()
    
    def _register_default_fallbacks(self):
        """Register default fallback mappings for common models."""
        # Heavy models -> lighter alternatives
        self.register_fallbacks("LLAMA-70B", [
            FallbackModelConfig("LLAMA-70B", 80.0, 64.0, 0),
            FallbackModelConfig("LLAMA-13B", 16.0, 16.0, 1),
            FallbackModelConfig("LLAMA-7B", 8.0, 8.0, 2),
        ])
        
        self.register_fallbacks("SDXL", [
            FallbackModelConfig("SDXL", 24.0, 16.0, 0),
            FallbackModelConfig("SDXL-Turbo", 12.0, 8.0, 1),
            FallbackModelConfig("SDXL-Light", 6.0, 4.0, 2),
        ])
        
        self.register_fallbacks("GPT-4", [
            FallbackModelConfig("GPT-4", 96.0, 80.0, 0),
            FallbackModelConfig("GPT-4-Turbo", 48.0, 40.0, 1),
            FallbackModelConfig("GPT-3.5", 24.0, 20.0, 2),
        ])
        
        self.register_fallbacks("StableDiffusion-XXL", [
            FallbackModelConfig("StableDiffusion-XXL", 48.0, 32.0, 0),
            FallbackModelConfig("SDXL-Turbo", 12.0, 8.0, 1),
            FallbackModelConfig("SDXL-Light", 6.0, 4.0, 2),
        ])
    
    def register_fallbacks(self, primary_model: str, fallbacks: List[FallbackModelConfig]):
        """Register fallback options for a primary model."""
        self._registry[primary_model] = fallbacks
    
    def get_fallbacks_for(self, model_name: str) -> Optional[List[FallbackModelConfig]]:
        """Get fallback options for a model."""
        return self._registry.get(model_name)
    
    def get_best_fallback(self, model_name: str, available_vram: float) -> Optional[FallbackModelConfig]:
        """Get the best available fallback for the given VRAM."""
        fallbacks = self.get_fallbacks_for(model_name)
        if not fallbacks:
            return None
        
        # Find first fallback that fits in available VRAM
        for fallback in fallbacks:
            if fallback.required_vram_gb <= available_vram:
                return fallback
        
        # If no fallback fits, return the lightest one (will likely fail but is best effort)
        return min(fallbacks, key=lambda f: f.required_vram_gb)


class VRAMMonitor:
    """Monitors VRAM usage and detects breaches."""
    
    def __init__(self, available_vram_gb: float, margin_gb: float = 1.0):
        self.available_vram_gb = available_vram_gb
        self.margin_gb = margin_gb
        self.current_usage_gb: float = 0.0
        self.breached: bool = False
        self._lock = threading.Lock()
    
    def check_margin(self, required_vram: float) -> bool:
        """Check if required VRAM breaches the margin."""
        with self._lock:
            available = self.available_vram_gb - self.margin_gb
            self.breached = required_vram > available
            return self.breached
    
    def get_available_vram(self) -> float:
        """Get available VRAM accounting for margin."""
        return self.available_vram_gb - self.margin_gb


class AutoFallbackAgent:
    """Agent with automatic fallback to hardware-aligned models."""
    
    def __init__(self, model_name: str, strict_mode: bool = True, 
                 vram_margin: float = 1.0, on_fallback: Optional[Callable[[str, str], None]] = None):
        """
        Initialize agent with auto-fallback capability.
        
        Args:
            model_name: The primary model name to load.
            strict_mode: If True, raise exception if no fallback available.
            vram_margin: Safety margin in GB to keep available.
            on_fallback: Callback function(model_name, reason) called when fallback occurs.
        """
        self.model_name = model_name
        self.strict_mode = strict_mode
        self.vram_margin = vram_margin
        self.on_fallback = on_fallback
        
        # Hardware detection
        self._detect_hardware()
        
        # Fallback registry
        self.registry = FallbackModelRegistry()
        self.vram_monitor = VRAMMonitor(self.available_vram_gb, vram_margin)
        
        # State tracking
        self.current_model: Optional[str] = None
        self.current_vram_gb: float = 0.0
        self.fallback_history: List[str] = []
        self._lock = threading.Lock()
        
        # Initialize with primary model or fallback immediately if needed
        self._initialize_model()
    
    def _detect_hardware(self):
        """Detect available hardware resources."""
        try:
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
                    # Estimate VRAM from model name
                    self._estimate_vram_from_model()
                else:
                    self._set_conservative_defaults()
            else:
                self._set_conservative_defaults()
        except Exception as e:
            self._set_conservative_defaults()
    
    def _estimate_vram_from_model(self):
        """Estimate VRAM based on GPU model name."""
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
            self._set_conservative_defaults()
    
    def _set_conservative_defaults(self):
        """Set conservative hardware defaults."""
        self.available_vram_gb = 8.0
        self.available_memory_gb = 16.0
        self.gpu_model = None
        self.driver_version = None
    
    def _initialize_model(self):
        """Initialize with primary model or fallback if VRAM breached."""
        # Check if primary model fits
        primary_config = self._get_model_config(self.model_name)
        
        if primary_config:
            self.current_model = self.model_name
            self.current_vram_gb = primary_config.required_vram_gb
            self._log_fallback(f"Loaded primary model: {self.model_name} ({primary_config.required_vram_gb:.1f}GB VRAM)")
        else:
            # No config found, try to find any fallback
            self._attempt_fallback("Primary model not found in registry")
    
    def _get_model_config(self, model_name: str) -> Optional[FallbackModelConfig]:
        """Get model config from registry or create synthetic one."""
        # Check registry first
        fallbacks = self.registry.get_fallbacks_for(model_name)
        if fallbacks:
            return fallbacks[0]  # Primary model is first
        
        # If not in registry, create synthetic config based on name heuristics
        return self._create_synthetic_config(model_name)
    
    def _create_synthetic_config(self, model_name: str) -> FallbackModelConfig:
        """Create synthetic config based on model name heuristics."""
        # Heuristic-based VRAM estimation
        model_lower = model_name.lower()
        if '70b' in model_lower or '70b' in model_lower:
            return FallbackModelConfig(model_name, 80.0, 64.0, 0)
        elif '13b' in model_lower or '13b' in model_lower:
            return FallbackModelConfig(model_name, 16.0, 16.0, 0)
        elif '7b' in model_lower or '7b' in model_lower:
            return FallbackModelConfig(model_name, 8.0, 8.0, 0)
        elif 'sdxl' in model_lower or 'sdxl' in model_lower:
            return FallbackModelConfig(model_name, 24.0, 16.0, 0)
        elif 'turbo' in model_lower:
            return FallbackModelConfig(model_name, 12.0, 8.0, 0)
        else:
            # Default to conservative
            return FallbackModelConfig(model_name, 8.0, 8.0, 0)
    
    def _attempt_fallback(self, reason: str):
        """Attempt to load a fallback model."""
        with self._lock:
            # Check if current model breaches VRAM margin
            current_config = self._get_model_config(self.model_name)
            if current_config:
                self.vram_monitor.check_margin(current_config.required_vram_gb)
            
            # Get best fallback
            best_fallback = self.registry.get_best_fallback(
                self.model_name, 
                self.vram_monitor.get_available_vram()
            )
            
            if best_fallback:
                self.current_model = best_fallback.model_name
                self.current_vram_gb = best_fallback.required_vram_gb
                self.fallback_history.append(self.model_name)
                self._log_fallback(
                    f"FALLOBACK: Switched from '{self.model_name}' to '{best_fallback.model_name}' "
                    f"(VRAM: {best_fallback.required_vram_gb:.1f}GB) - Reason: {reason}"
                )
                
                if self.on_fallback:
                    self.on_fallback(self.model_name, reason)
                
                return True
            
            # No fallback available
            if self.strict_mode:
                raise HardwareAlignmentError(
                    f"No fallback available for '{self.model_name}' with available VRAM: "
                    f"{self.vram_monitor.get_available_vram():.1f}GB"
                )
            else:
                self._log_fallback(f"No fallback available for '{self.model_name}' (strict_mode=False)")
            return False
    
    def _log_fallback(self, message: str):
        """Log fallback event."""
        print(f"[MHA-FALLOBACK] {message}")
        if self.on_fallback:
            self.on_fallback(self.model_name, message)
    
    def get_current_model(self) -> str:
        """Get currently loaded model name."""
        return self.current_model or self.model_name
    
    def get_vram_status(self) -> Dict[str, Any]:
        """Get current VRAM status."""
        return {
            'available_vram_gb': self.available_vram_gb,
            'current_model': self.current_model or self.model_name,
            'current_vram_gb': self.current_vram_gb,
            'margin_gb': self.vram_margin,
            'available_after_margin': self.vram_monitor.get_available_vram(),
            'breached': self.vram_monitor.breached,
            'fallback_history': self.fallback_history
        }


class HardwareAlignmentError(Exception):
    """Raised when hardware cannot support the requested model and no fallback is available."""
    pass


# Example usage and testing
if __name__ == "__main__":
    print("Testing Auto-Fallback mechanism...")
    
    # Test 1: Primary model fits
    print("\n=== Test 1: Primary model fits ===")
    try:
        agent = AutoFallbackAgent(
            model_name="LLAMA-70B",
            strict_mode=False,
            vram_margin=1.0
        )
        print(f"Current model: {agent.get_current_model()}")
        print(f"VRAM Status: {agent.get_vram_status()}")
    except HardwareAlignmentError as e:
        print(f"Hardware alignment failed: {e}")
    
    # Test 2: Force VRAM breach and fallback
    print("\n=== Test 2: Force VRAM breach ===")
    try:
        # Simulate limited VRAM by creating agent with small available VRAM
        agent = AutoFallbackAgent(
            model_name="LLAMA-70B",
            strict_mode=False,
            vram_margin=1.0
        )
        # Manually set available VRAM to low value to force fallback
        agent.available_vram_gb = 10.0  # Force fallback to lighter model
        agent._initialize_model()
        print(f"Current model: {agent.get_current_model()}")
        print(f"VRAM Status: {agent.get_vram_status()}")
    except HardwareAlignmentError as e:
        print(f"Hardware alignment failed: {e}")
