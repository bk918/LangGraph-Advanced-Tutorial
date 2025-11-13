import asyncio
from deep_researcher import deep_researcher
from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    result = asyncio.run(deep_researcher.ainvoke({"messages": {"role": "user", "content": "LangGraph, LangChain 그리고 DeepAgents 와의 관계에 대해 2025년 11월 기준 지식으로 정리해주세요."}}))
    print(result)