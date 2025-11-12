"""
serena/agno.py - Agno 에이전트 프레임워크 연동

이 파일은 Serena 에이전트를 Agno 프레임워크와 통합하기 위한 어댑터 클래스들을 포함합니다.
Serena의 도구들을 Agno가 이해할 수 있는 `Function` 형태로 변환하고,
Agno 에이전트의 생성 및 관리를 담당합니다.

주요 컴포넌트:
- SerenaAgnoToolkit: Serena의 도구들을 Agno `Toolkit`으로 래핑하는 클래스.
- SerenaAgnoAgentProvider: Agno 에이전트의 싱글톤 인스턴스를 제공하는 클래스.

아키텍처 노트:
- `SerenaAgnoToolkit`은 Serena의 각 `Tool`을 Agno의 `Function`으로 변환하여,
  Agno 에이전트가 Serena의 기능을 원활하게 사용할 수 있도록 합니다.
- `SerenaAgnoAgentProvider`는 Agno UI의 모듈 리로딩 특성으로 인해 발생할 수 있는
  중복 에이전트 생성을 방지하기 위해 싱글톤 패턴을 사용합니다.
"""
import argparse
import logging
import os
import threading
from pathlib import Path
from typing import Any

from agno.agent import Agent
from agno.memory import AgentMemory
from agno.models.base import Model
from agno.storage.sqlite import SqliteStorage
from agno.tools.function import Function
from agno.tools.toolkit import Toolkit
from dotenv import load_dotenv
from sensai.util.logging import LogTime

from serena.agent import SerenaAgent, Tool
from serena.config.context_mode import SerenaAgentContext
from serena.constants import REPO_ROOT
from serena.util.exception import show_fatal_exception_safe

log = logging.getLogger(__name__)


class SerenaAgnoToolkit(Toolkit):
    """
    Serena 도구들을 Agno 프레임워크의 `Toolkit`으로 변환하는 클래스.

    Serena 에이전트가 가진 도구들을 Agno의 `Function` 객체로 래핑하여,
    Agno 에이전트가 이를 사용할 수 있도록 제공합니다.
    """

    def __init__(self, serena_agent: SerenaAgent):
        """
        SerenaAgnoToolkit을 초기화합니다.

        Args:
            serena_agent (SerenaAgent): 도구를 가져올 Serena 에이전트 인스턴스.
        """
        super().__init__("Serena")
        for tool in serena_agent.get_exposed_tool_instances():
            self.functions[tool.get_name_from_cls()] = self._create_agno_function(tool)
        log.info("Agno 에이전트 함수: %s", list(self.functions.keys()))

    @staticmethod
    def _create_agno_function(tool: Tool) -> Function:
        """
        Serena `Tool`로부터 Agno `Function`을 생성합니다.

        Serena 도구의 `apply_ex` 메서드를 호출하는 엔트리포인트를 만들고,
        도구의 메타데이터를 사용하여 Agno `Function` 객체를 구성합니다.

        Args:
            tool (Tool): 변환할 Serena 도구.

        Returns:
            Function: 생성된 Agno 함수 객체.
        """

        def entrypoint(**kwargs: Any) -> str:
            if "kwargs" in kwargs:
                # Agno가 가끔 kwargs 인자를 명시적으로 전달하므로, 이를 병합합니다.
                kwargs.update(kwargs["kwargs"])
                del kwargs["kwargs"]
            log.info(f"도구 호출 중 {tool}")
            return tool.apply_ex(log_call=True, catch_exceptions=True, **kwargs)

        function = Function.from_callable(tool.get_apply_fn())
        function.name = tool.get_name_from_cls()
        function.entrypoint = entrypoint
        function.skip_entrypoint_processing = True
        return function


class SerenaAgnoAgentProvider:
    """
    Agno 에이전트의 싱글톤 인스턴스를 제공하는 클래스.

    Agno UI가 모듈을 리로드하는 특성 때문에 발생할 수 있는 중복 생성을 방지하기 위해
    Serena 에이전트의 싱글톤 인스턴스를 생성하고 관리합니다.

    Attributes:
        _agent (Agent | None): 캐시된 Agno 에이전트 인스턴스.
        _lock (threading.Lock): 스레드 안전한 인스턴스 생성을 위한 잠금 객체.
    """

    _agent: Agent | None = None
    _lock = threading.Lock()

    @classmethod
    def get_agent(cls, model: Model) -> Agent:
        """
        Serena 에이전트의 싱글톤 인스턴스를 반환하거나, 없으면 새로 생성합니다.

        NOTE: 이 방식은 관심사의 분리가 좋지 않아 매우 보기 흉하지만, Agno UI가
              `app` 변수를 정의하는 모듈을 리로드하는 방식으로 작동하기 때문에
              이와 같은 구현이 불가피합니다.

        Args:
            model (Model): 에이전트가 사용할 대규모 언어 모델.

        Returns:
            Agent: Agno 에이전트 인스턴스.
        """
        with cls._lock:
            if cls._agent is not None:
                return cls._agent

            # Serena 루트로 변경
            os.chdir(REPO_ROOT)

            load_dotenv()

            parser = argparse.ArgumentParser(description="Serena 코딩 어시스턴트")

            # 상호 배타적인 그룹 생성
            group = parser.add_mutually_exclusive_group()

            # 그룹에 인자 추가, 둘 다 동일한 대상으로 지정
            group.add_argument(
                "--project-file",
                required=False,
                help="프로젝트 경로 (또는 project.yml 파일).",
            )
            group.add_argument(
                "--project",
                required=False,
                help="프로젝트 경로 (또는 project.yml 파일).",
            )
            args = parser.parse_args()

            args_project_file = args.project or args.project_file

            if args_project_file:
                project_file = Path(args_project_file).resolve()
                # 프로젝트 파일 경로가 상대 경로인 경우, 프로젝트 루트와 결합하여 절대 경로로 만듭니다.
                if not project_file.is_absolute():
                    # 프로젝트 루트 디렉토리 가져오기 (scripts 디렉토리의 부모)
                    project_root = Path(REPO_ROOT)
                    project_file = project_root / args_project_file

                # 경로를 정규화하고 절대 경로로 만듭니다.
                project_file = str(project_file.resolve())
            else:
                project_file = None

            with LogTime("Serena 에이전트 로딩 중"):
                try:
                    serena_agent = SerenaAgent(project_file, context=SerenaAgentContext.load("agent"))
                except Exception as e:
                    show_fatal_exception_safe(e)
                    raise

            # 세션 간 기록을 유지하고 싶지 않더라도,
            # agno-ui가 대화 형식으로 작동하려면 디스크에 영구 저장소를 사용합니다.
            # 이 저장소는 세션 간에 삭제되어야 합니다.
            # 이는 벡터 검색 기반 도구 추가와 같은 에이전트의 사용자 지정 옵션과 충돌할 수 있습니다.
            # 설명은 여기를 참조하세요: https://www.reddit.com/r/agno/comments/1jk6qea/regarding_the_built_in_memory/
            sql_db_path = (Path("temp") / "agno_agent_storage.db").absolute()
            sql_db_path.parent.mkdir(exist_ok=True)
            # db 파일이 존재하면 삭제합니다.
            log.info(f"PID {os.getpid()}에서 DB 삭제 중")
            if sql_db_path.exists():
                sql_db_path.unlink()

            agno_agent = Agent(
                name="Serena",
                model=model,
                # 저장소가 필요한 이유에 대한 설명은 위를 참조하세요.
                storage=SqliteStorage(table_name="serena_agent_sessions", db_file=str(sql_db_path)),
                description="모든 기능을 갖춘 코딩 어시스턴트",
                tools=[SerenaAgnoToolkit(serena_agent)],
                # 도구 호출은 어차피 UI에 표시되므로, 도구별로 표시 여부를 설정할 수 있습니다.
                # 상세 로그를 보려면 serena 로거를 사용해야 합니다 (프로젝트 파일 경로에서 설정).
                show_tool_calls=False,
                markdown=True,
                system_message=serena_agent.create_system_prompt(),
                telemetry=False,
                memory=AgentMemory(),
                add_history_to_messages=True,
                num_history_responses=100,  # 비용 대비 기록 인지도를 고려하여 조정할 수 있습니다.
            )
            cls._agent = agno_agent
            log.info(f"에이전트 인스턴스화 완료: {agno_agent}")

        return agno_agent