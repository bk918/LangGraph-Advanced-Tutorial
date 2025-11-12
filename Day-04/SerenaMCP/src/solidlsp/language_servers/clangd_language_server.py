"""
SolidLSP C/C++ 언어 서버 모듈 - Clangd 기반 C/C++ 언어 지원

이 모듈은 C/C++ 프로그래밍 언어를 위한 LSP 서버를 구현합니다.
LLVM의 Clangd를 기반으로 하여 C/C++ 코드에 대한 완전한 언어 서비스를 제공합니다:

주요 기능:
- C/C++ 코드 완성 (IntelliSense)
- 코드 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사 (컴파일러 수준)
- 코드 리팩토링 및 네비게이션
- 헤더 파일 포함 처리

아키텍처:
- ClangdLanguageServer: Clangd 공식 LSP 서버를 래핑하는 클래스
- 다중 플랫폼 지원 (Linux, macOS, Windows)
- Clang 컴파일러 인덱싱 엔진 활용
- compile_commands.json 기반 빌드 정보 활용

지원하는 C/C++ 표준:
- C89, C99, C11, C17, C23
- C++98, C++11, C++14, C++17, C++20, C++23
- GNU 확장 및 Microsoft 확장
- 다양한 컴파일러 지원 (GCC, Clang, MSVC)

중요 요구사항:
- Clangd 설치 필요 (LLVM 프로젝트의 일부)
- compile_commands.json 파일 필요 (빌드 정보)
- 프로젝트 크기가 클수록 인덱싱 시간 증가
- 정확한 언어 서비스를 위해 여러 번 실행 권장

특징:
- 컴파일러 수준의 정확한 코드 분석
- 크로스 파일 참조 및 매크로 확장
- 템플릿 및 제네릭 타입 지원
- 실시간 컴파일 오류 검사
- 고성능 인덱싱 및 캐싱
"""

import logging
import os
import pathlib
import threading

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

from .common import RuntimeDependency, RuntimeDependencyCollection


class ClangdLanguageServer(SolidLanguageServer):
    """
    C/C++ 언어를 위한 Clangd 기반 LSP 서버 구현 클래스.

    SolidLanguageServer를 상속받아 LLVM Clangd를 백엔드로 사용하여
    C/C++ 코드에 대한 컴파일러 수준의 정확한 언어 서비스를 제공합니다.

    주요 특징:
    - LLVM Clangd 엔진 기반의 정확한 C/C++ 언어 분석
    - 컴파일러 수준의 정적 분석 및 오류 검사
    - 크로스 파일 참조 및 매크로 확장 지원
    - 광범위한 C/C++ 표준 및 확장 지원
    - 고성능 인덱싱 및 캐싱 메커니즘

    초기화 파라미터:
    - config: 언어 서버 설정
    - logger: 로깅을 위한 로거 인스턴스
    - repository_root_path: C/C++ 프로젝트 루트 경로
    - solidlsp_settings: SolidLSP 전역 설정

    빌드 시스템 요구사항:
    - compile_commands.json 파일 필요 (CMake, Bazel, Bear 등으로 생성)
    - 정확한 언어 서비스를 위해 최신 컴파일러 정보 필요
    - 대규모 프로젝트의 경우 인덱싱 시간이 오래 걸릴 수 있음

    Events:
    - server_ready: 서버가 완전히 시작되어 준비된 상태
    - service_ready_event: 서비스가 사용 가능한 상태
    - initialize_searcher_command_available: 심볼 검색 기능 사용 가능
    - resolve_main_method_available: 메인 메서드 분석 기능 사용 가능
    """

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        ClangdLanguageServer 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. Clangd를 백엔드로 사용하여 C/C++ 언어 서비스를 제공합니다.

        초기화 과정:
        1. 런타임 의존성(Clangd) 설치 및 설정
        2. 상위 클래스 초기화
        3. 서버 준비 상태 이벤트 설정

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: C/C++ 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Note:
            Clangd는 LLVM 프로젝트의 일부로, 별도 설치가 필요합니다.
            compile_commands.json 파일이 프로젝트 루트에 있어야 합니다.
            대규모 프로젝트의 경우 인덱싱 시간이 오래 걸릴 수 있습니다.

        Events:
            server_ready: 서버가 완전히 시작되어 준비된 상태를 알림
            service_ready_event: Clangd 서비스가 사용 가능한 상태를 알림
            initialize_searcher_command_available: 심볼 검색 명령이 사용 가능함을 알림
            resolve_main_method_available: 메인 메서드 분석 기능이 사용 가능함을 알림
        """
        clangd_executable_path = self._setup_runtime_dependencies(logger, config, solidlsp_settings)
        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=clangd_executable_path, cwd=repository_root_path),
            "cpp",
            solidlsp_settings,
        )
        self.server_ready = threading.Event()
        self.service_ready_event = threading.Event()
        self.initialize_searcher_command_available = threading.Event()
        self.resolve_main_method_available = threading.Event()

    @classmethod
    def _setup_runtime_dependencies(
        cls, logger: LanguageServerLogger, config: LanguageServerConfig, solidlsp_settings: SolidLSPSettings
    ) -> str:
        """
        ClangdLanguageServer의 런타임 의존성을 설정하고 서버 시작 경로를 반환합니다.

        이 메서드는 Clangd 실행 파일을 설치하고, 플랫폼에 맞는 실행 경로를 구성합니다.
        Clangd는 LLVM 프로젝트의 일부로, 공식 GitHub 릴리즈에서 다운로드됩니다.

        지원 플랫폼:
        - Linux (x64)
        - Windows (x64)
        - macOS (x64, Arm64)

        Args:
            logger: 설치 과정을 로깅할 로거
            config: 언어 서버 설정 (사용되지 않음)
            solidlsp_settings: SolidLSP 시스템 설정

        Returns:
            str: Clangd 실행 파일의 전체 경로

        설치 과정:
        1. 플랫폼별 Clangd 바이너리 의존성 정의
        2. GitHub 릴리즈에서 최신 Clangd 다운로드
        3. 플랫폼별 아카이브 압축 해제
        4. 실행 파일 경로 구성

        Clangd 버전:
        - 19.1.2 (2024년 최신 안정 버전)
        - 모든 플랫폼에서 동일 버전 사용
        - 정기적인 업데이트를 통해 최신 기능 지원

        Note:
            Clangd는 LLVM 프로젝트의 공식 언어 서버로,
            C/C++ 표준의 모든 기능을 완벽하게 지원합니다.
            실행 파일은 로컬 캐시에 저장되어 재사용됩니다.
        """
        deps = RuntimeDependencyCollection(
            [
                RuntimeDependency(
                    id="Clangd",
                    description="Clangd for Linux (x64)",
                    url="https://github.com/clangd/clangd/releases/download/19.1.2/clangd-linux-19.1.2.zip",
                    platform_id="linux-x64",
                    archive_type="zip",
                    binary_name="clangd_19.1.2/bin/clangd",
                ),
                RuntimeDependency(
                    id="Clangd",
                    description="Clangd for Windows (x64)",
                    url="https://github.com/clangd/clangd/releases/download/19.1.2/clangd-windows-19.1.2.zip",
                    platform_id="win-x64",
                    archive_type="zip",
                    binary_name="clangd_19.1.2/bin/clangd.exe",
                ),
                RuntimeDependency(
                    id="Clangd",
                    description="Clangd for macOS (x64)",
                    url="https://github.com/clangd/clangd/releases/download/19.1.2/clangd-mac-19.1.2.zip",
                    platform_id="osx-x64",
                    archive_type="zip",
                    binary_name="clangd_19.1.2/bin/clangd",
                ),
                RuntimeDependency(
                    id="Clangd",
                    description="Clangd for macOS (Arm64)",
                    url="https://github.com/clangd/clangd/releases/download/19.1.2/clangd-mac-19.1.2.zip",
                    platform_id="osx-arm64",
                    archive_type="zip",
                    binary_name="clangd_19.1.2/bin/clangd",
                ),
            ]
        )

        clangd_ls_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "clangd")
        dep = deps.get_single_dep_for_current_platform()
        clangd_executable_path = deps.binary_path(clangd_ls_dir)
        if not os.path.exists(clangd_executable_path):
            logger.log(
                f"Clangd executable not found at {clangd_executable_path}. Downloading from {dep.url}",
                logging.INFO,
            )
            deps.install(logger, clangd_ls_dir)
        if not os.path.exists(clangd_executable_path):
            raise FileNotFoundError(
                f"Clangd executable not found at {clangd_executable_path}.\n"
                "Make sure you have installed clangd. See https://clangd.llvm.org/installation"
            )
        os.chmod(clangd_executable_path, 0o755)

        return clangd_executable_path

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Clangd Language Server를 위한 LSP 초기화 파라미터를 생성합니다.

        이 메서드는 Clangd에 특화된 초기화 파라미터를 구성합니다.
        Clangd는 컴파일러 기반이므로, C/C++ 프로젝트의 빌드 정보를 활용합니다.

        Args:
            repository_absolute_path: 초기화할 프로젝트의 절대 경로

        Returns:
            InitializeParams: LSP 초기화 요청에 사용할 파라미터 딕셔너리

        초기화 파라미터 구성 요소:
        - processId: 현재 프로세스 ID
        - rootPath/Uri: 프로젝트 루트 경로
        - capabilities: Clangd 기능 지원 목록
          - textDocument: 문서 관련 기능들 (완료, 정의 등)
          - workspace: 작업 공간 관련 기능들 (폴더, 설정 변경)
        - workspaceFolders: 작업 공간 폴더 정보

        Clangd 특화 기능:
        - completionItem.snippetSupport: 코드 스니펫 지원
        - 다양한 트리거 문자들: ".", "<", ">", ":", '"', "/", "*"
        - compile_commands.json 파일 자동 감지

        Note:
            Clangd는 compile_commands.json 파일을 통해
            컴파일러 플래그와 포함 경로를 파악합니다.
            이 파일이 없으면 정확한 언어 서비스를 제공할 수 없습니다.
        """
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "locale": "en",
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True, "dynamicRegistration": True},
                    "completion": {"dynamicRegistration": True, "completionItem": {"snippetSupport": True}},
                    "definition": {"dynamicRegistration": True},
                },
                "workspace": {"workspaceFolders": True, "didChangeConfiguration": {"dynamicRegistration": True}},
            },
            "processId": os.getpid(),
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": "$name",
                }
            ],
        }

        return initialize_params

    def _start_server(self):
        """
        Clangd Language Server를 시작하고 서버 준비 완료를 기다립니다.

        이 메서드는 Clangd를 시작하고, 서버가 완전히 준비될 때까지 기다린 후
        클라이언트 요청을 처리할 준비를 완료합니다. Clangd는 컴파일러 기반이므로
        초기 인덱싱 시간이 오래 걸릴 수 있습니다.

        주요 단계:
        1. LSP 서버 프로세스 시작
        2. 다양한 LSP 핸들러 등록
        3. 초기화 파라미터 전송
        4. 서버 기능 검증
        5. 초기화 완료 알림
        6. 서버 준비 상태 대기

        등록되는 핸들러들:
        - client/registerCapability: 클라이언트 기능 등록
        - language/status: 언어 상태 알림 (ServiceReady 감지)
        - window/logMessage: 창 로그 메시지
        - workspace/executeClientCommand: 클라이언트 명령 실행
        - experimental/serverStatus: 실험적 서버 상태

        Clangd 특화 기능:
        - ServiceReady 상태 감지로 인덱싱 완료 확인
        - workspace/executeCommand 등록으로 심볼 검색 기능 활성화
        - 메인 메서드 분석 기능 활성화
        - 컴파일러 수준의 정확한 코드 분석

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

            Clangd 서버가 workspace/executeCommand 기능을 등록하면
            심볼 검색과 메인 메서드 분석 기능을 사용할 수 있게 됩니다.
            """
            assert "registrations" in params
            for registration in params["registrations"]:
                if registration["method"] == "workspace/executeCommand":
                    self.initialize_searcher_command_available.set()
                    self.resolve_main_method_available.set()
            return

        def lang_status_handler(params):
            """
            언어 상태 알림 핸들러.

            Clangd의 language/status 알림을 처리하여
            ServiceReady 상태가 되면 서비스 준비 완료를 알립니다.
            """
            # TODO: Should we wait for
            # server -> client: {'jsonrpc': '2.0', 'method': 'language/status', 'params': {'type': 'ProjectStatus', 'message': 'OK'}}
            # Before proceeding?
            # 계속 진행하기 전에 다음을 기다려야 할까요?
            if params["type"] == "ServiceReady" and params["message"] == "ServiceReady":
                self.service_ready_event.set()

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

        def check_experimental_status(params):
            """
            실험적 서버 상태 확인 핸들러.

            experimental/serverStatus 알림을 백업 메커니즘으로 사용하여
            서버가 조용한 상태(quiescent)가 되면 준비 완료로 판단합니다.

            Args:
                params: 서버 상태 파라미터
            """
            if params["quiescent"] == True:
                self.server_ready.set()

        def window_log_message(msg):
            """
            창 로그 메시지 핸들러.

            LSP 서버로부터 받은 로그 메시지를 SolidLSP 로거를 통해 기록합니다.
            Clangd의 상세한 로그 정보를 추적할 수 있습니다.
            """
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        # LSP 이벤트 핸들러 등록 - 각종 서버 알림 및 요청 처리
        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_notification("language/status", lang_status_handler)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("language/actionableNotification", do_nothing)
        self.server.on_notification("experimental/serverStatus", check_experimental_status)

        # Clangd Language Server 프로세스 시작
        self.logger.log("Starting Clangd server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)

        # Clangd 특화 기능 검증 - 필수 기능들이 올바르게 설정되었는지 확인
        assert init_response["capabilities"]["textDocumentSync"]["change"] == 2
        assert "completionProvider" in init_response["capabilities"]
        assert init_response["capabilities"]["completionProvider"] == {
            "triggerCharacters": [".", "<", ">", ":", '"', "/", "*"],
            "resolveProvider": False,
        }

        # 초기화 완료 알림 전송 - 서버가 완전히 준비되었음을 알림
        self.server.notify.initialized({})

        # Clangd 준비 완료 설정 - 완료 기능 활성화 및 서버 준비 완료
        self.completions_available.set()
        # set ready flag
        # 준비 완료 플래그 설정
        self.server_ready.set()
        self.server_ready.wait()
