from langchain_core.messages import HumanMessage, AIMessage
from config import MAX_AGENT_STEPS, GROQ_API_KEY
from db import setup_database, get_customer_list
from agent import build_graph
import uuid

def main():
    setup_database()
    if not GROQ_API_KEY:
        print("Missing GROQ_API_KEY. Add it to .env."); return
    customers=get_customer_list()
    print("=== ShopEasy SupportCopilot ===")
    for i,c in enumerate(customers,1): print(f"{i}. {c['name']} ({c['customer_id']})")
    try: customer=customers[int(input("Select customer number: ").strip())-1]
    except (ValueError,IndexError): print("Invalid selection."); return
    thread_id=str(uuid.uuid4()); graph=build_graph()
    print(f"Logged in as {customer['name']}. Type exit to quit.")
    while True:
        q=input("\nYou: ").strip()
        if q.lower() in {"exit","quit"}: break
        config={"configurable":{"thread_id":thread_id},"recursion_limit":MAX_AGENT_STEPS}
        try:
            result=graph.invoke({"messages":[HumanMessage(content=q)],"customer_id":customer["customer_id"],"thread_id":thread_id},config=config)
            print("\nSupportCopilot:",result.get("final_answer") or result["messages"][-1].content)
        except Exception:
            print("Sorry, the support service encountered an error. Check configuration and try again.")
if __name__=="__main__": main()
