"""
serena/dashboard.py - SerenaMCP 웹 대시보드 API

이 파일은 Serena 에이전트의 활동을 실시간으로 모니터링하고 관리하기 위한
Flask 기반의 웹 대시보드 API를 구현합니다.

주요 컴포넌트:
- SerenaDashboardAPI: 대시보드의 모든 API 엔드포인트와 웹 서버 로직을 포함하는 핵심 클래스.
- Request/Response 모델: Pydantic을 사용하여 API 요청 및 응답 데이터 구조를 정의합니다.
  (RequestLog, ResponseLog, ResponseToolNames, ResponseToolStats)

주요 기능:
- 실시간 로그 스트리밍: 에이전트의 로그 메시지를 웹 인터페이스로 전송합니다.
- 도구 사용 통계: 각 도구의 호출 횟수 및 토큰 사용량을 조회합니다.
- 에이전트 원격 종료: 웹 UI를 통해 Serena 에이전트 프로세스를 안전하게 종료시킬 수 있습니다.
- 정적 파일 서빙: 대시보드의 HTML, CSS, JavaScript 파일을 제공합니다.

아키텍처 노트:
- Flask 웹 프레임워크를 사용하여 간단하고 가벼운 웹 서버를 구현했습니다.
- `run_in_thread` 메서드를 통해 대시보드 서버를 별도의 데몬 스레드에서 실행함으로써,
  메인 에이전트의 동작을 방해하지 않고 독립적으로 운영됩니다.
- API 엔드포인트는 프론트엔드(Vue.js 기반)와 비동기적으로 통신하여 동적인 UI를 제공합니다.
- Werkzeug의 기본 로깅을 비활성화하여, Serena의 표준 로그 형식과 충돌하지 않도록 했습니다.
"""

import os
import socket
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from flask import Flask, Response, request, send_from_directory
from pydantic import BaseModel
from sensai.util import logging

from serena.analytics import ToolUsageStats
from serena.constants import SERENA_DASHBOARD_DIR
from serena.util.logging import MemoryLogHandler

if TYPE_CHECKING:
    from serena.agent import SerenaAgent

log = logging.getLogger(__name__)

# Werkzeug의 로깅을 비활성화하여 출력 혼잡을 방지합니다.
logging.getLogger("werkzeug").setLevel(logging.WARNING)


class RequestLog(BaseModel):
    """로그 메시지 요청을 위한 데이터 모델."""

    start_idx: int = 0


class ResponseLog(BaseModel):
    """로그 메시지 응답을 위한 데이터 모델."""

    messages: list[str]
    max_idx: int
    active_project: str | None = None


class ResponseToolNames(BaseModel):
    """도구 이름 목록 응답을 위한 데이터 모델."""

    tool_names: list[str]


class ResponseToolStats(BaseModel):
    """도구 사용 통계 응답을 위한 데이터 모델."""

    stats: dict[str, dict[str, int]]


class SerenaDashboardAPI:
    """
    Serena 웹 대시보드를 위한 Flask 기반 API 서버.

    이 클래스는 실시간 로그, 도구 정보, 통계 데이터를 제공하는 API 엔드포인트를 설정하고,
    웹 서버를 실행하는 역할을 담당합니다.

    Attributes:
        _memory_log_handler (MemoryLogHandler): 로그 메시지를 메모리에서 가져오기 위한 핸들러.
        _tool_names (list[str]): 에이전트에서 사용 가능한 도구 이름 목록.
        _agent (SerenaAgent): 현재 실행 중인 Serena 에이전트 인스턴스.
        _shutdown_callback (Callable | None): 서버 종료 시 호출될 콜백 함수.
        _app (Flask): Flask 애플리케이션 인스턴스.
        _tool_usage_stats (ToolUsageStats | None): 도구 사용 통계 관리 객체.
    """

    log = logging.getLogger(__qualname__)

    def __init__(
        self,
        memory_log_handler: MemoryLogHandler,
        tool_names: list[str],
        agent: "SerenaAgent",
        shutdown_callback: Callable[[], None] | None = None,
        tool_usage_stats: ToolUsageStats | None = None,
    ) -> None:
        """
        SerenaDashboardAPI를 초기화합니다.

        Args:
            memory_log_handler (MemoryLogHandler): 로그 메시지를 제공하는 메모리 로그 핸들러.
            tool_names (list[str]): 사용 가능한 도구들의 이름 목록.
            agent (SerenaAgent): 상호작용할 Serena 에이전트 인스턴스.
            shutdown_callback (Callable | None): 서버 종료 시 호출할 선택적 콜백.
            tool_usage_stats (ToolUsageStats | None): 도구 사용 통계를 관리하는 객체.
        """
        self._memory_log_handler = memory_log_handler
        self._tool_names = tool_names
        self._agent = agent
        self._shutdown_callback = shutdown_callback
        self._app = Flask(__name__)
        self._tool_usage_stats = tool_usage_stats
        self._setup_routes()

    @property
    def memory_log_handler(self) -> MemoryLogHandler:
        """메모리 로그 핸들러를 반환합니다."""
        return self._memory_log_handler

    def _setup_routes(self) -> None:
        """Flask 애플리케이션에 모든 API 및 정적 파일 라우트를 설정합니다."""

        @self._app.route("/dashboard/<path:filename>")
        def serve_dashboard(filename: str) -> Response:
            """대시보드 정적 파일을 서빙합니다."""
            return send_from_directory(SERENA_DASHBOARD_DIR, filename)

        @self._app.route("/dashboard/")
        def serve_dashboard_index() -> Response:
            """대시보드의 메인 index.html 파일을 서빙합니다."""
            return send_from_directory(SERENA_DASHBOARD_DIR, "index.html")

        @self._app.route("/get_log_messages", methods=["POST"])
        def get_log_messages() -> dict[str, Any]:
            """특정 인덱스부터의 로그 메시지를 JSON 형식으로 반환합니다."""
            request_data = request.get_json()
            request_log = RequestLog.model_validate(request_data) if request_data else RequestLog()
            result = self._get_log_messages(request_log)
            return result.model_dump()

        @self._app.route("/get_tool_names", methods=["GET"])
        def get_tool_names() -> dict[str, Any]:
            """사용 가능한 모든 도구의 이름을 JSON 형식으로 반환합니다."""
            result = self._get_tool_names()
            return result.model_dump()

        @self._app.route("/get_tool_stats", methods=["GET"])
        def get_tool_stats_route() -> dict[str, Any]:
            """도구 사용 통계를 JSON 형식으로 반환합니다."""
            result = self._get_tool_stats()
            return result.model_dump()

        @self._app.route("/clear_tool_stats", methods=["POST"])
        def clear_tool_stats_route() -> dict[str, str]:
            """기록된 도구 사용 통계를 초기화합니다."""
            self._clear_tool_stats()
            return {"status": "cleared"}

        @self._app.route("/get_token_count_estimator_name", methods=["GET"])
        def get_token_count_estimator_name() -> dict[str, str]:
            """현재 사용 중인 토큰 수 추정기의 이름을 반환합니다."""
            estimator_name = self._tool_usage_stats.token_estimator_name if self._tool_usage_stats else "unknown"
            return {"token_count_estimator_name": estimator_name}

        @self._app.route("/shutdown", methods=["PUT"])
        def shutdown() -> dict[str, str]:
            """Serena 에이전트 서버를 종료시킵니다."""
            self._shutdown()
            return {"status": "shutting down"}

    def _get_log_messages(self, request_log: RequestLog) -> ResponseLog:
        """요청된 범위의 로그 메시지와 현재 활성 프로젝트 정보를 반환합니다."""
        all_messages = self._memory_log_handler.get_log_messages()
        requested_messages = all_messages[request_log.start_idx :] if request_log.start_idx <= len(all_messages) else []
        project = self._agent.get_active_project()
        project_name = project.project_name if project else None
        return ResponseLog(messages=requested_messages, max_idx=len(all_messages) - 1, active_project=project_name)

    def _get_tool_names(self) -> ResponseToolNames:
        """사용 가능한 도구 이름 목록을 응답 모델에 담아 반환합니다."""
        return ResponseToolNames(tool_names=self._tool_names)

    def _get_tool_stats(self) -> ResponseToolStats:
        """도구 사용 통계를 응답 모델에 담아 반환합니다."""
        if self._tool_usage_stats is not None:
            return ResponseToolStats(stats=self._tool_usage_stats.get_tool_stats_dict())
        return ResponseToolStats(stats={})

    def _clear_tool_stats(self) -> None:
        """도구 사용 통계를 초기화합니다."""
        if self._tool_usage_stats is not None:
            self._tool_usage_stats.clear()

    def _shutdown(self) -> None:
        """에이전트 종료 로직을 실행합니다."""
        log.info("Serena를 종료합니다.")
        if self._shutdown_callback:
            self._shutdown_callback()
        else:
            os._exit(0)

    @staticmethod
    def _find_first_free_port(start_port: int) -> int:
        """
        지정된 포트 번호부터 시작하여 사용 가능한 첫 번째 포트를 찾습니다.

        Args:
            start_port (int): 검색을 시작할 포트 번호.

        Returns:
            int: 사용 가능한 첫 번째 포트 번호.

        Raises:
            RuntimeError: 사용 가능한 포트를 찾지 못했을 경우 발생합니다.
        """
        port = start_port
        while port <= 65535:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(("0.0.0.0", port))
                    return port
            except OSError:
                port += 1
        raise RuntimeError(f"{start_port}부터 시작하는 사용 가능한 포트를 찾을 수 없습니다.")

    def run(self, host: str = "0.0.0.0", port: int = 0x5EDA) -> int:
        """
        지정된 호스트와 포트에서 대시보드 웹 서버를 실행합니다.

        Args:
            host (str): 서버가 바인딩될 호스트 주소.
            port (int): 서버가 리스닝할 포트 번호.

        Returns:
            int: 실제 사용된 포트 번호.
        """
        from flask import cli

        # Flask의 기본 서버 배너 출력을 비활성화합니다.
        cli.show_server_banner = lambda *args, **kwargs: None

        self._app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
        return port

    def run_in_thread(self) -> tuple[threading.Thread, int]:
        """
        별도의 데몬 스레드에서 웹 서버를 실행하고, 사용된 스레드와 포트 번호를 반환합니다.

        Returns:
            tuple[threading.Thread, int]: 웹 서버가 실행 중인 스레드와 사용된 포트 번호.
        """
        port = self._find_first_free_port(0x5EDA)
        thread = threading.Thread(target=lambda: self.run(port=port), daemon=True)
        thread.start()
        return thread, port