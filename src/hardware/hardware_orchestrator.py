"""Hardware Orchestrator for Unified Physical Device Management.

This module provides a unified API for hardware-level operations including audio gain,
camera exposure, and other physical device controls. It abstracts hardware-level
operations behind a consistent interface that can be called from the middleware layer.

Phase 1.3: Hardware-Level Orchestration
"""

import os
import sys
from typing import Callable, Optional, Any, Dict, Union
from dataclasses import dataclass
from contextlib import contextmanager
import threading

# Import existing hardware abstraction components
from .kernel_synchronization import (
    HIPKernelSynchronizationBarrier,
    HIPKernelBarrierContext,
    HIP_SUCCESS,
    HIP_DEVICE_NOT_FOUND,
    HIP_NOT_INITIALIZED
)


@dataclass
class DeviceState:
    """Represents the state of a hardware device."""
    device_id: int
    device_type: str  # 'audio', 'camera', 'sensor', etc.
    status: str  # 'active', 'inactive', 'error'
    current_params: Dict[str, Any]
    error_code: Optional[int] = None


class HardwareOrchestrator:
    """
    Unified hardware orchestration layer that abstracts physical device operations
    behind a consistent interface.
    
    This class provides:
    - Device initialization and resource management
    - Unified API for physical adjustments (audio gain, camera exposure, etc.)
    - Thread-safe hardware operations with HIP synchronization barriers
    - Clean interface for cognitive tiers above
    """
    
    def __init__(
        self,
        device_id: int = 0,
        strict_mode: bool = True,
        auto_init: bool = True
    ):
        """
        Initialize the hardware orchestrator.
        
        Args:
            device_id: Primary HIP device ID (default: 0)
            strict_mode: If True, raise exceptions on hardware errors
            auto_init: If True, automatically initialize hardware resources
        """
        self.device_id = device_id
        self.strict_mode = strict_mode
        
        # HIP synchronization barrier for hardware operations
        self._hip_barrier = HIPKernelSynchronizationBarrier(device_id, strict_mode)
        
        # Resource management
        self._devices: Dict[str, Any] = {}  # device_type -> device_handle
        self._device_states: Dict[str, DeviceState] = {}
        self._resource_lock = threading.RLock()
        
        # Hardware abstraction layer
        self._audio_device = None
        self._camera_device = None
        self._sensor_devices: Dict[str, Any] = {}
        
        # Initialization state
        self._initialized = False
        self._init_error = None
        
        if auto_init:
            self._initialize_hardware()
    
    def _initialize_hardware(self):
        """Initialize hardware resources with HIP synchronization."""
        try:
            # Use HIP barrier context for thread-safe initialization
            with HIPKernelBarrierContext(self.device_id, self.strict_mode) as barrier:
                # Initialize audio subsystem
                self._audio_device = self._create_audio_device()
                
                # Initialize camera subsystem
                self._camera_device = self._create_camera_device()
                
                # Initialize sensor array
                self._sensor_devices = self._create_sensor_array()
                
                # Register devices in resource manager
                self._devices['audio'] = self._audio_device
                self._devices['camera'] = self._camera_device
                self._devices['sensors'] = self._sensor_devices
                
                self._initialized = True
                
        except Exception as e:
            self._init_error = e
            if self.strict_mode:
                raise RuntimeError(f"Hardware initialization failed: {e}")
            else:
                print(f"[WARNING] Hardware initialization failed: {e}", file=sys.stderr)
    
    def _create_audio_device(self):
        """Create audio device abstraction."""
        # Abstract audio device - in real implementation this would bind to
        # physical audio hardware (e.g., ALSA, JACK, or proprietary drivers)
        return {
            'type': 'audio',
            'gain': 0.0,  # -inf to +inf dB
            'sample_rate': 48000,
            'channels': 2,
            'buffer_size': 2048
        }
    
    def _create_camera_device(self):
        """Create camera device abstraction."""
        return {
            'type': 'camera',
            'exposure': 1.0,  # Auto-exposure default
            'iso': 400,
            'white_balance': 'auto',
            'resolution': (1920, 1080),
            'fps': 30
        }
    
    def _create_sensor_array(self):
        """Create sensor array abstraction."""
        return {
            'imu': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'gyro': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'magnetometer': {'x': 0.0, 'y': 0.0, 'z': 0.0}
        }
    
    def get_device_state(self, device_type: str) -> DeviceState:
        """
        Get the current state of a hardware device.
        
        Args:
            device_type: Type of device ('audio', 'camera', 'sensors')
            
        Returns:
            DeviceState: Current state of the device
        """
        with self._resource_lock:
            if device_type not in self._devices:
                raise RuntimeError(f"Device '{device_type}' not initialized")
            
            # Return current state snapshot
            return self._device_states.get(device_type, DeviceState(
                device_id=self.device_id,
                device_type=device_type,
                status='unknown',
                current_params={}
            ))
    
    def set_audio_gain(self, gain_db: float) -> bool:
        """
        Set audio gain level for the audio subsystem.
        
        Args:
            gain_db: Gain level in decibels (-inf to +inf)
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self._resource_lock:
            try:
                # Use HIP barrier for thread-safe hardware access
                with HIPKernelBarrierContext(self.device_id, self.strict_mode) as barrier:
                    # Simulate physical audio hardware adjustment
                    self._audio_device['gain'] = gain_db
                    
                    # Update device state
                    self._device_states['audio'] = DeviceState(
                        device_id=self.device_id,
                        device_type='audio',
                        status='active',
                        current_params={'gain_db': gain_db}
                    )
                    return True
                    
            except Exception as e:
                if self.strict_mode:
                    raise RuntimeError(f"Failed to set audio gain: {e}")
                return False
    
    def set_camera_exposure(self, exposure_value: float, iso: int = None) -> bool:
        """
        Set camera exposure and ISO settings.
        
        Args:
            exposure_value: Exposure value (EV) or shutter speed
            iso: ISO sensitivity (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self._resource_lock:
            try:
                with HIPKernelBarrierContext(self.device_id, self.strict_mode) as barrier:
                    # Simulate physical camera hardware adjustment
                    self._camera_device['exposure'] = exposure_value
                    if iso is not None:
                        self._camera_device['iso'] = iso
                    
                    # Update device state
                    self._device_states['camera'] = DeviceState(
                        device_id=self.device_id,
                        device_type='camera',
                        status='active',
                        current_params={'exposure': exposure_value, 'iso': iso}
                    )
                    return True
                    
            except Exception as e:
                if self.strict_mode:
                    raise RuntimeError(f"Failed to set camera exposure: {e}")
                return False
    
    def adjust_physical_parameter(
        self,
        device_type: str,
        param_name: str,
        value: Any,
        tolerance: float = 0.0
    ) -> bool:
        """
        Generic method to adjust any physical hardware parameter.
        
        Args:
            device_type: Type of device ('audio', 'camera', 'sensors')
            param_name: Name of the parameter to adjust
            value: Value to set
            tolerance: Acceptable tolerance for the adjustment
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self._resource_lock:
            try:
                with HIPKernelBarrierContext(self.device_id, self.strict_mode) as barrier:
                    # Map device type to actual device
                    device = self._devices.get(device_type)
                    if device is None:
                        raise RuntimeError(f"Unknown device type: {device_type}")
                    
                    # Set the parameter
                    device[param_name] = value
                    
                    # Update device state
                    self._device_states[device_type] = DeviceState(
                        device_id=self.device_id,
                        device_type=device_type,
                        status='active',
                        current_params={param_name: value}
                    )
                    return True
                    
            except Exception as e:
                if self.strict_mode:
                    raise RuntimeError(f"Failed to adjust physical parameter: {e}")
                return False
    
    def get_current_state(self) -> Dict[str, Any]:
        """
        Get current state of all hardware devices.
        
        Returns:
            Dict: Current state snapshot
        """
        with self._resource_lock:
            return {
                'initialized': self._initialized,
                'device_id': self.device_id,
                'devices': {
                    dtype: self._device_states.get(dtype, {}).to_dict() 
                    for dtype in self._devices.keys()
                }
            }
    
    def reset_device(self, device_type: str = None):
        """
        Reset a specific device or all devices.
        
        Args:
            device_type: Specific device to reset, or None for all
        """
        with self._resource_lock:
            if device_type:
                if device_type in self._devices:
                    del self._devices[device_type]
                    del self._device_states[device_type]
                    # Re-initialize the specific device
                    if device_type == 'audio':
                        self._audio_device = self._create_audio_device()
                    elif device_type == 'camera':
                        self._camera_device = self._create_camera_device()
                    elif device_type == 'sensors':
                        self._sensor_devices = self._create_sensor_array()
            else:
                # Reset all devices
                self._devices.clear()
                self._device_states.clear()
                self._initialized = False
                self._initialize_hardware()
    
    def cleanup(self):
        """
        Cleanup all hardware resources.
        """
        with self._resource_lock:
            # Close all devices
            for device_type, device in self._devices.items():
                if hasattr(device, 'close'):
                    device.close()
            
            # Clear references
            self._devices.clear()
            self._device_states.clear()
            self._initialized = False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()


# Convenience functions for middleware layer
def create_orchestrator(
    device_id: int = 0,
    strict_mode: bool = True,
    auto_init: bool = True
) -> HardwareOrchestrator:
    """
    Factory function to create a hardware orchestrator.
    
    Args:
        device_id: HIP device ID
        strict_mode: Raise exceptions on errors
        auto_init: Auto-initialize hardware resources
        
    Returns:
        HardwareOrchestrator: Configured orchestrator instance
    """
    return HardwareOrchestrator(device_id, strict_mode, auto_init)


# Hardware abstraction constants
AUDIO_GAIN_MIN = -120.0  # dB
AUDIO_GAIN_MAX = 0.0      # dB
CAMERA_EXPOSURE_MIN = -10.0  # EV
CAMERA_EXPOSURE_MAX = 10.0   # EV
CAMERA_ISO_MIN = 50
CAMERA_ISO_MAX = 25600


if __name__ == "__main__":
    # Test the orchestrator
    print("Testing HardwareOrchestrator...")
    
    # Create orchestrator
    with HardwareOrchestrator(device_id=0, strict_mode=True) as orchestrator:
        # Test audio gain adjustment
        success = orchestrator.set_audio_gain(-20.0)
        print(f"Set audio gain to -20dB: {success}")
        
        # Test camera exposure
        success = orchestrator.set_camera_exposure(0.5, iso=800)
        print(f"Set camera exposure to 0.5 EV, ISO 800: {success}")
        
        # Test generic parameter adjustment
        success = orchestrator.adjust_physical_parameter('audio', 'sample_rate', 44100)
        print(f"Set audio sample rate to 44100: {success}")
        
        # Get current state
        state = orchestrator.get_current_state()
        print(f"Current state: {state}")
    
    print("HardwareOrchestrator test complete.")
