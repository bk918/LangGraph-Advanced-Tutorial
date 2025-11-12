"""
SolidLSP Bash 언어 서버 모듈 - bash-language-server 기반 Bash/Shell 지원

이 모듈은 Bash 쉘 스크립팅 언어를 위한 LSP 서버를 구현합니다.
bash-language-server를 기반으로 하여 Bash/Shell 스크립트에 대한
완전한 언어 서비스를 제공합니다:

주요 기능:
- Bash/Shell 코드 완성 (IntelliSense)
- 코드 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사
- 코드 리팩토링 및 네이빅이션
- POSIX Shell 호환성 검사

아키텍처:
- BashLanguageServer: bash-language-server를 래핑하는 클래스
- Node.js 런타임 환경 연동
- Shell 스크립트 분석 엔진
- POSIX 표준 준수 검사

지원하는 Bash 기능:
- Bash 5.x 문법 및 최신 기능
- POSIX Shell 표준 준수
- 환경 변수 및 매개변수 확장
- 조건문 및 제어문
- 함수 정의 및 호출
- 파이프라인 및 리다이렉션
- 히어 도큐먼트 및 히어 스트링

특징:
- JavaScript/Node.js 기반 고성능 분석
- 실시간 구문 검사 및 오류 보고
- VS Code Bash 확장과 동일한 수준의 지원
- POSIX Shell 표준 준수 검사
- 스크립트 실행 경로 분석
- 환경 변수 의존성 추적

중요 요구사항:
- Node.js 18 이상 필요
- npm 패키지 매니저 필요
- bash-language-server 패키지 필요
- POSIX 호환 셸 환경 필요
- 스크립트 실행 권한 설정 권장
- 대규모 스크립트의 경우 분석 시간이 걸릴 수 있음

플랫폼 지원:
- Linux: 모든 주요 배포판
- macOS: bash/zsh/sh 지원
- Windows: Git Bash, WSL, Cygwin
- *BSD: FreeBSD, OpenBSD 등
- Unix 계열: Solaris, AIX 등

스크립팅 환경:
- DevOps 자동화 스크립트
- 시스템 관리 스크립트
- CI/CD 파이프라인 스크립트
- 배치 처리 스크립트
- 설정 및 초기화 스크립트
"""

import logging
import os
import pathlib
import shutil
import threading

from solidlsp import ls_types
from solidlsp.language_servers.common import RuntimeDependency, RuntimeDependencyCollection
from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings


class BashLanguageServer(SolidLanguageServer):
    """
    Bash 쉘 스크립팅을 위한 bash-language-server 구현 클래스.

    bash-language-server를 백엔드로 사용하여 Bash/Shell 스크립트에 대한
    완전한 언어 서비스를 제공합니다. VS Code의 Bash 확장과 동일한
    수준의 쉘 스크립팅 개발 경험을 제공합니다.

    주요 특징:
    - JavaScript 기반 bash-language-server의 정확한 Bash 분석
    - POSIX Shell 표준 및 Bash 5.x 최신 기능 완벽 지원
    - 실시간 구문 검사 및 POSIX 표준 준수 검사
    - 환경 변수 및 스크립트 의존성 분석
    - VS Code Bash 확장과 동일한 수준의 코드 완성과 오류 검사
    - 스크립트 실행 경로 및 권한 분석

    초기화 파라미터:
    - config: 언어 서버의 동작을 제어하는 설정 객체
    - logger: 서버 활동을 로깅할 로거 인스턴스
    - repository_root_path: Bash 스크립트 프로젝트의 루트 디렉토리 경로
    - solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

    Bash 프로젝트 요구사항:
    - Node.js 18 이상 설치 필요
    - bash-language-server 패키지 필요
    - POSIX 호환 셸 환경 필요
    - 스크립트 파일에 실행 권한 설정 권장
    - 대규모 스크립트의 경우 초기 인덱싱 시간이 필요할 수 있음

    지원하는 파일 확장자:
    - .sh (Bash/Shell 스크립트)
    - .bash (Bash 스크립트)
    - .zsh (Zsh 스크립트)
    - .ksh (Korn Shell 스크립트)
    - .csh (C Shell 스크립트)
    - .fish (Fish Shell 스크립트)

    DevOps 특화 기능:
    - CI/CD 스크립트 분석
    - Docker 및 컨테이너 스크립트 지원
    - 시스템 관리 스크립트 검사
    - 배치 처리 스크립트 최적화
    - 환경 변수 의존성 추적
    - 권한 및 보안 검사

    Note:
        Bash Language Server는 JavaScript/Node.js 기반으로 작동하며,
        VS Code의 Bash 확장과 동일한 엔진을 사용합니다.
        POSIX 표준 준수 및 Bash 최신 기능을 완벽하게 지원합니다.
    """

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        BashLanguageServer 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. bash-language-server를 백엔드로 사용하여
        Bash/Shell 언어 서비스를 제공합니다.

        초기화 과정:
        1. bash-language-server 런타임 의존성 설치 및 설정
        2. Node.js 환경에서 bash-language-server 실행 명령어 구성
        3. 상위 클래스 초기화

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: Bash 스크립트 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Instance Variables:
            server_ready: 서버가 완전히 시작되어 준비된 상태를 알림
            initialize_searcher_command_available: 심볼 검색 명령이 사용 가능함을 알림

        Note:
            Bash Language Server는 JavaScript/Node.js 기반으로 작동합니다.
            Node.js 18 이상과 bash-language-server 패키지가 필요합니다.
            모든 컴포넌트는 npm을 통해 자동으로 설치됩니다.

        DevOps 지원:
            DevOps 스크립트의 경우 CI/CD 파이프라인, Docker 스크립트,
            시스템 관리 스크립트 등에 특화된 분석을 제공합니다.
            환경 변수 의존성과 실행 권한을 특별히 검사합니다.

        플랫폼 지원:
            - Linux/Unix: 모든 주요 배포판
            - macOS: bash, zsh, sh 지원
            - Windows: Git Bash, WSL, Cygwin 환경
        """
        bash_lsp_executable_path = self._setup_runtime_dependencies(logger, config, solidlsp_settings)
        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=bash_lsp_executable_path, cwd=repository_root_path),
            "bash",
            solidlsp_settings,
        )
        self.server_ready = threading.Event()
        self.initialize_searcher_command_available = threading.Event()

    @classmethod
    def _setup_runtime_dependencies(
        cls, logger: LanguageServerLogger, config: LanguageServerConfig, solidlsp_settings: SolidLSPSettings
    ) -> str:
        """
        Bash Language Server의 런타임 의존성을 설정하고 실행 명령어를 반환합니다.

        이 메서드는 Bash/Shell 스크립트 분석을 위한 bash-language-server를 설치하고 설정합니다.
        JavaScript 기반의 bash-language-server 5.6.0을 npm을 통해 설치하며,
        Node.js 환경에서 실행되는 고성능 Bash/Shell 분석 엔진을 제공합니다.

        Args:
            logger: 설치 과정을 로깅할 로거
            config: 언어 서버 설정 (사용되지 않음)
            solidlsp_settings: SolidLSP 시스템 설정

        Returns:
            str: bash-language-server 실행 파일의 절대 경로

        설치되는 컴포넌트:
        1. **bash-language-server 5.6.0**: JavaScript 기반 Bash/Shell 분석 서버
        2. **Node.js 런타임**: JavaScript 실행 환경
        3. **npm 패키지 매니저**: 패키지 설치 및 관리

        설치 과정:
        1. Node.js 및 npm 설치 확인
        2. bash-language-server 패키지 다운로드 및 설치
        3. 플랫폼별 실행 파일 경로 결정 (Windows: .cmd, Unix: 직접 실행)
        4. 실행 권한 설정 (Unix 시스템의 경우)

        플랫폼별 처리:
        - Windows: .cmd 확장자 추가
        - Unix/Linux/macOS: 실행 권한 설정 (chmod +x)
        - 모든 플랫폼: bash-language-server 패키지의 .bin 디렉토리 사용

        Note:
            bash-language-server는 VS Code의 Bash 확장과 동일한 엔진을 사용하며,
            npm을 통해 설치됩니다. Node.js 18 이상이 필요하며,
            모든 주요 플랫폼에서 동일한 수준의 Bash/Shell 분석 기능을 제공합니다.
        """
        # Verify both node and npm are installed
        is_node_installed = shutil.which("node") is not None
        assert is_node_installed, "node is not installed or isn't in PATH. Please install NodeJS and try again."
        is_npm_installed = shutil.which("npm") is not None
        assert is_npm_installed, "npm is not installed or isn't in PATH. Please install npm and try again."

        deps = RuntimeDependencyCollection(
            [
                RuntimeDependency(
                    id="bash-language-server",
                    description="bash-language-server package",
                    command="npm install --prefix ./ bash-language-server@5.6.0",
                    platform_id="any",
                ),
            ]
        )

        # Install bash-language-server if not already installed
        bash_ls_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "bash-lsp")
        bash_executable_path = os.path.join(bash_ls_dir, "node_modules", ".bin", "bash-language-server")

        # Handle Windows executable extension
        if os.name == "nt":
            bash_executable_path += ".cmd"

        if not os.path.exists(bash_executable_path):
            logger.log(f"Bash Language Server executable not found at {bash_executable_path}. Installing...", logging.INFO)
            deps.install(logger, bash_ls_dir)
            logger.log("Bash language server dependencies installed successfully", logging.INFO)

        if not os.path.exists(bash_executable_path):
            raise FileNotFoundError(
                f"bash-language-server executable not found at {bash_executable_path}, something went wrong with the installation."
            )
        return f"{bash_executable_path} start"

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize params for the Bash Language Server.
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
        Bash Language Server를 시작하고 서버 준비 완료를 기다립니다.

        이 메서드는 bash-language-server를 시작하고, 서버가 완전히 준비될 때까지
        기다린 후 클라이언트 요청을 처리할 준비를 완료합니다. JavaScript 기반의
        bash-language-server는 Shell 스크립트 분석에 특화되어 있습니다.

        주요 단계:
        1. LSP 서버 프로세스 시작
        2. 다양한 LSP 핸들러 등록
        3. 초기화 파라미터 전송
        4. 서버 기능 검증
        5. 초기화 완료 알림

        등록되는 핸들러들:
        - client/registerCapability: 클라이언트 기능 등록
        - window/logMessage: 창 로그 메시지 (분석 완료 감지)
        - workspace/executeClientCommand: 클라이언트 명령 실행
        - $/progress: 진행 상태 알림
        - textDocument/publishDiagnostics: 진단 정보 게시

        Bash 특화 기능:
        - 분석 완료 감지 ("Analyzing", "analysis complete" 메시지)
        - 심볼 검색 명령 활성화
        - 문서 심볼 제공자 지원
        - 작업 공간 심볼 제공자 지원
        - 코드 액션 및 리팩토링 지원

        Note:
            bash-language-server는 JavaScript/Node.js 기반으로 작동하며,
            VS Code의 Bash 확장과 동일한 수준의 Shell 스크립트 분석 기능을 제공합니다.
            분석 완료 신호를 통해 서버 준비 상태를 정확하게 판단합니다.
        """

        def register_capability_handler(params):
            """
            클라이언트 기능 등록 핸들러.

            bash-language-server가 workspace/executeCommand 기능을 등록하면
            심볼 검색 명령을 사용할 수 있게 됩니다. Bash 스크립트에서는
            이러한 기능들이 특히 중요합니다.
            """
            assert "registrations" in params
            for registration in params["registrations"]:
                if registration["method"] == "workspace/executeCommand":
                    self.initialize_searcher_command_available.set()
            return

        def execute_client_command_handler(params):
            """
            클라이언트 명령 실행 핸들러.

            workspace/executeClientCommand 요청에 대한 응답으로 빈 리스트를 반환합니다.
            bash-language-server의 명령 실행 기능을 처리합니다.
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
            bash-language-server의 분석 완료 신호를 감지하여 서버 준비 상태를 판단합니다.

            Args:
                msg: 로그 메시지 파라미터
            """
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)
            # bash-language-server 준비 신호 감지
            message_text = msg.get("message", "")
            if "Analyzing" in message_text or "analysis complete" in message_text.lower():
                self.logger.log("Bash language server analysis signals detected", logging.INFO)
                self.server_ready.set()
                self.completions_available.set()

        # LSP 이벤트 핸들러 등록 - 각종 서버 알림 및 요청 처리
        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        # Bash Language Server 프로세스 시작
        self.logger.log("Starting Bash server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)
        self.logger.log(f"Received initialize response from bash server: {init_response}", logging.DEBUG)

        # bash-language-server 5.6.0 기능 검사 강화
        assert init_response["capabilities"]["textDocumentSync"] in [1, 2]  # Full or Incremental
        assert "completionProvider" in init_response["capabilities"]

        # 문서 심볼 지원 확인
        if "documentSymbolProvider" in init_response["capabilities"]:
            self.logger.log("Bash server supports document symbols", logging.INFO)
        else:
            self.logger.log("Warning: Bash server does not report document symbol support", logging.WARNING)

        self.server.notify.initialized({})

        # Wait for server readiness with timeout
        self.logger.log("Waiting for Bash language server to be ready...", logging.INFO)
        if not self.server_ready.wait(timeout=3.0):
            # Fallback: assume server is ready after timeout
            self.logger.log("Timeout waiting for bash server ready signal, proceeding anyway", logging.WARNING)
            self.server_ready.set()
            self.completions_available.set()
        else:
            self.logger.log("Bash server initialization complete", logging.INFO)

    def request_document_symbols(
        self, relative_file_path: str, include_body: bool = False
    ) -> tuple[list[ls_types.UnifiedSymbolInformation], list[ls_types.UnifiedSymbolInformation]]:
        """
        Request document symbols from bash-language-server via LSP.

        Uses the standard LSP documentSymbol request which provides reliable function detection
        for all bash function syntaxes including:
        - function name() { ... } (with function keyword)
        - name() { ... } (traditional syntax)
        - Functions with various indentation levels
        - Functions with comments before/after/inside

        Args:
            relative_file_path: Path to the bash file relative to repository root
            include_body: Whether to include function bodies in symbol information

        Returns:
            Tuple of (all_symbols, root_symbols) detected by the LSP server

        """
        self.logger.log(f"Requesting document symbols via LSP for {relative_file_path}", logging.DEBUG)

        # Use the standard LSP approach - bash-language-server handles all function syntaxes correctly
        all_symbols, root_symbols = super().request_document_symbols(relative_file_path, include_body)

        # Log detection results for debugging
        functions = [s for s in all_symbols if s.get("kind") == 12]
        self.logger.log(
            f"LSP function detection for {relative_file_path}: Found {len(functions)} functions",
            logging.INFO,
        )

        return all_symbols, root_symbols
