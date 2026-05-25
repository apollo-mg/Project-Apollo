import os
import time

class CompilerHardwareMappingRegistry:
    """
    Implements the 'Compiler-Hardware Mapping Registry' as suggested by the Subconscious Epiphany.
    Explicitly flags data types/quantization modes as 'Software Emulation' vs 'Hardware Accelerated'.
    This prevents mistaking emulation latency for hardware capability.
    """
    
    def __init__(self):
        # Registry of supported data types and their current hardware/compiler status
        # This is a living document of the 'Translation Lag'
        self.mapping = {
            "FP32": {"mode": "Hardware Accelerated", "driver": "ROCm", "latency_profile": "low"},
            "FP16": {"mode": "Hardware Accelerated", "driver": "ROCm", "latency_profile": "low"},
            "BF16": {"mode": "Hardware Accelerated", "driver": "ROCm", "latency_profile": "low"},
            "INT8": {"mode": "Hardware Accelerated", "driver": "ROCm", "latency_profile": "medium"},
            "FP8": {"mode": "Hardware Accelerated", "driver": "ROCm", "latency_profile": "low"},
            "INT4": {"mode": "Software Emulation", "driver": "Triton/Custom", "latency_profile": "high"},
            "NF4": {"mode": "Software Emulation", "driver": "Triton/Custom", "latency_profile": "high"},
            "GGUF_Q4_K_M": {"mode": "Software Emulation", "driver": "llama.cpp", "latency_profile": "high"},
            "IQ2_XXS": {"mode": "Hardware Accelerated", "driver": "PrismML/ROCm", "latency_profile": "low"},
        }

    def get_status(self, dtype):
        """Returns the mapping for a given data type."""
        return self.mapping.get(dtype, {"mode": "Unknown", "driver": "Unknown", "latency_profile": "Unknown"})

    def audit_performance_profile(self, dtype, measured_latency_ms):
        """
        Compares measured latency against the registry to flag if we are 
        measuring 'Compiler Maturity' instead of 'Hardware Potential'.
        """
        status = self.get_status(dtype)
        if status["mode"] == "Software Emulation":
            return f"[WARNING] {dtype} is in {status['mode']} mode. Measured latency ({measured_latency_ms}ms) reflects compiler/emuation overhead, NOT hardware potential."
        else:
            return f"[INFO] {dtype} is {status['mode']}. Measured latency ({measured_latency_ms}ms) reflects hardware capability."

if __name__ == "__main__":
    registry = CompilerHardwareMappingRegistry()
    
    # Test Case 1: Hardware Accelerated
    print(registry.audit_performance_profile("FP16", 12.5))
    
    # Test Case 2: Software Emulation (The 'Triton Red Zone')
    print(registry.audit_performance_profile("INT4", 85.0))