import hashlib, json, shutil
from functools import lru_cache
from config import BASE_DIR, DATA_DIR, CHROMA_DIR, POLICY_DIR
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

COLLECTION_NAME="shopeasy_policies"
MANIFEST_PATH=CHROMA_DIR/"manifest.json"
EMBEDDING_MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device":"cpu"},
        encode_kwargs={"normalize_embeddings":True,"batch_size":8})

def load_policy_documents():
    if not POLICY_DIR.exists(): raise FileNotFoundError(f"Missing {POLICY_DIR}")
    docs=[]
    for path in sorted(POLICY_DIR.glob("*.txt")):
        text=path.read_text(encoding="utf-8").strip()
        if text: docs.append(Document(page_content=text,metadata={"source":path.name,"policy_name":path.stem}))
    if not docs: raise ValueError("No non-empty .txt policy files in data/policies.")
    return docs

def _fingerprint(docs):
    h=hashlib.sha256()
    for d in docs: h.update(d.metadata["source"].encode()); h.update(b"\0"); h.update(d.page_content.encode()); h.update(b"\0")
    return h.hexdigest()

def split_policy_documents(docs):
    splitter=RecursiveCharacterTextSplitter(chunk_size=700,chunk_overlap=100,
        separators=["\n\n","\n",". "," ",""],add_start_index=True)
    return splitter.split_documents(docs)

def build_or_load_vectorstore():
    docs=load_policy_documents(); fingerprint=_fingerprint(docs); manifest=None
    if MANIFEST_PATH.exists():
        try: manifest=json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): pass
    rebuild=(not manifest or manifest.get("fingerprint")!=fingerprint
             or manifest.get("embedding_model")!=EMBEDDING_MODEL_NAME
             or not CHROMA_DIR.exists())
    if rebuild:
        if CHROMA_DIR.exists(): shutil.rmtree(CHROMA_DIR)
        CHROMA_DIR.mkdir(parents=True,exist_ok=True)
        chunks=split_policy_documents(docs)
        store=Chroma.from_documents(chunks,get_embeddings(),collection_name=COLLECTION_NAME,
                                    persist_directory=str(CHROMA_DIR))
        MANIFEST_PATH.write_text(json.dumps({"fingerprint":fingerprint,
            "embedding_model":EMBEDDING_MODEL_NAME,"chunk_count":len(chunks)},indent=2),encoding="utf-8")
        return store
    store=Chroma(collection_name=COLLECTION_NAME,persist_directory=str(CHROMA_DIR),
                 embedding_function=get_embeddings())
    if store._collection.count()==0:
        shutil.rmtree(CHROMA_DIR,ignore_errors=True)
        return build_or_load_vectorstore()
    return store

def retrieve_policy_context(question,k=4):
    if not question.strip(): return []
    store=build_or_load_vectorstore()
    return [{"content":d.page_content,"source":d.metadata.get("source","unknown"),
             "policy_name":d.metadata.get("policy_name","unknown"),"distance":float(score)}
            for d,score in store.similarity_search_with_score(question,k=k)]
