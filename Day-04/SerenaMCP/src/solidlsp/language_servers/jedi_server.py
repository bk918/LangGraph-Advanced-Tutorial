"""
SolidLSP Python 언어 서버 모듈 - Jedi 기반 Python 언어 지원

이 모듈은 Python 프로그래밍 언어를 위한 LSP (Language Server Protocol) 서버를 구현합니다.
Jedi 라이브러리를 기반으로 하여 Python 코드에 대한 완전한 언어 서비스를 제공합니다:

주요 기능:
- Python 코드 완성 (autocomplete)
- 코드 정의 및 참조 검색
- 호버 정보 제공
- 진단 및 오류 검사
- 심볼 탐색 및 네비게이션
- 코드 리팩토링 지원

아키텍처:
- JediServer: LSP 표준을 구현하는 메인 서버 클래스
- Jedi Language Server 프로세스와의 통신
- Python 특화된 설정 및 핸들러 제공

지원하는 Python 기능:
- 표준 Python 문법 및 라이브러리
- 가상환경 (venv, __pycache__) 무시 처리
- 광범위한 LSP 기능 지원 (완료, 정의, 참조, 진단 등)
"""

import logging
import os
import pathlib

from overrides import override

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings


class JediServer(SolidLanguageServer):
    """
    Python 언어를 위한 Jedi 기반 LSP 서버 구현 클래스.

    SolidLanguageServer를 상속받아 Python 특화된 LSP 기능을 제공합니다.
    Jedi Language Server 프로세스를 백엔드로 사용하여 Python 코드에 대한
    완전한 언어 서비스를 지원합니다.

    주요 특징:
    - Jedi 라이브러리 기반의 정확한 Python 언어 분석
    - 광범위한 LSP 기능 지원 (완료, 정의, 호버, 진단 등)
    - Python 가상환경 및 캐시 디렉토리 자동 무시
    - 실시간 코드 완성과 오류 검사

    초기화 파라미터:
    - config: 언어 서버 설정
    - logger: 로깅을 위한 로거 인스턴스
    - repository_root_path: 프로젝트 루트 경로
    - solidlsp_settings: SolidLSP 전역 설정
    """

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        JediServer 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. Jedi Language Server 프로세스를 백엔드로 사용하여 Python
        언어 서비스를 제공합니다.

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: 분석할 Python 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Note:
            Jedi Language Server는 별도 프로세스로 실행되며, LSP를 통해 통신합니다.
            서버 시작 시점에 초기화 파라미터가 전송되어 Python 언어 서비스가 활성화됩니다.
        """
        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd="jedi-language-server", cwd=repository_root_path),
            "python",
            solidlsp_settings,
        )

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        """
        Python 프로젝트에서 무시해야 할 디렉토리 이름을 판단합니다.

        기본 무시 디렉토리(예: .git, node_modules 등)에 더해 Python 특화된
        디렉토리들을 추가로 무시합니다.

        Args:
            dirname: 검사할 디렉토리 이름

        Returns:
            bool: 무시해야 하면 True, 그렇지 않으면 False

        무시 대상 디렉토리:
        - venv: Python 가상환경 디렉토리
        - __pycache__: Python 바이트코드 캐시 디렉토리
        - 기본 무시 디렉토리들 (.git, node_modules 등)
        """
        return super().is_ignored_dirname(dirname) or dirname in ["venv", "__pycache__"]

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Jedi Language Server를 위한 LSP 초기화 파라미터를 생성합니다.

        이 메서드는 Jedi Language Server에 전송할 초기화 파라미터를 구성합니다.
        파라미터에는 클라이언트 정보, 기능 지원 범위, 초기화 옵션 등이 포함됩니다.

        Args:
            repository_absolute_path: 초기화할 프로젝트의 절대 경로

        Returns:
            InitializeParams: LSP 초기화 요청에 사용할 파라미터 딕셔너리

        초기화 파라미터 구성 요소:
        - processId: 현재 프로세스 ID
        - clientInfo: Serena 클라이언트 정보 (이름, 버전)
        - rootPath/Uri: 프로젝트 루트 경로
        - capabilities: 지원하는 LSP 기능들의 상세 목록
        - initializationOptions: Jedi 서버 특화된 옵션들
        - workspaceFolders: 작업 공간 폴더 정보

        Note:
            capabilities 섹션은 매우 광범위한 LSP 기능을 포함하며,
            모든 표준 LSP 기능들을 지원하도록 구성되어 있습니다.
            maxSymbols가 0으로 설정되어 심볼 검색 제한이 없습니다.
        """
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "processId": os.getpid(),
            "clientInfo": {"name": "Serena", "version": "0.1.0"},
            "locale": "en",
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            # Note: this is not necessarily the minimal set of capabilities...
            "capabilities": {
                "workspace": {
                    "applyEdit": True,
                    "workspaceEdit": {
                        "documentChanges": True,
                        "resourceOperations": ["create", "rename", "delete"],
                        "failureHandling": "textOnlyTransactional",
                        "normalizesLineEndings": True,
                        "changeAnnotationSupport": {"groupsOnLabel": True},
                    },
                    "configuration": True,
                    "didChangeWatchedFiles": {"dynamicRegistration": True, "relativePatternSupport": True},
                    "symbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                        "tagSupport": {"valueSet": [1]},
                        "resolveSupport": {"properties": ["location.range"]},
                    },
                    "workspaceFolders": True,
                    "fileOperations": {
                        "dynamicRegistration": True,
                        "didCreate": True,
                        "didRename": True,
                        "didDelete": True,
                        "willCreate": True,
                        "willRename": True,
                        "willDelete": True,
                    },
                    "inlineValue": {"refreshSupport": True},
                    "inlayHint": {"refreshSupport": True},
                    "diagnostics": {"refreshSupport": True},
                },
                "textDocument": {
                    "publishDiagnostics": {
                        "relatedInformation": True,
                        "versionSupport": False,
                        "tagSupport": {"valueSet": [1, 2]},
                        "codeDescriptionSupport": True,
                        "dataSupport": True,
                    },
                    "synchronization": {"dynamicRegistration": True, "willSave": True, "willSaveWaitUntil": True, "didSave": True},
                    "hover": {"dynamicRegistration": True, "contentFormat": ["markdown", "plaintext"]},
                    "signatureHelp": {
                        "dynamicRegistration": True,
                        "signatureInformation": {
                            "documentationFormat": ["markdown", "plaintext"],
                            "parameterInformation": {"labelOffsetSupport": True},
                            "activeParameterSupport": True,
                        },
                        "contextSupport": True,
                    },
                    "definition": {"dynamicRegistration": True, "linkSupport": True},
                    "references": {"dynamicRegistration": True},
                    "documentHighlight": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                        "hierarchicalDocumentSymbolSupport": True,
                        "tagSupport": {"valueSet": [1]},
                        "labelSupport": True,
                    },
                    "documentLink": {"dynamicRegistration": True, "tooltipSupport": True},
                    "typeDefinition": {"dynamicRegistration": True, "linkSupport": True},
                    "implementation": {"dynamicRegistration": True, "linkSupport": True},
                    "declaration": {"dynamicRegistration": True, "linkSupport": True},
                    "selectionRange": {"dynamicRegistration": True},
                    "callHierarchy": {"dynamicRegistration": True},
                    "linkedEditingRange": {"dynamicRegistration": True},
                    "typeHierarchy": {"dynamicRegistration": True},
                    "inlineValue": {"dynamicRegistration": True},
                    "inlayHint": {
                        "dynamicRegistration": True,
                        "resolveSupport": {"properties": ["tooltip", "textEdits", "label.tooltip", "label.location", "label.command"]},
                    },
                    "diagnostic": {"dynamicRegistration": True, "relatedDocumentSupport": False},
                },
                "notebookDocument": {"synchronization": {"dynamicRegistration": True, "executionSummarySupport": True}},
                "experimental": {
                    "serverStatusNotification": True,
                    "openServerLogs": True,
                },
            },
            # See https://github.com/pappasam/jedi-language-server?tab=readme-ov-file
            # We use the default options except for maxSymbols, where 0 means no limit
            "initializationOptions": {
                "workspace": {
                    "symbols": {"ignoreFolders": [".nox", ".tox", ".venv", "__pycache__", "venv"], "maxSymbols": 0},
                },
            },
            "trace": "verbose",
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
        Jedi Language Server를 시작하고 LSP 핸들러들을 등록합니다.

        이 메서드는 다음 작업들을 수행합니다:
        1. LSP 서버 프로세스 시작
        2. 다양한 LSP 알림 및 요청 핸들러 등록
        3. 초기화 파라미터 전송
        4. 서버 기능 검증 (완료 제공자, 동기화 모드 등)

        등록되는 핸들러들:
        - client/registerCapability: 클라이언트 기능 등록
        - language/status: 언어 상태 알림
        - window/logMessage: 창 로그 메시지
        - workspace/executeClientCommand: 클라이언트 명령 실행
        - textDocument/publishDiagnostics: 진단 정보 게시
        - experimental/serverStatus: 실험적 서버 상태

        검증 항목:
        - textDocumentSync.change가 2 (증분 동기화)인지 확인
        - completionProvider가 올바르게 설정되어 있는지 확인
        - 지원하는 트리거 문자들: '.', "'", '"'

        Note:
            서버 시작 후 initialized 알림을 전송하여 서버가 완전히 준비되었음을 알립니다.
            이 과정에서 모든 LSP 기능이 활성화되고 클라이언트와의 통신이 시작됩니다.
        """

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
            """
            return

        def check_experimental_status(params):
            """
            실험적 서버 상태 확인 핸들러.

            서버가 조용한 상태(quiescent)가 되면 완료 기능이 사용 가능함을 알립니다.
            """
            if params["quiescent"] == True:
                self.completions_available.set()

        def window_log_message(msg):
            """
            창 로그 메시지 핸들러.

            LSP 서버로부터 받은 로그 메시지를 SolidLSP 로거를 통해 기록합니다.
            """
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        # LSP 이벤트 핸들러 등록 - 각종 서버 알림 및 요청 처리
        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_notification("language/status", do_nothing)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("language/actionableNotification", do_nothing)
        self.server.on_notification("experimental/serverStatus", check_experimental_status)

        # Jedi Language Server 프로세스 시작
        self.logger.log("Starting jedi-language-server server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)

        # 서버 응답 검증 - 필수 기능들이 올바르게 설정되었는지 확인
        assert init_response["capabilities"]["textDocumentSync"]["change"] == 2
        assert "completionProvider" in init_response["capabilities"]
        assert init_response["capabilities"]["completionProvider"] == {
            "triggerCharacters": [".", "'", '"'],
            "resolveProvider": True,
        }

        # 초기화 완료 알림 전송 - 서버가 완전히 준비되었음을 알림
        self.server.notify.initialized({})
