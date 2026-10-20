from db import setup_database
from nodes.faq import answer_faq

def main():
    setup_database()
    print("ShopEasy FAQ. Type exit to quit.")
    while True:
        question=input("\nYou: ").strip()
        if question.lower() in {"exit","quit"}: break
        result=answer_faq(question)
        print("\nSupportCopilot:",result["answer"])
        for d in result["retrieved_docs"]:
            print(f"- source={d['source']} distance={d['distance']:.4f}")
if __name__=="__main__": main()
