"""
SolidLSP Swift 언어 서버 모듈 - SourceKit LSP 기반 Swift 지원

이 모듈은 Swift 프로그래밍 언어를 위한 LSP 서버를 구현합니다.
Apple의 SourceKit LSP를 기반으로 하여 Swift 코드에 대한
완전한 언어 서비스를 제공합니다:

주요 기능:
- Swift 코드 완성 (IntelliSense)
- 코드 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사
- 코드 리팩토링 및 네이빅이션
- iOS/macOS/tvOS/watchOS 프로젝트 지원

아키텍처:
- SourceKitLSP: Apple 공식 SourceKit LSP 서버를 래핑하는 클래스
- Xcode/Apple Swift 생태계 통합
- Swift Package Manager 지원
- Swift Compiler 연동

지원하는 Swift 기능:
- Swift 5.x 문법 및 최신 기능
- SwiftUI 및 Combine 프레임워크
- 비동기/어웨이트 (async/await) 지원
- 프로토콜 지향 프로그래밍
- 제네릭 타입 및 프로토콜 지원
- Swift Package Manager 프로젝트 관리

특징:
- Apple 공식 Swift Language Server
- Xcode와 동일한 수준의 Swift 지원
- iOS/macOS/tvOS/watchOS 플랫폼 지원
- Swift Package Manager 완벽 연동
- 실시간 컴파일러 연동
- 고성능 증분 컴파일

중요 요구사항:
- Swift 5.7 이상 필요
- Xcode 14 이상 필요 (macOS에서)
- Swift Package Manager 필요
- iOS/macOS 개발 환경 필요
- Linux에서는 Swift Toolchain 필요
- 대규모 프로젝트의 경우 컴파일 시간이 오래 걸릴 수 있음

플랫폼 지원:
- macOS: iOS/macOS/tvOS/watchOS 앱 개발
- Linux: Swift Server Side 개발
- Windows: Swift Windows 지원 (제한적)
"""

import logging
import os
import pathlib
import subprocess
import threading
import time

from overrides import override

from solidlsp import ls_types
from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings


class SourceKitLSP(SolidLanguageServer):
    """
    Swift 언어를 위한 SourceKit LSP 구현 클래스.

    Apple의 공식 SourceKit LSP를 백엔드로 사용하여 Swift 코드에 대한
    완전한 언어 서비스를 제공합니다. Xcode와 동일한 수준의 Swift 개발 경험을 제공합니다.

    주요 특징:
    - Apple 공식 SourceKit LSP 기반의 정확한 Swift 언어 분석
    - iOS, macOS, tvOS, watchOS 등 모든 Apple 플랫폼 지원
    - Swift Package Manager와 완벽한 통합
    - Swift 5.x 최신 기능 및 SwiftUI/Combine 프레임워크 지원
    - 실시간 Swift 컴파일러 연동 및 정확한 오류 보고
    - Xcode와 동일한 수준의 코드 완성과 리팩토링

    초기화 파라미터:
    - config: 언어 서버의 동작을 제어하는 설정 객체
    - logger: 서버 활동을 로깅할 로거 인스턴스
    - repository_root_path: Swift 프로젝트의 루트 디렉토리 경로
    - solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

    Swift 프로젝트 요구사항:
    - Swift 5.7 이상 설치 필요
    - macOS에서는 Xcode 14 이상 필요
    - Linux에서는 Swift Toolchain 설치 필요
    - Package.swift 또는 .xcodeproj 파일 권장
    - iOS/macOS 프로젝트의 경우 Simulator SDK 필요
    - 대규모 프로젝트의 경우 초기 인덱싱 시간이 필요할 수 있음

    지원하는 파일 확장자:
    - .swift (Swift 소스 파일)
    - .h (Objective-C 헤더 파일)
    - Package.swift (Swift Package Manager)
    - .playground (Swift Playground)
    - .xcconfig (Xcode 구성 파일)

    iOS/macOS 특화 기능:
    - iOS/macOS/tvOS/watchOS SDK 인식
    - UIKit/SwiftUI 프레임워크 지원
    - Interface Builder 연동
    - Asset Catalog 지원
    - Core Data 모델 지원

    Note:
        SourceKit LSP는 Apple의 공식 프로젝트로, macOS/iOS 개발에 최적화되어 있습니다.
        Xcode의 Swift 플러그인과 동일한 엔진을 사용하므로 최고 수준의 Swift 지원을 제공합니다.
    """

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        """
        Swift 프로젝트에서 무시해야 할 디렉토리 이름을 판단합니다.

        기본 무시 디렉토리(예: .git, node_modules 등)에 더해 Swift 특화된
        디렉토리들을 추가로 무시합니다. Swift Package Manager의 빌드 출력과
        캐시 디렉토리를 제외합니다.

        Args:
            dirname: 검사할 디렉토리 이름

        Returns:
            bool: 무시해야 하면 True, 그렇지 않으면 False

        Swift 특화 무시 대상:
        - .build: Swift Package Manager의 빌드 출력 디렉토리 (거대하고 분석 불필요)
        - .swiftpm: Swift Package Manager의 메타데이터 및 캐시
        - node_modules: JavaScript 컴포넌트가 있는 경우 (하이브리드 프로젝트)
        - dist/build: 일반적인 빌드 출력 디렉토리들

        Note:
            SourceKit LSP는 Swift 컴파일러와 연동되므로,
            빌드 디렉토리를 무시하면 분석 성능이 크게 향상됩니다.
            이는 Swift 프로젝트의 표준 관행입니다.
        """
        # Swift 프로젝트의 무시 대상:
        # - .build: Swift Package Manager 빌드 산출물
        # - .swiftpm: Swift Package Manager 메타데이터
        # - node_modules: JavaScript 컴포넌트가 있는 경우
        # - dist/build: 일반적인 출력 디렉토리들
        return super().is_ignored_dirname(dirname) or dirname in [".build", ".swiftpm", "node_modules", "dist", "build"]

    @staticmethod
    def _get_sourcekit_lsp_version() -> str:
        """
        설치된 sourcekit-lsp 버전을 조회합니다.

        시스템에 설치된 SourceKit LSP의 버전 정보를 반환합니다.
        sourcekit-lsp가 설치되지 않은 경우 RuntimeError를 발생시킵니다.

        Returns:
            str: sourcekit-lsp 버전 정보 문자열

        Raises:
            RuntimeError: sourcekit-lsp가 설치되지 않았거나 실행할 수 없는 경우

        설치 방법:
            SourceKit LSP는 Xcode와 함께 설치되거나,
            https://github.com/apple/sourcekit-lsp#installation 에서
            별도로 설치할 수 있습니다.

        Note:
            SourceKit LSP는 Apple의 공식 Swift 언어 서버입니다.
            macOS에서는 Xcode 14 이상과 함께 자동으로 설치되며,
            Linux에서는 Swift Toolchain에 포함되어 있습니다.
        """
        try:
            result = subprocess.run(["sourcekit-lsp", "-h"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                raise Exception(f"`sourcekit-lsp -h` resulted in: {result}")
        except Exception as e:
            raise RuntimeError(
                "Could not find sourcekit-lsp, please install it as described in https://github.com/apple/sourcekit-lsp#installation"
                "And make sure it is available on your PATH."
            ) from e

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        SourceKitLSP 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. SourceKit LSP를 백엔드로 사용하여 Swift 언어 서비스를 제공합니다.

        초기화 과정:
        1. SourceKit LSP 버전 확인 및 검증
        2. 상위 클래스 초기화
        3. Swift 특화 상태 변수 초기화

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: Swift 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Instance Variables:
            server_ready: 서버가 완전히 시작되어 준비된 상태를 알림
            request_id: LSP 요청 ID 카운터
            _did_sleep_before_requesting_references: 참조 요청 전 대기 여부 플래그
            _initialization_timestamp: 초기화 시작 시간 기록

        Note:
            SourceKit LSP는 Apple의 공식 Swift 언어 서버로,
            Xcode 14 이상과 함께 설치되며 Swift 5.7 이상을 지원합니다.
            iOS/macOS/tvOS/watchOS 개발에 최적화되어 있습니다.

        Swift 특화 기능:
            - Swift Package Manager 프로젝트 자동 인식
            - iOS/macOS SDK 연동
            - SwiftUI/Combine 프레임워크 지원
            - Objective-C 상호 운용성 지원
        """
        sourcekit_version = self._get_sourcekit_lsp_version()
        logger.log(f"Starting sourcekit lsp with version: {sourcekit_version}", logging.INFO)

        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd="sourcekit-lsp", cwd=repository_root_path),
            "swift",
            solidlsp_settings,
        )
        self.server_ready = threading.Event()
        self.request_id = 0
        self._did_sleep_before_requesting_references = False
        self._initialization_timestamp = None

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Swift Language Server를 위한 LSP 초기화 파라미터를 생성합니다.

        이 메서드는 SourceKit LSP에 특화된 초기화 파라미터를 구성합니다.
        Xcode와 동일한 수준의 Swift 개발 환경을 제공하도록 설정되어 있습니다.

        Args:
            repository_absolute_path: 초기화할 Swift 프로젝트의 절대 경로

        Returns:
            InitializeParams: LSP 초기화 요청에 사용할 파라미터 딕셔너리

        초기화 파라미터 구성 요소:
        - capabilities: SourceKit LSP의 광범위한 기능 지원 목록
          - workspace: 작업 공간 관련 기능들 (편집, 심볼, 실행 등)
          - textDocument: 문서 관련 기능들 (완료, 정의, 진단 등)
          - window: 창 관련 기능들 (로그, 진행 상태 등)
        - rootUri: Swift 프로젝트 루트 디렉토리 URI
        - workspaceFolders: 작업 공간 폴더 정보

        Swift 특화 기능:
        - codeLens: 코드 렌즈 지원 (테스트 실행, 빌드 상태 등)
        - semanticTokens: 의미 토큰 (구문 하이라이트)
        - foldingRange: 코드 접기 범위
        - selectionRange: 선택 범위 확장
        - linkedEditingRange: 연결된 편집 범위
        - documentSymbolProvider: 문서 심볼 제공
        - workspaceSymbolProvider: 작업 공간 심볼 제공
        - executeCommandProvider: 명령 실행 지원

        Note:
            SourceKit LSP는 매우 광범위한 LSP 기능을 지원하므로,
            초기화 시점에 모든 표준 LSP 기능이 활성화됩니다.
            이는 Xcode의 Swift 확장과 동일한 수준의 기능을 제공합니다.
        """
        root_uri = pathlib.Path(repository_absolute_path).as_uri()

        initialize_params = {
            "capabilities": {
                "general": {
                    "markdown": {"parser": "marked", "version": "1.1.0"},
                    "positionEncodings": ["utf-16"],
                    "regularExpressions": {"engine": "ECMAScript", "version": "ES2020"},
                    "staleRequestSupport": {
                        "cancel": True,
                        "retryOnContentModified": [
                            "textDocument/semanticTokens/full",
                            "textDocument/semanticTokens/range",
                            "textDocument/semanticTokens/full/delta",
                        ],
                    },
                },
                "notebookDocument": {"synchronization": {"dynamicRegistration": True, "executionSummarySupport": True}},
                "textDocument": {
                    "callHierarchy": {"dynamicRegistration": True},
                    "codeAction": {
                        "codeActionLiteralSupport": {
                            "codeActionKind": {
                                "valueSet": [
                                    "",
                                    "quickfix",
                                    "refactor",
                                    "refactor.extract",
                                    "refactor.inline",
                                    "refactor.rewrite",
                                    "source",
                                    "source.organizeImports",
                                ]
                            }
                        },
                        "dataSupport": True,
                        "disabledSupport": True,
                        "dynamicRegistration": True,
                        "honorsChangeAnnotations": True,
                        "isPreferredSupport": True,
                        "resolveSupport": {"properties": ["edit"]},
                    },
                    "codeLens": {"dynamicRegistration": True},
                    "colorProvider": {"dynamicRegistration": True},
                    "completion": {
                        "completionItem": {
                            "commitCharactersSupport": True,
                            "deprecatedSupport": True,
                            "documentationFormat": ["markdown", "plaintext"],
                            "insertReplaceSupport": True,
                            "insertTextModeSupport": {"valueSet": [1, 2]},
                            "labelDetailsSupport": True,
                            "preselectSupport": True,
                            "resolveSupport": {"properties": ["documentation", "detail", "additionalTextEdits"]},
                            "snippetSupport": True,
                            "tagSupport": {"valueSet": [1]},
                        },
                        "completionItemKind": {
                            "valueSet": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
                        },
                        "completionList": {"itemDefaults": ["commitCharacters", "editRange", "insertTextFormat", "insertTextMode", "data"]},
                        "contextSupport": True,
                        "dynamicRegistration": True,
                        "insertTextMode": 2,
                    },
                    "declaration": {"dynamicRegistration": True, "linkSupport": True},
                    "definition": {"dynamicRegistration": True, "linkSupport": True},
                    "diagnostic": {"dynamicRegistration": True, "relatedDocumentSupport": False},
                    "documentHighlight": {"dynamicRegistration": True},
                    "documentLink": {"dynamicRegistration": True, "tooltipSupport": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "hierarchicalDocumentSymbolSupport": True,
                        "labelSupport": True,
                        "symbolKind": {
                            "valueSet": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]
                        },
                        "tagSupport": {"valueSet": [1]},
                    },
                    "foldingRange": {
                        "dynamicRegistration": True,
                        "foldingRange": {"collapsedText": False},
                        "foldingRangeKind": {"valueSet": ["comment", "imports", "region"]},
                        "lineFoldingOnly": True,
                        "rangeLimit": 5000,
                    },
                    "formatting": {"dynamicRegistration": True},
                    "hover": {"contentFormat": ["markdown", "plaintext"], "dynamicRegistration": True},
                    "implementation": {"dynamicRegistration": True, "linkSupport": True},
                    "inlayHint": {
                        "dynamicRegistration": True,
                        "resolveSupport": {"properties": ["tooltip", "textEdits", "label.tooltip", "label.location", "label.command"]},
                    },
                    "inlineValue": {"dynamicRegistration": True},
                    "linkedEditingRange": {"dynamicRegistration": True},
                    "onTypeFormatting": {"dynamicRegistration": True},
                    "publishDiagnostics": {
                        "codeDescriptionSupport": True,
                        "dataSupport": True,
                        "relatedInformation": True,
                        "tagSupport": {"valueSet": [1, 2]},
                        "versionSupport": False,
                    },
                    "rangeFormatting": {"dynamicRegistration": True, "rangesSupport": True},
                    "references": {"dynamicRegistration": True},
                    "rename": {
                        "dynamicRegistration": True,
                        "honorsChangeAnnotations": True,
                        "prepareSupport": True,
                        "prepareSupportDefaultBehavior": 1,
                    },
                    "selectionRange": {"dynamicRegistration": True},
                    "semanticTokens": {
                        "augmentsSyntaxTokens": True,
                        "dynamicRegistration": True,
                        "formats": ["relative"],
                        "multilineTokenSupport": False,
                        "overlappingTokenSupport": False,
                        "requests": {"full": {"delta": True}, "range": True},
                        "serverCancelSupport": True,
                        "tokenModifiers": [
                            "declaration",
                            "definition",
                            "readonly",
                            "static",
                            "deprecated",
                            "abstract",
                            "async",
                            "modification",
                            "documentation",
                            "defaultLibrary",
                        ],
                        "tokenTypes": [
                            "namespace",
                            "type",
                            "class",
                            "enum",
                            "interface",
                            "struct",
                            "typeParameter",
                            "parameter",
                            "variable",
                            "property",
                            "enumMember",
                            "event",
                            "function",
                            "method",
                            "macro",
                            "keyword",
                            "modifier",
                            "comment",
                            "string",
                            "number",
                            "regexp",
                            "operator",
                            "decorator",
                        ],
                    },
                    "signatureHelp": {
                        "contextSupport": True,
                        "dynamicRegistration": True,
                        "signatureInformation": {
                            "activeParameterSupport": True,
                            "documentationFormat": ["markdown", "plaintext"],
                            "parameterInformation": {"labelOffsetSupport": True},
                        },
                    },
                    "synchronization": {"didSave": True, "dynamicRegistration": True, "willSave": True, "willSaveWaitUntil": True},
                    "typeDefinition": {"dynamicRegistration": True, "linkSupport": True},
                    "typeHierarchy": {"dynamicRegistration": True},
                },
                "window": {
                    "showDocument": {"support": True},
                    "showMessage": {"messageActionItem": {"additionalPropertiesSupport": True}},
                    "workDoneProgress": True,
                },
                "workspace": {
                    "applyEdit": True,
                    "codeLens": {"refreshSupport": True},
                    "configuration": True,
                    "diagnostics": {"refreshSupport": True},
                    "didChangeConfiguration": {"dynamicRegistration": True},
                    "didChangeWatchedFiles": {"dynamicRegistration": True, "relativePatternSupport": True},
                    "executeCommand": {"dynamicRegistration": True},
                    "fileOperations": {
                        "didCreate": True,
                        "didDelete": True,
                        "didRename": True,
                        "dynamicRegistration": True,
                        "willCreate": True,
                        "willDelete": True,
                        "willRename": True,
                    },
                    "foldingRange": {"refreshSupport": True},
                    "inlayHint": {"refreshSupport": True},
                    "inlineValue": {"refreshSupport": True},
                    "semanticTokens": {"refreshSupport": False},
                    "symbol": {
                        "dynamicRegistration": True,
                        "resolveSupport": {"properties": ["location.range"]},
                        "symbolKind": {
                            "valueSet": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]
                        },
                        "tagSupport": {"valueSet": [1]},
                    },
                    "workspaceEdit": {
                        "changeAnnotationSupport": {"groupsOnLabel": True},
                        "documentChanges": True,
                        "failureHandling": "textOnlyTransactional",
                        "normalizesLineEndings": True,
                        "resourceOperations": ["create", "rename", "delete"],
                    },
                    "workspaceFolders": True,
                },
            },
            "clientInfo": {"name": "Visual Studio Code", "version": "1.102.2"},
            "initializationOptions": {
                "backgroundIndexing": True,
                "backgroundPreparationMode": "enabled",
                "textDocument/codeLens": {"supportedCommands": {"swift.debug": "swift.debug", "swift.run": "swift.run"}},
                "window/didChangeActiveDocument": True,
                "workspace/getReferenceDocument": True,
                "workspace/peekDocuments": True,
            },
            "locale": "en",
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
        SourceKit LSP 서버를 시작하고 서버 준비 완료를 기다립니다.

        이 메서드는 SourceKit LSP를 시작하고, 서버가 완전히 준비될 때까지
        기다린 후 클라이언트 요청을 처리할 준비를 완료합니다. SourceKit LSP는
        Swift 컴파일러와 연동되므로 초기화 시간이 다소 걸릴 수 있습니다.

        주요 단계:
        1. LSP 서버 프로세스 시작
        2. 다양한 LSP 핸들러 등록
        3. 초기화 파라미터 전송
        4. 서버 기능 검증
        5. 초기화 완료 알림

        등록되는 핸들러들:
        - client/registerCapability: 클라이언트 기능 등록
        - window/logMessage: 창 로그 메시지
        - $/progress: 진행 상태 알림
        - textDocument/publishDiagnostics: 진단 정보 게시

        검증 항목:
        - textDocumentSync: 문서 동기화 지원
        - definitionProvider: 정의로 이동 지원

        Swift 특화 기능:
        - Swift Package Manager 프로젝트 인식
        - iOS/macOS SDK 연동
        - SwiftUI/Combine 프레임워크 지원
        - Objective-C 상호 운용성 지원

        Note:
            SourceKit LSP는 Swift 컴파일러와 연동되므로,
            다른 언어 서버들보다 초기화 시간이 길 수 있습니다.
            이는 Swift의 타입 시스템과 Apple SDK의 복잡성 때문입니다.
        """

        def register_capability_handler(_params):
            """
            클라이언트 기능 등록 핸들러.

            SourceKit LSP가 클라이언트 기능을 등록하면
            이에 대한 응답을 처리합니다. Swift에서는
            특화된 기능들이 동적으로 등록될 수 있습니다.
            """
            return

        def window_log_message(msg):
            """
            창 로그 메시지 핸들러.

            LSP 서버로부터 받은 로그 메시지를 SolidLSP 로거를 통해 기록합니다.
            SourceKit LSP의 상세한 로그 정보를 추적할 수 있습니다.
            """
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        def do_nothing(_params):
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

        # SourceKit LSP 서버 프로세스 시작
        self.logger.log("Starting sourcekit-lsp server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)

        # SourceKit LSP 기능 검증
        capabilities = init_response["capabilities"]
        self.logger.log(f"SourceKit LSP capabilities: {list(capabilities.keys())}", logging.INFO)

        assert "textDocumentSync" in capabilities, "textDocumentSync capability missing"
        assert "definitionProvider" in capabilities, "definitionProvider capability missing"

        # 초기화 완료 알림 전송 - 서버가 완전히 준비되었음을 알림
        self.server.notify.initialized({})
        self.completions_available.set()

        # 서버 준비 완료 표시 및 대기
        self.server_ready.set()
        self.server_ready.wait()

        # 초기화 시간 기록 - 더 스마트한 지연 계산을 위해
        self._initialization_timestamp = time.time()

    @override
    def request_references(self, relative_file_path: str, line: int, column: int) -> list[ls_types.Location]:
        """
        Swift 프로젝트의 참조 정보를 요청합니다.

        SourceKit LSP는 초기화 후 인덱싱 시간이 필요하므로,
        정확한 참조 정보를 제공하기 위해 지연 시간을 적용합니다.
        CI 환경에서는 프로젝트 인덱싱과 크로스 파일 분석을 위해
        추가 시간이 필요합니다.

        Args:
            relative_file_path: 참조를 찾을 파일의 상대 경로
            line: 참조를 찾을 줄 번호
            column: 참조를 찾을 컬럼 번호

        Returns:
            list[ls_types.Location]: 참조 위치들의 목록

        Swift 특화 로직:
        1. **초기 대기 시간**: 첫 번째 참조 요청 시 CI/로컬 환경에 따라 5-15초 대기
        2. **스마트 지연 계산**: 초기화 후 경과 시간에 기반한 최소 지연 시간 계산
        3. **CI 재시도 로직**: CI 환경에서 참조를 찾지 못한 경우 5초 후 재시도
        4. **상태 추적**: 참조 요청 전 대기 여부 및 초기화 시간 추적

        CI 환경 최적화:
        - CI: 15초 베이스 지연 + 재시도 로직
        - 로컬: 5초 베이스 지연
        - 최소 2초 보장으로 레이스 컨디션 방지

        Note:
            Swift의 타입 시스템과 Apple SDK의 복잡성으로 인해
            다른 언어 서버들보다 참조 정보 수집에 시간이 더 걸립니다.
            이는 정확성을 위한 필수적인 과정입니다.
        """
        # SourceKit LSP는 초기화 후 인덱싱 시간이 필요하므로
        # 정확한 참조 정보를 제공하기 위해 지연 시간을 적용합니다.
        # CI 환경에서는 프로젝트 인덱싱과 크로스 파일 분석을 위해 추가 시간이 필요합니다.
        if not self._did_sleep_before_requesting_references:
            # 초기화 후 경과 시간에 기반한 최소 지연 시간 계산
            if self._initialization_timestamp:
                elapsed = time.time() - self._initialization_timestamp
                # 프로젝트 인덱싱을 위한 CI 지연 증가: CI 15초, 로컬 5초
                base_delay = 15 if os.getenv("CI") else 5
                remaining_delay = max(2, base_delay - elapsed)
            else:
                # 초기화 타임스탬프가 없는 경우의 폴백
                remaining_delay = 15 if os.getenv("CI") else 5

            self.logger.log(
                f"Sleeping {remaining_delay:.1f}s before requesting references for the first time (CI needs extra indexing time)",
                logging.INFO,
            )
            time.sleep(remaining_delay)
            self._did_sleep_before_requesting_references = True

        # CI 안정성을 위한 재시도 로직과 함께 참조 획득
        references = super().request_references(relative_file_path, line, column)

        # CI에서 참조를 찾지 못한 경우 추가 지연 후 한 번 재시도
        if os.getenv("CI") and not references:
            self.logger.log("No references found in CI - retrying after additional 5s delay", logging.INFO)
            time.sleep(5)
            references = super().request_references(relative_file_path, line, column)

        return references
