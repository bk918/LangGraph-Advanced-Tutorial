"""separate_agent.py 테스트 러너 - 모듈화된 구현 테스트"""

import asyncio
import sys
import time
from pathlib import Path

# .env 로드
from dotenv import load_dotenv
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# 로컬 imports
from langchain_core.tools import tool
from utils import tavily_search, think_tool
from state import ResearchComplete
from separate_agent import create_deep_research_agent
from langchain_core.runnables import RunnableConfig


async def main():
    question = "LangChain 및 LangGraph가 V1.0이 되면서 변경된 사항에 대해 꼼꼼하게 조사해줘."

    start_time = time.time()

    tools = [tavily_search, think_tool, tool(ResearchComplete)]

    agent = await create_deep_research_agent(
        tools=tools,
        model="openai:gpt-4.1",
        max_researcher_iterations=3,
        enable_critique=True,
        enable_clarification=False,
    )

    config = RunnableConfig(
        configurable={"thread_id": "test_separate"},
        recursion_limit=100,
    )

    # 스트리밍 방식으로 실행하여 중간 과정 확인
    step_count = 0
    print("\n[그래프 실행 과정]")
    async for event in agent.astream(
        {"messages": [{"role": "user", "content": question}]},
        config=config,
        stream_mode="updates",
    ):
        step_count += 1
        print(f"\n--- Step {step_count} ---")
        for node_name, node_output in event.items():
            print(f"Node: {node_name}")
            if node_output and "messages" in node_output:
                msgs = node_output["messages"]
                if msgs:
                    last_msg = msgs[-1] if isinstance(msgs, list) else msgs
                    msg_type = getattr(last_msg, '__class__', type(last_msg)).__name__
                    print(f"  Message type: {msg_type}")

    # 스트림 완료 후 최종 state 가져오기
    final_state = await agent.aget_state(config)
    result = final_state.values  # 전체 state 가져오기

    elapsed_time = time.time() - start_time

    # 결과 추출
    final_report = result.get("files", {}).get("/output/final_report.md", {}).get("content", [])
    report_text = "\n".join(final_report) if final_report else "보고서 없음"

    current_stage = result.get("files", {}).get("/status/current_stage.txt", {}).get("content", [])
    stage_text = "\n".join(current_stage) if current_stage else "알 수 없음"

    print("\n" + "=" * 80)
    print("결과")
    print("=" * 80)
    print(f"실행 시간: {elapsed_time:.2f}초")
    print(f"현재 단계: {stage_text}")
    print(f"보고서 길이: {len(report_text):,} 문자")
    print(f"생성된 파일 수: {len(result.get('files', {}))}")

    print("\n" + "=" * 80)
    print("보고서 미리보기 (처음 1000자)")
    print("=" * 80)
    print(report_text[:1000] + "..." if len(report_text) > 1000 else report_text)

    # 전체 보고서 및 실행 로그 저장
    from datetime import datetime
    dt = datetime.now().isoformat()
    with open(f"separate_result_{dt}.txt", "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write("SEPARATE_AGENT 실행 결과\n")
        f.write("="*80 + "\n\n")
        f.write(f"연구 질문: {question}\n")
        f.write(f"실행 시간: {elapsed_time:.2f}초\n")
        f.write(f"총 실행 단계: {step_count}\n")
        f.write(f"현재 단계: {stage_text}\n")
        f.write(f"생성된 파일 수: {len(result.get('files', {}))}\n")
        f.write(f"보고서 길이: {len(report_text):,} 문자\n")

        # 파일 목록
        f.write(f"\n{'='*80}\n생성된 파일 목록\n{'='*80}\n")
        for file_path in sorted(result.get('files', {}).keys()):
            f.write(f"  - {file_path}\n")

        # 전체 보고서
        f.write(f"\n{'='*80}\n전체 보고서\n{'='*80}\n\n")
        f.write(report_text)

    print("\n전체 보고서 저장됨: separate_result.txt")
    print("\nseparate_agent 실행 성공!")

    return result


if __name__ == "__main__":
    asyncio.run(main())
