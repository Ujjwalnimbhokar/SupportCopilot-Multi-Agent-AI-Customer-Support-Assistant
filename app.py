from dotenv import load_dotenv
load_dotenv()

import uuid
import traceback
from numpy import e
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from config import MODEL_NAME, GROQ_API_KEY, LANGCHAIN_API_KEY, LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT
from db import setup_database, get_customer_list, list_pending_approvals, get_approval, set_approval_status
from agent import build_graph
from rag import build_or_load_vectorstore



st.set_page_config(page_title="SupportCopilot | ShopEasy",page_icon="🛟",layout="wide")

@st.cache_resource
def resources():
    setup_database()
    build_or_load_vectorstore()
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    from config import DB_PATH
    conn=sqlite3.connect(DB_PATH,check_same_thread=False)
    checkpointer=SqliteSaver(conn)
    checkpointer.setup()
    graph=build_graph(checkpointer=checkpointer)
    return graph, conn

try:
    graph, _checkpointer_conn = resources()
except Exception as exc:
    st.error("SupportCopilot could not initialize. Check dependencies, policy files, and local configuration.")
    st.caption(f"Startup detail: {type(exc).__name__}")
    st.stop()

if "customer_id" not in st.session_state: st.session_state.customer_id=None
if "thread_id" not in st.session_state: st.session_state.thread_id=str(uuid.uuid4())
if "chat_history" not in st.session_state: st.session_state.chat_history=[]

with st.sidebar:
    st.title("SupportCopilot")
    customers=get_customer_list()
    choices={f"{c['name']} ({c['customer_id']})":c["customer_id"] for c in customers}
    selected=st.selectbox("Demo login",list(choices),index=0)
    new_customer=choices[selected]
    if st.session_state.customer_id != new_customer:
        st.session_state.customer_id=new_customer
        st.session_state.thread_id=str(uuid.uuid4())
        st.session_state.chat_history=[]
    if st.button("New conversation",use_container_width=True):
        st.session_state.thread_id=str(uuid.uuid4())
        st.session_state.chat_history=[]
        st.rerun()
    st.caption(f"Model: {MODEL_NAME}")
    st.caption("Status: configured" if GROQ_API_KEY else "Status: missing Groq API key")
    if LANGCHAIN_TRACING_V2.lower()=="true" and LANGCHAIN_API_KEY:
        st.caption(f"LangSmith project: {LANGCHAIN_PROJECT}")

chat_tab, approval_tab=st.tabs(["Customer Chat","Human Agent Dashboard"])
with chat_tab:
    st.subheader("ShopEasy customer support")
    for item in st.session_state.chat_history:
        with st.chat_message(item["role"]): st.markdown(item["content"])
    prompt=st.chat_input("Ask about an order, return, refund, shipping, or warranty")
    if prompt:
        st.session_state.chat_history.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            status=st.empty(); answer_area=st.empty()
            config={"configurable":{"thread_id":st.session_state.thread_id},
                    "recursion_limit":12,
                    "configurable": {"thread_id": st.session_state.thread_id,
                                     "customer_id": st.session_state.customer_id}}
            input_state={"messages":[HumanMessage(content=prompt)],
                         "customer_id":st.session_state.customer_id,
                         "thread_id":st.session_state.thread_id}
            final_text=""
            try:
                for update in graph.stream(input_state,config=config,stream_mode="updates"):
                    for node, payload in update.items():
                        status.info(f"Working: {node.replace('_',' ').title()}...")
                        if "__interrupt__" in payload:
                            status.warning("Waiting for human approval. Open the Human Agent Dashboard.")
                        for msg in payload.get("messages",[]):
                            if isinstance(msg,AIMessage) and not getattr(msg,"tool_calls",None):
                                final_text=str(msg.content)
                snapshot=graph.get_state(config)
                if snapshot and snapshot.tasks:
                    for task in snapshot.tasks:
                        if getattr(task,"interrupts",None):
                            status.warning("Waiting for human approval. Check the Human Agent Dashboard.")
                if not final_text:
                    final_text="Your request is waiting for review, or I couldn't produce a final answer yet."
                answer_area.markdown(final_text)
            except Exception:
                     print("SUPPORTCOPILOT ERROR:", repr(e))
                     traceback.print_exc()
                     final_text = "Sorry, the support service encountered an error. Please try again later."
                     answer_area.markdown(final_text)
        st.session_state.chat_history.append({"role":"assistant","content":final_text})

with approval_tab:
    st.subheader("Pending refund approvals")
    pending=list_pending_approvals()
    if not pending: st.info("No pending approvals.")
    for approval in pending:
        with st.container(border=True):
            st.markdown(f"**Approval:** `{approval['approval_id']}`")
            st.write(f"Customer: {approval['customer_id']} · Order: {approval['order_id']}")
            st.write(f"Amount: ${approval['amount']:.2f}")
            st.write(f"Reason: {approval['reason']}")
            st.caption(approval["explanation"])
            note=st.text_input("Human review note",key=f"note_{approval['approval_id']}")
            col1,col2=st.columns(2)
            with col1:
                if st.button("Approve",key=f"approve_{approval['approval_id']}",use_container_width=True):
                    try:
                        set_approval_status(approval["approval_id"],"approved",note)
                        config={"configurable":{"thread_id":approval["thread_id"]},"recursion_limit":12}
                        result=graph.invoke(Command(resume={"approved":True,"note":note}),config=config)
                        st.success("Approval submitted and graph resumed.")
                    except Exception:
                        st.error("Could not resume the workflow. Check the server logs and graph checkpoint.")
                    st.rerun()
            with col2:
                if st.button("Reject",key=f"reject_{approval['approval_id']}",use_container_width=True):
                    try:
                        set_approval_status(approval["approval_id"],"rejected",note)
                        config={"configurable":{"thread_id":approval["thread_id"]},"recursion_limit":12}
                        result=graph.invoke(Command(resume={"approved":False,"note":note}),config=config)
                        st.success("Rejection submitted and graph resumed.")
                    except Exception:
                        st.error("Could not resume the workflow. Check the server logs and graph checkpoint.")
                    st.rerun()
