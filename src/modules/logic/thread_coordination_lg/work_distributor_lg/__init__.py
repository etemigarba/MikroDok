"""
MikroDok Work Distributor Package
Provides work distribution and load balancing across available threads.
"""

from .work_distributor_lg import WorkDistributor

__all__ = [
    'WorkDistributor'
]
