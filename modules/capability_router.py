import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

"""
SOVEREIGN ENGINE: CAPABILITY ROUTER
===================================
Architectural Intent:
This module decouples 'Tools' from specific 'Hardware'. It treats AI capabilities as an economics problem: 
matching the physical requirements of a Tool (context window, math precision, internet) against the physical 
reality of a Hardware Node (RX 9070, Pi 5, S21), arbitrated by the user's acceptable wait time (Tokens Per Second).

LLM Agent Instructions:
When drafting new tools for the Sovereign Engine, you MUST define them as a `ToolRequirement` object here.
Do NOT hardcode a tool to run on the GPU. Define its minimum physics, and let this router assign it to the 
cheapest/slowest node that satisfies the requirement, saving the main GPU for heavy Architectural reasoning.
"""

@dataclass
class HardwareNode:
    """
    Represents a physical device in the Sovereign cluster.
    - precision_bits: The quantization level. 1.0 (BonPi 1-bit), 4.0 (Phone IQ4), 8.0/16.0 (Desktop GPU).
      Crucial for routing tasks that require high reasoning fidelity vs simple summarization.
    """
    name: str
    ip: str
    port: int
    context_window: int
    tps_baseline: float      # Tokens per second capability
    precision_bits: float    # 1.0 (BonPi), 4.0 (PocketAssistant), 16.0 (RX9070)
    internet_access: bool
    status: str = "idle"     # idle, working, offline

@dataclass
class ToolRequirement:
    """
    The physical and temporal minimums required to execute a specific Agentic Tool.
    """
    tool_name: str
    min_context: int
    min_tps: float
    min_precision: float
    requires_internet: bool

class SovereignRouter:
    """
    The arbitration ledger. Compares the ToolRequirement against the HardwareNode fleet.
    Priority is given to the 'weakest' capable node to maximize cluster efficiency.
    """
    def __init__(self):
        # In production, this would load from a local nodes.json registry
        self.fleet: List[HardwareNode] = [
            HardwareNode("RX_9070_XT", "127.0.0.1", 8082, 32768, 80.0, 8.0, True),
            HardwareNode("BonPi_Edge", "100.66.52.81", 8080, 65536, 2.8, 1.0, False),
            HardwareNode("PocketAssistant_S21", "100.75.156.52", 8080, 4096, 20.0, 4.0, True)
        ]
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    def evaluate_tool_request(self, requirement: ToolRequirement, max_wait_time_sec: Optional[int] = None) -> Optional[HardwareNode]:
        """
        The magic of AI awareness: Abstract the requirements down to capability and time.
        """
        logging.info(f"Evaluating routing for tool: '{requirement.tool_name}'")
        logging.info(f"Requirements -> Context: {requirement.min_context}, TPS: {requirement.min_tps}, Precision: {requirement.min_precision}bit, Internet: {requirement.requires_internet}")

        viable_nodes = []

        for node in self.fleet:
            if node.status != "idle":
                continue
            
            # Hard constraints (Physics)
            if node.context_window < requirement.min_context:
                continue
            if requirement.requires_internet and not node.internet_access:
                continue
            if node.precision_bits < requirement.min_precision:
                continue
            
            # Soft constraints (Time / Frustration)
            if node.tps_baseline < requirement.min_tps:
                # Unless they specifically say they don't care how long it takes, reject it
                if not max_wait_time_sec:
                    continue

            viable_nodes.append(node)

        if not viable_nodes:
            logging.error(f"No hardware nodes capable of executing '{requirement.tool_name}'.")
            return None

        # Sort by efficiency: We want to use the WEAKEST node that meets the requirements,
        # saving the RX 9070 XT for the heavy architectural lifting.
        viable_nodes.sort(key=lambda n: n.tps_baseline)
        
        selected_node = viable_nodes[0]
        logging.info(f"✅ Request routed to {selected_node.name} ({selected_node.ip}:{selected_node.port})")
        
        return selected_node


if __name__ == "__main__":
    router = SovereignRouter()

    # Scenario 1: A massive background read of a local 40k token whitepaper.
    # Time is not a factor (min_tps is low), but context window is huge.
    print("\n--- Scenario 1: Deep Background Read ---")
    req1 = ToolRequirement("read_whitepaper_local", 40000, 1.0, 1.0, False)
    router.evaluate_tool_request(req1)

    # Scenario 2: Quickly format a JSON table from the web.
    # Needs internet, decent precision (so it doesn't drop commas), and fast TPS.
    print("\n--- Scenario 2: Fast Web Formatting ---")
    req2 = ToolRequirement("format_web_table", 2000, 15.0, 4.0, True)
    router.evaluate_tool_request(req2)
    
    # Scenario 3: Complex coding logic that requires massive precision and speed.
    print("\n--- Scenario 3: Architectural Coding ---")
    req3 = ToolRequirement("generate_pydantic_wrapper", 8000, 50.0, 8.0, False)
    router.evaluate_tool_request(req3)
