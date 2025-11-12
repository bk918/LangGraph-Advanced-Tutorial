"""
SerenaMCP - 고급 코딩 에이전트 툴킷

SerenaMCP는 Model Context Protocol (MCP) 서버를 기반으로 한 고급 코딩 에이전트 시스템입니다.
이 모듈은 SerenaAgent 클래스를 중심으로 프로젝트 라이프사이클 관리, 도구 시스템 조정,
언어 서버 관리, 메모리 시스템 등을 통합적으로 제공합니다.

주요 기능:
- 다중 프로젝트 지원 및 라이프사이클 관리
- 40+ 개의 특화 도구 시스템 조정
- Language Server Protocol (LSP) 통합
- 프로젝트별 메모리 및 지식 관리
- 동적 설정 및 모드 적용
- 웹 대시보드 및 GUI 로그 뷰어
- 비동기 태스크 처리 및 오류 복구
"""

import multiprocessing
import os
import platform
import sys
import threading
import webbrowser
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, TypeVar

from sensai.util import logging
from sensai.util.logging import LogTime

from interprompt.jinja_template import JinjaTemplate
from serena import serena_version
from serena.analytics import RegisteredTokenCountEstimator, ToolUsageStats
from serena.config.context_mode import RegisteredContext, SerenaAgentContext, SerenaAgentMode
from serena.config.serena_config import SerenaConfig, ToolInclusionDefinition, ToolSet, get_serena_managed_in_project_dir
from serena.dashboard import SerenaDashboardAPI
from serena.project import Project
from serena.prompt_factory import SerenaPromptFactory
from serena.tools import ActivateProjectTool, GetCurrentConfigTool, Tool, ToolMarker, ToolRegistry
from serena.util.inspection import iter_subclasses
from serena.util.logging import MemoryLogHandler
from solidlsp import SolidLanguageServer

if TYPE_CHECKING:
    from serena.gui_log_viewer import GuiLogViewer

log = logging.getLogger(__name__)
TTool = TypeVar("TTool", bound="Tool")
T = TypeVar("T")
SUCCESS_RESULT = "OK"


class ProjectNotFoundError(Exception):
    pass


class LinesRead:
    """
    파일에서 읽은 라인들의 캐싱 및 추적을 담당하는 클래스.

    이 클래스는 파일의 특정 라인들이 이미 읽혔는지 추적하여,
    불필요한 파일 재읽기를 방지하는 데 사용됩니다.

    Attributes:
        files: 파일별로 읽힌 라인들의 집합을 저장하는 딕셔너리
              key: 파일의 상대 경로
              value: (시작줄, 끝줄) 튜플들의 집합
    """

    def __init__(self) -> None:
        """LinesRead 인스턴스를 초기화합니다."""
        # 파일별 읽힌 라인들을 추적하는 딕셔너리
        # defaultdict를 사용하여 존재하지 않는 키에 대해 빈 집합 반환
        self.files: dict[str, set[tuple[int, int]]] = defaultdict(lambda: set())

    def add_lines_read(self, relative_path: str, lines: tuple[int, int]) -> None:
        """
        파일의 특정 라인 범위가 읽혔음을 기록합니다.

        Args:
            relative_path: 파일의 상대 경로
            lines: (시작줄, 끝줄) 튜플
        """
        self.files[relative_path].add(lines)

    def were_lines_read(self, relative_path: str, lines: tuple[int, int]) -> bool:
        """
        파일의 특정 라인 범위가 이미 읽혔는지 확인합니다.

        Args:
            relative_path: 파일의 상대 경로
            lines: (시작줄, 끝줄) 튜플

        Returns:
            이미 읽혔으면 True, 아니면 False
        """
        lines_read_in_file = self.files[relative_path]
        return lines in lines_read_in_file

    def invalidate_lines_read(self, relative_path: str) -> None:
        """
        파일의 읽기 기록을 무효화합니다.
        파일이 수정되었을 때 호출되어 캐시된 읽기 정보를 초기화합니다.

        Args:
            relative_path: 무효화할 파일의 상대 경로
        """
        if relative_path in self.files:
            del self.files[relative_path]


class MemoriesManager:
    """
    프로젝트별 메모리 파일을 관리하는 클래스.

    이 클래스는 프로젝트의 지식과 학습 데이터를 마크다운 파일 형태로
    저장하고 관리하는 역할을 담당합니다. 각 프로젝트는 독립적인 메모리 공간을 가집니다.

    주요 기능:
    - 메모리 파일 저장 및 로드
    - 메모리 파일 목록 조회
    - 메모리 파일 삭제
    - 메모리 파일 경로 관리

    Attributes:
        _memory_dir: 메모리 파일들이 저장되는 디렉토리 경로
    """

    def __init__(self, project_root: str):
        """
        MemoriesManager를 초기화합니다.

        Args:
            project_root: 프로젝트 루트 디렉토리 경로
        """
        # 프로젝트의 관리 디렉토리 내에 memories 폴더 생성
        self._memory_dir = Path(get_serena_managed_in_project_dir(project_root)) / "memories"
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    def _get_memory_file_path(self, name: str) -> Path:
        """
        메모리 파일의 전체 경로를 반환합니다.

        Args:
            name: 메모리 파일 이름 (확장자 제외)

        Returns:
            메모리 파일의 Path 객체

        Note:
            모델들이 .md 확장자를 혼동하여 사용하므로,
            파일명에서 .md 확장자를 자동으로 제거합니다.
        """
        # .md 확장자를 제거 (모델들이 혼동하여 사용할 수 있음)
        name = name.replace(".md", "")
        filename = f"{name}.md"
        return self._memory_dir / filename

    def load_memory(self, name: str) -> str:
        """
        저장된 메모리 파일을 읽어옵니다.

        Args:
            name: 메모리 파일 이름 (확장자 제외)

        Returns:
            메모리 파일의 내용, 파일이 없으면 오류 메시지
        """
        memory_file_path = self._get_memory_file_path(name)
        if not memory_file_path.exists():
            return f"Memory file {name} not found, consider creating it with the `write_memory` tool if you need it."
        with open(memory_file_path, encoding="utf-8") as f:
            return f.read()

    def save_memory(self, name: str, content: str) -> str:
        """
        메모리를 마크다운 파일로 저장합니다.

        Args:
            name: 메모리 파일 이름 (확장자 제외)
            content: 저장할 내용

        Returns:
            성공 메시지
        """
        memory_file_path = self._get_memory_file_path(name)
        with open(memory_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Memory {name} written."

    def list_memories(self) -> list[str]:
        """
        현재 저장된 모든 메모리 파일들의 목록을 반환합니다.

        Returns:
            메모리 파일 이름들의 리스트 (확장자 제외)
        """
        return [f.name.replace(".md", "") for f in self._memory_dir.iterdir() if f.is_file()]

    def delete_memory(self, name: str) -> str:
        """
        메모리 파일을 삭제합니다.

        Args:
            name: 삭제할 메모리 파일 이름 (확장자 제외)

        Returns:
            성공 메시지
        """
        memory_file_path = self._get_memory_file_path(name)
        memory_file_path.unlink()
        return f"Memory {name} deleted."


class AvailableTools:
    def __init__(self, tools: list[Tool]):
        """
        :param tools: the list of available tools
        """
        self.tools = tools
        self.tool_names = [tool.get_name_from_cls() for tool in tools]
        self.tool_marker_names = set()
        for marker_class in iter_subclasses(ToolMarker):
            for tool in tools:
                if isinstance(tool, marker_class):
                    self.tool_marker_names.add(marker_class.__name__)

    def __len__(self) -> int:
        return len(self.tools)


class SerenaAgent:
    """
    SerenaMCP의 중앙 오케스트레이터 클래스.

    이 클래스는 SerenaMCP의 핵심 두뇌 역할을 수행하며, 다음의 주요 기능을 담당합니다:

    1. 프로젝트 라이프사이클 관리
       - 다중 프로젝트 활성화/비활성화
       - 프로젝트별 설정 및 리소스 관리
       - 프로젝트 간 격리 및 전환

    2. 도구 시스템 조정
       - 40+ 개의 특화 도구 관리 및 실행
       - Context/Mode 기반 동적 도구 필터링
       - 도구 사용 통계 수집 및 분석

    3. 언어 서버 관리
       - LSP 서버 초기화 및 생명주기 관리
       - 다국어 지원 (16+ 프로그래밍 언어)
       - 심볼 분석 및 캐싱

    4. 메모리 시스템 유지
       - 프로젝트별 지식 저장 및 검색
       - 대화 맥락 및 학습 데이터 관리
       - 영구 저장소 관리

    5. 설정 및 모드 적용
       - 계층적 설정 시스템 (CLI > Project > User > Context)
       - 동적 Context/Mode 전환
       - 사용자 맞춤 설정 지원

    6. MCP 서버와의 통신
       - 클라이언트 요청 처리
       - 비동기 응답 관리
       - 오류 처리 및 복구

    Args:
        project: 활성화할 프로젝트 경로 또는 이름
        project_activation_callback: 프로젝트 활성화 후 호출할 콜백 함수
        serena_config: Serena 설정 객체 (None이면 파일에서 로드)
        context: 사용할 Context 객체 (None이면 기본값 사용)
        modes: 사용할 Mode 리스트 (None이면 기본값 사용)
        memory_log_handler: 메모리 로그 핸들러 (GUI/대시보드용)

    Attributes:
        serena_config: Serena 설정 객체
        _context: 현재 활성 Context
        _modes: 현재 활성 Mode들
        _active_project: 현재 활성 프로젝트
        language_server: LSP 서버 인스턴스
        memories_manager: 메모리 관리자
        _all_tools: 모든 도구 인스턴스
        _active_tools: 현재 활성 도구들
        _task_executor: 비동기 태스크 실행기
    """

    def __init__(
        self,
        project: str | None = None,
        project_activation_callback: Callable[[], None] | None = None,
        serena_config: SerenaConfig | None = None,
        context: SerenaAgentContext | None = None,
        modes: list[SerenaAgentMode] | None = None,
        memory_log_handler: MemoryLogHandler | None = None,
    ):
        """
        SerenaAgent를 초기화합니다.

        초기화 과정:
        1. 설정 로딩 (계층적 설정 시스템 적용)
        2. 도구 시스템 초기화 (모든 도구 인스턴스화)
        3. Context & Mode 적용 (동적 도구 필터링)
        4. 언어 서버 초기화 (백그라운드에서 LSP 서버 시작)
        5. 프로젝트 활성화 (지정된 프로젝트 로드)
        6. GUI/대시보드 초기화 (플랫폼별 지원)

        Args:
            project: 즉시 로드할 프로젝트 (None이면 프로젝트 로드 안 함)
                   프로젝트 경로 또는 이미 등록된 프로젝트 이름 가능
            project_activation_callback: 프로젝트 활성화 시 호출할 콜백 함수
            serena_config: Serena 설정 객체 (None이면 기본 위치에서 읽어옴)
        :param context: the context in which the agent is operating, None for default context.
            The context may adjust prompts, tool availability, and tool descriptions.
        :param modes: list of modes in which the agent is operating (they will be combined), None for default modes.
            The modes may adjust prompts, tool availability, and tool descriptions.
        :param memory_log_handler: a MemoryLogHandler instance from which to read log messages; if None, a new one will be created
            if necessary.
        """
        # 1단계: 설정 로딩 (계층적 설정 시스템 적용)
        # 설정 파일에서 SerenaConfig 로딩 (CLI 인수가 우선 적용됨)
        self.serena_config = serena_config or SerenaConfig.from_config_file()

        # 프로젝트별 인스턴스들 (프로젝트 활성화 시 초기화됨)
        self._active_project: Project | None = None
        self.language_server: SolidLanguageServer | None = None
        self.memories_manager: MemoriesManager | None = None
        self.lines_read: LinesRead | None = None

        # 2단계: 로그 레벨 조정
        serena_log_level = self.serena_config.log_level
        if Logger.root.level > serena_log_level:
            log.info(f"Changing the root logger level to {serena_log_level}")
            Logger.root.setLevel(serena_log_level)

        def get_memory_log_handler() -> MemoryLogHandler:
            nonlocal memory_log_handler
            if memory_log_handler is None:
                memory_log_handler = MemoryLogHandler(level=serena_log_level)
                Logger.root.addHandler(memory_log_handler)
            return memory_log_handler

        # 3단계: GUI 로그 창 초기화 (플랫폼별 지원)
        self._gui_log_viewer: Optional["GuiLogViewer"] = None
        if self.serena_config.gui_log_window_enabled:
            if platform.system() == "Darwin":
                log.warning("GUI log window is not supported on macOS")
            else:
                # macOS에서는 tkinter 의존성으로 인해 import 실패 가능성 있음
                from serena.gui_log_viewer import GuiLogViewer

                self._gui_log_viewer = GuiLogViewer("dashboard", title="Serena Logs", memory_log_handler=get_memory_log_handler())
                self._gui_log_viewer.start()

        # 4단계: Context 설정
        # Context는 에이전트의 실행 환경을 정의 (desktop-app, ide-assistant, agent 등)
        if context is None:
            context = SerenaAgentContext.load_default()
        self._context = context

        # 5단계: 도구 시스템 초기화 (모든 도구 클래스를 인스턴스화)
        # ToolRegistry를 통해 모든 도구 클래스를 찾아서 인스턴스 생성
        self._all_tools: dict[type[Tool], Tool] = {tool_class: tool_class(self) for tool_class in ToolRegistry().get_all_tool_classes()}
        tool_names = [tool.get_name_from_cls() for tool in self._all_tools.values()]

        # GUI 로그 창이 활성화된 경우 도구 이름들을 하이라이트 설정
        if self._gui_log_viewer is not None:
            self._gui_log_viewer.set_tool_names(tool_names)

        # 6단계: 도구 사용 통계 시스템 초기화
        # 사용 통계 수집이 활성화된 경우 ToolUsageStats 인스턴스 생성
        self._tool_usage_stats: ToolUsageStats | None = None
        if self.serena_config.record_tool_usage_stats:
            token_count_estimator = RegisteredTokenCountEstimator[self.serena_config.token_count_estimator]
            log.info(f"Tool usage statistics recording is enabled with token count estimator: {token_count_estimator.name}.")
            self._tool_usage_stats = ToolUsageStats(token_count_estimator)

        # 7단계: 웹 대시보드 초기화 (웹 프론트엔드 시작)
        # 대시보드는 실시간 로그, 도구 통계, 시스템 상태를 제공
        if self.serena_config.web_dashboard:
            self._dashboard_thread, port = SerenaDashboardAPI(
                get_memory_log_handler(), tool_names, agent=self, tool_usage_stats=self._tool_usage_stats
            ).run_in_thread()
            dashboard_url = f"http://127.0.0.1:{port}/dashboard/index.html"
            log.info("Serena web dashboard started at %s", dashboard_url)
            if self.serena_config.web_dashboard_open_on_launch:
                # 기본 웹 브라우저에서 대시보드 URL 열기 (출력 리다이렉션 제어를 위해 별도 프로세스 사용)
                process = multiprocessing.Process(target=self._open_dashboard, args=(dashboard_url,))
                process.start()
                process.join(timeout=1)

        # 8단계: 기본 정보 로깅
        # 서버 버전, 프로세스 ID, 설정 파일 정보 등을 로그로 기록
        log.info(f"Starting Serena server (version={serena_version()}, process id={os.getpid()}, parent process id={os.getppid()})")
        log.info("Configuration file: %s", self.serena_config.config_file_path)
        log.info("Available projects: {}".format(", ".join(self.serena_config.project_names)))
        log.info(f"Loaded tools ({len(self._all_tools)}): {', '.join([tool.get_name_from_cls() for tool in self._all_tools.values()])}")

        # 셸 설정 검증 (Windows Git-Bash 관련 문제 해결)
        self._check_shell_settings()

        # 9단계: 기본 도구 세트 결정 (MCP가 볼 수 있는 노출 도구들 정의)
        # Serena 설정, Context, JetBrains 모드에 따라 도구 포함/제외 결정
        tool_inclusion_definitions: list[ToolInclusionDefinition] = [self.serena_config, self._context]
        if self._context.name == RegisteredContext.IDE_ASSISTANT.value:
            tool_inclusion_definitions.extend(self._ide_assistant_context_tool_inclusion_definitions(project))
        if self.serena_config.jetbrains:
            tool_inclusion_definitions.append(SerenaAgentMode.from_name_internal("jetbrains"))

        # 기본 도구 세트 생성 및 필터링 적용
        self._base_tool_set = ToolSet.default().apply(*tool_inclusion_definitions)
        self._exposed_tools = AvailableTools([t for t in self._all_tools.values() if self._base_tool_set.includes_name(t.get_name())])
        log.info(f"Number of exposed tools: {len(self._exposed_tools)}")

        # 10단계: 태스크 실행기 생성 (언어 서버 시작 및 도구 실행용)
        # 단일 스레드 실행기를 사용하여 선형적인 태스크 실행 보장
        self._task_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="SerenaAgentExecutor")
        self._task_executor_lock = threading.Lock()
        self._task_executor_task_index = 1

        # 11단계: 프롬프트 팩토리 초기화
        # 다국어 프롬프트 템플릿 관리 시스템
        self.prompt_factory = SerenaPromptFactory()
        self._project_activation_callback = project_activation_callback

        # 12단계: 활성 모드 설정
        # Mode는 작업 패턴을 정의 (planning, editing, interactive 등)
        if modes is None:
            modes = SerenaAgentMode.load_default_modes()
        self._modes = modes

        # 13단계: 활성 도구 업데이트
        # 현재 Context와 Mode에 따라 활성 도구들을 결정
        self._active_tools: dict[type[Tool], Tool] = {}
        self._update_active_tools()

        # 14단계: 프로젝트 활성화 (제공된 경우 또는 단일 프로젝트인 경우)
        # 초기 프로젝트가 지정된 경우 즉시 활성화
        if project is not None:
            try:
                self.activate_project_from_path_or_name(project)
            except Exception as e:
                log.error(f"Error activating project '{project}' at startup: {e}", exc_info=e)

    def get_context(self) -> SerenaAgentContext:
        return self._context

    def get_tool_description_override(self, tool_name: str) -> str | None:
        return self._context.tool_description_overrides.get(tool_name, None)

    def _check_shell_settings(self) -> None:
        # On Windows, Claude Code sets COMSPEC to Git-Bash (often even with a path containing spaces),
        # which causes all sorts of trouble, preventing language servers from being launched correctly.
        # So we make sure that COMSPEC is unset if it has been set to bash specifically.
        if platform.system() == "Windows":
            comspec = os.environ.get("COMSPEC", "")
            if "bash" in comspec:
                os.environ["COMSPEC"] = ""  # force use of default shell
                log.info("Adjusting COMSPEC environment variable to use the default shell instead of '%s'", comspec)

    def _ide_assistant_context_tool_inclusion_definitions(self, project_root_or_name: str | None) -> list[ToolInclusionDefinition]:
        """
        In the IDE assistant context, the agent is assumed to work on a single project, and we thus
        want to apply that project's tool exclusions/inclusions from the get-go, limiting the set
        of tools that will be exposed to the client.
        Furthermore, we disable tools that are only relevant for project activation.
        So if the project exists, we apply all the aforementioned exclusions.

        :param project_root_or_name: the project root path or project name
        :return:
        """
        tool_inclusion_definitions = []
        if project_root_or_name is not None:
            # Note: Auto-generation is disabled, because the result must be returned instantaneously
            #   (project generation could take too much time), so as not to delay MCP server startup
            #   and provide responses to the client immediately.
            project = self.load_project_from_path_or_name(project_root_or_name, autogenerate=False)
            if project is not None:
                tool_inclusion_definitions.append(
                    ToolInclusionDefinition(
                        excluded_tools=[ActivateProjectTool.get_name_from_cls(), GetCurrentConfigTool.get_name_from_cls()]
                    )
                )
                tool_inclusion_definitions.append(project.project_config)
        return tool_inclusion_definitions

    def record_tool_usage_if_enabled(self, input_kwargs: dict, tool_result: str | dict, tool: Tool) -> None:
        """
        Record the usage of a tool with the given input and output strings if tool usage statistics recording is enabled.
        """
        tool_name = tool.get_name()
        if self._tool_usage_stats is not None:
            input_str = str(input_kwargs)
            output_str = str(tool_result)
            log.debug(f"Recording tool usage for tool '{tool_name}'")
            self._tool_usage_stats.record_tool_usage(tool_name, input_str, output_str)
        else:
            log.debug(f"Tool usage statistics recording is disabled, not recording usage of '{tool_name}'.")

    @staticmethod
    def _open_dashboard(url: str) -> None:
        # Redirect stdout and stderr file descriptors to /dev/null,
        # making sure that nothing can be written to stdout/stderr, even by subprocesses
        null_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null_fd, sys.stdout.fileno())
        os.dup2(null_fd, sys.stderr.fileno())
        os.close(null_fd)

        # open the dashboard URL in the default web browser
        webbrowser.open(url)

    def get_project_root(self) -> str:
        """
        :return: the root directory of the active project (if any); raises a ValueError if there is no active project
        """
        project = self.get_active_project()
        if project is None:
            raise ValueError("Cannot get project root if no project is active.")
        return project.project_root

    def get_exposed_tool_instances(self) -> list["Tool"]:
        """
        :return: the tool instances which are exposed (e.g. to the MCP client).
            Note that the set of exposed tools is fixed for the session, as
            clients don't react to changes in the set of tools, so this is the superset
            of tools that can be offered during the session.
            If a client should attempt to use a tool that is dynamically disabled
            (e.g. because a project is activated that disables it), it will receive an error.
        """
        return list(self._exposed_tools.tools)

    def get_active_project(self) -> Project | None:
        """
        :return: the active project or None if no project is active
        """
        return self._active_project

    def get_active_project_or_raise(self) -> Project:
        """
        :return: the active project or raises an exception if no project is active
        """
        project = self.get_active_project()
        if project is None:
            raise ValueError("No active project. Please activate a project first.")
        return project

    def set_modes(self, modes: list[SerenaAgentMode]) -> None:
        """
        Set the current mode configurations.

        :param modes: List of mode names or paths to use
        """
        self._modes = modes
        self._update_active_tools()

        log.info(f"Set modes to {[mode.name for mode in modes]}")

    def get_active_modes(self) -> list[SerenaAgentMode]:
        """
        :return: the list of active modes
        """
        return list(self._modes)

    def _format_prompt(self, prompt_template: str) -> str:
        template = JinjaTemplate(prompt_template)
        return template.render(available_tools=self._exposed_tools.tool_names, available_markers=self._exposed_tools.tool_marker_names)

    def create_system_prompt(self) -> str:
        available_markers = self._exposed_tools.tool_marker_names
        log.info("Generating system prompt with available_tools=(see exposed tools), available_markers=%s", available_markers)
        system_prompt = self.prompt_factory.create_system_prompt(
            context_system_prompt=self._format_prompt(self._context.prompt),
            mode_system_prompts=[self._format_prompt(mode.prompt) for mode in self._modes],
            available_tools=self._exposed_tools.tool_names,
            available_markers=available_markers,
        )
        log.info("System prompt:\n%s", system_prompt)
        return system_prompt

    def _update_active_tools(self) -> None:
        """
        Update the active tools based on enabled modes and the active project.
        The base tool set already takes the Serena configuration and the context into account
        (as well as any internal modes that are not handled dynamically, such as JetBrains mode).
        """
        tool_set = self._base_tool_set.apply(*self._modes)
        if self._active_project is not None:
            tool_set = tool_set.apply(self._active_project.project_config)
            if self._active_project.project_config.read_only:
                tool_set = tool_set.without_editing_tools()

        self._active_tools = {
            tool_class: tool_instance
            for tool_class, tool_instance in self._all_tools.items()
            if tool_set.includes_name(tool_instance.get_name())
        }

        log.info(f"Active tools ({len(self._active_tools)}): {', '.join(self.get_active_tool_names())}")

    def issue_task(self, task: Callable[[], Any], name: str | None = None) -> Future:
        """
        Issue a task to the executor for asynchronous execution.
        It is ensured that tasks are executed in the order they are issued, one after another.

        :param task: the task to execute
        :param name: the name of the task for logging purposes; if None, use the task function's name
        :return: a Future object representing the execution of the task
        """
        with self._task_executor_lock:
            task_name = f"Task-{self._task_executor_task_index}[{name or task.__name__}]"
            self._task_executor_task_index += 1

            def task_execution_wrapper() -> Any:
                with LogTime(task_name, logger=log):
                    return task()

            log.info(f"Scheduling {task_name}")
            return self._task_executor.submit(task_execution_wrapper)

    def execute_task(self, task: Callable[[], T]) -> T:
        """
        Executes the given task synchronously via the agent's task executor.
        This is useful for tasks that need to be executed immediately and whose results are needed right away.

        :param task: the task to execute
        :return: the result of the task execution
        """
        future = self.issue_task(task)
        return future.result()

    def is_using_language_server(self) -> bool:
        """
        :return: whether this agent uses language server-based code analysis
        """
        return not self.serena_config.jetbrains

    def _activate_project(self, project: Project) -> None:
        log.info(f"Activating {project.project_name} at {project.project_root}")
        self._active_project = project
        self._update_active_tools()

        # initialize project-specific instances which do not depend on the language server
        self.memories_manager = MemoriesManager(project.project_root)
        self.lines_read = LinesRead()

        def init_language_server() -> None:
            # start the language server
            with LogTime("Language server initialization", logger=log):
                self.reset_language_server()
                assert self.language_server is not None

        # initialize the language server in the background (if in language server mode)
        if self.is_using_language_server():
            self.issue_task(init_language_server)

        if self._project_activation_callback is not None:
            self._project_activation_callback()

    def load_project_from_path_or_name(self, project_root_or_name: str, autogenerate: bool) -> Project | None:
        """
        Get a project instance from a path or a name.

        :param project_root_or_name: the path to the project root or the name of the project
        :param autogenerate: whether to autogenerate the project for the case where first argument is a directory
            which does not yet contain a Serena project configuration file
        :return: the project instance if it was found/could be created, None otherwise
        """
        project_instance: Project | None = self.serena_config.get_project(project_root_or_name)
        if project_instance is not None:
            log.info(f"Found registered project '{project_instance.project_name}' at path {project_instance.project_root}")
        elif autogenerate and os.path.isdir(project_root_or_name):
            project_instance = self.serena_config.add_project_from_path(project_root_or_name)
            log.info(f"Added new project {project_instance.project_name} for path {project_instance.project_root}")
        return project_instance

    def activate_project_from_path_or_name(self, project_root_or_name: str) -> Project:
        """
        Activate a project from a path or a name.
        If the project was already registered, it will just be activated.
        If the argument is a path at which no Serena project previously existed, the project will be created beforehand.
        Raises ProjectNotFoundError if the project could neither be found nor created.

        :return: a tuple of the project instance and a Boolean indicating whether the project was newly
            created
        """
        project_instance: Project | None = self.load_project_from_path_or_name(project_root_or_name, autogenerate=True)
        if project_instance is None:
            raise ProjectNotFoundError(
                f"Project '{project_root_or_name}' not found: Not a valid project name or directory. "
                f"Existing project names: {self.serena_config.project_names}"
            )
        self._activate_project(project_instance)
        return project_instance

    def get_active_tool_classes(self) -> list[type["Tool"]]:
        """
        :return: the list of active tool classes for the current project
        """
        return list(self._active_tools.keys())

    def get_active_tool_names(self) -> list[str]:
        """
        :return: the list of names of the active tools for the current project
        """
        return sorted([tool.get_name_from_cls() for tool in self.get_active_tool_classes()])

    def tool_is_active(self, tool_class: type["Tool"] | str) -> bool:
        """
        :param tool_class: the class or name of the tool to check
        :return: True if the tool is active, False otherwise
        """
        if isinstance(tool_class, str):
            return tool_class in self.get_active_tool_names()
        else:
            return tool_class in self.get_active_tool_classes()

    def get_current_config_overview(self) -> str:
        """
        :return: a string overview of the current configuration, including the active and available configuration options
        """
        result_str = "Current configuration:\n"
        result_str += f"Serena version: {serena_version()}\n"
        result_str += f"Loglevel: {self.serena_config.log_level}, trace_lsp_communication={self.serena_config.trace_lsp_communication}\n"
        if self._active_project is not None:
            result_str += f"Active project: {self._active_project.project_name}\n"
        else:
            result_str += "No active project\n"
        result_str += "Available projects:\n" + "\n".join(list(self.serena_config.project_names)) + "\n"
        result_str += f"Active context: {self._context.name}\n"

        # Active modes
        active_mode_names = [mode.name for mode in self.get_active_modes()]
        result_str += "Active modes: {}\n".format(", ".join(active_mode_names)) + "\n"

        # Available but not active modes
        all_available_modes = SerenaAgentMode.list_registered_mode_names()
        inactive_modes = [mode for mode in all_available_modes if mode not in active_mode_names]
        if inactive_modes:
            result_str += "Available but not active modes: {}\n".format(", ".join(inactive_modes)) + "\n"

        # Active tools
        result_str += "Active tools (after all exclusions from the project, context, and modes):\n"
        active_tool_names = self.get_active_tool_names()
        # print the tool names in chunks
        chunk_size = 4
        for i in range(0, len(active_tool_names), chunk_size):
            chunk = active_tool_names[i : i + chunk_size]
            result_str += "  " + ", ".join(chunk) + "\n"

        # Available but not active tools
        all_tool_names = sorted([tool.get_name_from_cls() for tool in self._all_tools.values()])
        inactive_tool_names = [tool for tool in all_tool_names if tool not in active_tool_names]
        if inactive_tool_names:
            result_str += "Available but not active tools:\n"
            for i in range(0, len(inactive_tool_names), chunk_size):
                chunk = inactive_tool_names[i : i + chunk_size]
                result_str += "  " + ", ".join(chunk) + "\n"

        return result_str

    def is_language_server_running(self) -> bool:
        return self.language_server is not None and self.language_server.is_running()

    def reset_language_server(self) -> None:
        """
        Starts/resets the language server for the current project
        """
        tool_timeout = self.serena_config.tool_timeout
        if tool_timeout is None or tool_timeout < 0:
            ls_timeout = None
        else:
            if tool_timeout < 10:
                raise ValueError(f"Tool timeout must be at least 10 seconds, but is {tool_timeout} seconds")
            ls_timeout = tool_timeout - 5  # the LS timeout is for a single call, it should be smaller than the tool timeout

        # stop the language server if it is running
        if self.is_language_server_running():
            assert self.language_server is not None
            log.info(f"Stopping the current language server at {self.language_server.repository_root_path} ...")
            self.language_server.stop()
            self.language_server = None

        # instantiate and start the language server
        assert self._active_project is not None
        self.language_server = self._active_project.create_language_server(
            log_level=self.serena_config.log_level,
            ls_timeout=ls_timeout,
            trace_lsp_communication=self.serena_config.trace_lsp_communication,
            ls_specific_settings=self.serena_config.ls_specific_settings,
        )
        log.info(f"Starting the language server for {self._active_project.project_name}")
        self.language_server.start()
        if not self.language_server.is_running():
            raise RuntimeError(
                f"Failed to start the language server for {self._active_project.project_name} at {self._active_project.project_root}"
            )

    def get_tool(self, tool_class: type[TTool]) -> TTool:
        return self._all_tools[tool_class]  # type: ignore

    def print_tool_overview(self) -> None:
        ToolRegistry().print_tool_overview(self._active_tools.values())

    def mark_file_modified(self, relative_path: str) -> None:
        assert self.lines_read is not None
        self.lines_read.invalidate_lines_read(relative_path)

    def __del__(self) -> None:
        """
        Destructor to clean up the language server instance and GUI logger
        """
        if not hasattr(self, "_is_initialized"):
            return
        log.info("SerenaAgent is shutting down ...")
        if self.is_language_server_running():
            log.info("Stopping the language server ...")
            assert self.language_server is not None
            self.language_server.save_cache()
            self.language_server.stop()
        if self._gui_log_viewer:
            log.info("Stopping the GUI log window ...")
            self._gui_log_viewer.stop()

    def get_tool_by_name(self, tool_name: str) -> Tool:
        tool_class = ToolRegistry().get_tool_class_by_name(tool_name)
        return self.get_tool(tool_class)
