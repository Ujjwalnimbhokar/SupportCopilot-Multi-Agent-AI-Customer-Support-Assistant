import json
from langchain.tools import tool
from db import get_order_for_customer, list_orders_for_customer, create_ticket

def make_order_tools(trusted_customer_id: str):
    """Create tools whose customer identity is bound by trusted application code."""
    @tool
    def get_order_status(order_id: int) -> str:
        """Look up status and details for one order belonging to the logged-in customer.
        Use for questions about a specific order. Supply only the numeric order ID.
        Never request or accept a customer ID from the customer."""
        try:
            order=get_order_for_customer(order_id,trusted_customer_id)
            if not order:
                return json.dumps({"ok":False,"message":"Order not found for the logged-in customer."})
            order.pop("notes",None)
            return json.dumps({"ok":True,"order":order})
        except Exception:
            return json.dumps({"ok":False,"message":"Order lookup failed. Please try again."})

    @tool
    def list_my_orders() -> str:
        """List the logged-in customer's own orders. Use when asked to list or summarize
        their orders. Customer identity is supplied by the trusted application."""
        try:
            return json.dumps({"ok":True,"orders":list_orders_for_customer(trusted_customer_id)})
        except Exception:
            return json.dumps({"ok":False,"message":"Order listing failed. Please try again."})

    @tool
    def create_support_ticket(reason: str, order_id: int | None = None) -> str:
        """Create a support ticket for the logged-in customer. Use when a customer needs
        follow-up or a policy does not cover their issue. If an order ID is supplied,
        the database verifies ownership before creating the ticket."""
        try:
            return json.dumps(create_ticket(trusted_customer_id,order_id,reason))
        except Exception:
            return json.dumps({"ok":False,"message":"Ticket creation failed. Please try again."})

    return [get_order_status,list_my_orders,create_support_ticket]
