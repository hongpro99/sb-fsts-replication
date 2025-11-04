# llm/agents/rag_agent.py
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI, AzureChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma


def _get_vectorstore(persist_dir="./.chromadb/local-rag", collection_name="local-rag"):
    """증분 인덱싱된 로컬 VectorStore 로드"""
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    return Chroma(
        collection_name=collection_name,
        persist_directory=persist_dir,
        embedding_function=embeddings,
    )
    
def rag_agent(state: dict):
    """
    LangGraph node: Drive 문서 기반 RAG 응답 생성.
    입력: state["input"]
    출력: state["response"], state["handled_by"]
    """
    print("---RAG Agent---")
    q = state.get("input", "")
    vs = _get_vectorstore()
        
    docs = vs.similarity_search(q, k=8)
    if not docs:
        answer = "관련 문서를 찾을 수 없습니다."
    else:
        context = "\n\n".join(doc.page_content for doc in docs[:6])

    prompt = f"""
    당신은 주식 투자 및 리서치 문서를 분석하는 전문가입니다.
    문서 내용을 참고하여 사용자의 질문에 정확하고 간결하게 답변하세요.
    특정 문서에 대해 질문하면 그 문서에 해당하는 내용만 답변해야 합니다.

    [문서 내용]
    {context}

    [질문]
    {q}
    """
    
    #llm 설정
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        azure_endpoint="https://sb-azure-openai-studio.openai.azure.com/",
        api_version="2024-10-21",
        temperature=0
        )
    answer = llm.invoke(prompt).content

    return {**state, "response": answer, "handled_by": "rag_agent"}
