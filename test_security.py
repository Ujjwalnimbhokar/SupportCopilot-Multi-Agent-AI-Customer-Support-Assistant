import json
from db import setup_database,get_order_for_customer
from tools import make_order_tools

def run_tests():
    setup_database()
    assert get_order_for_customer(1042,"CUST001") is not None
    assert get_order_for_customer(1043,"CUST001") is None
    get_status,list_orders,_=make_order_tools("CUST001")
    denied=json.loads(get_status.invoke({"order_id":1043}))
    assert denied["ok"] is False and "order" not in denied
    listed=json.loads(list_orders.invoke({}))
    assert all(o["order_id"] != 1043 for o in listed["orders"])
    print("PASS: own order accessible")
    print("PASS: cross-customer order denied")
    print("PASS: list restricted to logged-in customer")
if __name__=="__main__": run_tests()
