"""
SolidLSP Python 언어 서버 모듈 - Pyright 기반 Python 언어 지원

이 모듈은 Microsoft의 Pyright 타입 체커를 기반으로 한 Python 언어 서버를 구현합니다.
Pyright는 정적 타입 분석에 특화되어 있어 타입 관련 기능이 강력합니다:

주요 특징:
- 정적 타입 분석 및 타입 추론
- 고급 Python 타입 검사 (TypeScript 스타일)
- 빠른 코드 분석 및 오류 검출
- 제네릭 타입 및 프로토콜 지원
- Stub 파일 (.pyi) 지원

아키텍처:
- PyrightServer: Pyright 기반의 LSP 서버 클래스
- Pyright Language Server 프로세스와의 통신
- Python 타입 시스템 특화된 설정

지원하는 Python 기능:
- PEP 484 타입 힌트
- PEP 526 변수 어노테이션
- PEP 544 프로토콜
- PEP 561 Distributing and Packaging Type Information
- 제네릭 타입 (TypeVar, Generic)
- Callable 타입 및 오버로드
- NamedTuple, TypedDict 등 특수 폼

주의사항:
- Pyright는 별도 Python 패키지로 설치 필요
- 타입 분석에 특화되어 있어 Jedi보다 정확한 타입 정보 제공
- 대규모 프로젝트에서 더 나은 성능 발휘
"""

import logging
import os
import pathlib
import re
import threading

from overrides import override

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings


class PyrightServer(SolidLanguageServer):
    """
    Python 언어를 위한 Pyright 기반 LSP 서버 구현 클래스.

    Microsoft의 Pyright 타입 체커를 백엔드로 사용하여 Python 코드에 대한
    고급 타입 분석과 언어 서비스를 제공합니다. Jedi에 비해 타입 관련 기능이
    더 정확하고 강력합니다.

    주요 특징:
    - Microsoft Pyright 엔진 기반의 정확한 타입 분석
    - 광범위한 LSP 기능 지원 (완료, 정의, 호버, 진단 등)
    - Python 가상환경 및 캐시 디렉토리 자동 무시
    - 실시간 타입 검사 및 오류 보고
    - 제네릭 타입 및 프로토콜 지원

    초기화 파라미터:
    - config: 언어 서버 설정
    - logger: 로깅을 위한 로거 인스턴스
    - repository_root_path: 프로젝트 루트 경로
    - solidlsp_settings: SolidLSP 전역 설정

    타입 분석 기능:
    - PEP 484 준수 타입 힌트 지원
    - 제네릭 타입 (List[str], Dict[str, Any] 등)
    - Callable 타입 및 함수 오버로드
    - NamedTuple, TypedDict 등 특수 폼 지원
    """

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        PyrightServer 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. Pyright Language Server를 Python 모듈로 실행하여
        타입 분석에 특화된 Python 언어 서비스를 제공합니다.

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: 분석할 Python 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Note:
            Pyright는 Python 모듈로 실행되며 (`python -m pyright.langserver --stdio`),
            npm을 통한 별도 설치가 필요합니다. 타입 분석에 특화되어 있어
            복잡한 Python 프로젝트에서 더 나은 성능을 제공합니다.

        추가 설정:
            analysis_complete: 초기 작업 공간 분석 완료를 알리는 이벤트
            found_source_files: 소스 파일 발견 여부를 추적하는 플래그
        """
        super().__init__(
            config,
            logger,
            repository_root_path,
            # Note 1: we can also use `pyright-langserver --stdio` but it requires pyright to be installed with npm
            # Note 2: we can also use `bpyright-langserver --stdio` if we ever are unhappy with pyright
            ProcessLaunchInfo(cmd="python -m pyright.langserver --stdio", cwd=repository_root_path),
            "python",
            solidlsp_settings,
        )

        # Event to signal when initial workspace analysis is complete
        # 초기 작업 공간 분석 완료를 알리는 이벤트
        self.analysis_complete = threading.Event()
        self.found_source_files = False

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        """
        Python 프로젝트에서 Pyright가 무시해야 할 디렉토리 이름을 판단합니다.

        기본 무시 디렉토리(예: .git, node_modules 등)에 더해 Python 특화된
        디렉토리들을 추가로 무시합니다. Pyright는 타입 분석에 최적화되어 있으므로
        분석 성능을 위해 불필요한 디렉토리들을 제외합니다.

        Args:
            dirname: 검사할 디렉토리 이름

        Returns:
            bool: 무시해야 하면 True, 그렇지 않으면 False

        Pyright 특화 무시 대상:
        - venv: Python 가상환경 디렉토리 (타입 정보가 불완전할 수 있음)
        - __pycache__: Python 바이트코드 캐시 디렉토리
        - 기본 무시 디렉토리들 (.git, node_modules 등)

        Note:
            Pyright는 타입 정확성을 위해 가능한 한 많은 파일을 분석하려 하지만,
            성능과 정확성을 위해 불필요한 디렉토리들을 제외합니다.
        """
        return super().is_ignored_dirname(dirname) or dirname in ["venv", "__pycache__"]

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Pyright Language Server를 위한 LSP 초기화 파라미터를 생성합니다.

        이 메서드는 Pyright 타입 체커에 특화된 초기화 파라미터를 구성합니다.
        Pyright는 타입 분석에 최적화되어 있으므로, 타입 검사 관련 설정들이
        포함되어 있습니다.

        Args:
            repository_absolute_path: 초기화할 프로젝트의 절대 경로

        Returns:
            InitializeParams: LSP 초기화 요청에 사용할 파라미터 딕셔너리

        초기화 파라미터 구성 요소:
        - processId: 현재 프로세스 ID
        - rootPath/Uri: 프로젝트 루트 경로 (파일 시스템 경로 + URI)
        - initializationOptions: Pyright 특화된 옵션들
          - exclude: 분석에서 제외할 패턴들
          - reportMissingImports: 누락된 import 보고 수준
        - capabilities: 지원하는 LSP 기능들의 상세 목록

        Pyright 특화 설정:
        - reportMissingImports: "error"로 설정하여 누락된 import를 오류로 보고
        - 광범위한 LSP 기능 지원 (워크스페이스 편집, 심볼, 실행 명령 등)
        - 동적 등록 지원으로 런타임 기능 확장 가능

        Note:
            Pyright는 타입 정확성을 위해 가능한 한 많은 정보를 수집하려 하며,
            exclude 패턴을 통해 불필요한 디렉토리들을 제외합니다.
        """
        # Create basic initialization parameters
        # 기본 초기화 파라미터 생성
        initialize_params: InitializeParams = {  # type: ignore
            "processId": os.getpid(),
            "rootPath": repository_absolute_path,
            "rootUri": pathlib.Path(repository_absolute_path).as_uri(),
            "initializationOptions": {
                "exclude": [
                    "**/__pycache__",
                    "**/.venv",
                    "**/.env",
                    "**/build",
                    "**/dist",
                    "**/.pixi",
                ],
                "reportMissingImports": "error",
            },
            "capabilities": {
                "workspace": {
                    "workspaceEdit": {"documentChanges": True},
                    "didChangeConfiguration": {"dynamicRegistration": True},
                    "didChangeWatchedFiles": {"dynamicRegistration": True},
                    "symbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                    },
                    "executeCommand": {"dynamicRegistration": True},
                },
                "textDocument": {
                    "synchronization": {"dynamicRegistration": True, "willSave": True, "willSaveWaitUntil": True, "didSave": True},
                    "hover": {"dynamicRegistration": True, "contentFormat": ["markdown", "plaintext"]},
                    "signatureHelp": {
                        "dynamicRegistration": True,
                        "signatureInformation": {
                            "documentationFormat": ["markdown", "plaintext"],
                            "parameterInformation": {"labelOffsetSupport": True},
                        },
                    },
                    "definition": {"dynamicRegistration": True},
                    "references": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                        "hierarchicalDocumentSymbolSupport": True,
                    },
                    "publishDiagnostics": {"relatedInformation": True},
                },
            },
            "workspaceFolders": [
                {"uri": pathlib.Path(repository_absolute_path).as_uri(), "name": os.path.basename(repository_absolute_path)}
            ],
        }

        return initialize_params

    def _start_server(self):
        """
        Pyright Language Server를 시작하고 초기 작업 공간 분석 완료를 기다립니다.

        이 메서드는 좀비 프로세스 방지를 위해 Pyright가 초기 백그라운드 작업을
        완료할 때까지 기다린 후 서버가 준비되었다고 판단합니다.

        주요 단계:
        1. LSP 서버 프로세스 시작
        2. 다양한 LSP 핸들러 등록
        3. 초기화 파라미터 전송
        4. 서버 기능 검증
        5. 초기화 완료 알림
        6. 작업 공간 분석 완료 대기

        등록되는 핸들러들:
        - client/registerCapability: 클라이언트 기능 등록
        - language/status: 언어 상태 알림
        - window/logMessage: 창 로그 메시지 (분석 완료 감지용)
        - workspace/executeClientCommand: 클라이언트 명령 실행
        - textDocument/publishDiagnostics: 진단 정보 게시
        - experimental/serverStatus: 실험적 서버 상태

        분석 완료 감지:
        - "Found X source files" 로그 메시지 패턴으로 분석 완료 감지
        - experimental/serverStatus의 quiescent 상태로 백업 감지
        - 타임아웃(5초) 후 강제 진행

        Usage:
        ```
        async with lsp.start_server():
            # LanguageServer has been initialized and workspace analysis is complete
            # 언어 서버가 초기화되고 작업 공간 분석이 완료됨
            await lsp.request_definition(...)
            await lsp.request_references(...)
            # Shutdown the LanguageServer on exit from scope
            # 범위 종료 시 언어 서버가 정리 종료됨
        # LanguageServer has been shutdown cleanly
        # 언어 서버가 정상적으로 종료됨
        ```
        """

        def execute_client_command_handler(params):
            """
            클라이언트 명령 실행 핸들러.

            workspace/executeClientCommand 요청에 대한 응답으로 빈 리스트를 반환합니다.
            Pyright의 명령 실행 기능을 처리합니다.
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
            Pyright의 로그 메시지를 모니터링하여 초기 분석 완료를 감지합니다.

            Pyright는 작업 공간 스캔이 완료되면 "Found X source files" 메시지를
            로그로 출력합니다. 이 패턴을 감지하여 분석 완료 상태를 판단합니다.

            Args:
                msg: LSP 서버로부터 받은 로그 메시지
            """
            message_text = msg.get("message", "")
            self.logger.log(f"LSP: window/logMessage: {message_text}", logging.INFO)

            # Look for "Found X source files" which indicates workspace scanning is complete
            # 작업 공간 스캔 완료를 나타내는 "Found X source files" 패턴을 찾습니다
            # Unfortunately, pyright is unreliable and there seems to be no better way
            # 불행히도 Pyright는 신뢰할 수 없으며 더 나은 방법이 없는 것 같습니다
            if re.search(r"Found \d+ source files?", message_text):
                self.logger.log("Pyright workspace scanning complete", logging.INFO)
                self.found_source_files = True
                self.analysis_complete.set()
                self.completions_available.set()

        def check_experimental_status(params):
            """
            실험적 서버 상태를 백업 신호로 수신합니다.

            experimental/serverStatus 알림을 백업 메커니즘으로 사용하여
            서버가 조용한 상태(quiescent)가 되면 분석 완료로 판단합니다.

            Args:
                params: 서버 상태 파라미터
            """
            if params.get("quiescent") == True:
                self.logger.log("Received experimental/serverStatus with quiescent=true", logging.INFO)
                if not self.found_source_files:
                    self.analysis_complete.set()
                    self.completions_available.set()

        # Set up notification handlers - LSP 알림 핸들러 설정
        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_notification("language/status", do_nothing)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("language/actionableNotification", do_nothing)
        self.server.on_notification("experimental/serverStatus", check_experimental_status)

        # Pyright Language Server 프로세스 시작
        self.logger.log("Starting pyright-langserver server process", logging.INFO)
        self.server.start()

        # Send proper initialization parameters - 올바른 초기화 파라미터 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)

        self.logger.log(
            "Sending initialize request from LSP client to pyright server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)
        self.logger.log(f"Received initialize response from pyright server: {init_response}", logging.INFO)

        # Verify that the server supports our required features - 필수 기능 지원 확인
        assert "textDocumentSync" in init_response["capabilities"]
        assert "completionProvider" in init_response["capabilities"]
        assert "definitionProvider" in init_response["capabilities"]

        # Complete the initialization handshake - 초기화 핸드셰이크 완료
        self.server.notify.initialized({})

        # Wait for Pyright to complete its initial workspace analysis
        # Pyright의 초기 작업 공간 분석 완료 대기
        # This prevents zombie processes by ensuring background tasks finish
        # 백그라운드 작업이 완료되도록 하여 좀비 프로세스 방지
        self.logger.log("Waiting for Pyright to complete initial workspace analysis...", logging.INFO)
        if self.analysis_complete.wait(timeout=5.0):
            self.logger.log("Pyright initial analysis complete, server ready", logging.INFO)
        else:
            self.logger.log("Timeout waiting for Pyright analysis completion, proceeding anyway", logging.WARNING)
            # Fallback: assume analysis is complete after timeout
            # 폴백: 타임아웃 후 분석이 완료되었다고 가정
            self.analysis_complete.set()
            self.completions_available.set()
