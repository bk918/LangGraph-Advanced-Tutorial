import os
from pathlib import Path
from typing import TypedDict, Annotated
from langchain.agents import create_agent
from langchain.tools import ToolRuntime
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend

# PROJECT_ROOT 동적 결정: 환경 변수 또는 현재 작업 디렉토리
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", os.getcwd()))
WORKSPACE_DIR = PROJECT_ROOT / "workspace"

# workspace 디렉토리 자동 생성
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# CompositeBackend 경로 규칙을 명시하는 System Prompt
FILE_STORAGE_RULES = """
## 파일 저장 위치 규칙

파일을 생성하거나 편집할 때 **반드시** 아래 경로 규칙을 따라야 합니다.

<영구 저장 (실제 디스크에 저장)>
- **경로**: `/workspace/`로 시작하는 모든 파일
- **예시**: 
  - `/workspace/data.csv` - 데이터 파일
  - `/workspace/reports/analysis.md` - 분석 보고서
  - `/workspace/output/results.json` - 처리 결과
- **용도**: 
  - 사용자에게 전달해야 하는 최종 결과물
  - 장기 보관이 필요한 데이터
  - 외부 프로그램과 공유할 파일
  - 다음 세션에서도 접근해야 하는 파일
</영구 저장>

<임시 저장 (메모리/세션에만 저장)>
- **경로**: `/workspace/` 이외의 모든 경로
- **예시**: 
  - `/temp/notes.txt` - 임시 메모
  - `/scratch/intermediate.json` - 중간 처리 결과
  - `/cache/processed_data.csv` - 캐시 데이터
- **용도**: 
  - 일시적인 작업 파일
  - 중간 계산 결과
  - 디버깅용 임시 파일
- **주의**: 세션 종료 시 **자동으로 삭제**됩니다!
</임시 저장>

<사용 가이드>
1. **영구 보관 필요**: 반드시 `/workspace/` 사용
2. **임시 작업**: `/temp/`, `/scratch/`, `/cache/` 등 자유롭게 사용
3. **불확실한 경우**: 영구 저장(`/workspace/`)이 안전합니다
</사용 가이드>

<예시 시나리오>
- 사용자가 "데이터 분석 결과를 저장해줘" → `/workspace/analysis_result.csv` 
- 중간 계산용 임시 파일 → `/temp/calculation_step1.json` 
- 최종 보고서 생성 → `/workspace/reports/final_report.md` 
</예시 시나리오>
"""

fake_model = FakeChatModel()
real_model = ChatOpenAI(model="gpt-4.1", temperature=0.3)

agent = create_agent(fake_model, [])


# CompositeBackend 설정: State와 FileSystem을 동시에 사용
def create_composite_backend(runtime):
    """
    CompositeBackend를 생성하는 팩토리 함수

    - /temp/* 경로: LangGraph State에 저장 (휘발성)
    - /workspace/* 경로: 파일시스템에 저장 (영구적)
    - 기타 경로: State에 저장 (기본)
    """
    # 기본 백엔드: LangGraph State 사용
    state_backend = StateBackend(runtime)

    # 파일 시스템 백엔드: 실제 디스크에 저장
    filesystem_backend = FilesystemBackend(
        root_dir=WORKSPACE_DIR,
        virtual_mode=True,  # 보안을 위해 루트 디렉토리 밖으로 나가지 못하게 제한
    )

    # CompositeBackend 구성
    # routes: 특정 경로 접두어를 특정 백엔드로 라우팅
    composite = CompositeBackend(
        default=state_backend,  # 매칭되지 않는 경로는 State 사용
        routes={
            "/workspace/": filesystem_backend,  # /workspace/* 는 파일시스템
        },
    )

    return composite


# 이건 기본 라이브러리를 활용해서 만든 것.
# 장점: 바로 쓰기는 쉬움 - 입문용
# 단점: 자유도가 매우 떨어짐 - Enterprise 에서는 부적절함 >> 라이브러리 소스코드를 드린 이유?
deep_agent = create_deep_agent(
    real_model,
    [],
    backend=create_composite_backend,  # 함수 자체를 전달 (호출하지 않음!)
    system_prompt=FILE_STORAGE_RULES,  # 파일 저장 규칙을 시스템 프롬프트로 전달
)


class SampleState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


workflow = StateGraph(state_schema=SampleState)
workflow.add_node("첫번째", lambda x: x)
workflow.add_node("두번째", agent)
workflow.add_node("세번째", deep_agent)

workflow.set_entry_point("첫번째")
workflow.add_edge("첫번째", "두번째")
workflow.add_edge("두번째", "세번째")
workflow.set_finish_point("세번째")

sample_graph = workflow.compile()
