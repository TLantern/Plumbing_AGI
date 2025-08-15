# Inventory Adapter - Currently disabled, will be implemented later
# import httpx
# from ops_integrations.models import Part
# import os

# class InventoryAdapter:
#     def __init__(self):
#         self.client = httpx.Client()
#         self.api_url = os.getenv('SUPPLIER_API_URL')
#         self.api_key = os.getenv('SUPPLIER_API_KEY')

#     def get_stock(self, sku: str) -> Part:
#         # TODO: fetch stock info
#         return Part(sku=sku, description="", stock_level=0, supplier="")

#     def reorder_part(self, part: Part, qty: int) -> None:
#         # TODO: place reorder
#         pass

# Placeholder class for current implementation
class InventoryAdapter:
    def __init__(self):
        pass  # Inventory integration disabled for now 