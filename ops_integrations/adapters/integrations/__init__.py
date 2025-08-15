"""
Integration adapters for business systems and CRMs.

This module contains adapters for:
- CRM system integration
- Akaunting accounting system
- Inventory management
- Calendar system integration
"""

from . import crm
from . import akaunting
from . import inventory
from . import calender

__all__ = [
    'crm',
    'akaunting',
    'inventory',
    'calender'
] 