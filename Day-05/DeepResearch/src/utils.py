"""Deep Research 에이전트를 위한 유틸리티 함수 및 헬퍼들."""

import asyncio
import logging
import os
import warnings
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

import aiohttp
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    MessageLikeRepresentation,
    filter_messages,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import (
    BaseTool,
    InjectedToolArg,
    StructuredTool,
    ToolException,
    tool,
)
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.config import get_store
from mcp import McpError
from tavily import AsyncTavilyClient

from configuration import Configuration, SearchAPI
from prompts import summarize_webpage_prompt
from state import ResearchComplete, Summary

##########################
# Tavily 검색 도구 유틸리티
##########################
TAVILY_SEARCH_DESCRIPTION = (
    "A search engine optimized for comprehensive, accurate, and trusted results. "
    "Useful for when you need to answer questions about current events."
)


@tool(description=TAVILY_SEARCH_DESCRIPTION)
async def tavily_search(
    queries: list[str],
    max_results: Annotated[int, InjectedToolArg] = 5,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
    config: RunnableConfig = None,
) -> str:
    """Fetch and summarize search results from Tavily search API.

    Args:
        queries: List of search queries to execute
        max_results: Maximum number of results to return per query
        topic: Topic filter for search results (general, news, or finance)
        config: Runtime configuration for API keys and model settings

    Returns:
        Formatted string containing summarized search results
    """
    # 단계 1: 검색 쿼리를 비동기적으로 실행
    search_results = await tavily_search_async(
        queries, max_results=max_results, topic=topic, include_raw_content=True, config=config
    )

    # 단계 2: 동일한 콘텐츠를 여러 번 처리하지 않도록 URL로 결과 중복 제거
    unique_results = {}
    for response in search_results:
        for result in response["results"]:
            url = result["url"]
            if url not in unique_results:
                unique_results[url] = {**result, "query": response["query"]}

    # 단계 3: 구성으로 요약 모델 설정
    configurable = Configuration.from_runnable_config(config)

    # 모델 토큰 제한 내에 유지하기 위한 문자 제한 (구성 가능)
    max_char_to_include = configurable.max_content_length

    # 재시도 로직과 함께 요약 모델 초기화
    model_api_key = get_api_key_for_model(configurable.summarization_model, config)
    summarization_model = (
        init_chat_model(
            model=configurable.summarization_model,
            max_tokens=configurable.summarization_model_max_tokens,
            api_key=model_api_key,
            tags=["langsmith:nostream"],
        )
        .with_structured_output(Summary)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
    )

    # 단계 4: 요약 작업 생성 (빈 콘텐츠는 건너뛰기)
    async def noop():
        """원시 콘텐츠가 없는 결과를 위한 No-op 함수."""
        return None

    summarization_tasks = [
        noop()
        if not result.get("raw_content")
        else summarize_webpage(summarization_model, result["raw_content"][:max_char_to_include])
        for result in unique_results.values()
    ]

    # 단계 5: 모든 요약 작업을 병렬로 실행
    summaries = await asyncio.gather(*summarization_tasks)

    # 단계 6: 결과와 요약을 결합
    summarized_results = {
        url: {
            "title": result["title"],
            "content": result["content"] if summary is None else summary,
        }
        for url, result, summary in zip(
            unique_results.keys(),
            unique_results.values(),
            summaries,
            strict=True,
        )
    }

    # 단계 7: 최종 출력 포맷
    if not summarized_results:
        return "유효한 검색 결과를 찾을 수 없습니다. 다른 검색 쿼리를 시도하거나 다른 검색 API를 사용하세요."

    formatted_output = "Search results: \n\n"
    for i, (url, result) in enumerate(summarized_results.items()):
        formatted_output += f"\n\n--- SOURCE {i + 1}: {result['title']} ---\n"
        formatted_output += f"URL: {url}\n\n"
        formatted_output += f"SUMMARY:\n{result['content']}\n\n"
        formatted_output += "\n\n" + "-" * 80 + "\n"

    return formatted_output


async def tavily_search_async(
    search_queries,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = True,
    config: RunnableConfig = None,
):
    """여러 Tavily 검색 쿼리를 비동기적으로 실행합니다.

    Args:
        search_queries: 실행할 검색 쿼리 문자열 목록
        max_results: 쿼리당 최대 결과 수
        topic: 결과 필터링을 위한 주제 카테고리
        include_raw_content: 전체 웹페이지 콘텐츠 포함 여부
        config: API 키 액세스를 위한 런타임 구성

    Returns:
        Tavily API로부터의 검색 결과 딕셔너리 목록
    """
    # 구성의 API 키로 Tavily 클라이언트 초기화
    tavily_client = AsyncTavilyClient(api_key=get_tavily_api_key(config))

    # 병렬 실행을 위한 검색 작업 생성
    search_tasks = [
        tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
        )
        for query in search_queries
    ]

    # 모든 검색 쿼리를 병렬로 실행하고 결과 반환
    search_results = await asyncio.gather(*search_tasks)
    return search_results


# 참고: Context Engineering 포인트
async def summarize_webpage(model: BaseChatModel, webpage_content: str) -> str:
    """타임아웃 보호와 함께 AI 모델을 사용하여 웹페이지 콘텐츠를 요약합니다.

    Args:
        model: 요약을 위해 구성된 챗 모델
        webpage_content: 요약할 원시 웹페이지 콘텐츠

    Returns:
        주요 발취문을 포함한 포맷된 요약, 요약 실패 시 원본 콘텐츠
    """
    try:
        # 현재 날짜 컨텍스트로 프롬프트 생성
        prompt_content = summarize_webpage_prompt.format(
            webpage_content=webpage_content, date=get_today_str()
        )

        # 걸림 현상을 방지하기 위해 타임아웃과 함께 요약 실행
        summary = await asyncio.wait_for(
            model.ainvoke([HumanMessage(content=prompt_content)]),
            timeout=60.0,  # 요약을 위한 60초 타임아웃
        )

        # 구조화된 섹션으로 요약 포맷
        formatted_summary = (
            f"<summary>\n{summary.summary}\n</summary>\n\n"
            f"<key_excerpts>\n{summary.key_excerpts}\n</key_excerpts>"
        )

        return formatted_summary

    except TimeoutError:
        # 요약 중 타임아웃 - 원본 콘텐츠 반환
        logging.warning("60초 후 요약 타임아웃, 원본 콘텐츠 반환")
        return webpage_content
    except Exception as e:
        # 요약 중 기타 오류 - 로그 기록 및 원본 콘텐츠 반환
        logging.warning(f"오류로 인해 요약 실패: {str(e)}, 원본 콘텐츠 반환")
        return webpage_content


##########################
# Reflection Tool Utils
##########################


@tool(description="Strategic reflection tool for research planning")
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"


##########################
# MCP Utils
##########################


async def get_mcp_access_token(
    supabase_token: str,
    base_mcp_url: str,
) -> dict[str, Any] | None:
    """OAuth 토큰 교환을 사용하여 Supabase 토큰을 MCP 액세스 토큰으로 교환합니다.

    Args:
        supabase_token: 유효한 Supabase 인증 토큰
        base_mcp_url: MCP 서버의 기본 URL

    Returns:
        성공 시 토큰 데이터 딕셔너리, 실패 시 None
    """
    try:
        # OAuth 토큰 교환 요청 데이터 준비
        form_data = {
            "client_id": "mcp_default",
            "subject_token": supabase_token,
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "resource": base_mcp_url.rstrip("/") + "/mcp",
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        }

        # 토큰 교환 요청 실행
        async with aiohttp.ClientSession() as session:
            token_url = base_mcp_url.rstrip("/") + "/oauth/token"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            async with session.post(token_url, headers=headers, data=form_data) as response:
                if response.status == 200:
                    # 토큰 획득 성공
                    token_data = await response.json()
                    return token_data
                else:
                    # 디버깅을 위한 오류 세부 정보 로그 기록
                    response_text = await response.text()
                    logging.error(f"토큰 교환 실패: {response_text}")

    except Exception as e:
        logging.error(f"토큰 교환 중 오류: {e}")

    return None


async def get_tokens(config: RunnableConfig):
    """만료 검증을 포함하여 저장된 인증 토큰을 가져옵니다.

    Args:
        config: 스레드 및 사용자 식별자를 포함하는 런타임 구성

    Returns:
        유효하고 만료되지 않은 경우 토큰 딕셔너리, 그렇지 않으면 None
    """
    store = get_store()

    # 구성에서 필수 식별자 추출
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        return None

    user_id = config.get("metadata", {}).get("owner")
    if not user_id:
        return None

    # 저장된 토큰 가져오기
    tokens = await store.aget((user_id, "tokens"), "data")
    if not tokens:
        return None

    # 토큰 만료 확인
    expires_in = tokens.value.get("expires_in")  # 만료까지 남은 초
    created_at = tokens.created_at  # 토큰 생성 시간
    current_time = datetime.now(UTC)
    expiration_time = created_at + timedelta(seconds=expires_in)

    if current_time > expiration_time:
        # 토큰 만료됨, 정리하고 None 반환
        await store.adelete((user_id, "tokens"), "data")
        return None

    return tokens.value


async def set_tokens(config: RunnableConfig, tokens: dict[str, Any]):
    """구성 저장소에 인증 토큰을 저장합니다.

    Args:
        config: 스레드 및 사용자 식별자를 포함하는 런타임 구성
        tokens: 저장할 토큰 딕셔너리
    """
    store = get_store()

    # 구성에서 필수 식별자 추출
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        return

    user_id = config.get("metadata", {}).get("owner")
    if not user_id:
        return

    # 토큰 저장
    await store.aput((user_id, "tokens"), "data", tokens)


async def fetch_tokens(config: RunnableConfig) -> dict[str, Any]:
    """필요 시 새 토큰을 가져오며 MCP 토큰을 가져오고 갱신합니다.

    Args:
        config: 인증 세부 정보를 포함한 런타임 구성

    Returns:
        유효한 토큰 딕셔너리, 토큰을 얻을 수 없는 경우 None
    """
    # 먼저 기존의 유효한 토큰 가져오기 시도
    current_tokens = await get_tokens(config)
    if current_tokens:
        return current_tokens

    # 새 토큰 교환을 위한 Supabase 토큰 추출
    supabase_token = config.get("configurable", {}).get("x-supabase-access-token")
    if not supabase_token:
        return None

    # MCP 구성 추출
    mcp_config = config.get("configurable", {}).get("mcp_config")
    if not mcp_config or not mcp_config.get("url"):
        return None

    # Supabase 토큰을 MCP 토큰으로 교환
    mcp_tokens = await get_mcp_access_token(supabase_token, mcp_config.get("url"))
    if not mcp_tokens:
        return None

    # 새 토큰을 저장하고 반환
    await set_tokens(config, mcp_tokens)
    return mcp_tokens


def wrap_mcp_authenticate_tool(tool: StructuredTool) -> StructuredTool:
    """포괄적인 인증 및 오류 처리로 MCP 도구를 래핑합니다.

    Args:
        tool: 래핑할 MCP 구조화된 도구

    Returns:
        인증 오류 처리가 강화된 도구
    """
    original_coroutine = tool.coroutine

    async def authentication_wrapper(**kwargs):
        """MCP 오류 처리와 사용자 친화적인 메시지가 포함된 강화된 코루틴."""

        def _find_mcp_error_in_exception_chain(exc: BaseException) -> McpError | None:
            """예외 체인에서 MCP 오류를 재귀적으로 검색."""
            if isinstance(exc, McpError):
                return exc

            # ExceptionGroup (Python 3.11+) 처리
            if hasattr(exc, "exceptions"):
                for sub_exception in exc.exceptions:
                    if found_error := _find_mcp_error_in_exception_chain(sub_exception):
                        return found_error
            return None

        try:
            # 원본 도구 기능 실행
            return await original_coroutine(**kwargs)

        except BaseException as original_error:
            # 예외 체인에서 MCP 특정 오류 검색
            mcp_error = _find_mcp_error_in_exception_chain(original_error)
            if not mcp_error:
                # MCP 오류가 아니면 원본 예외를 다시 발생시킵니다.
                raise original_error

            # MCP 특정 오류 처리
            error_details = mcp_error.error
            error_code = getattr(error_details, "code", None)
            error_data = getattr(error_details, "data", None) or {}

            # 인증/상호작용이 필요한 오류 확인
            if error_code == -32003:  # Interaction required error code
                message_payload = error_data.get("message", {})
                error_message = "Required interaction"

                # 사용자 친화적인 메시지 추출
                if isinstance(message_payload, dict):
                    error_message = message_payload.get("text") or error_message

                # 사용자 참조를 위한 URL 추가
                if url := error_data.get("url"):
                    error_message = f"{error_message} {url}"

                raise ToolException(error_message) from original_error

            # 다른 MCP 오류에 대해서는 원본을 다시 발생시킵니다.
            raise original_error

    # 도구의 코루틴을 강화된 버전으로 교체
    tool.coroutine = authentication_wrapper
    return tool


async def load_mcp_tools(
    config: RunnableConfig,
    existing_tool_names: set[str],
) -> list[BaseTool]:
    """MCP (Model Context Protocol) 도구를 인증과 함께 로드하고 구성합니다.

    Args:
        config: MCP 서버 세부 정보를 포함하는 런타임 구성
        existing_tool_names: 충돌을 피하기 위해 이미 사용 중인 도구 이름 집합

    Returns:
        사용 준비가 된 구성된 MCP 도구 목록
    """
    configurable = Configuration.from_runnable_config(config)

    # 단계 1: 필요한 경우 인증 처리
    if configurable.mcp_config and configurable.mcp_config.auth_required:
        mcp_tokens = await fetch_tokens(config)
    else:
        mcp_tokens = None

    # 단계 2: 구성 요구사항 검증
    config_valid = (
        configurable.mcp_config
        and configurable.mcp_config.url
        and configurable.mcp_config.tools
        and (mcp_tokens or not configurable.mcp_config.auth_required)
    )

    if not config_valid:
        return []

    # 단계 3: MCP 서버 연결 설정
    server_url = configurable.mcp_config.url.rstrip("/") + "/mcp"

    # 토큰이 사용 가능한 경우 인증 헤더 구성
    auth_headers = None
    if mcp_tokens:
        auth_headers = {"Authorization": f"Bearer {mcp_tokens['access_token']}"}

    mcp_server_config = {
        "server_1": {"url": server_url, "headers": auth_headers, "transport": "streamable_http"}
    }
    # TODO: OAP에 Multi-MCP Server 지원이 병합되면 이 코드 업데이트

    # 단계 4: MCP 서버에서 도구 로드
    try:
        client = MultiServerMCPClient(mcp_server_config)
        available_mcp_tools = await client.get_tools()
    except Exception:
        # MCP 서버 연결 실패 시 빈 목록 반환
        return []

    # 단계 5: 도구 필터링 및 구성
    configured_tools = []
    for mcp_tool in available_mcp_tools:
        # 충돌하는 이름의 도구는 건너뛰기
        if mcp_tool.name in existing_tool_names:
            warnings.warn(f"MCP 도구 '{mcp_tool.name}'이(가) 기존 도구 이름과 충돌 - 건너뛰기")
            continue

        # 구성에 지정된 도구만 포함
        if mcp_tool.name not in set(configurable.mcp_config.tools):
            continue

        # 인증 처리로 도구 래핑하고 목록에 추가
        enhanced_tool = wrap_mcp_authenticate_tool(mcp_tool)
        configured_tools.append(enhanced_tool)

    return configured_tools


##########################
# 도구 유틸리티
##########################


async def get_search_tool(search_api: SearchAPI):
    """지정된 API 제공자를 기반으로 검색 도구를 구성하고 반환합니다.

    Args:
        search_api: 사용할 검색 API 제공자 (Anthropic, OpenAI, Tavily, 또는 None)

    Returns:
        지정된 제공자에 대해 구성된 검색 도구 객체 목록
    """
    if search_api == SearchAPI.OPENAI:
        # OpenAI의 웹 검색 미리보기 기능
        return [{"type": "web_search_preview"}]

    elif search_api == SearchAPI.TAVILY:
        # 메타데이터로 Tavily 검색 도구 구성
        search_tool = tavily_search
        search_tool.metadata = {
            **(search_tool.metadata or {}),
            "type": "search",
            "name": "web_search",
        }
        return [search_tool]

    elif search_api == SearchAPI.NONE:
        # 검색 기능이 구성되지 않음
        return []

    # 알 수 없는 검색 API 유형에 대한 기본 폴백
    return []


async def get_all_tools(config: RunnableConfig):
    """연구, 검색, MCP 도구를 포함한 완전한 도구 키트를 조립합니다.

    Args:
        config: 검색 API 및 MCP 설정을 지정하는 런타임 구성

    Returns:
        연구 작업에 대해 구성되고 사용 가능한 모든 도구 목록
    """
    # 핵심 연구 도구로 시작
    tools = [tool(ResearchComplete), think_tool]

    # 구성된 검색 도구 추가
    configurable = Configuration.from_runnable_config(config)
    search_api = SearchAPI(get_config_value(configurable.search_api))
    search_tools = await get_search_tool(search_api)
    tools.extend(search_tools)

    # 충돌을 방지하기 위해 기존 도구 이름 추적
    existing_tool_names = {
        tool.name if hasattr(tool, "name") else tool.get("name", "web_search") for tool in tools
    }

    # 구성된 경우 MCP 도구 추가
    mcp_tools = await load_mcp_tools(config, existing_tool_names)
    tools.extend(mcp_tools)

    return tools


def get_notes_from_tool_calls(messages: list[MessageLikeRepresentation]):
    """도구 호출 메시지에서 노트를 추출합니다."""
    return [tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")]


##########################
# 모델 제공자 네이티브 웹검색 유틸리티
##########################


def anthropic_websearch_called(response):
    """응답에서 Anthropic의 네이티브 웹 검색이 사용되었는지 감지합니다.

    Args:
        response: Anthropic API의 응답 객체

    Returns:
        웹 검색이 호출된 경우 True, 그렇지 않으면 False
    """
    try:
        # 응답 메타데이터 구조를 탐색
        usage = response.response_metadata.get("usage")
        if not usage:
            return False

        # 서버측 도구 사용 정보 확인
        server_tool_use = usage.get("server_tool_use")
        if not server_tool_use:
            return False

        # 웹 검색 요청 수 찾기
        web_search_requests = server_tool_use.get("web_search_requests")
        if web_search_requests is None:
            return False

        # 웹 검색 요청이 있었다면 True 반환
        return web_search_requests > 0

    except (AttributeError, TypeError):
        # 응답 구조가 예상치 못한 경우 처리
        return False


def openai_websearch_called(response):
    """응답에서 OpenAI의 웹 검색 기능이 사용되었는지 감지합니다.

    Args:
        response: OpenAI API의 응답 객체

    Returns:
        웹 검색이 호출된 경우 True, 그렇지 않으면 False
    """
    # 응답 메타데이터에서 도구 출력 확인
    tool_outputs = response.additional_kwargs.get("tool_outputs")
    if not tool_outputs:
        return False

    # 도구 출력에서 웹 검색 호출 찾기
    for tool_output in tool_outputs:
        if tool_output.get("type") == "web_search_call":
            return True

    return False


##########################
# 토큰 제한 초과 유틸리티
##########################


def is_token_limit_exceeded(exception: Exception, model_name: str = None) -> bool:
    """예외가 토큰/컨텍스트 제한 초과를 나타내는지 판단합니다.

    Args:
        exception: 분석할 예외
        model_name: 제공자 감지를 최적화하기 위한 선택적 모델 이름

    Returns:
        예외가 토큰 제한 초과를 나타내면 True, 그렇지 않으면 False
    """
    error_str = str(exception).lower()

    # 단계 1: 가능한 경우 모델 이름에서 제공자 결정
    provider = None
    if model_name:
        model_str = str(model_name).lower()
        if model_str.startswith("openai:"):
            provider = "openai"
        elif model_str.startswith("anthropic:"):
            provider = "anthropic"
        elif model_str.startswith("gemini:") or model_str.startswith("google:"):
            provider = "gemini"

    # 단계 2: 제공자별 토큰 제한 패턴 확인
    if provider == "openai":
        return _check_openai_token_limit(exception, error_str)
    elif provider == "anthropic":
        return _check_anthropic_token_limit(exception, error_str)
    elif provider == "gemini":
        return _check_gemini_token_limit(exception, error_str)

    # 단계 3: 제공자를 알 수 없는 경우 모든 제공자 확인
    return (
        _check_openai_token_limit(exception, error_str)
        or _check_anthropic_token_limit(exception, error_str)
        or _check_gemini_token_limit(exception, error_str)
    )


def _check_openai_token_limit(exception: Exception, error_str: str) -> bool:
    """예외가 OpenAI 토큰 제한 초과를 나타내는지 확인합니다."""
    # 예외 메타데이터 분석
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, "__module__", "")

    # OpenAI 예외인지 확인
    is_openai_exception = "openai" in exception_type.lower() or "openai" in module_name.lower()

    # 일반적인 OpenAI 토큰 제한 오류 유형 확인
    is_request_error = class_name in ["BadRequestError", "InvalidRequestError"]

    if is_openai_exception and is_request_error:
        # 오류 메시지에서 토큰 관련 키워드 찾기
        token_keywords = ["token", "context", "length", "maximum context", "reduce"]
        if any(keyword in error_str for keyword in token_keywords):
            return True

    # 특정 OpenAI 오류 코드 확인
    if hasattr(exception, "code") and hasattr(exception, "type"):
        error_code = getattr(exception, "code", "")
        error_type = getattr(exception, "type", "")

        if error_code == "context_length_exceeded" or error_type == "invalid_request_error":
            return True

    return False


def _check_anthropic_token_limit(exception: Exception, error_str: str) -> bool:
    """예외가 Anthropic 토큰 제한 초과를 나타내는지 확인합니다."""
    # 예외 메타데이터 분석
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, "__module__", "")

    # Anthropic 예외인지 확인
    is_anthropic_exception = (
        "anthropic" in exception_type.lower() or "anthropic" in module_name.lower()
    )

    # Anthropic 특정 오류 패턴 확인
    is_bad_request = class_name == "BadRequestError"

    if is_anthropic_exception and is_bad_request:
        # Anthropic은 토큰 제한에 대해 특정 오류 메시지 사용
        if "prompt is too long" in error_str:
            return True

    return False


def _check_gemini_token_limit(exception: Exception, error_str: str) -> bool:
    """예외가 Google/Gemini 토큰 제한 초과를 나타내는지 확인합니다."""
    # 예외 메타데이터 분석
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, "__module__", "")

    # Google/Gemini 예외인지 확인
    is_google_exception = "google" in exception_type.lower() or "google" in module_name.lower()

    # Google 특정 리소스 고갈 오류 확인
    is_resource_exhausted = class_name in ["ResourceExhausted", "GoogleGenerativeAIFetchError"]

    if is_google_exception and is_resource_exhausted:
        return True

    # 특정 Google API 리소스 고갈 패턴 확인
    if "google.api_core.exceptions.resourceexhausted" in exception_type.lower():
        return True

    return False


MODEL_TOKEN_LIMITS = {
    "openai:gpt-4.1-mini": 1047576,
    "openai:gpt-4.1-nano": 1047576,
    "openai:gpt-4.1": 1047576,
}


def get_model_token_limit(model_string):
    """특정 모델의 토큰 제한을 조회합니다.

    Args:
        model_string: 조회할 모델 식별자 문자열

    Returns:
        찾은 경우 정수로 토큰 제한, 모델이 조회 테이블에 없으면 None
    """
    # 알려진 모델 토큰 제한을 검색
    for model_key, token_limit in MODEL_TOKEN_LIMITS.items():
        if model_key in model_string:
            return token_limit

    # 조회 테이블에서 모델을 찾을 수 없음
    return None


def remove_up_to_last_ai_message(
    messages: list[MessageLikeRepresentation],
) -> list[MessageLikeRepresentation]:
    """마지막 AI 메시지까지 제거하여 메시지 기록을 잘라냅니다.

    최근 컨텍스트를 제거하여 토큰 제한 초과 오류를 처리하는 데 유용합니다.

    Args:
        messages: 잘라낼 메시지 객체 목록

    Returns:
        마지막 AI 메시지까지(포함하지 않음) 잘라낸 메시지 목록
    """
    # 메시지를 역방향으로 검색하여 마지막 AI 메시지 찾기
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            # 마지막 AI 메시지까지(포함하지 않음) 모든 것을 반환
            return messages[:i]

    # AI 메시지를 찾을 수 없음, 원본 목록 반환
    return messages


##########################
# 기타 유틸리티
##########################


def get_today_str() -> str:
    """프롬프트와 출력에 표시하기 위해 포맷된 현재 날짜를 가져옵니다.

    Returns:
        'Mon Jan 15, 2024'와 같은 형식의 사람이 읽을 수 있는 날짜 문자열
    """
    now = datetime.now()
    return f"{now:%a} {now:%b} {now.day}, {now:%Y}"


def get_config_value(value):
    """열거형과 None 값을 처리하여 구성에서 값을 추출합니다."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    elif isinstance(value, dict):
        return value
    else:
        return value.value


def get_api_key_for_model(model_name: str, config: RunnableConfig):
    """환경 또는 구성에서 특정 모델에 대한 API 키를 가져옵니다."""
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    model_name = model_name.lower()
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        if model_name.startswith("openai:"):
            return api_keys.get("OPENAI_API_KEY")
        elif model_name.startswith("anthropic:"):
            return api_keys.get("ANTHROPIC_API_KEY")
        elif model_name.startswith("google"):
            return api_keys.get("GOOGLE_API_KEY")
        return None
    else:
        if model_name.startswith("openai:"):
            return os.getenv("OPENAI_API_KEY")
        elif model_name.startswith("anthropic:"):
            return os.getenv("ANTHROPIC_API_KEY")
        elif model_name.startswith("google"):
            return os.getenv("GOOGLE_API_KEY")
        return None


def get_tavily_api_key(config: RunnableConfig):
    """환경 또는 구성에서 Tavily API 키를 가져옵니다."""
    should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false")
    if should_get_from_config.lower() == "true":
        api_keys = config.get("configurable", {}).get("apiKeys", {})
        if not api_keys:
            return None
        return api_keys.get("TAVILY_API_KEY")
    else:
        return os.getenv("TAVILY_API_KEY")
