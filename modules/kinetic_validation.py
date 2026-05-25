#!/usr/bin/env python3
"""Kinetic Validation Protocol.

This module implements a complexity-to-precision ratio analysis system to prevent
unnecessary scaling (Political Turbulence) by auditing incoming requests and
determining appropriate resource tier allocation.
"""

import math
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, Optional, Tuple, Union


class ResourceTier(Enum):
    """Resource tier classifications for request routing."""
    TIER_0 = auto()  # Basic/Edge resources - low latency, low cost
    TIER_1 = auto()  # Standard resources - moderate complexity
    TIER_2 = auto()  # High-performance resources - complex operations
    TIER_3 = auto()  # Premium resources - maximum complexity, high cost


@dataclass
class ComplexityProfile:
    """Represents the complexity characteristics of a request."""
    semantic_density: float  # Information density per token (0.0-1.0)
    logical_depth: int  # Nesting/dependency depth
    ambiguity_score: float  # Ambiguity level (0.0-1.0)
    context_window: int  # Required context window size
    dependency_graph_size: int  # Number of external dependencies
    
    def __post_init__(self):
        # Normalize values
        self.semantic_density = max(0.0, min(1.0, self.semantic_density))
        self.ambiguity_score = max(0.0, min(1.0, self.ambiguity_score))


@dataclass
class TierCapability:
    """Represents the processing capabilities of a resource tier."""
    max_complexity: float  # Maximum complexity score this tier can handle
    latency_budget_ms: int  # Maximum acceptable latency
    cost_per_request: float  # Relative cost metric
    throughput_qps: int  # Queries per second capacity


class KineticValidator:
    """Validates requests against resource tiers to prevent unnecessary scaling."""
    
    # Tier capability definitions
    TIER_CAPABILITIES = {
        ResourceTier.TIER_0: TierCapability(
            max_complexity=0.3,
            latency_budget_ms=50,
            cost_per_request=0.01,
            throughput_qps=10000
        ),
        ResourceTier.TIER_1: TierCapability(
            max_complexity=0.6,
            latency_budget_ms=200,
            cost_per_request=0.1,
            throughput_qps=1000
        ),
        ResourceTier.TIER_2: TierCapability(
            max_complexity=0.85,
            latency_budget_ms=500,
            cost_per_request=1.0,
            throughput_qps=100
        ),
        ResourceTier.TIER_3: TierCapability(
            max_complexity=1.0,
            latency_budget_ms=2000,
            cost_per_request=10.0,
            throughput_qps=10
        ),
    }
    
    def __init__(self):
        self._request_cache: Dict[str, Any] = {}
        self._complexity_weights = {
            'semantic_density': 0.3,
            'logical_depth': 0.25,
            'ambiguity': 0.25,
            'context_window': 0.1,
            'dependency_graph': 0.1
        }
    
    def analyze_request(
        self,
        request_id: str,
        request_data: Dict[str, Any],
        current_tier: Optional[ResourceTier] = None
    ) -> Tuple[ResourceTier, float, Dict[str, Any]]:
        """
        Analyze a request to determine appropriate resource tier.
        
        Args:
            request_id: Unique identifier for the request
            request_data: Dictionary containing request characteristics
            current_tier: Current tier assignment (if any)
            
        Returns:
            Tuple of (recommended_tier, complexity_score, analysis_metadata)
        """
        # Extract complexity indicators from request
        complexity_profile = self._extract_complexity_profile(request_data)
        
        # Calculate complexity score
        complexity_score = self._calculate_complexity_score(complexity_profile)
        
        # Determine appropriate tier
        recommended_tier = self._find_appropriate_tier(complexity_score, current_tier)
        
        # Generate metadata for audit trail
        metadata = {
            'request_id': request_id,
            'complexity_score': complexity_score,
            'complexity_profile': complexity_profile.__dict__,
            'recommended_tier': recommended_tier.name,
            'tier_capability': self.TIER_CAPABILITIES[recommended_tier].__dict__,
            'escalation_prevented': self._is_escalation(current_tier, recommended_tier)
        }
        
        # Cache the analysis
        self._request_cache[request_id] = {
            'profile': complexity_profile,
            'score': complexity_score,
            'tier': recommended_tier,
            'metadata': metadata
        }
        
        return (recommended_tier, complexity_score, metadata)
    
    def _extract_complexity_profile(
        self,
        request_data: Dict[str, Any]
    ) -> ComplexityProfile:
        """Extract complexity characteristics from raw request data."""
        # Parse semantic density from content
        semantic_density = self._calculate_semantic_density(request_data.get('content', ''))
        
        # Determine logical depth from request structure
        logical_depth = self._measure_logical_depth(request_data.get('structure', {}))
        
        # Calculate ambiguity from request parameters
        ambiguity = self._assess_ambiguity(request_data)
        
        # Extract context requirements
        context_window = request_data.get('context_window', 4096)
        
        # Count dependencies
        dependency_graph_size = len(request_data.get('dependencies', []))
        
        return ComplexityProfile(
            semantic_density=semantic_density,
            logical_depth=logical_depth,
            ambiguity_score=ambiguity,
            context_window=context_window,
            dependency_graph_size=dependency_graph_size
        )
    
    def _calculate_semantic_density(self, content: str) -> float:
        """Calculate information density of request content."""
        if not content:
            return 0.0
        
        # Ratio of non-whitespace to total, adjusted by entropy
        non_whitespace = len(content.replace(' ', ''))
        total = len(content)
        
        if total == 0:
            return 0.0
        
        base_ratio = non_whitespace / total
        
        # Adjust for special characters (indicates complexity)
        special_char_ratio = len(re.findall(r'[\W]', content)) / max(len(content), 1)
        
        return min(1.0, base_ratio + (special_char_ratio * 0.3))
    
    def _measure_logical_depth(self, structure: Dict) -> int:
        """Measure nesting/dependency depth in request structure."""
        if not structure:
            return 1
        
        # Recursively measure depth
        def _depth(obj, current_depth=0):
            if isinstance(obj, dict):
                if not obj:
                    return current_depth
                return max(_depth(v, current_depth + 1) for v in obj.values())
            elif isinstance(obj, list):
                if not obj:
                    return current_depth
                return max(_depth(item, current_depth + 1) for item in obj)
            else:
                return current_depth
        
        return _depth(structure)
    
    def _assess_ambiguity(self, request_data: Dict) -> float:
        """Assess ambiguity level of request parameters."""
        # Higher ambiguity when parameters are underspecified
        ambiguity = 0.0
        
        # Check for vague parameters
        vague_indicators = ['any', 'some', 'maybe', 'possibly', 'approximately']
        for key, value in request_data.items():
            if isinstance(value, str):
                if any(indicator in value.lower() for indicator in vague_indicators):
                    ambiguity += 0.1
        
        # Check for missing required fields
        required_fields = ['target', 'constraint', 'priority']
        missing = sum(1 for field in required_fields if field not in request_data)
        ambiguity += min(0.5, missing * 0.15)
        
        return min(1.0, ambiguity)
    
    def _calculate_complexity_score(
        self,
        profile: ComplexityProfile
    ) -> float:
        """Calculate weighted complexity score."""
        score = (
            profile.semantic_density * self._complexity_weights['semantic_density'] +
            (profile.logical_depth / 10.0) * self._complexity_weights['logical_depth'] +
            profile.ambiguity_score * self._complexity_weights['ambiguity'] +
            (math.log2(profile.context_window + 1) / 10.0) * self._complexity_weights['context_window'] +
            (min(profile.dependency_graph_size, 100) / 100.0) * self._complexity_weights['dependency_graph']
        )
        
        return min(1.0, max(0.0, score))
    
    def _find_appropriate_tier(
        self,
        complexity_score: float,
        current_tier: Optional[ResourceTier]
    ) -> ResourceTier:
        """Find the lowest-cost tier capable of handling the complexity."""
        # Find tiers that can handle this complexity
        capable_tiers = [
            tier for tier, cap in self.TIER_CAPABILITIES.items()
            if cap.max_complexity >= complexity_score
        ]
        
        if not capable_tiers:
            # Force to highest tier if complexity exceeds all
            return ResourceTier.TIER_3
        
        # Select lowest cost tier that can handle the load
        # (preventing unnecessary scaling)
        return min(capable_tiers, key=lambda t: self.TIER_CAPABILITIES[t].cost_per_request)
    
    def _is_escalation(
        self,
        current_tier: Optional[ResourceTier],
        recommended_tier: ResourceTier
    ) -> bool:
        """Check if moving to recommended tier represents escalation."""
        if current_tier is None:
            return False
        
        current_cost = self.TIER_CAPABILITIES[current_tier].cost_per_request
        recommended_cost = self.TIER_CAPABILITIES[recommended_tier].cost_per_request
        
        return recommended_cost > current_cost
    
    def get_tier_capability(self, tier: ResourceTier) -> TierCapability:
        """Get capability constraints for a specific tier."""
        return self.TIER_CAPABILITIES[tier]
    
    def clear_cache(self):
        """Clear the request cache."""
        self._request_cache.clear()


class PoliticalTurbulenceDetector:
    """Detects and prevents unnecessary scaling (Political Turbulence)."""
    
    def __init__(self, validator: KineticValidator):
        self.validator = validator
        self.turbulence_history: Dict[str, int] = {}
    
    def detect_turbulence(
        self,
        request_id: str,
        current_tier: ResourceTier,
        recommended_tier: ResourceTier
    ) -> Tuple[bool, str]:
        """
        Detect if request routing represents Political Turbulence.
        
        Returns:
            Tuple of (is_turbulence, explanation)
        """
        # Check if this represents unnecessary escalation
        if current_tier != recommended_tier:
            current_cost = self.validator.TIER_CAPABILITIES[current_tier].cost_per_request
            recommended_cost = self.validator.TIER_CAPABILITIES[recommended_tier].cost_per_request
            
            if recommended_cost > current_cost:
                # This is unnecessary scaling
                self.turbulence_history[request_id] = self.turbulence_history.get(request_id, 0) + 1
                return (
                    True,
                    f"Unnecessary escalation detected: {current_tier.name} -> {recommended_tier.name} "
                    f"(cost: ${current_cost:.2f} -> ${recommended_cost:.2f})"
                )
        
        return (False, "No turbulence detected")
    
    def get_turbulence_stats(self) -> Dict[str, int]:
        """Get turbulence detection statistics."""
        return self.turbulence_history.copy()


# Convenience functions for direct usage
_validator: Optional[KineticValidator] = None


def validate_request(
    request_id: str,
    request_data: Dict[str, Any],
    current_tier: Optional[ResourceTier] = None
) -> Tuple[ResourceTier, float, Dict]:
    """
    Validate a request against resource tiers.
    
    Usage:
        tier, score, metadata = validate_request('req-001', {'content': '...', 'structure': {...}})
    """
    global _validator
    if _validator is None:
        _validator = KineticValidator()
    
    return _validator.analyze_request(request_id, request_data, current_tier)


def get_tier_for_complexity(complexity_score: float) -> ResourceTier:
    """Quick lookup for appropriate tier based on complexity score."""
    global _validator
    if _validator is None:
        _validator = KineticValidator()
    
    validator = _validator
    
    for tier, cap in validator.TIER_CAPABILITIES.items():
        if cap.max_complexity >= complexity_score:
            return tier
    
    return ResourceTier.TIER_3


# Example usage and testing
if __name__ == "__main__":
    # Test the implementation
    validator = KineticValidator()
    
    # Test case 1: Low complexity request (should route to Tier 0)
    low_complexity_request = {
        'content': 'Simple query with basic parameters',
        'structure': {'a': 1},
        'context_window': 512,
        'dependencies': []
    }
    
    tier, score, meta = validator.analyze_request('test-001', low_complexity_request)
    print(f"Low complexity: Tier={tier}, Score={score:.4f}")
    print(f"Metadata: {meta}")
    
    # Test case 2: High complexity request (should route to Tier 2 or 3)
    high_complexity_request = {
        'content': 'Complex nested query with multiple dependencies and high ambiguity',
        'structure': {'level1': {'level2': {'level3': 'deep'}}},
        'context_window': 32768,
        'dependencies': ['dep1', 'dep2', 'dep3'],
        'target': 'any',
        'constraint': 'possibly required'
    }
    
    tier, score, meta = validator.analyze_request('test-002', high_complexity_request)
    print(f"High complexity: Tier={tier}, Score={score:.4f}")
    print(f"Metadata: {meta}")
    
    # Test turbulence detection
    detector = PoliticalTurbulenceDetector(validator)
    is_turbulence, explanation = detector.detect_turbulence(
        'test-003',
        ResourceTier.TIER_0,
        ResourceTier.TIER_2
    )
    print(f"Turbulence detected: {is_turbulence} - {explanation}")
