from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Currently used models
class Invoice(BaseModel):
    id: str
    customer_id: str
    amount: float
    status: str

class Customer(BaseModel):
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    # Simplified for current use - future expansion below
    # jobs: List[Job] = []
    # invoices: List[Invoice] = []
    # preferences: Dict[str, Any] = {}
    # notes: Optional[str] = None

# Future models - currently commented out
# class Part(BaseModel):
#     sku: str
#     description: str
#     stock_level: int
#     supplier: str
#     van_location: Optional[str]

# class Job(BaseModel):
#     id: str
#     customer_id: str
#     type: str
#     scheduled_time: Optional[str]
#     tech_id: Optional[str]
