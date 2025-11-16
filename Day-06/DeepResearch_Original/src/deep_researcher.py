"""Deep Research 에이전트를 위한 LangGraph 구현."""

import asyncio
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    filter_messages,
    get_buffer_string,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from configuration import (
    Configuration,
)
from prompts import (
    clarify_with_user_instructions,
    compress_research_simple_human_message,
    compress_research_system_prompt,
    final_report_generation_prompt,
    lead_researcher_prompt,
    research_system_prompt,
    transform_messages_into_research_topic_prompt,
)
from state import (
    AgentInputState,
    AgentState,
    ClarifyWithUser,
    ConductResearch,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    ResearchQuestion,
    SupervisorState,
)
from utils import (
    anthropic_websearch_called,
    get_all_tools,
    get_api_key_for_model,
    get_model_token_limit,
    get_notes_from_tool_calls,
    get_today_str,
    is_token_limit_exceeded,
    openai_websearch_called,
    remove_up_to_last_ai_message,
    think_tool,
)

# 에이전트 전반에서 사용할 구성 가능한 모델 초기화
llm_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def clarify_with_user(
    state: AgentState, 
    config: RunnableConfig
) -> Command[Literal["write_research_brief", END]]:
    """연구 범위가 불명확한 경우 사용자 메시지를 분석하고 명확화 질문을 합니다.

    이 함수는 연구를 진행하기 전에 사용자의 요청에 명확화가 필요한지 판단합니다.
    명확화가 비활성화되어 있거나 필요하지 않은 경우, 바로 연구로 진행합니다.

    Args:
        state: 사용자 메시지를 포함하는 현재 에이전트 상태
        config: 모델 설정과 선호도를 포함하는 런타임 구성

    Returns:
        명확화 질문으로 종료하거나 연구 계획 작성으로 진행하는 Command
    """
    # 단계 1: 구성에서 명확화가 활성화되어 있는지 확인
    configurable = Configuration.from_runnable_config(config)
    if not configurable.allow_clarification:
        # Skip clarification and proceed to research
        return Command(goto="write_research_brief")

    # 단계 2: 구조화된 명확화 분석을 위한 모델 준비
    messages = state["messages"]
    model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
    }

    # 구조화된 출력과 재시도 로직으로 모델 구성
    clarification_model = (
        llm_model
        .with_structured_output(ClarifyWithUser)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(model_config)
    )

    # 단계 3: 명확화가 필요한지 분석
    prompt_content = clarify_with_user_instructions.format(
        messages=get_buffer_string(messages), date=get_today_str()
    )
    response = await clarification_model.ainvoke([HumanMessage(content=prompt_content)])

    # 단계 4: 명확화 분석 결과에 따라 라우팅
    if response.need_clarification:
        # 사용자를 위한 명확화 질문으로 종료
        return Command(goto=END, update={"messages": [AIMessage(content=response.question)]})
    else:
        # Proceed to research with confirmation message
        return Command(
            goto="write_research_brief",
            update={"messages": [AIMessage(content=response.verification)]},
        )


async def write_research_brief(
    state: AgentState, 
    config: RunnableConfig
) -> Command[Literal["research_supervisor"]]:
    """사용자 메시지를 구조화된 연구 계획서로 변환하고 총괄 관리자를 초기화합니다.

    이 함수는 사용자의 메시지를 분석하고 연구 총괄 관리자를 안내할 집중된 연구 계획서를
    생성합니다. 또한 적절한 프롬프트와 지침으로 초기 총괄 관리자 컨텍스트를 설정합니다.

    Args:
        state: 사용자 메시지를 포함하는 현재 에이전트 상태
        config: 모델 설정을 포함하는 런타임 구성

    Returns:
        초기화된 컨텍스트로 연구 총괄 관리자로 진행하는 Command
    """
    # 단계 1: 구조화된 출력을 위한 연구 모델 설정
    configurable = Configuration.from_runnable_config(config)
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
    }

    # 구조화된 연구 질문 생성을 위한 모델 구성
    research_model = (
        llm_model.with_structured_output(ResearchQuestion)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )

    # 단계 2: 사용자 메시지로부터 구조화된 연구 계획서 생성
    prompt_content = transform_messages_into_research_topic_prompt.format(
        messages=get_buffer_string(state.get("messages", [])), date=get_today_str()
    )
    response = await research_model.ainvoke([HumanMessage(content=prompt_content)])

    # 단계 3: 연구 계획서와 지침으로 총괄 관리자 초기화
    supervisor_system_prompt = lead_researcher_prompt.format(
        date=get_today_str(),
        max_concurrent_research_units=configurable.max_concurrent_research_units,
        max_researcher_iterations=configurable.max_researcher_iterations,
    )


    return Command(
        goto="research_supervisor",
        update={
            "research_brief": response.research_brief,
            "supervisor_messages": {
                "type": "override",
                "value": [
                    SystemMessage(content=supervisor_system_prompt),
                    HumanMessage(content=response.research_brief),
                ],
            },
        },
    )


async def supervisor(
    state: SupervisorState, 
    config: RunnableConfig
) -> dict:
    """연구 전략을 계획하고 연구자들에게 위임하는 연구 총괄 관리자입니다.

    총괄 관리자는 연구 계획서를 분석하고 연구를 관리 가능한 작업들로 나누는 방법을 결정합니다.
    전략적 계획을 위한 think_tool, 하위 연구자들에게 작업을 위임하는 ConductResearch,
    또는 결과에 만족할 때 ResearchComplete를 사용할 수 있습니다.

    Args:
        state: 메시지와 연구 컨텍스트를 포함하는 현재 총괄 관리자 상태
        config: 모델 설정을 포함하는 런타임 구성

    Returns:
        도구 실행을 위해 supervisor_tools로 진행하는 Command
    """
    # 단계 1: 사용 가능한 도구로 총괄 관리자 모델 구성
    configurable = Configuration.from_runnable_config(config)
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
    }

    # 사용 가능한 도구: 연구 위임, 완료 신호, 그리고 전략적 사고
    lead_researcher_tools = [ConductResearch, ResearchComplete, think_tool]

    # 도구, 재시도 로직, 그리고 모델 설정으로 모델 구성
    research_model = (
        llm_model.bind_tools(lead_researcher_tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )

    # 단계 2: 현재 컨텍스트를 기반으로 총괄 관리자 응답 생성
    supervisor_messages = state.get("supervisor_messages", [])
    response = await research_model.ainvoke(supervisor_messages)

    # Step 3: Update state and proceed to tool execution
    # TODO: add_edge() 활용해서 바꿔주세요.
    return {
        "supervisor_messages": [response],
        "research_iterations": state.get("research_iterations", 0) + 1,
    }


async def supervisor_tools(
    state: SupervisorState, 
    config: RunnableConfig
) -> Command[Literal["supervisor", END]]:
    """연구 위임과 전략적 사고를 포함하여 총괄 관리자가 호출한 도구를 실행합니다.

    이 함수는 세 가지 유형의 총괄 관리자 도구 호출을 처리합니다:
    1. think_tool - 대화를 계속하는 전략적 반성
    2. ConductResearch - 하위 연구자들에게 연구 작업 위임
    3. ResearchComplete - 연구 단계 완료 신호

    Args:
        state: 메시지와 반복 횟수를 포함하는 현재 총괄 관리자 상태
        config: 연구 제한과 모델 설정을 포함하는 런타임 구성

    Returns:
        총괄 관리 루프를 계속하거나 연구 단계를 종료하는 Command
    """
    # 단계 1: 현재 상태를 추출하고 종료 조건 확인
    configurable = Configuration.from_runnable_config(config)
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]

    # [비즈니스 로직] 연구 단계의 종료 기준 정의
    exceeded_allowed_iterations = research_iterations > configurable.max_researcher_iterations
    no_tool_calls = not most_recent_message.tool_calls
    research_complete_tool_call = any(
        tool_call["name"] == "ResearchComplete" for tool_call in most_recent_message.tool_calls
    )

    # 종료 조건이 충족되면 종료
    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        # 종료 시 notes/raw_notes의 길이를 계산하고 raw_notes를 상위 상태로 내보냄
        final_notes = get_notes_from_tool_calls(supervisor_messages)
        compressed_length = len("\n".join(final_notes)) if final_notes else 0
        raw_notes_list = state.get("raw_notes", [])
        raw_notes_str = "\n".join(raw_notes_list) if raw_notes_list else ""
        raw_length = len(raw_notes_str)
        return Command(
            goto=END,
            update={
                "notes": final_notes,
                "raw_notes": raw_notes_list,
                "research_brief": state.get("research_brief", ""),
                "compressed_research_length": compressed_length,
                "raw_notes_length": raw_length,
            },
        )

    # 단계 2: 모든 도구 호출을 함께 처리 (think_tool과 ConductResearch 모두)
    all_tool_messages = []
    update_payload = {"supervisor_messages": []}

    # think_tool 호출 처리 (전략적 반성)
    # NOTE: 이거 굳이 왜 해야되죠? 그냥 think_tools 에서 처리할 수 있을 것 같은데....
    think_tool_calls = [
        tool_call
        for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "think_tool"
    ]

    for tool_call in think_tool_calls:
        reflection_content = tool_call["args"]["reflection"]

        all_tool_messages.append(
            ToolMessage(
                content=f"Reflection recorded: {reflection_content}",
                name="think_tool",
                tool_call_id=tool_call["id"],
            )
        )

    # ConductResearch 호출 처리 (연구 위임)
    conduct_research_calls = [
        tool_call
        for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "ConductResearch"
    ]

    if conduct_research_calls:
        try:
            # 리소스 고갈을 방지하기 위해 동시 연구 단위 제한
            allowed_conduct_research_calls = conduct_research_calls[
                : configurable.max_concurrent_research_units
            ]
            overflow_conduct_research_calls = conduct_research_calls[
                configurable.max_concurrent_research_units :
            ]

            # 연구 작업을 병렬로 실행
            research_tasks = [
                researcher_subgraph.ainvoke(
                    {
                        "researcher_messages": [
                            HumanMessage(content=tool_call["args"]["research_topic"])
                        ],
                        "research_topic": tool_call["args"]["research_topic"],
                    },
                    config,
                )
                for tool_call in allowed_conduct_research_calls
            ]

            tool_results = await asyncio.gather(*research_tasks)

            # 연구 결과로 도구 메시지 생성
            for observation, tool_call in zip(
                tool_results,
                allowed_conduct_research_calls,
                strict=True,
            ):
                all_tool_messages.append(
                    ToolMessage(
                        content=observation.get(
                            "compressed_research",
                            "Error synthesizing research report: Maximum retries exceeded",
                        ),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                    )
                )

            # 초과된 연구 호출을 오류 메시지로 처리
            for overflow_call in overflow_conduct_research_calls:
                all_tool_messages.append(
                    ToolMessage(
                        content=f"Error: Did not run this research as you have already exceeded the maximum number of concurrent research units. Please try again with {configurable.max_concurrent_research_units} or fewer research units.",
                        name="ConductResearch",
                        tool_call_id=overflow_call["id"],
                    )
                )

            # 모든 연구 결과로부터 raw notes 집계
            raw_notes_concat = "\n".join(
                ["\n".join(observation.get("raw_notes", [])) for observation in tool_results]
            )

            if raw_notes_concat:
                update_payload["raw_notes"] = [raw_notes_concat]
                update_payload["raw_notes_length"] = len(raw_notes_concat)

        except Exception as e:
            # 연구 실행 오류 처리
            if is_token_limit_exceeded(e, configurable.research_model) or True:
                # 토큰 제한 초과 또는 기타 오류 - 연구 단계 종료
                return Command(
                    goto=END,
                    update={
                        "notes": get_notes_from_tool_calls(supervisor_messages),
                        "research_brief": state.get("research_brief", ""),
                    },
                )

    # Step 3: Return command with all tool results
    update_payload["supervisor_messages"] = all_tool_messages
    return Command(goto="supervisor", update=update_payload)


# Supervisor 서브그래프 생성
# 연구 위임과 조정을 관리하는 총괄 관리자 워크플로우 생성
supervisor_builder = StateGraph(state_schema=SupervisorState, context_schema=Configuration)

# Add supervisor nodes for research management
supervisor_builder.add_node("supervisor", supervisor)  # Main supervisor logic
supervisor_builder.add_node("supervisor_tools", supervisor_tools)  # Tool execution handler

# Define supervisor workflow edges
supervisor_builder.add_edge(START, "supervisor")  # Entry point to supervisor
supervisor_builder.add_edge("supervisor", "supervisor_tools") # Command -> Edge 로 변경

# 메인 워크플로우에서 사용하기 위한 총괄 관리자 서브그래프 컴파일
supervisor_subgraph = supervisor_builder.compile()


async def researcher(
    state: ResearcherState, config: RunnableConfig
) -> Command[Literal["researcher_tools"]]:
    """Individual researcher that conducts focused research on specific topics.

    이 연구자는 총괄 관리자로부터 특정 연구 주제를 받고
    사용 가능한 도구(검색, think_tool, MCP 도구)를 사용하여 포괄적인 정보를 수집합니다.
    검색 사이에 전략적 계획을 위해 think_tool을 사용할 수 있습니다.

    Args:
        state: 메시지와 주제 컨텍스트를 포함하는 현재 연구자 상태
        config: 모델 설정과 도구 가용성을 포함하는 런타임 구성

    Returns:
        도구 실행을 위해 researcher_tools로 진행하는 Command
    """
    # 단계 1: 구성 로드하고 도구 가용성 검증
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])

    # 사용 가능한 모든 연구 도구 가져오기 (검색, MCP, think_tool)
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError(
            "No tools found to conduct research: Please configure either your "
            "search API or add MCP tools to your configuration."
        )

    # 단계 2: 도구로 연구자 모델 구성
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
    }

    # MCP 컨텍스트가 있으면 시스템 프롬프트 준비
    researcher_prompt = research_system_prompt.format(
        mcp_prompt=configurable.mcp_prompt or "", date=get_today_str()
    )

    # 도구, 재시도 로직, 그리고 설정으로 모델 구성
    research_model = (
        llm_model.bind_tools(tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )

    # 단계 3: 시스템 컨텍스트를 포함하여 연구자 응답 생성
    messages = [SystemMessage(content=researcher_prompt)] + researcher_messages
    response = await research_model.ainvoke(messages)

    # Step 4: Update state and proceed to tool execution
    return Command(
        goto="researcher_tools",
        update={
            "researcher_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
        },
    )


# 도구 실행 헬퍼 함수
async def execute_tool_safely(tool, args, config):
    """오류 처리를 포함하여 도구를 안전하게 실행합니다."""
    try:
        return await tool.ainvoke(args, config)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


async def researcher_tools(
    state: ResearcherState, config: RunnableConfig
) -> Command:
    """검색 도구와 전략적 사고를 포함하여 연구자가 호출한 도구를 실행합니다.

    이 함수는 다양한 유형의 연구자 도구 호출을 처리합니다:
    1. think_tool - 연구 대화를 계속하는 전략적 반성
    2. 검색 도구 (tavily_search, web_search) - 정보 수집
    3. MCP 도구 - 외부 도구 통합
    4. ResearchComplete - 개별 연구 작업 완료 신호

    Args:
        state: 메시지와 반복 횟수를 포함하는 현재 연구자 상태
        config: 연구 제한과 도구 설정을 포함하는 런타임 구성

    Returns:
        연구 루프를 계속하거나 압축으로 진행하는 Command
    """
    # 단계 1: 현재 상태를 추출하고 조기 종료 조건 확인
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    most_recent_message = researcher_messages[-1]

    # 도구 호출이 없으면 (네이티브 웹 검색 포함) 조기 종료
    has_tool_calls = bool(most_recent_message.tool_calls)
    has_native_search = openai_websearch_called(most_recent_message) or anthropic_websearch_called(
        most_recent_message
    )

    if not has_tool_calls and not has_native_search:
        return Command(goto="compress_research")

    # 단계 2: 기타 도구 호출 처리 (검색, MCP 도구 등)
    tools = await get_all_tools(config)
    tools_by_name = {
        tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool
        for tool in tools
    }

    # 모든 도구 호출을 병렬로 실행
    tool_calls = most_recent_message.tool_calls
    tool_execution_tasks = [
        execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config)
        for tool_call in tool_calls
    ]
    observations = await asyncio.gather(*tool_execution_tasks)

    # 실행 결과로 도구 메시지 생성
    tool_outputs = [
        ToolMessage(content=observation, name=tool_call["name"], tool_call_id=tool_call["id"])
        for observation, tool_call in zip(
            observations,
            tool_calls,
            strict=True,
        )
    ]

    # 단계 3: 후기 종료 조건 확인 (도구 처리 후)
    exceeded_iterations = state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls
    research_complete_called = any(
        tool_call["name"] == "ResearchComplete" for tool_call in most_recent_message.tool_calls
    )

    if exceeded_iterations or research_complete_called:
        # End research and proceed to compression
        return Command(goto="compress_research", update={"researcher_messages": tool_outputs})

    # Continue research loop with tool results
    return Command(goto="researcher", update={"researcher_messages": tool_outputs})


async def compress_research(state: ResearcherState, config: RunnableConfig):
    """연구 결과를 간결하고 구조화된 요약으로 압축하고 통합합니다.

    이 함수는 연구자의 작업에서 모든 연구 결과, 도구 출력, AI 메시지를 가져와
    모든 중요한 정보와 발견 사항을 보존하면서 깨끗하고 포괄적인 요약으로 정제합니다.

    Args:
        state: 축적된 연구 메시지를 포함하는 현재 연구자 상태
        config: 압축 모델 설정을 포함하는 런타임 구성

    Returns:
        압축된 연구 요약과 raw notes를 포함하는 딕셔너리
    """
    # 단계 1: 압축 모델 구성
    configurable = Configuration.from_runnable_config(config)
    synthesizer_model = llm_model.with_config(
        {
            "model": configurable.compression_model,
            "max_tokens": configurable.compression_model_max_tokens,
            "api_key": get_api_key_for_model(configurable.compression_model, config),
        }
    )

    # 단계 2: 압축을 위한 메시지 준비
    researcher_messages = state.get("researcher_messages", [])

    # 연구 모드에서 압축 모드로 전환하는 지시 추가
    researcher_messages.append(HumanMessage(content=compress_research_simple_human_message))

    # 단계 3: 토큰 제한 문제에 대한 재시도 로직으로 압축 시도
    synthesis_attempts = 0
    max_attempts = 3

    while synthesis_attempts < max_attempts:
        try:
            # 압축 작업에 집중된 시스템 프롬프트 생성
            compression_prompt = compress_research_system_prompt.format(date=get_today_str())
            messages = [SystemMessage(content=compression_prompt)] + researcher_messages

            # 압축 실행
            response = await synthesizer_model.ainvoke(messages)

            # 모든 도구와 AI 메시지로부터 raw notes 추출
            raw_notes_content = "\n".join(
                [
                    str(message.content)
                    for message in filter_messages(
                        researcher_messages, include_types=["tool", "ai"]
                    )
                ]
            )

            # 성공적인 압축 결과 반환
            return {"compressed_research": str(response.content), "raw_notes": [raw_notes_content]}

        except Exception as e:
            synthesis_attempts += 1

            # 이전 메시지를 제거하여 토큰 제한 초과 처리
            if is_token_limit_exceeded(e, configurable.research_model):
                researcher_messages = remove_up_to_last_ai_message(researcher_messages)
                continue

            # 기타 오류의 경우, 재시도 계속
            continue

    # 단계 4: 모든 시도가 실패한 경우 오류 결과 반환
    raw_notes_content = "\n".join(
        [
            str(message.content)
            for message in filter_messages(researcher_messages, include_types=["tool", "ai"])
        ]
    )

    return {
        "compressed_research": "Error synthesizing research report: Maximum retries exceeded",
        "raw_notes": [raw_notes_content],
    }


# Researcher 서브그래프 생성
# 특정 주제에 대한 집중된 연구를 수행하는 개별 연구자 워크플로우 생성
researcher_builder = StateGraph(
    state_schema=ResearcherState, 
    output_schema=ResearcherOutputState, 
    context_schema=Configuration,
)

# Add researcher nodes for research execution and compression
researcher_builder.add_node("researcher", researcher)  # Main researcher logic
researcher_builder.add_node("researcher_tools", researcher_tools)  # Tool execution handler
researcher_builder.add_node("compress_research", compress_research)  # Research compression

# Define researcher workflow edges
researcher_builder.add_edge(START, "researcher")  # Entry point to researcher
researcher_builder.add_edge("compress_research", END)  # Exit point after compression

# 총괄 관리자의 병렬 실행을 위한 연구자 서브그래프 컴파일
researcher_subgraph = researcher_builder.compile()


async def final_report_generation(state: AgentState, config: RunnableConfig):
    """토큰 제한에 대한 재시도 로직을 포함하여 최종 종합 연구 보고서를 생성합니다.

    이 함수는 수집된 모든 연구 결과를 가져와 구성된 보고서 생성 모델을 사용하여
    잘 구조화된 포괄적인 최종 보고서로 통합합니다.

    Args:
        state: 연구 결과와 컨텍스트를 포함하는 에이전트 상태
        config: 모델 설정과 API 키를 포함하는 런타임 구성

    Returns:
        최종 보고서와 정리된 상태를 포함하는 딕셔너리
    """
    # 단계 1: 연구 결과를 추출하고 상태 정리 준비
    notes = state.get("notes", [])
    cleared_state = {"notes": {"type": "override", "value": []}}
    findings = "\n".join(notes)
    # 대체/보고서 직전 스냅샷으로 길이 계산
    compressed_length = len(findings) if findings else 0
    raw_notes_str = "\n".join(state.get("raw_notes", [])) if state.get("raw_notes") else ""
    raw_length = len(raw_notes_str)

    # 단계 2: 최종 보고서 생성 모델 구성
    configurable = Configuration.from_runnable_config(config)
    writer_model_config = {
        "model": configurable.final_report_model,
        "max_tokens": configurable.final_report_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.final_report_model, config),
    }

    # 단계 3: 토큰 제한 재시도 로직으로 보고서 생성 시도
    max_retries = 3
    current_retry = 0
    findings_token_limit = None

    while current_retry <= max_retries:
        try:
            # 모든 연구 컨텍스트를 포함하는 포괄적인 프롬프트 생성
            final_report_prompt = final_report_generation_prompt.format(
                research_brief=state.get("research_brief", ""),
                messages=get_buffer_string(state.get("messages", [])),
                findings=findings,
                date=get_today_str(),
            )

            # 최종 보고서 생성
            final_report = await llm_model.with_config(writer_model_config).ainvoke(
                [HumanMessage(content=final_report_prompt)]
            )

            # 성공적인 보고서 생성 결과 반환
            return {
                "final_report": final_report.content,
                "messages": [final_report],
                "compressed_research_length": compressed_length,
                "raw_notes_length": raw_length,
                **cleared_state,
            }

        except Exception as e:
            # 점진적 절단으로 토큰 제한 초과 오류 처리
            if is_token_limit_exceeded(e, configurable.final_report_model):
                current_retry += 1

                if current_retry == 1:
                    # 첫 번째 재시도: 초기 절단 제한 결정
                    model_token_limit = get_model_token_limit(configurable.final_report_model)
                    if not model_token_limit:
                        return {
                            "final_report": f"Error generating final report: Token limit exceeded, however, we could not determine the model's maximum context length. Please update the model map in deep_researcher/utils.py with this information. {e}",
                            "messages": [
                                AIMessage(content="Report generation failed due to token limits")
                            ],
                            "compressed_research_length": compressed_length,
                            "raw_notes_length": raw_length,
                            **cleared_state,
                        }
                    # 절단을 위한 문자 근사치로 4배 토큰 제한 사용
                    findings_token_limit = model_token_limit * 4
                else:
                    # 후속 재시도: 매번 10%씩 감소
                    findings_token_limit = int(findings_token_limit * 0.9)

                # 결과를 절단하고 재시도
                findings = findings[:findings_token_limit]
                continue
            else:
                # 토큰 제한이 아닌 오류: 즉시 오류 반환
                return {
                    "final_report": f"Error generating final report: {e}",
                    "messages": [AIMessage(content="Report generation failed due to an error")],
                    "compressed_research_length": compressed_length,
                    "raw_notes_length": raw_length,
                    **cleared_state,
                }

    # 단계 4: 모든 재시도가 소진된 경우 실패 결과 반환
    return {
        "final_report": "Error generating final report: Maximum retries exceeded",
        "messages": [AIMessage(content="Report generation failed after maximum retries")],
        "compressed_research_length": compressed_length,
        "raw_notes_length": raw_length,
        **cleared_state,
    }


# 메인 Deep Researcher 그래프 생성
# 사용자 입력부터 최종 보고서까지 완전한 심층 연구 워크플로우 생성
deep_researcher_builder = StateGraph(
    state_schema=AgentState, 
    input_schema=AgentInputState, 
    context_schema=Configuration,
)

# Add main workflow nodes for the complete research process
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)  # User clarification phase
deep_researcher_builder.add_node(
    "write_research_brief",
    write_research_brief,
)  # Research planning phase

deep_researcher_builder.add_node(
    "research_supervisor",
    supervisor_subgraph,
)  # Research execution phase
deep_researcher_builder.add_node(
    "final_report_generation",
    final_report_generation,
)  # Report generation phase

# Define main workflow edges for sequential execution
deep_researcher_builder.add_edge(START, "clarify_with_user")  # Entry point
deep_researcher_builder.add_edge(
    "research_supervisor",
    "final_report_generation",
)  # Research to report
deep_researcher_builder.add_edge("final_report_generation", END)  # Final exit point

# 완전한 deep researcher 워크플로우 컴파일
deep_researcher = deep_researcher_builder.compile()
