"""
SolidLSP TypeScript/JavaScript 언어 서버 모듈 - TypeScript Language Server 기반

이 모듈은 TypeScript와 JavaScript 프로그래밍 언어를 위한 LSP 서버를 구현합니다.
TypeScript Language Server를 기반으로 하여 JavaScript와 TypeScript 모두에 대한
완전한 언어 서비스를 제공합니다:

주요 기능:
- TypeScript/JavaScript 코드 완성 (IntelliSense)
- 타입 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사
- 코드 리팩토링 및 네비게이션
- JSX/TSX 지원

아키텍처:
- TypeScriptLanguageServer: TypeScript 공식 LSP 서버를 래핑하는 클래스
- 다중 플랫폼 지원 (Linux, macOS, Windows)
- Node.js 런타임 의존성 관리
- TypeScript/JavaScript 프로젝트 자동 감지

지원하는 파일 확장자:
- .ts (TypeScript)
- .tsx (TypeScript + JSX)
- .js (JavaScript)
- .jsx (JavaScript + JSX)
- .json (JSON with comments)
- .vue (Vue.js single file components)

특징:
- 공식 TypeScript Language Server 사용으로 정확한 타입 정보 제공
- 광범위한 프레임워크 지원 (React, Vue, Angular 등)
- 실시간 타입 검사 및 오류 보고
- 스마트 코드 완성과 리팩토링 기능
"""

import logging
import os
import pathlib
import shutil
import threading

from overrides import override
from sensai.util.logging import LogTime

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.ls_utils import PlatformId, PlatformUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

from .common import RuntimeDependency, RuntimeDependencyCollection

# Platform-specific imports - 플랫폼별 import 처리
if os.name != "nt":  # Unix-like systems
    import pwd
else:
    # Dummy pwd module for Windows - Windows용 더미 pwd 모듈
    class pwd:
        @staticmethod
        def getpwuid(uid):
            return type("obj", (), {"pw_name": os.environ.get("USERNAME", "unknown")})()


# Conditionally import pwd module (Unix-only) - Unix 전용 pwd 모듈 조건부 import
if not PlatformUtils.get_platform_id().value.startswith("win"):
    pass


class TypeScriptLanguageServer(SolidLanguageServer):
    """
    TypeScript/JavaScript 언어를 위한 LSP 서버 구현 클래스.

    SolidLanguageServer를 상속받아 TypeScript Language Server를 백엔드로 사용하여
    TypeScript와 JavaScript 코드에 대한 완전한 언어 서비스를 제공합니다.

    주요 특징:
    - 공식 TypeScript Language Server 기반의 정확한 타입 분석
    - TypeScript와 JavaScript 동시 지원
    - JSX/TSX 파일 지원 (React, Vue 등)
    - 실시간 타입 검사 및 오류 보고
    - 광범위한 LSP 기능 지원

    초기화 파라미터:
    - config: 언어 서버 설정
    - logger: 로깅을 위한 로거 인스턴스
    - repository_root_path: 프로젝트 루트 경로
    - solidlsp_settings: SolidLSP 전역 설정

    Node.js 의존성:
    - TypeScript Language Server 패키지가 필요
    - 플랫폼별 자동 설치 및 관리
    - 다중 플랫폼 지원 (Linux, macOS, Windows)
    """

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        TypeScriptLanguageServer 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. TypeScript Language Server를 Node.js 환경에서 실행하여
        TypeScript/JavaScript 언어 서비스를 제공합니다.

        초기화 과정:
        1. 런타임 의존성(typescript-language-server) 설치 및 설정
        2. 상위 클래스 초기화
        3. 서버 준비 상태 이벤트 설정

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: TypeScript/JavaScript 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Note:
            TypeScript Language Server는 Node.js 기반으로 실행되므로,
            Node.js 런타임이 설치되어 있어야 합니다.
            서버 시작 시점에 런타임 의존성이 자동으로 설치됩니다.

        Events:
            server_ready: 서버가 완전히 시작되어 준비된 상태를 알림
            initialize_searcher_command_available: 심볼 검색 명령이 사용 가능함을 알림
        """
        ts_lsp_executable_path = self._setup_runtime_dependencies(logger, config, solidlsp_settings)
        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=ts_lsp_executable_path, cwd=repository_root_path),
            "typescript",
            solidlsp_settings,
        )
        self.server_ready = threading.Event()
        self.initialize_searcher_command_available = threading.Event()

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        """
        TypeScript/JavaScript 프로젝트에서 무시해야 할 디렉토리 이름을 판단합니다.

        기본 무시 디렉토리(예: .git, node_modules 등)에 더해 JavaScript/TypeScript
        프로젝트 특화된 디렉토리들을 추가로 무시합니다. 이러한 디렉토리들은
        타입 분석에 불필요하거나 방해가 될 수 있습니다.

        Args:
            dirname: 검사할 디렉토리 이름

        Returns:
            bool: 무시해야 하면 True, 그렇지 않으면 False

        TypeScript/JavaScript 특화 무시 대상:
        - node_modules: npm 패키지들이 설치되는 디렉토리 (거대하고 타입 분석 불필요)
        - dist: 빌드 결과물이 저장되는 디렉토리
        - build: 빌드 중간 파일들이 저장되는 디렉토리
        - coverage: 테스트 커버리지 리포트 디렉토리
        - 기본 무시 디렉토리들 (.git, node_modules 등)

        Note:
            TypeScript Language Server는 가능한 한 많은 파일을 분석하려 하지만,
            성능과 정확성을 위해 빌드 산출물과 의존성 디렉토리들을 제외합니다.
        """
        return super().is_ignored_dirname(dirname) or dirname in [
            "node_modules",
            "dist",
            "build",
            "coverage",
        ]

    @classmethod
    def _setup_runtime_dependencies(
        cls, logger: LanguageServerLogger, config: LanguageServerConfig, solidlsp_settings: SolidLSPSettings
    ) -> list[str]:
        """
        TypeScript Language Server의 런타임 의존성을 설정하고 서버 시작 명령어를 반환합니다.

        이 메서드는 TypeScript Language Server를 실행하기 위해 필요한 Node.js 기반
        런타임 의존성들을 설치하고, 플랫폼에 맞는 실행 명령어를 구성합니다.

        지원 플랫폼:
        - Linux (x64, arm64)
        - macOS (x64, arm64, Intel)
        - Windows (x64, arm64)

        Args:
            logger: 설치 과정을 로깅할 로거
            config: 언어 서버 설정 (사용되지 않음)
            solidlsp_settings: SolidLSP 시스템 설정

        Returns:
            list[str]: TypeScript Language Server를 시작할 명령어 리스트

        설치 과정:
        1. 플랫폼 검증 (지원되지 않는 플랫폼은 예외 발생)
        2. TypeScript Language Server 패키지 의존성 정의
        3. 플랫폼별 다운로드 URL 및 설치 경로 설정
        4. RuntimeDependencyCollection을 통한 의존성 설치
        5. Node.js를 통한 서버 실행 명령어 구성

        Note:
            TypeScript Language Server는 Node.js 기반으로 실행되므로,
            Node.js 런타임이 시스템에 설치되어 있어야 합니다.
            의존성은 자동으로 다운로드되어 로컬에 설치됩니다.
        """
        platform_id = PlatformUtils.get_platform_id()

        valid_platforms = [
            PlatformId.LINUX_x64,
            PlatformId.LINUX_arm64,
            PlatformId.OSX,
            PlatformId.OSX_x64,
            PlatformId.OSX_arm64,
            PlatformId.WIN_x64,
            PlatformId.WIN_arm64,
        ]
        assert platform_id in valid_platforms, f"Platform {platform_id} is not supported for multilspy javascript/typescript at the moment"

        deps = RuntimeDependencyCollection(
            [
                RuntimeDependency(
                    id="typescript",
                    description="typescript package",
                    command=["npm", "install", "--prefix", "./", "typescript@5.5.4"],
                    platform_id="any",
                ),
                RuntimeDependency(
                    id="typescript-language-server",
                    description="typescript-language-server package",
                    command=["npm", "install", "--prefix", "./", "typescript-language-server@4.3.3"],
                    platform_id="any",
                ),
            ]
        )

        # Verify both node and npm are installed
        is_node_installed = shutil.which("node") is not None
        assert is_node_installed, "node is not installed or isn't in PATH. Please install NodeJS and try again."
        is_npm_installed = shutil.which("npm") is not None
        assert is_npm_installed, "npm is not installed or isn't in PATH. Please install npm and try again."

        # Verify both node and npm are installed
        is_node_installed = shutil.which("node") is not None
        assert is_node_installed, "node is not installed or isn't in PATH. Please install NodeJS and try again."
        is_npm_installed = shutil.which("npm") is not None
        assert is_npm_installed, "npm is not installed or isn't in PATH. Please install npm and try again."

        # Install typescript and typescript-language-server if not already installed
        tsserver_ls_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "ts-lsp")
        tsserver_executable_path = os.path.join(tsserver_ls_dir, "node_modules", ".bin", "typescript-language-server")
        if not os.path.exists(tsserver_executable_path):
            logger.log(f"Typescript Language Server executable not found at {tsserver_executable_path}. Installing...", logging.INFO)
            with LogTime("Installation of TypeScript language server dependencies", logger=logger.logger):
                deps.install(logger, tsserver_ls_dir)

        if not os.path.exists(tsserver_executable_path):
            raise FileNotFoundError(
                f"typescript-language-server executable not found at {tsserver_executable_path}, something went wrong with the installation."
            )
        return [tsserver_executable_path, "--stdio"]

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        TypeScript Language Server를 위한 LSP 초기화 파라미터를 생성합니다.

        이 메서드는 TypeScript Language Server에 특화된 초기화 파라미터를 구성합니다.
        TypeScript는 JavaScript와 함께 사용되므로, 두 언어 모두에 대한 지원을 포함합니다.

        Args:
            repository_absolute_path: 초기화할 프로젝트의 절대 경로

        Returns:
            InitializeParams: LSP 초기화 요청에 사용할 파라미터 딕셔너리

        초기화 파라미터 구성 요소:
        - processId: 현재 프로세스 ID
        - rootPath/Uri: 프로젝트 루트 경로
        - capabilities: TypeScript Language Server 기능 지원 목록
          - textDocument: 문서 관련 기능들 (완료, 정의, 참조, 심볼, 호버 등)
          - workspace: 작업 공간 관련 기능들 (폴더, 설정 변경, 심볼)
        - workspaceFolders: 작업 공간 폴더 정보

        TypeScript 특화 기능:
        - completionItem.snippetSupport: 코드 스니펫 지원
        - hierarchicalDocumentSymbolSupport: 계층적 문서 심볼 지원
        - 광범위한 트리거 문자들: ".", '"', "'", "/", "@", "<"

        Note:
            TypeScript Language Server는 JavaScript와 TypeScript를 모두 지원하므로,
            초기화 시점에 두 언어에 대한 기능이 모두 활성화됩니다.
        """
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "locale": "en",
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True, "dynamicRegistration": True},
                    "completion": {"dynamicRegistration": True, "completionItem": {"snippetSupport": True}},
                    "definition": {"dynamicRegistration": True},
                    "references": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "hierarchicalDocumentSymbolSupport": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                    },
                    "hover": {"dynamicRegistration": True, "contentFormat": ["markdown", "plaintext"]},
                    "signatureHelp": {"dynamicRegistration": True},
                    "codeAction": {"dynamicRegistration": True},
                },
                "workspace": {
                    "workspaceFolders": True,
                    "didChangeConfiguration": {"dynamicRegistration": True},
                    "symbol": {"dynamicRegistration": True},
                },
            },
            "processId": os.getpid(),
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": os.path.basename(repository_absolute_path),
                }
            ],
        }
        return initialize_params

    def _start_server(self):
        """
        TypeScript Language Server를 시작하고 서버 준비 완료를 기다립니다.

        이 메서드는 TypeScript Language Server를 시작하고, 서버가 완전히 준비될 때까지
        기다린 후 클라이언트 요청을 처리할 준비를 완료합니다.

        주요 단계:
        1. LSP 서버 프로세스 시작
        2. 다양한 LSP 핸들러 등록
        3. 초기화 파라미터 전송
        4. 서버 기능 검증
        5. 초기화 완료 알림
        6. 서버 준비 상태 대기

        등록되는 핸들러들:
        - client/registerCapability: 클라이언트 기능 등록
        - window/logMessage: 창 로그 메시지
        - workspace/executeClientCommand: 클라이언트 명령 실행
        - experimental/serverStatus: 실험적 서버 상태

        TypeScript 특화 기능:
        - workspace/executeCommand 등록 감지로 심볼 검색 기능 활성화
        - 서버 준비 상태 확인 (1초 타임아웃)
        - 완료 기능 활성화

        Usage:
        ```
        async with lsp.start_server():
            # LanguageServer has been initialized and ready to serve requests
            # 언어 서버가 초기화되고 요청 처리를 위한 준비가 완료됨
            await lsp.request_definition(...)
            await lsp.request_references(...)
            # Shutdown the LanguageServer on exit from scope
            # 범위 종료 시 언어 서버가 정리 종료됨
        # LanguageServer has been shutdown
        # 언어 서버가 정상적으로 종료됨
        """

        def register_capability_handler(params):
            """
            클라이언트 기능 등록 핸들러.

            TypeScript 서버가 workspace/executeCommand 기능을 등록하면
            심볼 검색 명령이 사용 가능함을 알립니다.
            """
            assert "registrations" in params
            for registration in params["registrations"]:
                if registration["method"] == "workspace/executeCommand":
                    self.initialize_searcher_command_available.set()
                    # TypeScript doesn't have a direct equivalent to resolve_main_method
                    # TypeScript에는 resolve_main_method에 해당하는 직접적인 기능이 없습니다
                    # 다른 플래그를 설정하거나 이 줄을 제거할 수 있습니다
                    # self.resolve_main_method_available.set()
            return

        def execute_client_command_handler(params):
            """
            클라이언트 명령 실행 핸들러.

            workspace/executeClientCommand 요청에 대한 응답으로 빈 리스트를 반환합니다.
            """
            return []

        def do_nothing(params):
            """
            기본 핸들러 함수.

            대부분의 알림에 대해 아무 작업도 수행하지 않습니다.
            LSP 표준에 따라 다양한 이벤트들을 처리하기 위한 기본 핸들러입니다.
            """
            return

        def window_log_message(msg):
            """
            창 로그 메시지 핸들러.

            LSP 서버로부터 받은 로그 메시지를 SolidLSP 로거를 통해 기록합니다.
            """
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        def check_experimental_status(params):
            """
            실험적 서버 상태 확인 핸들러.

            experimental/serverStatus 알림을 백업 메커니즘으로 사용하여
            서버가 조용한 상태(quiescent)가 되면 준비 완료로 판단합니다.

            Args:
                params: 서버 상태 파라미터
            """
            if params.get("quiescent") == True:
                self.server_ready.set()
                self.completions_available.set()

        # LSP 이벤트 핸들러 등록 - 각종 서버 알림 및 요청 처리
        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("experimental/serverStatus", check_experimental_status)

        # TypeScript Language Server 프로세스 시작
        self.logger.log("Starting TypeScript server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)

        # TypeScript 특화 기능 검증 - 필수 기능들이 올바르게 설정되었는지 확인
        assert init_response["capabilities"]["textDocumentSync"] == 2
        assert "completionProvider" in init_response["capabilities"]
        assert init_response["capabilities"]["completionProvider"] == {
            "triggerCharacters": [".", '"', "'", "/", "@", "<"],
            "resolveProvider": True,
        }

        # 초기화 완료 알림 전송 - 서버가 완전히 준비되었음을 알림
        self.server.notify.initialized({})

        # TypeScript 서버 준비 상태 대기 (1초 타임아웃)
        if self.server_ready.wait(timeout=1.0):
            self.logger.log("TypeScript server is ready", logging.INFO)
        else:
            self.logger.log("Timeout waiting for TypeScript server to become ready, proceeding anyway", logging.INFO)
            # Fallback: assume server is ready after timeout
            # 폴백: 타임아웃 후 서버가 준비되었다고 가정
            self.server_ready.set()
        self.completions_available.set()

    @override
    def _get_wait_time_for_cross_file_referencing(self) -> float:
        """
        파일 간 참조를 위한 대기 시간을 반환합니다.

        TypeScript는 다른 언어들에 비해 파일 간 참조가 빠르게 처리되므로
        짧은 대기 시간을 설정합니다.

        Returns:
            float: 파일 간 참조 대기 시간 (초)

        Note:
            TypeScript는 정적 타입 분석으로 인해 다른 언어들보다
            파일 간 참조 처리가 빠를 수 있으므로 1초로 설정합니다.
        """
        return 1
