#!/usr/bin/env python3
"""Auto-Fallback mechanism for Model-to-Hardware Alignment (MHA).

This module implements automatic fallback logic that switches to hardware-aligned
models (e.g., SDXL-Turbo) when VRAM margins are breached, ensuring continuous
operation under hardware constraints.
"""

import os
import sys
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from pathlib import Path
import warnings


@dataclass
class FallbackModelVariant:
    """Represents a lighter model variant for fallback scenarios."""
    
    variant_name: str
    required_vram_gb: float
    required_memory_gb: float
    required_compute_flops: Optional[float] = None  # TFLOPS
    min_driver_version: Optional[str] = None
    priority: int = 0  # Lower number = higher priority (0 is preferred)
    
    def __post_init__(self):
        if self.required_vram_gb < 0:
            raise ValueError("VRAM requirement cannot be negative")
        if self.required_memory_gb < 0:
            raise ValueError("Memory requirement cannot be negative")


class VRAMMonitor:
    """Monitors VRAM usage and detects breaches against margins."""
    
    def __init__(self, available_vram_gb: float, margin_gb: float = 0.5):
        """
        Initialize VRAM monitor.
        
        Args:
            available_vram_gb: Currently available VRAM in GB
            margin_gb: Safety margin in GB (default 0.5GB)
        """
        self.available_vram_gb = available_vram_gb
        self.margin_gb = margin_gb
        self.current_usage_gb: Optional[float] = None
        self.breach_detected: bool = False
        
    def check_margin(self, required_vram_gb: float) -> bool:
        """
        Check if required VRAM breaches the available margin.
        
        Returns:
            True if margin is breached (required > available - margin)
        """
        available_with_margin = self.available_vram_gb - self.margin_gb
        return required_vram_gb > available_with_margin
    
    def get_effective_available_vram(self) -> float:
        """
        Get effective available VRAM accounting for safety margin.
        """
        return self.available_vram_gb - self.margin_gb


class AutoFallbackManager:
    """
    Manages automatic fallback to lighter model variants when VRAM margins are breached.
    
    This class implements the core logic for hardware-aligned model switching,
    ensuring continuous operation under hardware constraints.
    """
    
    def __init__(self, available_vram_gb: float, margin_gb: float = 0.5):
        """
        Initialize the fallback manager.
        
        Args:
            available_vram_gb: Currently available VRAM in GB
            margin_gb: Safety margin in GB (default 0.5GB)
        """
        self.vram_monitor = VRAMMonitor(available_vram_gb, margin_gb)
        self.fallback_stack: List[FallbackModelVariant] = []
        self.current_model: Optional[FallbackModelVariant] = None
        self.fallback_callback: Optional[Callable[[FallbackModelVariant], None]] = None
        self.last_breach_reason: Optional[str] = None
        
    def register_fallback_variant(self, variant: FallbackModelVariant):
        """
        Register a fallback model variant.
        
        Args:
            variant: The model variant to register
        """
        self.fallback_stack.append(variant)
        # Sort by priority (lower number = higher priority)
        self.fallback_stack.sort(key=lambda v: v.priority)
        
    def set_fallback_callback(self, callback: Callable[[FallbackModelVariant], None]):
        """
        Set callback to be invoked when fallback occurs.
        
        Args:
            callback: Function to call when fallback happens, receives the variant
        """
        self.fallback_callback = callback
        
    def check_and_fallback(self, required_vram_gb: float) -> FallbackModelVariant:
        """
        Check if current VRAM requirements breach the margin and fallback if needed.
        
        Args:
            required_vram_gb: Required VRAM for the current model
            
        Returns:
            The model variant to use (either current or fallback)
        """
        # Check if margin is breached
        if self.vram_monitor.check_margin(required_vram_gb):
            self._trigger_fallback(required_vram_gb)
            return self.current_model
        
        # No breach, use current model or return None if not set
        return self.current_model if self.current_model else None
    
    def _trigger_fallback(self, required_vram_gb: float):
        """
        Trigger fallback to a lighter model variant.
        """
        # Find first variant that fits within margin
        for variant in self.fallback_stack:
            if not self.vram_monitor.check_margin(variant.required_vram_gb):
                # Found a variant that fits
                self.current_model = variant
                self.last_breach_reason = (
                    f"VRAM margin breached: required {required_vram_gb:.1f}GB > "
                    f"effective available {self.vram_monitor.get_effective_available_vram():.1f}GB"
                )
                
                if self.fallback_callback:
                    self.fallback_callback(variant)
                
                warnings.warn(
                    f"Auto-Fallback triggered: Switching to {variant.variant_name} "
                    f"(Reason: {self.last_breach_reason})"
                )
                return
        
        # No suitable variant found
        raise HardwareAlignmentError(
            f"No suitable fallback variant found for VRAM requirement {required_vram_gb:.1f}GB. "
            f"Available VRAM: {self.vram_monitor.available_vram_gb:.1f}GB, "
            f"Margin: {self.vram_monitor.margin_gb:.1f}GB"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the fallback manager.
        """
        return {
            'available_vram_gb': self.vram_monitor.available_vram_gb,
            'margin_gb': self.vram_monitor.margin_gb,
            'effective_available_vram': self.vram_monitor.get_effective_available_vram(),
            'current_model': self.current_model.variant_name if self.current_model else None,
            'registered_variants': [
                v.variant_name for v in self.fallback_stack
            ],
            'last_breach_reason': self.last_breach_reason
        }


class HardwareAlignmentError(Exception):
    """Raised when hardware cannot support the requested model and no fallback is available."""
    pass


# Example usage and testing
if __name__ == "__main__":
    print("Testing Auto-Fallback mechanism...")
    
    # Initialize manager with 8GB VRAM available, 0.5GB margin
    manager = AutoFallbackManager(available_vram_gb=8.0, margin_gb=0.5)
    
    # Register fallback variants (lighter models)
    # SDXL-Turbo is a lighter variant requiring less VRAM
    manager.register_fallback_variant(FallbackModelVariant(
        variant_name="SDXL-Turbo",
        required_vram_gb=6.0,
        required_memory_gb=8.0,
        priority=1
    ))
    
    manager.register_fallback_variant(FallbackModelVariant(
        variant_name="SDXL-Light",
        required_vram_gb=4.0,
        required_memory_gb=6.0,
        priority=2
    ))
    
    # Register callback to handle fallback
    def on_fallback(variant: FallbackModelVariant):
        print(f"[FALLBACK] Switching to {variant.variant_name} with "
              f"VRAM requirement: {variant.required_vram_gb:.1f}GB")
    
    manager.set_fallback_callback(on_fallback)
    
    # Test: Try to use a model requiring 10GB VRAM (should trigger fallback)
    print("\nAttempting to load model requiring 10GB VRAM...")
    try:
        result = manager.check_and_fallback(required_vram_gb=10.0)
        print(f"Active model: {result.variant_name if result else 'None'}")
    except HardwareAlignmentError as e:
        print(f"Error: {e}")
    
    # Test: Try with 5GB requirement (should not trigger fallback)
    print("\nAttempting to load model requiring 5GB VRAM...")
    result = manager.check_and_fallback(required_vram_gb=5.0)
    print(f"Active model: {result.variant_name if result else 'None'}")
    
    # Show status
    print(f"\nManager Status: {manager.get_status()}")


# Integration with existing Agent system
class MHAEnabledAgent:
    """
    Extended Agent with auto-fallback capability.
    """
    
    def __init__(self, model_requirements, strict_mode: bool = True, 
                 available_vram_gb: float = 8.0, margin_gb: float = 0.5):
        """
        Initialize agent with MHA and auto-fallback.
        """
        self.model_requirements = model_requirements
        self.strict_mode = strict_mode
        self.fallback_manager = AutoFallbackManager(available_vram_gb, margin_gb)
        self.current_model_variant: Optional[FallbackModelVariant] = None
        
        # Register hardware-aligned fallback variants
        self._register_default_variants()
        
    def _register_default_variants(self):
        """
        Register default hardware-aligned model variants.
        """
        # SDXL-Turbo: Lighter variant for VRAM-constrained environments
        self.fallback_manager.register_fallback_variant(FallbackModelVariant(
            variant_name="SDXL-Turbo",
            required_vram_gb=6.0,
            required_memory_gb=8.0,
            priority=1
        ))
        
        # SDXL-Light: Even lighter variant
        self.fallback_manager.register_fallback_variant(FallbackModelVariant(
            variant_name="SDXL-Light",
            required_vram_gb=4.0,
            required_memory_gb=6.0,
            priority=2
        ))
        
    def load_model(self, required_vram_gb: float):
        """
        Load model with automatic fallback if VRAM margin is breached.
        """
        return self.fallback_manager.check_and_fallback(required_vram_gb)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status including fallback state.
        """
        return self.fallback_manager.get_status()


if __name__ == "__main__":
    # Test integration
    print("\n--- Testing MHA-Enabled Agent ---")
    agent = MHAEnabledAgent(
        model_requirements=None,
        available_vram_gb=8.0,
        margin_gb=0.5
    )
    
    # Try to load heavy model (10GB)
    print("Loading heavy model (10GB VRAM)...")
    variant = agent.load_model(required_vram_gb=10.0)
    print(f"Active variant: {variant.variant_name}")
    
    # Try to load light model (5GB)
    print("\nLoading light model (5GB VRAM)...")
    variant = agent.load_model(required_vram_gb=5.0)
    print(f"Active variant: {variant.variant_name if variant else 'None'}")
    
    print(f"\nAgent Status: {agent.get_status()}")
