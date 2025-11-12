"""
serena/mcp.py - Serena 모델 컨텍스트 프로토콜(MCP) 서버

이 파일은 Serena 에이전트를 MCP 클라이언트와 연결하는 서버를 생성하고 관리하는 로직을 포함합니다.
FastMCP 프레임워크를 기반으로 하며, Serena의 도구들을 MCP 사양에 맞게 변환하고,
서버의 생명주기를 관리하는 역할을 합니다.

주요 컴포넌트:
- SerenaMCPFactory: MCP 서버 생성을 위한 추상 팩토리 클래스.
- SerenaMCPFactorySingleProcess: SerenaAgent와 MCP 서버를 단일 프로세스에서 실행하는 구체 팩토리 클래스.

주요 기능:
- Serena 도구를 MCP 도구 형식으로 변환 (`make_mcp_tool`).
- Pydantic/JSON 스키마를 OpenAI 도구 스키마와 호환되도록 변환 (`_sanitize_for_openai_tools`).
- MCP 서버 인스턴스 생성 및 설정 (`create_mcp_server`).
- 서버 시작 및 종료 생명주기 관리 (`server_lifespan`).

아키텍처 노트:
- `FastMCP` 라이브러리를 확장하여 Serena 에이전트와의 통합을 구현합니다.
- 로깅 설정은 `FastMCP`의 기본 설정을 패치하여 Serena의 표준 로깅 포맷을 사용하도록 합니다.
- `SerenaMCPFactory`는 팩토리 패턴을 사용하여, 향후 다중 프로세스 아키텍처 등
  다양한 서버 실행 전략을 지원할 수 있도록 설계되었습니다.
- `docstring_parser`를 사용하여 도구의 docstring을 동적으로 파싱하고, 이를 MCP 도구의 설명으로 활용하여
  문서와 실제 구현 간의 일관성을 유지합니다.
"""

import sys
from abc import abstractmethod
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, cast

import docstring_parser
from mcp.server.fastmcp import server
from mcp.server.fastmcp.server import FastMCP, Settings
from mcp.server.fastmcp.tools.base import Tool as MCPTool
from pydantic_settings import SettingsConfigDict
from sensai.util import logging

from serena.agent import (
    SerenaAgent,
    SerenaConfig,
)
from serena.config.context_mode import SerenaAgentContext, SerenaAgentMode
from serena.constants import DEFAULT_CONTEXT, DEFAULT_MODES, SERENA_LOG_FORMAT
from serena.tools import Tool
from serena.util.exception import show_fatal_exception_safe
from serena.util.logging import MemoryLogHandler

log = logging.getLogger(__name__)


def configure_logging(*args, **kwargs) -> None:  # type: ignore
    """FastMCP의 기본 로깅 설정을 오버라이드하기 위한 함수."""
    if not logging.is_enabled():
        logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=SERENA_LOG_FORMAT)


# FastMCP의 하드코딩된 로깅 설정 함수를 패치합니다.
server.configure_logging = configure_logging  # type: ignore


@dataclass
class SerenaMCPRequestContext:
    """MCP 요청 컨텍스트를 위한 데이터 클래스."""

    agent: SerenaAgent


class SerenaMCPFactory:
    """
    Serena MCP 서버 인스턴스를 생성하기 위한 추상 팩토리 클래스.
    """

    def __init__(self, context: str = DEFAULT_CONTEXT, project: str | None = None):
        """
        SerenaMCPFactory를 초기화합니다.

        Args:
            context (str): 컨텍스트 이름 또는 컨텍스트 파일 경로.
            project (str | None): 프로젝트의 절대 경로 또는 이미 등록된 프로젝트의 이름.
                만약 등록되지 않은 프로젝트 경로가 전달되면, 자동으로 등록됩니다.
        """
        self.context = SerenaAgentContext.load(context)
        self.project = project

    @staticmethod
    def _sanitize_for_openai_tools(schema: dict) -> dict:
        """
        Pydantic/JSON 스키마 객체를 OpenAI 도구 스키마와 호환되도록 만듭니다.

        - 'integer' 타입을 'number' 타입으로 변환하고 'multipleOf: 1'을 추가합니다.
        - 유니온 타입 배열에서 'null'을 제거합니다.
        - 정수만 포함하는 enum을 'number' 타입으로 강제 변환합니다.
        - oneOf/anyOf가 정수/숫자 타입만으로 다를 경우, 이를 단순화합니다.

        Note:
            이 메서드는 GPT-5에 의해 작성되었으며, 상세한 검토는 이루어지지 않았습니다.
            `openai_tool_compatible`이 True일 때만 호출됩니다.

        Args:
            schema (dict): 변환할 Pydantic/JSON 스키마.

        Returns:
            dict: OpenAI 도구와 호환되는 스키마.
        """
        s = deepcopy(schema)

        def walk(node):  # type: ignore
            if not isinstance(node, dict):
                return node

            t = node.get("type")
            if isinstance(t, str):
                if t == "integer":
                    node["type"] = "number"
                    if "multipleOf" not in node:
                        node["multipleOf"] = 1
            elif isinstance(t, list):
                t2 = [x if x != "integer" else "number" for x in t if x != "null"]
                if not t2:
                    t2 = ["object"]
                node["type"] = t2[0] if len(t2) == 1 else t2
                if "integer" in t or "number" in t2:
                    node.setdefault("multipleOf", 1)

            if "enum" in node and isinstance(node["enum"], list):
                vals = node["enum"]
                if vals and all(isinstance(v, int) for v in vals):
                    node.setdefault("type", "number")
                    node.setdefault("multipleOf", 1)

            for key in ("oneOf", "anyOf"):
                if key in node and isinstance(node[key], list):
                    if len(node[key]) == 2:
                        types = [sub.get("type") for sub in node[key]]
                        if "null" in types:
                            non_null_type = next(t for t in types if t != "null")
                            if isinstance(non_null_type, str):
                                node["type"] = non_null_type
                                node.pop(key, None)
                                continue
                    simplified = []
                    changed = False
                    for sub in node[key]:
                        sub = walk(sub)
                        simplified.append(sub)
                    try:
                        import json

                        canon = [json.dumps(x, sort_keys=True) for x in simplified]
                        if len(set(canon)) == 1:
                            only = simplified[0]
                            node.pop(key, None)
                            for k, v in only.items():
                                if k not in node:
                                    node[k] = v
                            changed = True
                    except Exception:
                        pass
                    if not changed:
                        node[key] = simplified

            for child_key in ("properties", "patternProperties", "definitions", "$defs"):
                if child_key in node and isinstance(node[child_key], dict):
                    for k, v in list(node[child_key].items()):
                        node[child_key][k] = walk(v)

            if "items" in node:
                node["items"] = walk(node["items"])

            for key in ("allOf",):
                if key in node and isinstance(node[key], list):
                    node[key] = [walk(x) for x in node[key]]

            if "if" in node:
                node["if"] = walk(node["if"])
            if "then" in node:
                node["then"] = walk(node["then"])
            if "else" in node:
                node["else"] = walk(node["else"])

            return node

        return walk(s)

    @staticmethod
    def make_mcp_tool(tool: Tool, openai_tool_compatible: bool = True) -> MCPTool:
        """
        Serena 도구 인스턴스에서 MCP 도구를 생성합니다.

        Args:
            tool (Tool): 변환할 Serena 도구 인스턴스.
            openai_tool_compatible (bool): 도구 스키마를 OpenAI 도구와 호환되도록 처리할지 여부.
                (예: 'integer' 대신 'number' 필요). 이는 codex 내에서 Serena MCP를 사용하는 것을 허용합니다.

        Returns:
            MCPTool: 생성된 MCP 도구.
        """
        func_name = tool.get_name()
        func_doc = tool.get_apply_docstring() or ""
        func_arg_metadata = tool.get_apply_fn_metadata()
        is_async = False
        parameters = func_arg_metadata.arg_model.model_json_schema()
        if openai_tool_compatible:
            parameters = SerenaMCPFactory._sanitize_for_openai_tools(parameters)

        docstring = docstring_parser.parse(func_doc)

        overridden_description = tool.agent.get_context().tool_description_overrides.get(func_name, None)

        if overridden_description is not None:
            func_doc = overridden_description
        elif docstring.description:
            func_doc = docstring.description
        else:
            func_doc = ""
        func_doc = func_doc.strip().strip(".")
        if func_doc:
            func_doc += "."
        if docstring.returns and (docstring_returns_descr := docstring.returns.description):
            prefix = " " if func_doc else ""
            func_doc = f"{func_doc}{prefix}반환값: {docstring_returns_descr.strip().strip('.')}."

        docstring_params = {param.arg_name: param for param in docstring.params}
        parameters_properties: dict[str, dict[str, Any]] = parameters["properties"]
        for parameter, properties in parameters_properties.items():
            if (param_doc := docstring_params.get(parameter)) and param_doc.description:
                param_desc = f"{param_doc.description.strip().strip('.') + '.'}"
                properties["description"] = param_desc[0].upper() + param_desc[1:]

        def execute_fn(**kwargs) -> str:  # type: ignore
            return tool.apply_ex(log_call=True, catch_exceptions=True, **kwargs)

        return MCPTool(
            fn=execute_fn,
            name=func_name,
            description=func_doc,
            parameters=parameters,
            fn_metadata=func_arg_metadata,
            is_async=is_async,
            context_kwarg=None,
            annotations=None,
            title=None,
        )

    @abstractmethod
    def _iter_tools(self) -> Iterator[Tool]:
        """사용 가능한 도구들을 반복하는 이터레이터를 반환합니다."""
        pass

    def _set_mcp_tools(self, mcp: FastMCP, openai_tool_compatible: bool = False) -> None:
        """MCP 서버의 도구들을 업데이트합니다."""
        if mcp is not None:
            mcp._tool_manager._tools = {}
            for tool in self._iter_tools():
                mcp_tool = self.make_mcp_tool(tool, openai_tool_compatible=openai_tool_compatible)
                mcp._tool_manager._tools[tool.get_name()] = mcp_tool
            log.info(f"{len(mcp._tool_manager._tools)}개의 도구로 MCP 서버를 시작합니다: {list(mcp._tool_manager._tools.keys())}")

    @abstractmethod
    def _instantiate_agent(self, serena_config: SerenaConfig, modes: list[SerenaAgentMode]) -> None:
        """Serena 에이전트 인스턴스를 생성합니다."""
        pass

    def create_mcp_server(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        modes: Sequence[str] = DEFAULT_MODES,
        enable_web_dashboard: bool | None = None,
        enable_gui_log_window: bool | None = None,
        log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None,
        trace_lsp_communication: bool | None = None,
        tool_timeout: float | None = None,
    ) -> FastMCP:
        """
        MCP 서버를 생성합니다.

        Args:
            host (str): 바인딩할 호스트.
            port (int): 바인딩할 포트.
            modes (Sequence[str]): 모드 이름 또는 모드 파일 경로 목록.
            enable_web_dashboard (bool | None): 웹 대시보드 활성화 여부. 지정하지 않으면 Serena 설정 값을 따릅니다.
            enable_gui_log_window (bool | None): GUI 로그 창 활성화 여부. macOS에서는 현재 작동하지 않으며, True로 설정해도 무시됩니다.
                지정하지 않으면 Serena 설정 값을 따릅니다.
            log_level (str | None): 로그 레벨. 지정하지 않으면 Serena 설정 값을 따릅니다.
            trace_lsp_communication (bool | None): Serena와 언어 서버 간의 통신을 추적할지 여부.
                언어 서버 문제 디버깅에 유용합니다.
            tool_timeout (float | None): 도구 실행 시간 초과(초). 지정하지 않으면 Serena 설정 값을 따릅니다.

        Returns:
            FastMCP: 생성된 FastMCP 서버 인스턴스.
        """
        try:
            config = SerenaConfig.from_config_file()

            if enable_web_dashboard is not None:
                config.web_dashboard = enable_web_dashboard
            if enable_gui_log_window is not None:
                config.gui_log_window_enabled = enable_gui_log_window
            if log_level is not None:
                log_level = cast(Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], log_level.upper())
                config.log_level = logging.getLevelNamesMapping()[log_level]
            if trace_lsp_communication is not None:
                config.trace_lsp_communication = trace_lsp_communication
            if tool_timeout is not None:
                config.tool_timeout = tool_timeout

            modes_instances = [SerenaAgentMode.load(mode) for mode in modes]
            self._instantiate_agent(config, modes_instances)

        except Exception as e:
            show_fatal_exception_safe(e)
            raise

        Settings.model_config = SettingsConfigDict(env_prefix="FASTMCP_")
        instructions = self._get_initial_instructions()
        mcp = FastMCP(lifespan=self.server_lifespan, host=host, port=port, instructions=instructions)
        return mcp

    @asynccontextmanager
    @abstractmethod
    async def server_lifespan(self, mcp_server: FastMCP) -> AsyncIterator[None]:
        """서버 시작 및 종료 생명주기를 관리합니다."""
        yield None

    @abstractmethod
    def _get_initial_instructions(self) -> str:
        """초기 지침을 가져옵니다."""
        pass


class SerenaMCPFactorySingleProcess(SerenaMCPFactory):
    """
    SerenaAgent와 언어 서버가 MCP 서버와 동일한 프로세스에서 실행되는 MCP 서버 팩토리.
    """

    def __init__(self, context: str = DEFAULT_CONTEXT, project: str | None = None, memory_log_handler: MemoryLogHandler | None = None):
        """
        SerenaMCPFactorySingleProcess를 초기화합니다.

        Args:
            context (str): 컨텍스트 이름 또는 컨텍스트 파일 경로.
            project (str | None): 프로젝트의 절대 경로 또는 이미 등록된 프로젝트의 이름.
            memory_log_handler (MemoryLogHandler | None): 메모리 로그 핸들러.
        """
        super().__init__(context=context, project=project)
        self.agent: SerenaAgent | None = None
        self.memory_log_handler = memory_log_handler

    def _instantiate_agent(self, serena_config: SerenaConfig, modes: list[SerenaAgentMode]) -> None:
        """SerenaAgent 인스턴스를 생성하고 초기화합니다."""
        self.agent = SerenaAgent(
            project=self.project, serena_config=serena_config, context=self.context, modes=modes, memory_log_handler=self.memory_log_handler
        )

    def _iter_tools(self) -> Iterator[Tool]:
        """노출된 도구 인스턴스들을 반복합니다."""
        assert self.agent is not None
        yield from self.agent.get_exposed_tool_instances()

    def _get_initial_instructions(self) -> str:
        """에이전트로부터 초기 시스템 프롬프트를 생성하여 반환합니다."""
        assert self.agent is not None
        return self.agent.create_system_prompt()

    @asynccontextmanager
    async def server_lifespan(self, mcp_server: FastMCP) -> AsyncIterator[None]:
        """서버 생명주기 동안 도구를 설정하고 정리합니다."""
        openai_tool_compatible = self.context.name in ["chatgpt", "codex", "oaicompat-agent"]
        self._set_mcp_tools(mcp_server, openai_tool_compatible=openai_tool_compatible)
        log.info("MCP 서버 생명주기 설정 완료")
        yield