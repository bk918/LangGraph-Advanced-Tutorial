"serena/cli.py - Serena 커맨드 라인 인터페이스(CLI)

이 파일은 `click` 라이브러리를 사용하여 Serena 에이전트의 주요 기능을
커맨드 라인에서 실행할 수 있도록 하는 CLI를 구현합니다.

주요 기능:
- MCP 서버 시작 (`start-mcp-server`)
- 프로젝트 관리 (`project` 그룹: yml 생성, 인덱싱, 상태 확인)
- 컨텍스트 및 모드 관리 (`context`, `mode` 그룹: 생성, 수정, 삭제, 목록 조회)
- 시스템 프롬프트 출력 (`print-system-prompt`)
- 도구 및 프롬프트 관리 (`tools`, `prompts` 그룹)

아키텍처 노트:
- `click.Group`을 상속받은 `AutoRegisteringGroup`을 사용하여,
  각 명령어 그룹 내에 정의된 `@click.command`들을 자동으로 등록합니다.
- 각 명령어 그룹(예: `TopLevelCommands`, `ProjectCommands`)은 특정 기능과 관련된
  서브커맨드들을 논리적으로 묶어 관리합니다.
- `ProjectType` 커스텀 파라미터 타입을 정의하여, 프로젝트를 이름 또는 경로로
  유연하게 지정할 수 있도록 합니다.
"
import glob
import json
import os
import shutil
import subprocess
import sys
from logging import Logger
from pathlib import Path
from typing import Any, Literal

import click
from sensai.util import logging
from sensai.util.logging import FileLoggerContext, datetime_tag
from tqdm import tqdm

from serena.agent import SerenaAgent
from serena.config.context_mode import SerenaAgentContext, SerenaAgentMode
from serena.config.serena_config import ProjectConfig, SerenaConfig, SerenaPaths
from serena.constants import (
    DEFAULT_CONTEXT,
    DEFAULT_MODES,
    PROMPT_TEMPLATES_DIR_IN_USER_HOME,
    PROMPT_TEMPLATES_DIR_INTERNAL,
    SERENA_LOG_FORMAT,
    SERENA_MANAGED_DIR_IN_HOME,
    SERENAS_OWN_CONTEXT_YAMLS_DIR,
    SERENAS_OWN_MODE_YAMLS_DIR,
    USER_CONTEXT_YAMLS_DIR,
    USER_MODE_YAMLS_DIR,
)
from serena.mcp import SerenaMCPFactory, SerenaMCPFactorySingleProcess
from serena.project import Project
from serena.tools import FindReferencingSymbolsTool, FindSymbolTool, GetSymbolsOverviewTool, SearchForPatternTool, ToolRegistry
from serena.util.logging import MemoryLogHandler
from solidlsp.ls_config import Language
from solidlsp.util.subprocess_util import subprocess_kwargs

log = logging.getLogger(__name__)

# --------------------- 유틸리티 -------------------------------------


def _open_in_editor(path: str) -> None:
    """시스템의 기본 편집기나 뷰어에서 주어진 파일을 엽니다."""
    editor = os.environ.get("EDITOR")
    run_kwargs = subprocess_kwargs()
    try:
        if editor:
            subprocess.run([editor, path], check=False, **run_kwargs)
        elif sys.platform.startswith("win"):
            try:
                os.startfile(path)
            except OSError:
                subprocess.run(["notepad.exe", path], check=False, **run_kwargs)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False, **run_kwargs)
        else:
            subprocess.run(["xdg-open", path], check=False, **run_kwargs)
    except Exception as e:
        print(f"{path}를 여는 데 실패했습니다: {e}")


class ProjectType(click.ParamType):
    """프로젝트 이름 또는 프로젝트 디렉토리 경로를 허용하는 ParamType."""

    name = "[PROJECT_NAME|PROJECT_PATH]"

    def convert(self, value: str, param: Any, ctx: Any) -> str:
        path = Path(value).resolve()
        if path.exists() and path.is_dir():
            return str(path)
        return value


PROJECT_TYPE = ProjectType()


class AutoRegisteringGroup(click.Group):
    """
    클래스에 정의된 click.Command 속성들을 그룹에 자동으로 등록하는 click.Group 서브클래스.

    초기화 후, 자체 클래스에서 click.Command 인스턴스(일반적으로 @click.command로 생성됨)인
    속성들을 검사하고 각각에 대해 self.add_command(cmd)를 호출합니다.
    이를 통해 수동 등록 없이 IDE 친화적인 구성을 위해 서브클래스에서 명령을 정적 메서드로
    정의할 수 있습니다.
    """

    def __init__(self, name: str, help: str):
        super().__init__(name=name, help=help)
        # 클래스 속성을 스캔하여 click.Command 인스턴스를 찾아 등록합니다.
        for attr in dir(self.__class__):
            cmd = getattr(self.__class__, attr)
            if isinstance(cmd, click.Command):
                self.add_command(cmd)


class TopLevelCommands(AutoRegisteringGroup):
    """핵심 Serena 명령어를 포함하는 루트 CLI 그룹."""

    def __init__(self) -> None:
        super().__init__(name="serena", help="Serena CLI 명령어. 각 명령어에 대한 자세한 정보는 `<command> --help`로 확인할 수 있습니다.")

    @staticmethod
    @click.command("start-mcp-server", help="Serena MCP 서버를 시작합니다.")
    @click.option("--project", "project", type=PROJECT_TYPE, default=None, help="시작 시 활성화할 프로젝트의 경로 또는 이름.")
    @click.option("--project-file", "project", type=PROJECT_TYPE, default=None, help="[사용되지 않음] --project를 사용하세요.")
    @click.argument("project_file_arg", type=PROJECT_TYPE, required=False, default=None, metavar="")
    @click.option(
        "--context", type=str, default=DEFAULT_CONTEXT, show_default=True, help="내장 컨텍스트 이름 또는 사용자 정의 컨텍스트 YAML 경로."
    )
    @click.option(
        "--mode",
        "modes",
        type=str,
        multiple=True,
        default=DEFAULT_MODES,
        show_default=True,
        help="내장 모드 이름 또는 사용자 정의 모드 YAML 경로.",
    )
    @click.option(
        "--transport",
        type=click.Choice(["stdio", "sse", "streamable-http"]),
        default="stdio",
        show_default=True,
        help="전송 프로토콜.",
    )
    @click.option("--host", type=str, default="0.0.0.0", show_default=True)
    @click.option("--port", type=int, default=8000, show_default=True)
    @click.option("--enable-web-dashboard", type=bool, is_flag=False, default=None, help="설정 파일의 대시보드 설정을 재정의합니다.")
    @click.option("--enable-gui-log-window", type=bool, is_flag=False, default=None, help="설정 파일의 GUI 로그 창 설정을 재정의합니다.")
    @click.option(
        "--log-level",
        type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
        default=None,
        help="설정 파일의 로그 레벨을 재정의합니다.",
    )
    @click.option("--trace-lsp-communication", type=bool, is_flag=False, default=None, help="LSP 통신을 추적할지 여부.")
    @click.option("--tool-timeout", type=float, default=None, help="설정 파일의 도구 실행 시간 초과를 재정의합니다.")
    def start_mcp_server(
        project: str | None,
        project_file_arg: str | None,
        context: str,
        modes: tuple[str, ...],
        transport: Literal["stdio", "sse", "streamable-http"],
        host: str,
        port: int,
        enable_web_dashboard: bool | None,
        enable_gui_log_window: bool | None,
        log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None,
        trace_lsp_communication: bool | None,
        tool_timeout: float | None,
    ) -> None:
        # 로깅 초기화, 처음에는 INFO 레벨 사용 (나중에 SerenaAgent가 설정에 따라 조정)
        #   * 메모리 로그 핸들러 (GUI/대시보드용)
        #   * stderr 스트림 핸들러 (직접 콘솔 출력용, Claude Desktop과 같은 클라이언트에서도 캡처됨)
        #   * 파일 핸들러
        # (stdout은 MCP 서버가 클라이언트와 통신하는 데 사용되므로 로깅에 절대 사용해서는 안 됩니다.)
        Logger.root.setLevel(logging.INFO)
        formatter = logging.Formatter(SERENA_LOG_FORMAT)
        memory_log_handler = MemoryLogHandler()
        Logger.root.addHandler(memory_log_handler)
        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        stderr_handler.formatter = formatter
        Logger.root.addHandler(stderr_handler)
        log_path = SerenaPaths().get_next_log_file_path("mcp")
        file_handler = logging.FileHandler(log_path, mode="w")
        file_handler.formatter = formatter
        Logger.root.addHandler(file_handler)

        log.info("Serena MCP 서버 초기화 중")
        log.info("로그 저장 위치: %s", log_path)
        project_file = project_file_arg or project
        factory = SerenaMCPFactorySingleProcess(context=context, project=project_file, memory_log_handler=memory_log_handler)
        server = factory.create_mcp_server(
            host=host,
            port=port,
            modes=modes,
            enable_web_dashboard=enable_web_dashboard,
            enable_gui_log_window=enable_gui_log_window,
            log_level=log_level,
            trace_lsp_communication=trace_lsp_communication,
            tool_timeout=tool_timeout,
        )
        if project_file_arg:
            log.warning(
                "위치 기반 프로젝트 인자는 더 이상 사용되지 않습니다. --project를 사용하세요. 사용된 인자: %s",
                project_file,
            )
        log.info("MCP 서버 시작 중…")
        server.run(transport=transport)

    @staticmethod
    @click.command("print-system-prompt", help="프로젝트의 시스템 프롬프트를 출력합니다.")
    @click.argument("project", type=click.Path(exists=True), default=os.getcwd(), required=False)
    @click.option(
        "--log-level",
        type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
        default="WARNING",
        help="프롬프트 생성 시 로그 레벨.",
    )
    @click.option("--only-instructions", is_flag=True, help="접두사/접미사 없이 초기 지침만 출력합니다.")
    @click.option(
        "--context", type=str, default=DEFAULT_CONTEXT, show_default=True, help="내장 컨텍스트 이름 또는 사용자 정의 컨텍스트 YAML 경로."
    )
    @click.option(
        "--mode",
        "modes",
        type=str,
        multiple=True,
        default=DEFAULT_MODES,
        show_default=True,
        help="내장 모드 이름 또는 사용자 정의 모드 YAML 경로.",
    )
    def print_system_prompt(project: str, log_level: str, only_instructions: bool, context: str, modes: tuple[str, ...]) -> None:
        prefix = "Serena의 심볼릭 도구에 접근할 수 있습니다. 아래는 사용 지침이며, 이를 고려해야 합니다."
        postfix = "위 지침을 이해했으며 작업을 받을 준비가 되었음을 인정하며 시작합니다."
        from serena.tools.workflow_tools import InitialInstructionsTool

        lvl = logging.getLevelNamesMapping()[log_level.upper()]
        logging.configure(level=lvl)
        context_instance = SerenaAgentContext.load(context)
        mode_instances = [SerenaAgentMode.load(mode) for mode in modes]
        agent = SerenaAgent(
            project=os.path.abspath(project),
            serena_config=SerenaConfig(web_dashboard=False, log_level=lvl),
            context=context_instance,
            modes=mode_instances,
        )
        tool = agent.get_tool(InitialInstructionsTool)
        instr = tool.apply()
        if only_instructions:
            print(instr)
        else:
            print(f"{prefix}\n{instr}\n{postfix}")


class ModeCommands(AutoRegisteringGroup):
    """'mode' 서브커맨드를 위한 그룹."""

    def __init__(self) -> None:
        super().__init__(name="mode", help="Serena 모드를 관리합니다. `mode <command> --help`로 각 명령어의 자세한 정보를 확인할 수 있습니다.")

    @staticmethod
    @click.command("list", help="사용 가능한 모드를 나열합니다.")
    def list() -> None:
        mode_names = SerenaAgentMode.list_registered_mode_names()
        max_len_name = max(len(name) for name in mode_names) if mode_names else 20
        for name in mode_names:
            mode_yml_path = SerenaAgentMode.get_path(name)
            is_internal = Path(mode_yml_path).is_relative_to(SERENAS_OWN_MODE_YAMLS_DIR)
            descriptor = "(내장)" if is_internal else f"({mode_yml_path}에 위치)"
            name_descr_string = f"{name:<{max_len_name + 4}}{descriptor}"
            click.echo(name_descr_string)

    @staticmethod
    @click.command("create", help="새 모드를 생성하거나 내장 모드를 복사합니다.")
    @click.option(
        "--name",
        "-n",
        type=str,
        default=None,
        help="새 모드의 이름. --from-internal이 전달된 경우 비워두면 동일한 이름의 모드를 생성하여 내장 모드를 재정의합니다.",
    )
    @click.option("--from-internal", "from_internal", type=str, default=None, help="내장 모드에서 복사합니다.")
    def create(name: str, from_internal: str) -> None:
        if not (name or from_internal):
            raise click.UsageError("--name 또는 --from-internal 중 하나 이상을 제공해야 합니다.")
        mode_name = name or from_internal
        dest = os.path.join(USER_MODE_YAMLS_DIR, f"{mode_name}.yml")
        src = (
            os.path.join(SERENAS_OWN_MODE_YAMLS_DIR, f"{from_internal}.yml")
            if from_internal
            else os.path.join(SERENAS_OWN_MODE_YAMLS_DIR, "mode.template.yml")
        )
        if not os.path.exists(src):
            raise FileNotFoundError(
                f"내장 모드 '{from_internal}'를 {SERENAS_OWN_MODE_YAMLS_DIR}에서 찾을 수 없습니다. 사용 가능한 모드: {SerenaAgentMode.list_registered_mode_names()}"
            )
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(src, dest)
        click.echo(f"'{mode_name}' 모드를 {dest}에 생성했습니다.")
        _open_in_editor(dest)

    @staticmethod
    @click.command("edit", help="사용자 정의 모드 YAML 파일을 편집합니다.")
    @click.argument("mode_name")
    def edit(mode_name: str) -> None:
        path = os.path.join(USER_MODE_YAMLS_DIR, f"{mode_name}.yml")
        if not os.path.exists(path):
            if mode_name in SerenaAgentMode.list_registered_mode_names(include_user_modes=False):
                click.echo(
                    f"모드 '{mode_name}'는 내장 모드이므로 직접 편집할 수 없습니다. "
                    f"'mode create --from-internal {mode_name}'를 사용하여 재정의하는 사용자 정의 모드를 생성한 후 편집하세요."
                )
            else:
                click.echo(f"사용자 정의 모드 '{mode_name}'를 찾을 수 없습니다. 'mode create --name {mode_name}'로 생성하세요.")
            return
        _open_in_editor(path)

    @staticmethod
    @click.command("delete", help="사용자 정의 모드 파일을 삭제합니다.")
    @click.argument("mode_name")
    def delete(mode_name: str) -> None:
        path = os.path.join(USER_MODE_YAMLS_DIR, f"{mode_name}.yml")
        if not os.path.exists(path):
            click.echo(f"사용자 정의 모드 '{mode_name}'를 찾을 수 없습니다.")
            return
        os.remove(path)
        click.echo(f"사용자 정의 모드 '{mode_name}'를 삭제했습니다.")


class ContextCommands(AutoRegisteringGroup):
    """'context' 서브커맨드를 위한 그룹."""

    def __init__(self) -> None:
        super().__init__(
            name="context", help="Serena 컨텍스트를 관리합니다. `context <command> --help`로 각 명령어의 자세한 정보를 확인할 수 있습니다."
        )

    @staticmethod
    @click.command("list", help="사용 가능한 컨텍스트를 나열합니다.")
    def list() -> None:
        context_names = SerenaAgentContext.list_registered_context_names()
        max_len_name = max(len(name) for name in context_names) if context_names else 20
        for name in context_names:
            context_yml_path = SerenaAgentContext.get_path(name)
            is_internal = Path(context_yml_path).is_relative_to(SERENAS_OWN_CONTEXT_YAMLS_DIR)
            descriptor = "(내장)" if is_internal else f"({context_yml_path}에 위치)"
            name_descr_string = f"{name:<{max_len_name + 4}}{descriptor}"
            click.echo(name_descr_string)

    @staticmethod
    @click.command("create", help="새 컨텍스트를 생성하거나 내장 컨텍스트를 복사합니다.")
    @click.option(
        "--name",
        "-n",
        type=str,
        default=None,
        help="새 컨텍스트의 이름. --from-internal이 전달된 경우 비워두면 동일한 이름의 컨텍스트를 생성하여 내장 컨텍스트를 재정의합니다.",
    )
    @click.option("--from-internal", "from_internal", type=str, default=None, help="내장 컨텍스트에서 복사합니다.")
    def create(name: str, from_internal: str) -> None:
        if not (name or from_internal):
            raise click.UsageError("--name 또는 --from-internal 중 하나 이상을 제공해야 합니다.")
        ctx_name = name or from_internal
        dest = os.path.join(USER_CONTEXT_YAMLS_DIR, f"{ctx_name}.yml")
        src = (
            os.path.join(SERENAS_OWN_CONTEXT_YAMLS_DIR, f"{from_internal}.yml")
            if from_internal
            else os.path.join(SERENAS_OWN_CONTEXT_YAMLS_DIR, "context.template.yml")
        )
        if not os.path.exists(src):
            raise FileNotFoundError(
                f"내장 컨텍스트 '{from_internal}'를 {SERENAS_OWN_CONTEXT_YAMLS_DIR}에서 찾을 수 없습니다. 사용 가능한 컨텍스트: {SerenaAgentContext.list_registered_context_names()}"
            )
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(src, dest)
        click.echo(f"컨텍스트 '{ctx_name}'를 {dest}에 생성했습니다.")
        _open_in_editor(dest)

    @staticmethod
    @click.command("edit", help="사용자 정의 컨텍스트 YAML 파일을 편집합니다.")
    @click.argument("context_name")
    def edit(context_name: str) -> None:
        path = os.path.join(USER_CONTEXT_YAMLS_DIR, f"{context_name}.yml")
        if not os.path.exists(path):
            if context_name in SerenaAgentContext.list_registered_context_names(include_user_contexts=False):
                click.echo(
                    f"컨텍스트 '{context_name}'는 내장 컨텍스트이므로 직접 편집할 수 없습니다. "
                    f"'context create --from-internal {context_name}'를 사용하여 재정의하는 사용자 정의 컨텍스트를 생성한 후 편집하세요."
                )
            else:
                click.echo(f"사용자 정의 컨텍스트 '{context_name}'를 찾을 수 없습니다. 'context create --name {context_name}'로 생성하세요.")
            return
        _open_in_editor(path)

    @staticmethod
    @click.command("delete", help="사용자 정의 컨텍스트 파일을 삭제합니다.")
    @click.argument("context_name")
    def delete(context_name: str) -> None:
        path = os.path.join(USER_CONTEXT_YAMLS_DIR, f"{context_name}.yml")
        if not os.path.exists(path):
            click.echo(f"사용자 정의 컨텍스트 '{context_name}'를 찾을 수 없습니다.")
            return
        os.remove(path)
        click.echo(f"사용자 정의 컨텍스트 '{context_name}'를 삭제했습니다.")


class SerenaConfigCommands(AutoRegisteringGroup):
    """'config' 서브커맨드를 위한 그룹."""

    def __init__(self) -> None:
        super().__init__(name="config", help="Serena 설정을 관리합니다.")

    @staticmethod
    @click.command(
        "edit", help="기본 편집기에서 serena_config.yml을 편집합니다. 설정 파일이 없으면 템플릿에서 생성합니다."
    )
    def edit() -> None:
        config_path = os.path.join(SERENA_MANAGED_DIR_IN_HOME, "serena_config.yml")
        if not os.path.exists(config_path):
            SerenaConfig.generate_config_file(config_path)
        _open_in_editor(config_path)


class ProjectCommands(AutoRegisteringGroup):
    """'project' 서브커맨드를 위한 그룹."""

    def __init__(self) -> None:
        super().__init__(
            name="project", help="Serena 프로젝트를 관리합니다. `project <command> --help`로 각 명령어의 자세한 정보를 확인할 수 있습니다."
        )

    @staticmethod
    @click.command("generate-yml", help="project.yml 파일을 생성합니다.")
    @click.argument("project_path", type=click.Path(exists=True, file_okay=False), default=os.getcwd())
    @click.option("--language", type=str, default=None, help="프로그래밍 언어; 지정하지 않으면 추론됩니다.")
    def generate_yml(project_path: str, language: str | None = None) -> None:
        yml_path = os.path.join(project_path, ProjectConfig.rel_path_to_project_yml())
        if os.path.exists(yml_path):
            raise FileExistsError(f"프로젝트 파일 {yml_path}가 이미 존재합니다.")
        lang_inst = None
        if language:
            try:
                lang_inst = Language[language.upper()]
            except KeyError:
                all_langs = [l.name.lower() for l in Language.iter_all(include_experimental=True)]
                raise ValueError(f"알 수 없는 언어 '{language}'. 지원되는 언어: {all_langs}")
        generated_conf = ProjectConfig.autogenerate(project_root=project_path, project_language=lang_inst)
        print(f"언어 {generated_conf.language.value}로 {yml_path}에 project.yml을 생성했습니다.")

    @staticmethod
    @click.command("index", help="LSP 캐시에 심볼을 저장하여 프로젝트를 인덱싱합니다.")
    @click.argument("project", type=click.Path(exists=True), default=os.getcwd(), required=False)
    @click.option(
        "--log-level",
        type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
        default="WARNING",
        help="인덱싱 시 로그 레벨.",
    )
    @click.option("--timeout", type=float, default=10, help="단일 파일 인덱싱 시간 초과.")
    def index(project: str, log_level: str, timeout: float) -> None:
        ProjectCommands._index_project(project, log_level, timeout=timeout)

    @staticmethod
    @click.command("index-deprecated", help="사용되지 않는 'serena project index'의 별칭입니다.")
    @click.argument("project", type=click.Path(exists=True), default=os.getcwd(), required=False)
    @click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]), default="WARNING")
    @click.option("--timeout", type=float, default=10, help="단일 파일 인덱싱 시간 초과.")
    def index_deprecated(project: str, log_level: str, timeout: float) -> None:
        click.echo("사용되지 않음! `serena project index`를 대신 사용하세요.")
        ProjectCommands._index_project(project, log_level, timeout=timeout)

    @staticmethod
    def _index_project(project: str, log_level: str, timeout: float) -> None:
        lvl = logging.getLevelNamesMapping()[log_level.upper()]
        logging.configure(level=lvl)
        serena_config = SerenaConfig.from_config_file()
        proj = Project.load(os.path.abspath(project))
        click.echo(f"프로젝트 {project}의 심볼 인덱싱 중…")
        ls = proj.create_language_server(log_level=lvl, ls_timeout=timeout, ls_specific_settings=serena_config.ls_specific_settings)
        log_file = os.path.join(project, ".serena", "logs", "indexing.txt")

        collected_exceptions: list[Exception] = []
        files_failed = []
        with ls.start_server():
            files = proj.gather_source_files()
            for i, f in enumerate(tqdm(files, desc="인덱싱")):
                try:
                    ls.request_document_symbols(f, include_body=False)
                    ls.request_document_symbols(f, include_body=True)
                except Exception as e:
                    log.error(f"{f} 인덱싱 실패, 계속 진행합니다.")
                    collected_exceptions.append(e)
                    files_failed.append(f)
                if (i + 1) % 10 == 0:
                    ls.save_cache()
            ls.save_cache()
        click.echo(f"심볼을 {ls.cache_path}에 저장했습니다.")
        if len(files_failed) > 0:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, "w") as f:
                for file, exception in zip(files_failed, collected_exceptions, strict=True):
                    f.write(f"{file}\n")
                    f.write(f"{exception}\n")
            click.echo(f"{len(files_failed)}개 파일 인덱싱 실패, 로그 참조:\n{log_file}")

    @staticmethod
    @click.command("is_ignored_path", help="경로가 프로젝트 설정에 의해 무시되는지 확인합니다.")
    @click.argument("path", type=click.Path(exists=False, file_okay=True, dir_okay=True))
    @click.argument("project", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=os.getcwd())
    def is_ignored_path(path: str, project: str) -> None:
        """
        주어진 경로가 프로젝트 설정에 의해 무시되는지 확인합니다.

        :param path: 확인할 경로.
        :param project: 프로젝트 디렉토리 경로, 기본값은 현재 작업 디렉토리.
        """
        proj = Project.load(os.path.abspath(project))
        if os.path.isabs(path):
            path = os.path.relpath(path, start=proj.project_root)
        is_ignored = proj.is_ignored_path(path)
        click.echo(f"경로 '{path}'는 프로젝트 설정에 의해 {'무시됩니다' if is_ignored else '무시되지 않습니다'}.")

    @staticmethod
    @click.command("index-file", help="단일 파일을 인덱싱하여 LSP 캐시에 심볼을 저장합니다.")
    @click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
    @click.argument("project", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=os.getcwd())
    @click.option("--verbose", "-v", is_flag=True, help="인덱싱된 심볼에 대한 상세 정보를 출력합니다.")
    def index_file(file: str, project: str, verbose: bool) -> None:
        """
        단일 파일을 인덱싱하여 LSP 캐시에 심볼을 저장합니다. 디버깅에 유용합니다.
        :param file: 인덱싱할 파일 경로, 프로젝트 디렉토리 내에 있어야 합니다.
        :param project: 프로젝트 디렉토리 경로, 기본값은 현재 작업 디렉토리.
        :param verbose: 설정 시, 인덱싱된 심볼에 대한 상세 정보를 출력합니다.
        """
        proj = Project.load(os.path.abspath(project))
        if os.path.isabs(file):
            file = os.path.relpath(file, start=proj.project_root)
        if proj.is_ignored_path(file, ignore_non_source_files=True):
            click.echo(f"'{file}'는 프로젝트 설정에 의해 무시되거나 코드가 아닌 파일로 선언되어 인덱싱하지 않습니다.")
            exit(1)
        ls = proj.create_language_server()
        with ls.start_server():
            symbols, _ = ls.request_document_symbols(file, include_body=False)
            ls.request_document_symbols(file, include_body=True)
            if verbose:
                click.echo(f"파일 '{file}'의 심볼:")
                for symbol in symbols:
                    click.echo(f"  - {symbol['name']} (종류: {symbol['kind']}) at line {symbol['selectionRange']['start']['line']}")
            ls.save_cache()
            click.echo(f"파일 '{file}' 인덱싱 성공, {len(symbols)}개 심볼을 {ls.cache_path}에 저장했습니다.")

    @staticmethod
    @click.command("health-check", help="프로젝트의 도구 및 언어 서버에 대한 포괄적인 상태 점검을 수행합니다.")
    @click.argument("project", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=os.getcwd())
    def health_check(project: str) -> None:
        """
        프로젝트의 도구 및 언어 서버에 대한 포괄적인 상태 점검을 수행합니다.

        :param project: 프로젝트 디렉토리 경로, 기본값은 현재 작업 디렉토리.
        """
        # NOTE: Claude Code에 의해 완전히 작성되었으며, 기능만 검토되었고 구현은 검토되지 않았습니다.
        logging.configure(level=logging.INFO)
        project_path = os.path.abspath(project)
        proj = Project.load(project_path)

        # 타임스탬프가 있는 로그 파일 생성
        timestamp = datetime_tag()
        log_dir = os.path.join(project_path, ".serena", "logs", "health-checks")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"health_check_{timestamp}.log")

        with FileLoggerContext(log_file, append=False, enabled=True):
            log.info("프로젝트 상태 점검 시작: %s", project_path)

            try:
                # 대시보드가 비활성화된 SerenaAgent 생성
                log.info("대시보드가 비활성화된 SerenaAgent 생성 중...")
                config = SerenaConfig(gui_log_window_enabled=False, web_dashboard=False)
                agent = SerenaAgent(project=project_path, serena_config=config)
                log.info("SerenaAgent 생성 성공")

                # 분석 가능한 비어있지 않은 첫 번째 파일 찾기
                log.info("분석 가능한 파일 검색 중...")
                files = proj.gather_source_files()
                target_file = None

                for file_path in files:
                    try:
                        full_path = os.path.join(project_path, file_path)
                        if os.path.getsize(full_path) > 0:
                            target_file = file_path
                            log.info("분석 가능한 파일 찾음: %s", target_file)
                            break
                    except (OSError, FileNotFoundError):
                        continue

                if not target_file:
                    log.error("프로젝트에서 분석 가능한 파일을 찾을 수 없음")
                    click.echo("❌ 상태 점검 실패: 분석 가능한 파일을 찾을 수 없음")
                    click.echo(f"로그 저장 위치: {log_file}")
                    return

                # 에이전트에서 도구 가져오기
                overview_tool = agent.get_tool(GetSymbolsOverviewTool)
                find_symbol_tool = agent.get_tool(FindSymbolTool)
                find_refs_tool = agent.get_tool(FindReferencingSymbolsTool)
                search_pattern_tool = agent.get_tool(SearchForPatternTool)

                # 테스트 1: 심볼 개요 가져오기
                log.info("파일에 대한 GetSymbolsOverviewTool 테스트: %s", target_file)
                overview_result = agent.execute_task(lambda: overview_tool.apply(target_file))
                overview_data = json.loads(overview_result)
                log.info("GetSymbolsOverviewTool이 %d개의 심볼을 반환함", len(overview_data))

                if not overview_data:
                    log.error("파일 %s에서 심볼을 찾을 수 없음", target_file)
                    click.echo("❌ 상태 점검 실패: 대상 파일에서 심볼을 찾을 수 없음")
                    click.echo(f"로그 저장 위치: {log_file}")
                    return

                # 적합한 심볼 추출 (변수보다 클래스나 함수 선호)
                # LSP 심볼 종류: 5=class, 12=function, 6=method, 9=constructor
                preferred_kinds = [5, 12, 6, 9]  # class, function, method, constructor

                selected_symbol = None
                for symbol in overview_data:
                    if symbol.get("kind") in preferred_kinds:
                        selected_symbol = symbol
                        break

                # 선호하는 심볼이 없으면 첫 번째 사용 가능한 심볼 사용
                if not selected_symbol:
                    selected_symbol = overview_data[0]
                    log.info("클래스나 함수를 찾을 수 없어 첫 번째 사용 가능한 심볼 사용")

                symbol_name = selected_symbol.get("name_path", "unknown")
                symbol_kind = selected_symbol.get("kind", "unknown")
                log.info("테스트에 사용할 심볼: %s (종류: %d)", symbol_name, symbol_kind)

                # 테스트 2: FindSymbolTool
                log.info("심볼에 대한 FindSymbolTool 테스트: %s", symbol_name)
                find_symbol_result = agent.execute_task(
                    lambda: find_symbol_tool.apply(symbol_name, relative_path=target_file, include_body=True)
                )
                find_symbol_data = json.loads(find_symbol_result)
                log.info("FindSymbolTool이 심볼 %s에 대해 %d개의 일치 항목을 찾음", len(find_symbol_data), symbol_name)

                # 테스트 3: FindReferencingSymbolsTool
                log.info("심볼에 대한 FindReferencingSymbolsTool 테스트: %s", symbol_name)
                try:
                    find_refs_result = agent.execute_task(lambda: find_refs_tool.apply(symbol_name, relative_path=target_file))
                    find_refs_data = json.loads(find_refs_result)
                    log.info("FindReferencingSymbolsTool이 심볼 %s에 대해 %d개의 참조를 찾음", len(find_refs_data), symbol_name)
                except Exception as e:
                    log.warning("심볼 %s에 대한 FindReferencingSymbolsTool 실패: %s", symbol_name, str(e))
                    find_refs_data = []

                # 테스트 4: 참조 확인을 위한 SearchForPatternTool
                log.info("패턴에 대한 SearchForPatternTool 테스트: %s", symbol_name)
                try:
                    search_result = agent.execute_task(
                        lambda: search_pattern_tool.apply(substring_pattern=symbol_name, restrict_search_to_code_files=True)
                    )
                    search_data = json.loads(search_result)
                    pattern_matches = sum(len(matches) for matches in search_data.values())
                    log.info("SearchForPatternTool이 %s에 대해 %d개의 패턴 일치 항목을 찾음", pattern_matches, symbol_name)
                except Exception as e:
                    log.warning("패턴 %s에 대한 SearchForPatternTool 실패: %s", symbol_name, str(e))
                    pattern_matches = 0

                # 도구가 예상대로 작동했는지 확인
                tools_working = True
                if not find_symbol_data:
                    log.error("FindSymbolTool이 결과를 반환하지 않음")
                    tools_working = False

                if len(find_refs_data) == 0 and pattern_matches == 0:
                    log.warning("FindReferencingSymbolsTool과 SearchForPatternTool 모두 일치 항목을 찾지 못함 - 문제가 있을 수 있음")

                log.info("상태 점검 성공적으로 완료")

                if tools_working:
                    click.echo("✅ 상태 점검 통과 - 모든 도구가 올바르게 작동합니다")
                else:
                    click.echo("⚠️  상태 점검이 경고와 함께 완료됨 - 자세한 내용은 로그를 확인하세요")

            except Exception as e:
                log.exception("상태 점검 중 예외 발생: %s", str(e))
                click.echo(f"❌ 상태 점검 실패: {e!s}")

            finally:
                click.echo(f"로그 저장 위치: {log_file}")


class ToolCommands(AutoRegisteringGroup):
    """'tool' 서브커맨드를 위한 그룹."""

    def __init__(self) -> None:
        super().__init__(
            name="tools",
            help="Serena의 도구 관련 명령어. `serena tools <command> --help`로 각 명령어의 자세한 정보를 확인할 수 있습니다.",
        )

    @staticmethod
    @click.command(
        "list",
        help="기본적으로 활성화된 도구들의 개요를 출력합니다 (프로젝트에 활성화된 도구만 해당되지 않음). 모든 도구를 보려면 `--all / -a`를 전달하세요.",
    )
    @click.option("--quiet", "-q", is_flag=True)
    @click.option("--all", "-a", "include_optional", is_flag=True, help="기본적으로 활성화되지 않은 도구를 포함하여 모든 도구를 나열합니다.")
    @click.option("--only-optional", is_flag=True, help="선택적 도구(기본적으로 활성화되지 않음)만 나열합니다.")
    def list(quiet: bool = False, include_optional: bool = False, only_optional: bool = False) -> None:
        tool_registry = ToolRegistry()
        if quiet:
            if only_optional:
                tool_names = tool_registry.get_tool_names_optional()
            elif include_optional:
                tool_names = tool_registry.get_tool_names()
            else:
                tool_names = tool_registry.get_tool_names_default_enabled()
            for tool_name in tool_names:
                click.echo(tool_name)
        else:
            ToolRegistry().print_tool_overview(include_optional=include_optional, only_optional=only_optional)

    @staticmethod
    @click.command(
        "description",
        help="도구의 설명을 출력합니다. 선택적으로 특정 컨텍스트를 지정할 수 있습니다 (후자는 기본 설명을 수정할 수 있음).",
    )
    @click.argument("tool_name", type=str)
    @click.option("--context", type=str, default=None, help="컨텍스트 이름 또는 컨텍스트 파일 경로.")
    def description(tool_name: str, context: str | None = None) -> None:
        # 컨텍스트 로드
        serena_context = None
        if context:
            serena_context = SerenaAgentContext.load(context)

        agent = SerenaAgent(
            project=None,
            serena_config=SerenaConfig(web_dashboard=False, log_level=logging.INFO),
            context=serena_context,
        )
        tool = agent.get_tool_by_name(tool_name)
        mcp_tool = SerenaMCPFactory.make_mcp_tool(tool)
        click.echo(mcp_tool.description)


class PromptCommands(AutoRegisteringGroup):
    def __init__(self) -> None:
        super().__init__(name="prompts", help="컨텍스트와 모드 외부에 있는 Serena의 프롬프트 관련 명령어.")

    @staticmethod
    def _get_user_prompt_yaml_path(prompt_yaml_name: str) -> str:
        os.makedirs(PROMPT_TEMPLATES_DIR_IN_USER_HOME, exist_ok=True)
        return os.path.join(PROMPT_TEMPLATES_DIR_IN_USER_HOME, prompt_yaml_name)

    @staticmethod
    @click.command("list", help="프롬프트 정의에 사용되는 yaml 목록을 나열합니다.")
    def list() -> None:
        serena_prompt_yaml_names = [os.path.basename(f) for f in glob.glob(PROMPT_TEMPLATES_DIR_INTERNAL + "/*.yml")]
        for prompt_yaml_name in serena_prompt_yaml_names:
            user_prompt_yaml_path = PromptCommands._get_user_prompt_yaml_path(prompt_yaml_name)
            if os.path.exists(user_prompt_yaml_path):
                click.echo(f"{user_prompt_yaml_path}가 {prompt_yaml_name}의 기본 프롬프트와 병합됨")
            else:
                click.echo(prompt_yaml_name)

    @staticmethod
    @click.command("create-override", help="Serena의 프롬프트를 사용자 정의하기 위해 내장 프롬프트 yaml의 재정의를 생성합니다.")
    @click.argument("prompt_yaml_name")
    def create_override(prompt_yaml_name: str) -> None:
        """
        :param prompt_yaml_name: 재정의하려는 프롬프트의 yaml 이름. 유효한 프롬프트 yaml 이름을 찾으려면 `list` 명령을 호출하세요.
        :return:
        """
        # 편의를 위해 .yml 없이 이름을 전달할 수 있습니다.
        if not prompt_yaml_name.endswith(".yml"):
            prompt_yaml_name = prompt_yaml_name + ".yml"
        user_prompt_yaml_path = PromptCommands._get_user_prompt_yaml_path(prompt_yaml_name)
        if os.path.exists(user_prompt_yaml_path):
            raise FileExistsError(f"{user_prompt_yaml_path}가 이미 존재합니다.")
        serena_prompt_yaml_path = os.path.join(PROMPT_TEMPLATES_DIR_INTERNAL, prompt_yaml_name)
        shutil.copyfile(serena_prompt_yaml_path, user_prompt_yaml_path)
        _open_in_editor(user_prompt_yaml_path)

    @staticmethod
    @click.command("edit-override", help="기존 프롬프트 재정의 파일을 편집합니다.")
    @click.argument("prompt_yaml_name")
    def edit_override(prompt_yaml_name: str) -> None:
        """
        :param prompt_yaml_name: 편집할 프롬프트 재정의의 yaml 이름.
        :return:
        """
        # 편의를 위해 .yml 없이 이름을 전달할 수 있습니다.
        if not prompt_yaml_name.endswith(".yml"):
            prompt_yaml_name = prompt_yaml_name + ".yml"
        user_prompt_yaml_path = PromptCommands._get_user_prompt_yaml_path(prompt_yaml_name)
        if not os.path.exists(user_prompt_yaml_path):
            click.echo(f"재정의 파일 '{prompt_yaml_name}'를 찾을 수 없습니다. 'prompts create-override {prompt_yaml_name}'로 생성하세요.")
            return
        _open_in_editor(user_prompt_yaml_path)

    @staticmethod
    @click.command("list-overrides", help="기존 프롬프트 재정의 파일을 나열합니다.")
    def list_overrides() -> None:
        os.makedirs(PROMPT_TEMPLATES_DIR_IN_USER_HOME, exist_ok=True)
        serena_prompt_yaml_names = [os.path.basename(f) for f in glob.glob(PROMPT_TEMPLATES_DIR_INTERNAL + "/*.yml")]
        override_files = glob.glob(os.path.join(PROMPT_TEMPLATES_DIR_IN_USER_HOME, "*.yml"))
        for file_path in override_files:
            if os.path.basename(file_path) in serena_prompt_yaml_names:
                click.echo(file_path)

    @staticmethod
    @click.command("delete-override", help="프롬프트 재정의 파일을 삭제합니다.")
    @click.argument("prompt_yaml_name")
    def delete_override(prompt_yaml_name: str) -> None:
        ""

        :param prompt_yaml_name:  삭제할 프롬프트 재정의의 yaml 이름."
        :return:
        """
        # 편의를 위해 .yml 없이 이름을 전달할 수 있습니다.
        if not prompt_yaml_name.endswith(".yml"):
            prompt_yaml_name = prompt_yaml_name + ".yml"
        user_prompt_yaml_path = PromptCommands._get_user_prompt_yaml_path(prompt_yaml_name)
        if not os.path.exists(user_prompt_yaml_path):
            click.echo(f"재정의 파일 '{prompt_yaml_name}'를 찾을 수 없습니다.")
            return
        os.remove(user_prompt_yaml_path)
        click.echo(f"재정의 파일 '{prompt_yaml_name}'를 삭제했습니다.")


# 그룹을 노출하여 pyproject.toml에서 참조할 수 있도록 합니다.
mode = ModeCommands()
context = ContextCommands()
project = ProjectCommands()
config = SerenaConfigCommands()
tools = ToolCommands()
prompts = PromptCommands()

# 동일한 이유로 최상위 명령어를 노출합니다.
top_level = TopLevelCommands()
start_mcp_server = top_level.start_mcp_server
index_project = project.index_deprecated

# 도움말 스크립트가 작동하려면 모든 서브커맨드를 최상위 그룹에 등록해야 합니다.
for subgroup in (mode, context, project, config, tools, prompts):
    top_level.add_command(subgroup)


def get_help() -> str:
    """최상위 Serena CLI에 대한 도움말 텍스트를 검색합니다."""
    return top_level.get_help(click.Context(top_level, info_name="serena"))