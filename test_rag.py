from db import setup_database
from rag import retrieve_policy_context

def check(query,needle,source):
    docs=retrieve_policy_context(query,k=4)
    text=" ".join(d["content"].lower() for d in docs)
    assert needle.lower() in text, f"Missing {needle!r}"
    assert any(d["source"]==source for d in docs), f"Missing source {source}"

if __name__=="__main__":
    setup_database()
    check("How many days to return a laptop?","15 calendar days","return_policy.txt")
    check("What evidence for damaged item refund?","30 calendar days","refund_policy.txt")
    print("PASS: laptop return policy retrieval")
    print("PASS: damaged item refund policy retrieval")
