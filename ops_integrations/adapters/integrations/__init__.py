"""
Integration adapters for business systems and CRMs.

This module contains adapters for:
- CRM system integration
- Akaunting accounting system
"""

from . import crm
from . import akaunting

__all__ = [
    'crm',
    'akaunting'
] 