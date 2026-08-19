"""
Optimization Trigger Module
Evaluates system metrics against thresholds and triggers appropriate optimization actions based on resource pressure.
"""

from .optimization_trigger_lg import (
    OptimizationTrigger,
    IOptimizationTrigger,
    TriggerCondition,
    TriggerType,
    OptimizationAction,
    TriggerConfiguration,
    MetricThreshold,
    TriggerEvent,
    OptimizationContext
)

__all__ = [
    'OptimizationTrigger',
    'IOptimizationTrigger',
    'TriggerCondition',
    'TriggerType',
    'OptimizationAction',
    'TriggerConfiguration',
    'MetricThreshold',
    'TriggerEvent',
    'OptimizationContext'
]
