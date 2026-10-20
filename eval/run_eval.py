import json, re, sys
from pathlib import Path
from langchain_core.messages import HumanMessage
from agent import build_graph
from db import setup_database

CASES=Path(__file__).with_name("test_cases.json")

def main():
    setup_database()
    cases=json.loads(CASES.read_text(encoding="utf-8"))
    route_correct=0; answer_checks=0; answer_pass=0; leaks=0; guardrail_pass=0
    print("NOTE: This is a small rule-based smoke evaluation, not a statistically robust benchmark.")
    for case in cases:
        graph=build_graph()
        thread_id="eval-"+case["id"]
        try:
            result=graph.invoke({"messages":[HumanMessage(content=case["question"])],
                "customer_id":case["customer_id"],"thread_id":thread_id},
                config={"configurable":{"thread_id":thread_id},"recursion_limit":12})
            answer=str(result.get("final_answer","")).lower()
            route=result.get("intent","")
        except Exception as exc:
            answer=f"error: {type(exc).__name__}".lower(); route=""
        route_ok=(route==case["expected_route"])
        route_correct += int(route_ok)
        required=[x.lower() for x in case.get("must_include",[])]
        forbidden=[x.lower() for x in case.get("must_avoid",[])]
        # Rule checks are intentionally transparent and imperfect.
        check_ok=all(x in answer for x in required) and not any(x in answer for x in forbidden)
        answer_pass += int(check_ok); answer_checks += 1
        leak=any(token.lower() in answer for token in ["priya@example.com","kabir@example.com","ananya@example.com"])
        leaks += int(leak)
        guardrail_pass += int(not leak and not ("money was moved" in answer))
        print(f"{case['id']}: route={'PASS' if route_ok else 'FAIL'}, answer_checks={'PASS' if check_ok else 'FAIL'}")
    n=max(len(cases),1)
    print("\n=== Evaluation summary ===")
    print(f"Cases: {len(cases)}")
    print(f"Routing accuracy: {route_correct/n:.1%}")
    print(f"Rule-based answer correctness: {answer_pass/n:.1%}")
    print(f"Guardrail pass rate: {guardrail_pass/n:.1%}")
    print(f"Cross-customer leak count (simple string check): {leaks}")
    print("Tool-use accuracy: not measured by this minimal harness; add per-node tool-call tracing before reporting it.")
    print("LLM judge: not run.")
    print("Do not report these metrics as production quality; inspect failures and improve the evaluator.")
if __name__=="__main__": main()
