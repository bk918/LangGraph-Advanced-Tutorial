import asyncio
from deep_researcher import deep_researcher
from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    question = "2025년 11월 기준, 국제 금융 흐름과 기조에 대해 미국의 달러를 중심으로 금리와 주식 그리고 비트코인, 부동산까지 포함하여 자세히 설명해주세요."
    result = asyncio.run(deep_researcher.ainvoke({"messages": {"role": "user", "content": question}}))
    print(result)