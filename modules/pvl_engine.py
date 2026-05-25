"""Prior-Validation Layer (PVL) Engine.

A pre-computation safety layer that detects high-risk contexts and injects
anti-prior instructions into the system prompt to prevent cognitive errors.
"""

import re
import json
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum, auto



class RiskLevel(Enum):
    """Risk classification for context validation."""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass
class ValidationResult:
    """Result of a validation check."""
    risk_level: RiskLevel
    context_hash: str
    anti_prior_instructions: List[str]
    blocked: bool
    reason: Optional[str]


class PriorValidationLayer:
    """
    Pre-computation safety layer that validates context before allowing
    the cognitive tier to proceed.
    """
    
    # Known hallucination triggers and high-risk patterns
    HALLUCINATION_TRIGGERS = [
        r'\b(?:definitely|absolutely|guaranteed|100%|certainly)\b',
        r'\b(?:infinite|eternal|perpetual|never-ending)\b',
        r'\b(?:contradiction|paradox|oxymoron)\b',
        r'\b(?:self-referential|self-referencing|self-referential)\b',
        r'\b(?:recursive|recursion|recursively)\b',
        r'\b(?:infinite|infinite loop|infinite recursion)\b',
    ]
    
    # Edge case patterns that require special handling
    EDGE_CASE_PATTERNS = [
        r'\b(?:edge case|edge-case|boundary condition|boundary-condition)\b',
        r'\b(?:exception|exceptional|exceptionally)\b',
        r'\b(?:corner case|corner-case)\b',
    ]
    
    # Anti-prior instructions to inject into system prompt
    ANTI_PRIOR_INSTRUCTIONS = {
        'hallucination': [
            "You are operating under strict anti-hallucination constraints. "
            "Do not generate any content that could be interpreted as "
            "hallucination triggers or self-referential paradoxes.",
            "If you encounter a self-referential statement, "
            "immediately halt and request human intervention.",
        ],
        'edge_case': [
            "You are operating under strict edge-case constraints. "
            "Do not generate any content that could be interpreted as "
            "edge-case triggers or boundary-condition paradoxes.",
            "If you encounter an edge-case statement, "
            "immediately halt and request human intervention.",
        ],
        'high_risk': [
            "You are operating under strict high-risk constraints. "
            "Do not generate any content that could be interpreted as "
            "high-risk triggers or cognitive paradoxes.",
            "If you encounter a high-risk statement, "
            "immediately halt and request human intervention.",
        ],
    }
    
    def __init__(self):
        """Initialize the PVL engine."""
        self._risk_patterns = {
            'hallucination': self.HALLUCINATION_TRIGGERS,
            'edge_case': self.EDGE_CASE_PATTERNS,
        }
        self._anti_prior_instructions = self.ANTI_PRIOR_INSTRUCTIONS
    
    def detect_high_risk_context(self, context: str) -> ValidationResult:
        """
        Detect high-risk contexts and return validation result.
        
        Args:
            context: The context string to validate
            
        Returns:
            ValidationResult containing risk level and anti-prior instructions
        """
        # Check for hallucination triggers
        hallucination_matches = self._find_matches(context, self.HALLUCINATION_TRIGGERS)
        
        # Check for edge case patterns
        edge_case_matches = self._find_matches(context, self.EDGE_CASE_PATTERNS)
        
        # Determine risk level
        if hallucination_matches or edge_case_matches:
            risk_level = RiskLevel.CRITICAL
            anti_prior = self._get_anti_prior_instructions('hallucination')
            blocked = True
            reason = "High-risk context detected: hallucination triggers or edge-case patterns"
        else:
            risk_level = RiskLevel.LOW
            anti_prior = []
            blocked = False
            reason = None
            
        return ValidationResult(
            risk_level=risk_level,
            context_hash=self._hash_context(context),
            anti_prior_instructions=anti_prior,
            blocked=blocked,
            reason=reason
        )
    
    def _find_matches(self, text: str, patterns: List[str]) -> List[str]:
        """Find all matches for given patterns in text."""
        matches = []
        for pattern in patterns:
            try:
                matches.extend(re.findall(pattern, text, re.IGNORECASE))
            except re.error:
                pass
        return matches
    
    def _hash_context(self, context: str) -> str:
        """Generate hash for context."""
        import hashlib
        return hashlib.sha256(context.encode()).hexdigest()
    
    def _get_anti_prior_instructions(self, risk_type: str) -> List[str]:
        """Get anti-prior instructions for given risk type."""
        return self._anti_prior_instructions.get(risk_type, [])
    
    def validate_and_inject(self, context: str, system_prompt: str) -> Dict[str, Any]:
        """
        Validate context and inject anti-prior instructions into system prompt.
        
        Args:
            context: The context to validate
            system_prompt: The base system prompt
            
        Returns:
            Dictionary containing validation result and modified system prompt
        """
        result = self.detect_high_risk_context(context)
        
        # Inject anti-prior instructions into system prompt
        if result.anti_prior_instructions:
            modified_prompt = self._inject_anti_prior(
                system_prompt, 
                result.anti_prior_instructions
            )
        else:
            modified_prompt = system_prompt
            
        return {
            'validation_result': result,
            'system_prompt': modified_prompt,
            'risk_level': result.risk_level,
            'blocked': result.blocked,
            'reason': result.reason
        }
    
    def _inject_anti_prior(self, system_prompt: str, instructions: List[str]) -> str:
        """Inject anti-prior instructions into system prompt."""
        if not instructions:
            return system_prompt
            
        # Prepend anti-prior instructions to system prompt
        anti_prior_section = "\n\n=== ANTI-PRIOR INSTRUCTIONS ===\n"
        for i, instruction in enumerate(instructions, 1):
            anti_prior_section += f"{i}. {instruction}\n"
        anti_prior_section += "==============================\n\n"
        
        return anti_prior_section + system_prompt


# Global instance for singleton pattern
_pvl_engine: Optional[PriorValidationLayer] = None


def get_pvl_engine() -> PriorValidationLayer:
    """Get global PVL engine instance."""
    global _pvl_engine
    if _pvl_engine is None:
        _pvl_engine = PriorValidationLayer()
    return _pvl_engine


def validate_context(context: str, system_prompt: str) -> Dict[str, Any]:
    """
    Convenience function to validate context and inject anti-prior instructions.
    
    Args:
        context: The context to validate
        system_prompt: The base system prompt
        
    Returns:
        Dictionary containing validation result and modified system prompt
    """
    engine = get_pvl_engine()
    return engine.validate_and_inject(context, system_prompt)
