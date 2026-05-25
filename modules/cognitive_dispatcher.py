#!/usr/bin/env python3
"""
Cognitive Dispatcher (CDP) - Apollo Architecture

Routes tasks between Architect Tier (Deliberative/High-Cap) and Worker Tier (Reactive/Low-Cap)
based on task complexity analysis and resource availability.

Architecture:
- Architect Tier: High-compute, high-context, deep reasoning (30B+ models)
- Worker Tier: Low-compute, fast-response, reactive (0.6B-8B models)
"""

import os
import sys
import json
import time
import re
import uuid
from typing import Dict, Optional, Any, Literal
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from datetime import datetime
import threading

# Apollo imports
from modules.memory_core import vmm
from llm_interface import query_llm, DeploymentConfig, DEPLOYMENT_CONFIGS


class Tier(Enum):
    """Computational tiers for task routing."""
    ARCHITECT = "architect"  # High-compute, high-context, deep reasoning
    WORKER = "worker"        # Low-compute, fast-response, reactive


class TaskComplexity(Enum):
    """Task complexity classification."""
    TRIVIAL = "trivial"        # Simple lookup, reactive
    SIMPLE = "simple"           # Single-step, bounded
    MODERATE = "moderate"       # Multi-step, requires planning
    COMPLEX = "complex"         # Multi-step reasoning, requires architect
    UNKNOWN = "unknown"          # Complexity not yet determined


@dataclass
class TaskContext:
    """Context for a routed task."""
    task_id: str
    user_input: str
    complexity: TaskComplexity = TaskComplexity.UNKNOWN
    tier: Tier = Tier.WORKER  # Default to worker for unknown
    priority: int = 5  # 1-10, where 10 is highest
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    processing_time_ms: Optional[float] = None


class CognitiveDispatcher:
    """
    Routes tasks between Architect and Worker tiers based on complexity analysis.
    
    Architecture:
    - Architect Tier: Deliberative, high-capacity, deep reasoning (30B+ models)
    - Worker Tier: Reactive, low-capacity, fast-response (0.6B-8B models)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._architect_config = self._get_architect_config()
        self._worker_config = self._get_worker_config()
        
        # Task queues
        self._architect_queue = deque(maxlen=100)  # High-priority, complex tasks
        self._worker_queue = deque(maxlen=500)    # Low-priority, simple tasks
        
        # Metrics
        self._metrics = {
            "architect_tasks": 0,
            "worker_tasks": 0,
            "total_routing_time_ms": 0,
            "complexity_distribution": {}
        }
        
        # Thread safety
        self._lock = threading.Lock()
        
    def _get_architect_config(self) -> DeploymentConfig:
        """Returns the high-compute tier configuration."""
        # Architect tier: 30B+ models for deep reasoning
        return DeploymentConfig(
            url="http://127.0.0.1:8082/v1/chat/completions",
            model_name="Qwen3-Coder-30B-A3B-UD-IQ2_XXS",
            max_tokens=8192,
            temperature=0.6,
            stream_timeout=600
        )
    
    def _get_worker_config(self) -> DeploymentConfig:
        """Returns the low-compute tier configuration."""
        # Worker tier: 0.6B-8B models for fast reactive tasks
        return DeploymentConfig(
            url="http://127.0.0.1:8082/v1/chat/completions",
            model_name="Qwen3-0.6B-GGUF",
            max_tokens=2048,
            temperature=0.7,
            stream_timeout=60
        )
    
    def analyze_complexity(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> TaskComplexity:
        """
        Analyzes task complexity using heuristic rules and LLM triage.
        
        Heuristics:
        - TRIVIAL: Simple lookup, reactive, bounded scope
        - SIMPLE: Single-step, standard coding, fast scripts
        - MODERATE: Multi-step, requires planning, research
        - COMPLEX: Multi-step reasoning, deep architecture, CAD
        """
        # Heuristic analysis without LLM call (fast path)
        input_lower = user_input.lower()
        
        # TRIVIAL: Simple reactive tasks (factual questions)
        if any(word in input_lower for word in ['who', 'what', 'when', 'where']):
            if any(word in input_lower for word in ['is', 'are', 'was', 'were']):
                if any(word in input_lower for word in ['capital', 'population', 'date', 'time']):
                    return TaskComplexity.TRIVIAL
        
        # SIMPLE: Standard coding tasks
        if any(word in input_lower for word in ['write', 'code', 'script', 'python', 'bash']):
            if any(word in input_lower for word in ['simple', 'fast', 'quick', 'parse', 'csv']):
                return TaskComplexity.SIMPLE
        
        # MODERATE: Multi-step reasoning
        if any(word in input_lower for word in ['analyze', 'compare', 'evaluate', 'research']):
            return TaskComplexity.MODERATE
        
        # COMPLEX: Deep reasoning, architecture
        if any(word in input_lower for word in ['architect', 'refactor', 'system', 'design', 'cad']):
            if any(word in input_lower for word in ['complex', 'deep', 'structural', 'entire', 'comprehensive']):
                return TaskComplexity.COMPLEX
        
        # Fallback to LLM triage for ambiguous cases
        return self._llm_triage(user_input)
    
    def _llm_triage(self, user_input: str) -> TaskComplexity:
        """Use LLM to classify task complexity when heuristics fail."""
        prompt = f"""Classify the complexity of this task: {user_input}
        
        Return ONLY one of: TRIVIAL, SIMPLE, MODERATE, COMPLEX
        
        Guidelines:
        - TRIVIAL: Simple lookup, reactive, bounded scope
        - SIMPLE: Single-step, standard coding, fast scripts
        - MODERATE: Multi-step, requires planning, research
        - COMPLEX: Multi-step reasoning, deep architecture, CAD
        """
        
        try:
            # Fast inference with worker config
            response = query_llm(
                prompt=prompt,
                system_message="You are a task classifier. Return ONLY the complexity level.",
                config=self._worker_config,
                max_tokens=100
            )
            
            if "TRIVIAL" in response:
                return TaskComplexity.TRIVIAL
            elif "SIMPLE" in response:
                return TaskComplexity.SIMPLE
            elif "MODERATE" in response:
                return TaskComplexity.MODERATE
            else:
                return TaskComplexity.COMPLEX
                
        except Exception as e:
            # Fallback to COMPLEX for safety
            return TaskComplexity.COMPLEX
    
    def route_task(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> TaskContext:
        """
        Routes a task to the appropriate tier based on complexity analysis.
        
        Returns:
            TaskContext with routing decision and metadata
        """
        start_time = time.time()
        
        # Analyze complexity
        complexity = self.analyze_complexity(user_input, context)
        
        # Determine tier based on complexity
        if complexity in [TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE]:
            tier = Tier.WORKER
            priority = 3  # Low priority
        elif complexity == TaskComplexity.MODERATE:
            tier = Tier.WORKER
            priority = 5  # Medium priority
        else:  # COMPLEX
            tier = Tier.ARCHITECT
            priority = 8  # High priority
        
        # Create task context
        task = TaskContext(
            task_id=str(uuid.uuid4()),
            user_input=user_input,
            complexity=complexity,
            tier=tier,
            priority=priority,
            created_at=datetime.now()
        )
        
        # Queue management
        with self._lock:
            if tier == Tier.ARCHITECT:
                self._architect_queue.append(task)
                self._metrics["architect_tasks"] += 1
            else:
                self._worker_queue.append(task)
                self._metrics["worker_tasks"] += 1
        
        task.processing_time_ms = (time.time() - start_time) * 1000
        
        return task
    
    def execute_task(self, task: TaskContext) -> Dict[str, Any]:
        """
        Executes the task on the appropriate tier.
        """
        if task.tier == Tier.ARCHITECT:
            return self._execute_architect(task)
        else:
            return self._execute_worker(task)
    
    def _execute_architect(self, task: TaskContext) -> Dict[str, Any]:
        """Execute on Architect tier (high-compute, deep reasoning)."""
        # Architect tier: Deep reasoning, complex structural logic
        prompt = f"""You are the ARCHITECT (Qwen3-Coder 30B). 
        You handle complex structural logic, parametric CAD design (FeatureScript/OpenSCAD), 
        and large-scale refactoring. Think deeply about the system as a whole.
        
        Task: {task.user_input}
        """
        
        result = query_llm(
            prompt=prompt,
            system_message="You are the ARCHITECT. Think deeply and provide comprehensive analysis.",
            config=self._architect_config,
            max_tokens=8192
        )
        
        return {
            "tier": "architect",
            "result": result,
            "task_id": task.task_id,
            "complexity": task.complexity.value
        }
    
    def _execute_worker(self, task: TaskContext) -> Dict[str, Any]:
        """Execute on Worker tier (low-compute, fast-response)."""
        # Worker tier: Fast reactive tasks
        prompt = f"""You are a fast, reactive assistant. 
        Handle simple, single-step tasks efficiently.
        
        Task: {task.user_input}
        """
        
        result = query_llm(
            prompt=prompt,
            system_message="You are a fast, reactive assistant. Handle simple tasks efficiently.",
            config=self._worker_config,
            max_tokens=2048
        )
        
        return {
            "tier": "worker",
            "result": result,
            "task_id": task.task_id,
            "complexity": task.complexity.value
        }
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Returns statistics on queued tasks."""
        with self._lock:
            return {
                "architect_queue_size": len(self._architect_queue),
                "worker_queue_size": len(self._worker_queue),
                "metrics": self._metrics
            }
    
    def clear_queues(self):
        """Clears all task queues."""
        with self._lock:
            self._architect_queue.clear()
            self._worker_queue.clear()


# Global instance for singleton usage
dispatcher = CognitiveDispatcher()


def route(user_input: str, context: Optional[Dict[str, Any]] = None) -> TaskContext:
    """
    Convenience function to route a task.
    
    Args:
        user_input: The user's request/task description
        context: Optional context dictionary for additional metadata
        
    Returns:
        TaskContext with routing decision
    """
    return dispatcher.route_task(user_input, context)


def execute(user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function to route and execute a task.
    
    Args:
        user_input: The user's request/task description
        context: Optional context dictionary for additional metadata
        
    Returns:
        Execution result with tier and result
    """
    task = dispatcher.route_task(user_input, context)
    return dispatcher.execute_task(task)


# Example usage and testing
if __name__ == "__main__":
    print("Cognitive Dispatcher initialized.")
    print(f"Architect queue size: {len(dispatcher._architect_queue)}")
    print(f"Worker queue size: {len(dispatcher._worker_queue)}")
