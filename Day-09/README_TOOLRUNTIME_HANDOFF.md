# ToolRuntime을 활용한 Custom Hand-off 도구 구현

## 🎯 핵심 인사이트

**ToolRuntime**을 사용하면 `InjectedState`, `InjectedToolCallId` 같은 복잡한 Annotated 타입 없이도 **단일 매개변수**로 모든 컨텍스트에 접근할 수 있습니다!

```python
# ❌ 기존 방식 (복잡함)
@tool
def handoff(
    instruction: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    ...

# ✅ ToolRuntime 방식 (간단!)
@tool
def handoff(
    instruction: str,
    runtime: ToolRuntime,  # 이것만 있으면 됨!
) -> Command:
    state = runtime.state
    tool_call_id = runtime.tool_call_id
    ...
```

## 📚 ToolRuntime이란?

**ToolRuntime**은 LangChain v1.0+에서 도입된 표준 컨텍스트 객체로, 도구 실행 시 필요한 모든 정보를 담고 있습니다.

### 접근 가능한 속성

```python
class ToolRuntime:
    state: StateT              # 현재 그래프 상태
    tool_call_id: str | None   # 도구 호출 ID
    config: RunnableConfig     # 실행 설정
    context: ContextT          # 런타임 컨텍스트
    store: BaseStore | None    # 영구 저장소
    stream_writer: StreamWriter # 스트림 출력
```

### 사용 방법

```python
from langchain_core.tools import tool
from langchain.tools import ToolRuntime

@tool
def my_tool(x: int, runtime: ToolRuntime) -> str:
    # State 접근
    messages = runtime.state["messages"]
    
    # Tool Call ID 접근
    print(f"Tool call ID: {runtime.tool_call_id}")
    
    # Config 접근
    run_id = runtime.config.get("run_id")
    
    # Store 사용 (영구 저장)
    runtime.store.put(("metrics",), "count", 1)
    
    # 스트림 출력
    runtime.stream_writer.write("Processing...")
    
    return f"Processed {x}"
```

## 🚀 Custom Hand-off 도구 구현

### 1단계: Hand-off 도구 생성 함수

```python
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime
from langgraph.types import Command

def create_custom_handoff_tool(
    subagent_name: str,
    allowed_state_keys: list[str],
    description: str,
):
    """
    필요한 정보만 선택적으로 전달하는 hand-off 도구
    """
    tool_name = f"delegate_to_{subagent_name}"
    
    @tool(tool_name, description=description)
    def handoff_to_subagent(
        instruction: str,
        runtime: ToolRuntime,  # ✨ 핵심!
    ) -> Command:
        # 1. 필요한 state 키만 필터링
        filtered_state = {
            k: v for k, v in runtime.state.items()
            if k in allowed_state_keys
        }
        
        # 2. instruction을 새 메시지로 추가
        filtered_state["messages"] = [
            HumanMessage(content=instruction)
        ]
        
        # 3. ToolMessage 생성
        tool_message = ToolMessage(
            content=f"Successfully delegated to {subagent_name}",
            name=tool_name,
            tool_call_id=runtime.tool_call_id,
        )
        
        # 4. Command로 서브에이전트에 라우팅
        return Command(
            goto=subagent_name,
            update={
                **filtered_state,
                "messages": runtime.state["messages"] + [tool_message],
            },
        )
    
    return handoff_to_subagent
```

### 2단계: 서브에이전트 생성

```python
from deepagents import create_deep_agent

# 데이터 분석 전문 에이전트 (files만 접근 가능)
analyst = create_deep_agent(
    model="gpt-4",
    tools=[...],
    system_prompt="""
    You are a Data Analyst.
    You ONLY have access to files.
    You do NOT have access to user_data.
    """,
    backend=create_composite_backend,
    name="data_analyst",
)

# 연구 전문 에이전트 (analysis_results만 접근 가능)
researcher = create_deep_agent(
    model="gpt-4",
    tools=[...],
    system_prompt="""
    You are a Researcher.
    You ONLY have access to analysis_results.
    You do NOT have access to files or user_data.
    """,
    backend=create_composite_backend,
    name="researcher",
)
```

### 3단계: Hand-off 도구 생성

```python
# Analyst에게 위임하는 도구 (files만 전달)
delegate_to_analyst = create_custom_handoff_tool(
    subagent_name="data_analyst",
    allowed_state_keys=["files"],  # ✨ files만!
    description=(
        "Delegate data analysis tasks to the Data Analyst. "
        "The analyst ONLY has access to files, not user_data."
    ),
)

# Researcher에게 위임하는 도구 (analysis_results만 전달)
delegate_to_researcher = create_custom_handoff_tool(
    subagent_name="researcher",
    allowed_state_keys=["analysis_results"],  # ✨ analysis_results만!
    description=(
        "Delegate research tasks to the Researcher. "
        "The researcher ONLY has access to analysis results."
    ),
)
```

### 4단계: 메인 에이전트 생성

```python
# 메인 에이전트에 hand-off 도구 추가
main_agent = create_deep_agent(
    model="gpt-4",
    tools=[delegate_to_analyst, delegate_to_researcher],
    system_prompt="""
    You are the Main Orchestrator.
    
    Available sub-agents:
    - delegate_to_data_analyst: For data analysis (has file access)
    - delegate_to_researcher: For research (has analysis results access)
    
    Choose the right sub-agent based on the task.
    """,
    backend=create_composite_backend,
    name="main_orchestrator",
)
```

### 5단계: StateGraph 통합

```python
from langgraph.graph import StateGraph, START

# State 정의
class MainAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    files: dict
    user_data: dict  # 민감 정보
    analysis_results: list[str]

# 그래프 생성
workflow = StateGraph(state_schema=MainAgentState)

# 노드 추가
workflow.add_node("main_orchestrator", main_agent)
workflow.add_node("data_analyst", analyst)
workflow.add_node("researcher", researcher)

# 엣지 설정
workflow.add_edge(START, "main_orchestrator")
workflow.add_edge("data_analyst", "main_orchestrator")  # 완료 후 메인으로
workflow.add_edge("researcher", "main_orchestrator")

# 컴파일
app = workflow.compile()
```

## 💡 실제 사용 시나리오

### 시나리오: 데이터 분석 파이프라인

```python
# 초기 상태
initial_state = {
    "messages": [
        HumanMessage(content="Analyze sales data and provide insights")
    ],
    "files": {},  # 파일 시스템
    "user_data": {  # 민감 정보
        "user_id": "12345",
        "email": "user@example.com",
        "api_key": "secret_xxx",
    },
    "analysis_results": [],
}

# 실행
result = app.invoke(initial_state)
```

### 실행 흐름

```
1. Main Orchestrator
   ↓ delegate_to_data_analyst(instruction="Analyze sales data")
   ↓ filtered_state = {"files": {...}}  # user_data 제외!
   
2. Data Analyst
   - files 접근 가능 ✅
   - user_data 접근 불가 ❌ (전달되지 않음!)
   ↓ 분석 완료
   
3. Main Orchestrator (복귀)
   ↓ delegate_to_researcher(instruction="Synthesize findings")
   ↓ filtered_state = {"analysis_results": [...]}  # files 제외!
   
4. Researcher
   - analysis_results 접근 가능 ✅
   - files 접근 불가 ❌
   - user_data 접근 불가 ❌
   ↓ 연구 완료
   
5. Main Orchestrator (최종 복귀)
   → 최종 결과 반환
```

## 🔒 보안 강화

### 정보 분리 전략

```python
# 민감도 레벨별 에이전트 구성
security_levels = {
    "public": ["messages", "analysis_results"],
    "internal": ["messages", "analysis_results", "files"],
    "sensitive": ["messages", "user_data", "api_credentials"],
}

# 레벨별 hand-off 도구 생성
for level, allowed_keys in security_levels.items():
    create_custom_handoff_tool(
        subagent_name=f"{level}_agent",
        allowed_state_keys=allowed_keys,
        description=f"Delegate to {level} level agent",
    )
```

## 📊 비교: 3가지 접근 방식

### 1️⃣ DeepAgent SubAgentMiddleware (기본)

```python
deep_agent = create_deep_agent(
    model,
    tools,
    subagents=[{
        "name": "analyst",
        "description": "...",
        "system_prompt": "...",
    }]
)
```

**장점**: 간단, 빠른 설정
**단점**: 전체 state 전달, 정보 제어 불가

### 2️⃣ InjectedState + InjectedToolCallId

```python
@tool
def handoff(
    instruction: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    ...
```

**장점**: 정보 제어 가능
**단점**: Annotated 래퍼 복잡, 타입 힌트 장황

### 3️⃣ ToolRuntime (✨ 권장!)

```python
@tool
def handoff(
    instruction: str,
    runtime: ToolRuntime,
) -> Command:
    state = runtime.state
    tool_call_id = runtime.tool_call_id
    ...
```

**장점**: 
- ✅ 단일 매개변수로 깔끔
- ✅ 타입 안전
- ✅ LangChain v1.0+ 표준
- ✅ 모든 컨텍스트 접근 가능
- ✅ 정보 제어 완벽

## 🎯 권장 사항

| 상황 | 권장 방식 |
|-----|----------|
| **빠른 프로토타입** | DeepAgent SubAgentMiddleware |
| **프로덕션 환경** | ToolRuntime hand-off ⭐ |
| **보안 중요** | ToolRuntime hand-off ⭐ |
| **복잡한 워크플로우** | ToolRuntime hand-off ⭐ |
| **정보 제어 필요** | ToolRuntime hand-off ⭐ |

## 🔗 참고 자료

- [LangGraph ToolRuntime 문서](https://langchain-ai.github.io/langgraph/reference/prebuilt/#toolruntime)
- [langgraph-supervisor-py](https://github.com/langchain-ai/langgraph-supervisor-py)
- [LangChain Tools 가이드](https://python.langchain.com/docs/how_to/custom_tools/)

## 📝 요약

ToolRuntime을 사용하면:

1. ✅ **단순성**: 단일 매개변수로 모든 컨텍스트 접근
2. ✅ **타입 안전**: Annotated 래퍼 불필요
3. ✅ **명시적**: `runtime.state`, `runtime.tool_call_id` 명확
4. ✅ **표준**: LangChain v1.0+ 공식 권장 방식
5. ✅ **유연성**: 필요한 정보만 선택적으로 전달 가능

**결론**: Tool-Based Delegation + ToolRuntime = 최고의 멀티 에이전트 아키텍처! 🚀
