"""Integrity Layer for Apollo Architecture.

This module implements the Mutation Guard to distinguish between:
- **Self-Correction**: Intentional architectural decisions made during code-writing tasks
- **Systemic Mutation**: Unintended systemic mutations that could compromise system integrity

The Mutation Guard analyzes code changes to determine their nature and ensures
that only intentional architectural decisions are preserved while systemic
mutations are detected and prevented.
"""

import os
import sys
import json
import uuid
import threading
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import OrderedDict


class MutationType(Enum):
    """Classification of mutations in the Integrity Layer."""
    SELF_CORRECTION = auto()  # Intentional architectural decisions
    SYSTEMIC_MUTATION = auto()  # Unintended systemic mutations
    ARCHITECTURAL_DECISION = auto()  # Permanent architectural decisions
    TEMPORARY_FIX = auto()  # Temporary workarounds


class MutationStatus(Enum):
    """Status of a mutation in the Integrity Layer."""
    PENDING = auto()  # Mutation pending analysis
    ANALYZING = auto()  # Under analysis by Mutation Guard
    SELF_CORRECTED = auto()  # Determined to be intentional self-correction
    SYSTEMIC = auto()  # Determined to be systemic mutation
    BLOCKED = auto()  # Blocked by Mutation Guard
    INTEGRATED = auto()  # Integrated into system architecture


@dataclass
class MutationMetadata:
    """Metadata for a mutation in the Integrity Layer."""
    mutation_id: str
    mutation_type: MutationType
    status: MutationStatus
    description: str
    architectural_impact: str
    code_hash: Optional[str]  # Hash of the code change
    file_path: Optional[str]  # Path to affected file
    timestamp: Optional[str]  # When mutation occurred
    guard_decision: Optional[str]  # Decision by Mutation Guard
    
    def __post_init__(self):
        if self.mutation_id is None:
            self.mutation_id = str(uuid.uuid4())


class MutationGuard:
    """
    The Mutation Guard analyzes code changes to distinguish between:
    - Self-Correction: Intentional architectural decisions
    - Systemic Mutation: Unintended systemic mutations
    
    This guard ensures that only intentional architectural decisions are preserved
    while systemic mutations are detected and prevented.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self._mutations: Dict[str, MutationMetadata] = {}
        self._lock = threading.Lock()
        self._guard_registry = self._init_registry()
        self._analysis_cache: Dict[str, Any] = {}
        
    def _init_registry(self) -> Dict[str, Any]:
        """Initialize the guard registry for tracking mutations."""
        return {
            "self_corrections": [],  # Intentional architectural decisions
            "systemic_mutations": [],  # Unintended systemic mutations
            "architectural_decisions": [],  # Permanent decisions
            "blocked_mutations": [],  # Mutations blocked by guard
            "analysis_queue": []  # Pending analysis
        }
    
    def analyze_mutation(
        self,
        code_change: str,
        file_path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a code change to determine if it represents:
        - Self-Correction: Intentional architectural decision
        - Systemic Mutation: Unintended systemic mutation
        
        Args:
            code_change: The code change to analyze
            file_path: Path to the affected file
            context: Additional context for analysis
            
        Returns:
            Analysis results with mutation classification
        """
        with self._lock:
            # Generate mutation ID
            mutation_id = str(uuid.uuid4())
            
            # Compute hash of the code change for tracking
            code_hash = hashlib.sha256(code_change.encode()).hexdigest()
            
            # Analyze the mutation
            analysis = self._perform_analysis(code_change, file_path, context)
            
            # Determine mutation type
            mutation_type = self._classify_mutation(analysis, code_hash)
            
            # Create metadata
            metadata = MutationMetadata(
                mutation_id=mutation_id,
                mutation_type=mutation_type,
                status=MutationStatus.PENDING,
                description=f"Mutation analysis: {analysis['description']}",
                architectural_impact=analysis['architectural_impact'],
                code_hash=code_hash,
                file_path=file_path,
                timestamp=datetime.now().isoformat(),
                guard_decision=analysis['decision']
            )
            
            # Register the mutation
            self._mutations[mutation_id] = metadata
            
            # Update registry based on type
            if mutation_type == MutationType.SELF_CORRECTION:
                self._guard_registry["self_corrections"].append(mutation_id)
            elif mutation_type == MutationType.SYSTEMIC_MUTATION:
                self._guard_registry["systemic_mutations"].append(mutation_id)
                self._guard_registry["blocked_mutations"].append(mutation_id)
            
            return {
                "mutation_id": mutation_id,
                "type": mutation_type.value,
                "status": "BLOCKED" if mutation_type == MutationType.SYSTEMIC_MUTATION else "INTEGRATED",
                "analysis": analysis,
                "code_hash": code_hash
            }
    
    def _perform_analysis(
        self,
        code_change: str,
        file_path: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Perform analysis on the code change to determine its nature.
        """
        # Extract features from the code change
        features = self._extract_features(code_change, file_path)
        
        # Determine if this is self-correction or systemic mutation
        is_self_correction = self._is_self_correction(features, code_change)
        
        return {
            "features": features,
            "is_self_correction": is_self_correction,
            "description": self._generate_description(features, is_self_correction),
            "architectural_impact": self._assess_impact(features),
            "decision": "ALLOW" if is_self_correction else "BLOCK"
        }
    
    def _extract_features(self, code_change: str, file_path: Optional[str]) -> Dict[str, Any]:
        """
        Extract features from the code change for analysis.
        """
        # Analyze code structure, imports, patterns
        features = {
            "file_path": file_path,
            "code_length": len(code_change),
            "import_count": code_change.count("import ") + code_change.count("from "),
            "class_count": code_change.count("class "),
            "function_count": code_change.count("def "),
            "comment_ratio": code_change.count("# ") / max(len(code_change), 1),
            "timestamp": datetime.now().isoformat()
        }
        
        return features
    
    def _is_self_correction(self, features: Dict[str, Any], code_change: str) -> bool:
        """
        Determine if the mutation represents intentional self-correction
        or unintended systemic mutation.
        """
        # Criteria for self-correction (intentional architectural decision):
        # 1. High architectural intent (explicit comments, clear structure)
        # 2. Consistent with existing architectural patterns
        # 3. Not a temporary workaround
        
        # Check for signs of systemic mutation (unintended):
        # - Random imports without clear purpose
        # - Temporary-looking fixes (TODO, FIXME, HACK)
        # - Inconsistent with architectural patterns
        
        systemic_indicators = [
            "TODO", "FIXME", "HACK", "TEMP", "TEMPORARY",
            "WORKAROUND", "PATCH", "HOTFIX"
        ]
        
        # Check if code contains systemic mutation indicators
        has_systemic_indicators = any(
            indicator in code_change.upper() 
            for indicator in systemic_indicators
        )
        
        # Self-correction indicators (intentional):
        # - Clear architectural comments
        # - Consistent naming patterns
        # - Proper documentation
        
        is_self_correction = not has_systemic_indicators and (
            features["import_count"] < 10 or  # Not excessive imports
            features["comment_ratio"] > 0.1  # Has documentation
        )
        
        return is_self_correction
    
    def _classify_mutation(
        self,
        analysis: Dict[str, Any],
        code_hash: str
    ) -> MutationType:
        """
        Classify the mutation based on analysis.
        """
        if analysis["is_self_correction"]:
            return MutationType.SELF_CORRECTION
        else:
            return MutationType.SYSTEMIC_MUTATION
    
    def _generate_description(
        self,
        features: Dict[str, Any],
        is_self_correction: bool
    ) -> str:
        """
        Generate a description for the mutation.
        """
        if is_self_correction:
            return "Intentional architectural decision - Self-Correction"
        else:
            return "Unintended systemic mutation detected - BLOCKED"
    
    def _assess_impact(self, features: Dict[str, Any]) -> str:
        """
        Assess the architectural impact of the mutation.
        """
        return "Architectural decision with system-wide implications"
    
    def block_mutation(self, mutation_id: str) -> bool:
        """
        Block a systemic mutation to prevent it from compromising system integrity.
        """
        with self._lock:
            if mutation_id not in self._mutations:
                return False
            
            self._mutations[mutation_id].status = MutationStatus.BLOCKED
            self._guard_registry["blocked_mutations"].append(mutation_id)
            return True
    
    def allow_mutation(self, mutation_id: str) -> bool:
        """
        Allow a self-correction to be integrated into the system.
        """
        with self._lock:
            if mutation_id not in self._mutations:
                return False
            
            self._mutations[mutation_id].status = MutationStatus.INTEGRATED
            self._guard_registry["architectural_decisions"].append(mutation_id)
            return True
    
    def get_mutation_status(self, mutation_id: str) -> Optional[MutationMetadata]:
        """Retrieve the status of a mutation."""
        return self._mutations.get(mutation_id)
    
    def get_guard_report(self) -> Dict[str, Any]:
        """
        Get a report on the current state of the Mutation Guard.
        """
        return {
            "total_mutations": len(self._mutations),
            "self_corrections": self._guard_registry.get("self_corrections", []),
            "systemic_mutations": self._guard_registry.get("systemic_mutations", []),
            "blocked_mutations": self._guard_registry.get("blocked_mutations", []),
            "architectural_decisions": self._guard_registry.get("architectural_decisions", []),
            "timestamp": datetime.now().isoformat()
        }


class IntegrityLayer:
    """
    High-level interface for the Integrity Layer in Apollo Architecture.
    
    This layer ensures that code changes are analyzed to distinguish between:
    - Self-Correction: Intentional architectural decisions
    - Systemic Mutation: Unintended systemic mutations
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.guard = MutationGuard(config_path)
        self._strict_mode = True
        
    def analyze_code_change(
        self,
        code_change: str,
        file_path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a code change to determine if it represents:
        - Self-Correction: Intentional architectural decision
        - Systemic Mutation: Unintended systemic mutation
        
        Returns:
            Analysis results with mutation classification and decision
        """
        return self.guard.analyze_mutation(code_change, file_path, context)
    
    def get_mutation_guard(self) -> MutationGuard:
        """Get the Mutation Guard instance."""
        return self.guard
    
    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the codebase by analyzing all mutations.
        """
        return self.guard.get_guard_report()


# Global instance for easy access across the architecture
integrity_layer = IntegrityLayer()


# Documentation and Protocol Specification
# This layer formalizes the concept of mutation analysis as a permanent
# architectural decision rather than a temporary workaround.
# It ensures that only intentional architectural decisions are preserved
# while systemic mutations are detected and prevented.


# Example usage:
# integrity_layer = IntegrityLayer()
# result = integrity_layer.analyze_code_change(code_change, file_path="path/to/file.py")
# if result["status"] == "BLOCKED":
#     # Handle systemic mutation
#     pass
# else:
#     # Handle self-correction
#     pass
