#!/usr/bin/env python3
"""
Cognitive Escalation Module - Apollo Architecture

Triggers Deep Reasoning (e.g., DeepSeek-R1) when critical system/hardware errors are detected.
Monitors for emergency-level conditions and escalates cognitive processing accordingly.
"""

import os
import sys
import json
import time
import re
import uuid
import threading
import subprocess
from typing import Dict, Optional, Any, Literal, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from datetime import datetime
from pathlib import Path

# Apollo imports
from modules.cognitive_dispatcher import CognitiveDispatcher, Tier, TaskComplexity
from modules.memory_core import vmm


class EscalationLevel(Enum):
    """Emergency escalation levels for cognitive processing."""
    WATCH = "watch"              # Monitoring only, no action required
    CRITICAL = "critical"         # System/hardware error detected, prepare for deep reasoning
    EMERGENCY = "emergency"      # Critical hardware failure imminent, trigger immediate deep reasoning
    CATASTROPHIC = "catastrophic" # System-level failure, all emergency protocols engaged


@dataclass
class SystemHealth:
    """Real-time system health metrics."""
    memory_usage: float = 0.0      # Percentage of RAM in use
    cpu_usage: float = 0.0         # Percentage of CPU in use
    disk_usage: float = 0.0        # Percentage of disk in use
    temperature: float = 0.0       # CPU temperature in Celsius
    network_latency: float = 0.0   # ms
    active_processes: int = 0
    error_count: int = 0            # Current error count in system logs
    last_check: datetime = field(default_factory=datetime.now)


class CognitiveEscalation:
    """
    Monitors for critical system/hardware errors and triggers Deep Reasoning capabilities
    (e.g., DeepSeek-R1) for emergency-level cognitive processing.
    
    Architecture:
    - Monitor Layer: Continuous system health checks (memory, CPU, disk, hardware)
    - Detection Layer: Classify errors as CRITICAL, EMERGENCY, or CATASTROPHIC
    - Escalation Layer: Trigger deep reasoning models when thresholds breached
    - Emergency Response: Coordinate with cognitive dispatcher for high-compute resources
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Thresholds for escalations
        self.thresholds = {
            'memory_warning': 80,      # % RAM
            'memory_critical': 90,     # % RAM
            'cpu_warning': 70,         # % CPU
            'cpu_critical': 90,        # % CPU
            'disk_warning': 80,        # % disk
            'disk_critical': 95,       # % disk
            'temperature_warning': 70, # Celsius
            'temperature_critical': 90, # Celsius
        }
        
        # Escalation history
        self._escalation_log = deque(maxlen=100)
        self._current_level: EscalationLevel = EscalationLevel.WATCH
        
        # Deep reasoning trigger (DeepSeek-R1 or similar)
        self._deep_reasoning_active = False
        self._emergency_context: Dict[str, Any] = {}
        
        # Cognitive dispatcher for routing to high-compute tier
        self._dispatcher = CognitiveDispatcher(config=config)
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Emergency handlers (callbacks)
        self._emergency_handlers: Dict[str, Callable] = {}
        
    def _get_system_health(self) -> SystemHealth:
        """Gathers real-time system health metrics."""
        try:
            # Memory usage
            import psutil
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu = psutil.cpu_percent(interval=1)
            
            # CPU temperature (platform specific)
            temp = 0.0
            try:
                # Linux
                if hasattr(psutil, 'sensors'):
                    sensors = psutil.sensors_cpu()
                    if hasattr(sensors, 'cpu'):
                        temp = sensors.cpu[0].current or 0.0
            except:
                pass
            
            # Network latency (ping to local host)
            net_latency = 0.0
            try:
                start = time.time()
                subprocess.run(['ping', '-c', '1', '127.0.0.1'], 
                             capture_output=True, timeout=5)
                net_latency = (time.time() - start) * 1000
            except:
                net_latency = 0.0
            
            # Active processes
            active_procs = len(os.listdir('/proc')) if os.path.exists('/proc') else 0
            
            return SystemHealth(
                memory_usage=memory.percent,
                cpu_usage=cpu,
                disk_usage=disk.percent,
                temperature=temp,
                network_latency=net_latency,
                active_processes=active_procs,
                last_check=datetime.now()
            )
        except Exception as e:
            # Fallback for systems without psutil
            return SystemHealth(last_check=datetime.now())
    
    def _detect_critical_errors(self) -> tuple[EscalationLevel, str]:
        """
        Detects critical system/hardware errors based on health metrics.
        Returns (level, message) tuple.
        """
        health = self._get_system_health()
        
        # Check for catastrophic conditions
        if health.disk_usage >= self.thresholds['disk_critical']:
            return EscalationLevel.CATASTROPHIC, \
                   f"CRITICAL: Disk usage at {health.disk_usage:.1f}% - imminent system failure"
        
        if health.memory_usage >= self.thresholds['memory_critical']:
            return EscalationLevel.CATASTROPHIC, \
                   f"CRITICAL: Memory usage at {health.memory_usage:.1f}% - system instability imminent"
        
        if health.cpu_usage >= self.thresholds['cpu_critical']:
            return EscalationLevel.CATASTROPHIC, \
                   f"CRITICAL: CPU usage at {health.cpu_usage:.1f}% - compute bottleneck detected"
        
        if health.temperature >= self.thresholds['temperature_critical']:
            return EscalationLevel.CATASTROPHIC, \
                   f"CRITICAL: Hardware temperature at {health.temperature:.1f}°C - thermal shutdown imminent"
        
        # Check for emergency conditions
        if health.memory_usage >= self.thresholds['memory_warning']:
            return EscalationLevel.CRITICAL, \
                   f"WARNING: Memory usage elevated at {health.memory_usage:.1f}%"
        
        if health.cpu_usage >= self.thresholds['cpu_warning']:
            return EscalationLevel.CRITICAL, \
                   f"WARNING: CPU usage elevated at {health.cpu_usage:.1f}%"
        
        if health.disk_usage >= self.thresholds['disk_warning']:
            return EscalationLevel.CRITICAL, \
                   f"WARNING: Disk usage elevated at {health.disk_usage:.1f}%"
        
        if health.temperature >= self.thresholds['temperature_warning']:
            return EscalationLevel.CRITICAL, \
                   f"WARNING: Hardware temperature elevated at {health.temperature:.1f}°C"
        
        return EscalationLevel.WATCH, "System operating within normal parameters"
    
    def trigger_deep_reasoning(self, emergency_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Triggers Deep Reasoning capabilities (DeepSeek-R1) for emergency-level cognitive processing.
        
        This is the critical function that escalates cognitive processing when:
        - Critical system/hardware errors are detected
        - Emergency-level conditions threaten system stability
        - Catastrophic failures require immediate high-compute response
        """
        with self._lock:
            # Generate emergency ID
            emergency_id = str(uuid.uuid4())
            
            # Route to Architect tier for deep reasoning
            # This triggers the high-compute tier (30B+ models) for emergency processing
            task = self._dispatcher.route_task(
                user_input=f"EMERGENCY: {self._current_level.name} - Critical system/hardware error detected. Trigger deep reasoning for emergency cognitive processing.",
                context=emergency_context
            )
            
            # Force architect tier for emergency processing
            if self._current_level in [EscalationLevel.CRITICAL, EscalationLevel.EMERGENCY, EscalationLevel.CATASTROPHIC]:
                task.tier = Tier.ARCHITECT
                task.priority = 10  # Maximum priority
            
            # Execute deep reasoning task
            result = self._dispatcher.execute_task(task)
            
            # Log escalations
            self._escalation_log.append({
                'emergency_id': emergency_id,
                'level': self._current_level.value,
                'timestamp': datetime.now().isoformat(),
                'context': emergency_context,
                'result': result
            })
            
            return result
    
    def monitor(self, interval: float = 1.0, handlers: Optional[Dict[str, Callable]] = None) -> None:
        """
        Continuous monitoring loop that detects critical errors and triggers escalations.
        
        Args:
            interval: Check interval in seconds
            handlers: Callback functions for specific escalations
        """
        if handlers:
            self._emergency_handlers = handlers
        
        running = True
        while running:
            try:
                # Detect errors
                level, message = self._detect_critical_errors()
                
                # Update current level
                self._current_level = level
                
                # Trigger appropriate response
                if level == EscalationLevel.CATASTROPHIC:
                    self.trigger_deep_reasoning({
                        'level': 'catastrophic',
                        'message': message,
                        'action': 'immediate emergency response required'
                    })
                    
                    # Trigger catastrophic handler if registered
                    if 'catastrophic' in self._emergency_handlers:
                        self._emergency_handlers['catastrophic']()
                
                elif level == EscalationLevel.EMERGENCY:
                    self.trigger_deep_reasoning({
                        'level': 'emergency',
                        'message': message,
                        'action': 'emergency protocols engaged'
                    })
                    
                    if 'emergency' in self._emergency_handlers:
                        self._emergency_handlers['emergency']()
                
                elif level == EscalationLevel.CRITICAL:
                    self.trigger_deep_reasoning({
                        'level': 'critical',
                        'message': message,
                        'action': 'prepare for deep reasoning'
                    })
                    
                    if 'critical' in self._emergency_handlers:
                        self._emergency_handlers['critical']()
                
                # Sleep before next check
                time.sleep(interval)
                
            except KeyboardInterrupt:
                running = False
                print("\n[COGNITIVE ESCALATION]: Monitor stopped")
            except Exception as e:
                print(f"[COGNITIVE ESCALATION ERROR]: {e}")
                time.sleep(1)
    
    def get_status(self) -> Dict[str, Any]:
        """Returns current escalations status."""
        level, msg = self._detect_critical_errors()
        return {
            'current_level': self._current_level.value,
            'detected_level': level.value,
            'message': msg,
            'escalation_log': list(self._escalation_log)[-10:],  # Last 10 entries
            'deep_reasoning_active': self._deep_reasoning_active
        }
    
    def reset(self):
        """Resets the escalations module state."""
        with self._lock:
            self._escalation_log.clear()
            self._current_level = EscalationLevel.WATCH
            self._deep_reasoning_active = False
            self._emergency_context = {}


# Convenience function for direct usage
def emergency_detect(critical_threshold: float = 90.0) -> tuple[EscalationLevel, str]:
    """
    Quick emergency detection without full module initialization.
    
    Args:
        critical_threshold: Memory/CPU threshold that triggers critical escalations (0-100)
    
    Returns:
        (EscalationLevel, message) tuple
    """
    import psutil
    
    # Check memory
    mem = psutil.virtual_memory()
    if mem.percent >= critical_threshold:
        return EscalationLevel.CATASTROPHIC, f"CRITICAL: Memory at {mem.percent:.1f}%"
    
    # Check CPU
    cpu = psutil.cpu_percent(interval=1)
    if cpu >= critical_threshold:
        return EscalationLevel.CATASTROPHIC, f"CRITICAL: CPU at {cpu:.1f}%"
    
    # Check disk
    disk = psutil.disk_usage('/')
    if disk.percent >= critical_threshold:
        return EscalationLevel.CATASTROPHIC, f"CRITICAL: Disk at {disk.percent:.1f}%"
    
    return EscalationLevel.WATCH, "System operating normally"


if __name__ == "__main__":
    # Demo/test code
    print("Cognitive Escalation Module - Apollo Architecture")
    print("=" * 60)
    
    # Initialize escalations
    escalations = CognitiveEscalation()
    
    # Define emergency handlers
    def on_catastrophic():
        print(f"\n[🚨 CATASTROPHIC]: Emergency protocol engaged at {datetime.now().isoformat()}")
    
    def on_emergency():
        print(f"\n[🚨 EMERGENCY]: Emergency protocols engaged at {datetime.now().isoformat()}")
    
    def on_critical():
        print(f"\n[⚠️ CRITICAL]: Critical error detected at {datetime.now().isoformat()}")
    
    # Run monitor
    print("Starting system monitor...")
    print(f"Press Ctrl+C to stop")
    
    handlers = {
        'catastrophic': on_catastrophic,
        'emergency': on_emergency,
        'critical': on_critical
    }
    
    escalations.monitor(interval=2.0, handlers=handlers)
