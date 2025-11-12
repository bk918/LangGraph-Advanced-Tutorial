"""
SolidLSP Go 언어 서버 모듈 - Gopls 기반 Go 언어 지원

이 모듈은 Go 프로그래밍 언어를 위한 LSP 서버를 구현합니다.
Google의 공식 Gopls (Go Language Server)를 기반으로 하여 Go 코드에 대한
완전한 언어 서비스를 제공합니다:

주요 기능:
- Go 코드 완성 (IntelliSense)
- 코드 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사
- 코드 리팩토링 및 네비게이션
- Go 모듈 지원

아키텍처:
- Gopls: Go 공식 LSP 서버를 래핑하는 클래스
- Go 도구체인 통합
- Go 모듈 및 작업 공간 지원
- 고성능 타입 검사 및 분석

지원하는 Go 기능:
- 표준 Go 문법 및 라이브러리
- Go 모듈 (go.mod) 지원
- 제네릭 타입 (Go 1.18+)
- 고루틴 및 채널 지원
- 구조체 임베딩 및 인터페이스
- 테스트 파일 자동 인식

특징:
- Google 공식 Go 도구체인과 완벽한 통합
- 실시간 타입 검사 및 오류 보고
- 고성능 인덱싱 및 캐싱
- Go 모듈 의존성 분석
- 다양한 Go 프로젝트 구조 지원

중요 요구사항:
- Go 1.18 이상 필요
- go.mod 파일이 있는 프로젝트 권장
- Gopls는 Go 도구체인과 함께 설치됨
- 네트워크 작업 시 GOPROXY 설정 권장
"""

import logging
import os
import pathlib
import subprocess
import threading

from overrides import override

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings


class Gopls(SolidLanguageServer):
    """
    Go 언어를 위한 Gopls 기반 LSP 서버 구현 클래스.

    Google의 공식 Go Language Server (Gopls)를 백엔드로 사용하여
    Go 코드에 대한 완전한 언어 서비스를 제공합니다. Go 도구체인과
    완벽하게 통합되어 최적의 Go 개발 경험을 제공합니다.

    주요 특징:
    - Google 공식 Gopls 엔진 기반의 정확한 Go 언어 분석
    - Go 1.18 이상의 모든 최신 기능 지원 (제네릭 포함)
    - Go 모듈 및 작업 공간 완벽 지원
    - 실시간 컴파일 및 상세한 오류 보고
    - 고루틴, 채널 등 고급 Go 기능 완벽 지원
    - 테스트 파일 자동 인식 및 지원

    초기화 파라미터:
    - config: 언어 서버의 동작을 제어하는 설정 객체
    - logger: 서버 활동을 로깅할 로거 인스턴스
    - repository_root_path: Go 프로젝트의 루트 디렉토리 경로
    - solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

    Go 프로젝트 요구사항:
    - Go 1.18 이상 설치 필요
    - go.mod 파일이 있는 프로젝트에서 최적 성능
    - 표준 Go 프로젝트 레이아웃 (cmd/, pkg/, internal/ 등) 지원
    - Go 모듈 프록시 (GOPROXY) 설정 권장

    지원하는 파일 확장자:
    - .go (Go 소스 파일)
    - .mod (Go 모듈 파일)
    - .sum (Go 모듈 체크섬 파일)
    - .work (Go 작업 공간 파일)

    Note:
        Gopls는 Go 공식 도구체인의 일부로, 상업용 프로젝트에서도
        무료로 사용 가능합니다. Google이 지속적으로 유지보수하며,
        Go 언어의 최신 기능을 가장 빠르게 지원합니다.
    """

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        """
        Go 프로젝트에서 무시해야 할 디렉토리 이름을 판단합니다.

        기본 무시 디렉토리(예: .git, node_modules 등)에 더해 Go 특화된
        디렉토리들을 추가로 무시합니다. 이러한 디렉토리들은 타입 분석에
        불필요하거나 방해가 될 수 있습니다.

        Args:
            dirname: 검사할 디렉토리 이름

        Returns:
            bool: 무시해야 하면 True, 그렇지 않으면 False

        Go 특화 무시 대상:
        - vendor: Go 모듈 벤더링 디렉토리 (의존성)
        - node_modules: JavaScript 컴포넌트가 있는 경우
        - dist: 빌드 출력 디렉토리
        - build: 빌드 중간 파일 디렉토리
        - 기본 무시 디렉토리들 (.git, node_modules 등)

        Note:
            Go 모듈 시스템에서는 vendor 디렉토리를 무시하는 것이 중요합니다.
            Gopls는 Go 모듈을 통해 의존성을 관리하므로 vendor는 분석에서 제외됩니다.
        """
        # For Go projects, we should ignore:
        # - vendor: third-party dependencies vendored into the project
        # - node_modules: if the project has JavaScript components
        # - dist/build: common output directories
        return super().is_ignored_dirname(dirname) or dirname in ["vendor", "node_modules", "dist", "build"]

    @staticmethod
    def _get_go_version():
        """
        설치된 Go 버전을 조회합니다.

        시스템에 설치된 Go 컴파일러의 버전 정보를 반환합니다.
        Go가 설치되지 않은 경우 None을 반환합니다.

        Returns:
            str or None: Go 버전 문자열 (예: "go version go1.21.0 ...") 또는 None

        Note:
            이 메서드는 Go 도구체인이 올바르게 설치되어 있는지
            확인하는 용도로 사용됩니다.
        """
        try:
            result = subprocess.run(["go", "version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            return None
        return None

    @staticmethod
    def _get_gopls_version():
        """
        설치된 Gopls 버전을 조회합니다.

        시스템에 설치된 Gopls 언어 서버의 버전 정보를 반환합니다.
        Gopls가 설치되지 않은 경우 None을 반환합니다.

        Returns:
            str or None: Gopls 버전 문자열 (예: "gopls v0.14.2") 또는 None

        Note:
            Gopls는 Go 도구체인과 함께 설치되므로,
            Go가 설치되어 있다면 일반적으로 Gopls도 함께 설치됩니다.
        """
        try:
            result = subprocess.run(["gopls", "version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            return None
        return None

    @staticmethod
    def _setup_runtime_dependency():
        """
        필요한 Go 런타임 의존성이 설치되어 있는지 확인합니다.

        Go 컴파일러와 Gopls 언어 서버가 올바르게 설치되어 있는지 검증합니다.
        의존성이 누락된 경우 상세한 오류 메시지와 함께 RuntimeError를 발생시킵니다.

        Raises:
            RuntimeError: Go 또는 Gopls가 설치되지 않은 경우

        검증 항목:
        1. Go 컴파일러 (`go` 명령어) 설치 확인
        2. Gopls 언어 서버 (`gopls` 명령어) 설치 확인

        Note:
            Gopls는 Go 도구체인과 함께 설치되므로,
            Go가 올바르게 설치되어 있다면 Gopls도 함께 설치됩니다.
            설치 경로는 시스템 PATH에 포함되어야 합니다.
        """
        go_version = Gopls._get_go_version()
        if not go_version:
            raise RuntimeError(
                "Go is not installed. Please install Go from https://golang.org/doc/install and make sure it is added to your PATH."
            )

        gopls_version = Gopls._get_gopls_version()
        if not gopls_version:
            raise RuntimeError(
                "Found a Go version but gopls is not installed.\n"
                "Please install gopls as described in https://pkg.go.dev/golang.org/x/tools/gopls#section-readme\n\n"
                "After installation, make sure it is added to your PATH (it might be installed in a different location than Go)."
            )

        return True

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        Gopls 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. Gopls 언어 서버를 백엔드로 사용하여 Go 언어 서비스를 제공합니다.

        초기화 과정:
        1. Go 및 Gopls 의존성 검증
        2. 상위 클래스 초기화
        3. 서버 준비 상태 이벤트 설정

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: Go 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Note:
            Gopls는 Go 도구체인의 일부로 실행되므로,
            Go 1.18 이상이 시스템에 설치되어 있어야 합니다.
            go.mod 파일이 있는 프로젝트에서 최적의 성능을 제공합니다.

        Events:
            server_ready: 서버가 완전히 시작되어 준비된 상태를 알림
            request_id: LSP 요청 ID를 추적하기 위한 카운터
        """
        self._setup_runtime_dependency()

        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd="gopls", cwd=repository_root_path),
            "go",
            solidlsp_settings,
        )
        self.server_ready = threading.Event()
        self.request_id = 0

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Go Language Server를 위한 LSP 초기화 파라미터를 생성합니다.

        이 메서드는 Gopls에 특화된 초기화 파라미터를 구성합니다.
        Go 모듈과 작업 공간을 완벽하게 지원하도록 설정되어 있습니다.

        Args:
            repository_absolute_path: 초기화할 프로젝트의 절대 경로

        Returns:
            InitializeParams: LSP 초기화 요청에 사용할 파라미터 딕셔너리

        초기화 파라미터 구성 요소:
        - processId: 현재 프로세스 ID
        - rootPath/Uri: 프로젝트 루트 경로
        - capabilities: Gopls 기능 지원 목록
          - textDocument: 문서 관련 기능들 (정의, 심볼 등)
          - workspace: 작업 공간 관련 기능들 (폴더, 설정 변경)
        - workspaceFolders: 작업 공간 폴더 정보

        Gopls 특화 기능:
        - hierarchicalDocumentSymbolSupport: 계층적 문서 심볼 지원
        - 광범위한 심볼 종류 지원 (함수, 변수, 타입 등)
        - Go 모듈 자동 감지 및 설정

        Note:
            Gopls는 Go 모듈 시스템과 완벽하게 통합되어 있으므로,
            go.mod 파일이 있는 프로젝트에서 최상의 성능을 제공합니다.
            작업 공간 기반으로 여러 Go 모듈을 동시에 분석할 수 있습니다.
        """
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "locale": "en",
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True, "dynamicRegistration": True},
                    "definition": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "hierarchicalDocumentSymbolSupport": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                    },
                },
                "workspace": {"workspaceFolders": True, "didChangeConfiguration": {"dynamicRegistration": True}},
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
        Gopls 서버 프로세스를 시작하고 서버 준비 완료를 기다립니다.

        이 메서드는 Gopls 언어 서버를 시작하고, 서버가 완전히 준비될 때까지
        기다린 후 클라이언트 요청을 처리할 준비를 완료합니다. Gopls는 일반적으로
        초기화 직후 바로 준비되므로 빠른 시작이 가능합니다.

        주요 단계:
        1. LSP 서버 프로세스 시작
        2. 다양한 LSP 핸들러 등록
        3. 초기화 파라미터 전송
        4. 서버 기능 검증
        5. 초기화 완료 알림
        6. 서버 준비 상태 설정

        등록되는 핸들러들:
        - client/registerCapability: 클라이언트 기능 등록
        - window/logMessage: 창 로그 메시지
        - $/progress: 진행 상태 알림
        - textDocument/publishDiagnostics: 진단 정보 게시

        Gopls 특화 기능:
        - 초기화 직후 즉시 준비 상태로 전환
        - 빠른 서버 시작으로 대기 시간 최소화
        - 안정적인 연결 상태 유지
        - 실시간 Go 코드 분석 및 오류 검사

        Note:
            Gopls는 다른 언어 서버들과 달리 초기화 후 즉시 준비 상태가 되므로,
            별도의 준비 대기 시간이 필요하지 않습니다. 이는 Go의 빠른 컴파일 특성을 활용한 것입니다.
        """

        def register_capability_handler(params):
            """
            클라이언트 기능 등록 핸들러.

            Gopls의 클라이언트 기능 등록 요청을 처리합니다.
            Go 프로젝트의 특성상 특별한 추가 설정이 필요하지 않습니다.
            """
            return

        def window_log_message(msg):
            """
            창 로그 메시지 핸들러.

            LSP 서버로부터 받은 로그 메시지를 SolidLSP 로거를 통해 기록합니다.
            Gopls의 상세한 로그 정보를 추적할 수 있습니다.
            """
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        def do_nothing(params):
            """
            기본 핸들러 함수.

            대부분의 알림에 대해 아무 작업도 수행하지 않습니다.
            LSP 표준에 따라 다양한 이벤트들을 처리하기 위한 기본 핸들러입니다.
            """
            return

        # LSP 이벤트 핸들러 등록 - 각종 서버 알림 및 요청 처리
        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        # Gopls 서버 프로세스 시작
        self.logger.log("Starting gopls server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)

        # 서버 기능 검증 - 필수 기능들이 올바르게 설정되었는지 확인
        assert "textDocumentSync" in init_response["capabilities"]
        assert "completionProvider" in init_response["capabilities"]
        assert "definitionProvider" in init_response["capabilities"]

        # 초기화 완료 알림 전송 - 서버가 완전히 준비되었음을 알림
        self.server.notify.initialized({})
        self.completions_available.set()

        # Gopls 서버는 일반적으로 초기화 직후 바로 준비됨
        # gopls server is typically ready immediately after initialization
        self.server_ready.set()
        self.server_ready.wait()
