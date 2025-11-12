"""
SolidLSP Rust 언어 서버 모듈 - Rust Analyzer 기반 Rust 언어 지원

이 모듈은 Rust 프로그래밍 언어를 위한 LSP 서버를 구현합니다.
Rust 공식 Rust Analyzer를 기반으로 하여 Rust 코드에 대한
완전한 언어 서비스를 제공합니다:

주요 기능:
- Rust 코드 완성 (IntelliSense)
- 코드 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사 (컴파일러 수준)
- 코드 리팩토링 및 네이빅이션
- Cargo 프로젝트 지원

아키텍처:
- RustAnalyzer: Rust 공식 LSP 서버를 래핑하는 클래스
- Rust 도구체인 통합 (rustup, cargo)
- RLS (Rust Language Server) 후속 프로젝트
- 고성능 증분 컴파일 지원

지원하는 Rust 기능:
- 표준 Rust 문법 및 라이브러리
- 소유권 시스템 (Ownership) 분석
- 제네릭 타입 및 트레잇 지원
- 매크로 확장 및 분석
- 비동기/어웨이트 지원
- Cargo.toml 프로젝트 관리

특징:
- Rust 공식 팀이 개발한 최고 수준의 Rust 지원
- 실시간 타입 검사 및 소유권 분석
- Cargo 프로젝트와 완벽한 통합
- RLS보다 월등히 향상된 성능
- 풍부한 리팩토링 기능
- 메모리 안전성 검사

중요 요구사항:
- Rust 1.70 이상 필요
- rustup 도구체인 매니저 필요
- Cargo 프로젝트 (Cargo.toml) 권장
- 컴파일 시간이 오래 걸리는 대규모 프로젝트 지원
- Rust Analyzer는 rustup을 통해 설치됨
"""

import logging
import os
import pathlib
import shutil
import subprocess
import threading

from overrides import override

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings


class RustAnalyzer(SolidLanguageServer):
    """
    Rust 언어를 위한 Rust Analyzer 기반 LSP 서버 구현 클래스.

    Rust 공식 팀이 개발한 차세대 Rust 언어 서버로, 기존 RLS의 한계를 넘어선
    고성능 Rust 개발 환경을 제공합니다. Cargo 및 rustup과 완벽하게 통합되어
    최고 수준의 Rust 개발 경험을 제공합니다.

    주요 특징:
    - Rust 공식 팀 개발로 최고 수준의 Rust 언어 지원
    - 기존 RLS 대비 월등히 향상된 성능과 정확성
    - Cargo 프로젝트 및 작업 공간 완벽 지원
    - 실시간 소유권 및 빌림 검사 (Borrow Checker)
    - 고급 리팩토링 기능 (Extract Function, Move 등)
    - 메모리 안전성 및 동시성 분석

    초기화 파라미터:
    - config: 언어 서버의 동작을 제어하는 설정 객체
    - logger: 서버 활동을 로깅할 로거 인스턴스
    - repository_root_path: Rust 프로젝트의 루트 디렉토리 경로
    - solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

    Rust 프로젝트 요구사항:
    - Rust 1.70 이상 설치 필요
    - rustup 도구체인 매니저 필요
    - Cargo.toml이 있는 프로젝트에서 최적 성능
    - 대규모 프로젝트의 경우 컴파일 시간이 오래 걸릴 수 있음

    지원하는 파일 확장자:
    - .rs (Rust 소스 파일)
    - .toml (Cargo.toml, Cargo.lock)
    - .lock (Cargo.lock 파일)

    Note:
        Rust Analyzer는 Rust 공식 프로젝트로, 상업용 프로젝트에서도
        무료로 사용 가능합니다. Rust 생태계의 표준 도구이며,
        지속적으로 업데이트되어 최신 Rust 기능을 지원합니다.
    """

    @staticmethod
    def _get_rustup_version():
        """
        설치된 rustup 버전을 조회합니다.

        시스템에 설치된 Rust 도구체인 매니저의 버전 정보를 반환합니다.
        rustup이 설치되지 않은 경우 None을 반환합니다.

        Returns:
            str or None: rustup 버전 문자열 (예: "rustup 1.27.1 (...)") 또는 None

        Note:
            rustup은 Rust 도구체인을 관리하는 표준 도구입니다.
            이 메서드는 Rust 개발 환경이 올바르게 설정되어 있는지 확인합니다.
        """
        try:
            result = subprocess.run(["rustup", "--version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            return None
        return None

    @staticmethod
    def _get_rust_analyzer_path():
        """
        rust-analyzer 실행 파일 경로를 조회합니다.

        rustup을 통하거나 시스템 PATH에서 rust-analyzer 경로를 찾습니다.
        Rust Analyzer는 rustup을 통해 설치되는 것이 표준입니다.

        Returns:
            str or None: rust-analyzer 실행 파일의 절대 경로 또는 None

        검색 우선순위:
        1. rustup which rust-analyzer (권장 방법)
        2. 시스템 PATH에서 rust-analyzer 검색 (폴백)

        Note:
            Rust Analyzer는 rustup을 통해 설치하는 것이 표준이며,
            이를 통해 최신 버전의 Rust Analyzer를 자동으로 업데이트할 수 있습니다.
        """
        # First try rustup - rustup을 통한 검색 우선
        try:
            result = subprocess.run(["rustup", "which", "rust-analyzer"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass

        # Fallback to system PATH - 시스템 PATH에서 검색 (폴백)
        return shutil.which("rust-analyzer")

    @staticmethod
    def _ensure_rust_analyzer_installed():
        """
        Rust Analyzer가 설치되어 있는지 확인하고, 필요시 rustup을 통해 설치합니다.

        시스템에 Rust Analyzer가 설치되어 있는지 확인하고, 없는 경우 rustup을 통해
        자동으로 설치합니다. Rust 생태계의 표준 설치 방법을 따릅니다.

        Returns:
            str: rust-analyzer 실행 파일의 절대 경로

        Raises:
            RuntimeError: rust-analyzer와 rustup 모두 설치되지 않은 경우

        설치 절차:
        1. 기존 rust-analyzer 경로 확인
        2. rustup 사용 가능 여부 확인
        3. rustup을 통한 rust-analyzer 컴포넌트 설치
        4. 설치 후 경로 재확인

        Note:
            rustup component add rust-analyzer 명령어를 사용하여
            공식 Rust 도구체인에서 Rust Analyzer를 설치합니다.
            이는 Rust 프로젝트의 표준 설치 방법입니다.
        """
        path = RustAnalyzer._get_rust_analyzer_path()
        if path:
            return path

        # Check if rustup is available - rustup 사용 가능 여부 확인
        if not RustAnalyzer._get_rustup_version():
            raise RuntimeError(
                "Neither rust-analyzer nor rustup is installed.\n"
                "Please install Rust via https://rustup.rs/ or install rust-analyzer separately."
            )

        # Try to install rust-analyzer component - rust-analyzer 컴포넌트 설치 시도
        result = subprocess.run(["rustup", "component", "add", "rust-analyzer"], check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to install rust-analyzer via rustup: {result.stderr}")

        # Try again after installation - 설치 후 경로 재확인
        path = RustAnalyzer._get_rust_analyzer_path()
        if not path:
            raise RuntimeError("rust-analyzer installation succeeded but binary not found in PATH")

        return path

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        RustAnalyzer 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. Rust Analyzer를 백엔드로 사용하여 Rust 언어 서비스를 제공합니다.

        초기화 과정:
        1. Rust Analyzer 자동 설치 확인 및 설치
        2. 상위 클래스 초기화
        3. 서버 준비 상태 이벤트 설정

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: Rust 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Note:
            Rust Analyzer는 rustup을 통해 자동으로 설치되며,
            Rust 1.70 이상이 시스템에 설치되어 있어야 합니다.
            Cargo.toml이 있는 프로젝트에서 최적의 성능을 제공합니다.

        Events:
            server_ready: 서버가 완전히 시작되어 준비된 상태를 알림
            service_ready_event: Rust Analyzer 서비스가 사용 가능한 상태를 알림
            initialize_searcher_command_available: 심볼 검색 명령이 사용 가능함을 알림
            resolve_main_method_available: 메인 함수 분석 기능이 사용 가능함을 알림
        """
        rustanalyzer_executable_path = self._ensure_rust_analyzer_installed()
        logger.log(f"Using rust-analyzer at: {rustanalyzer_executable_path}", logging.INFO)

        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=rustanalyzer_executable_path, cwd=repository_root_path),
            "rust",
            solidlsp_settings,
        )
        self.server_ready = threading.Event()
        self.service_ready_event = threading.Event()
        self.initialize_searcher_command_available = threading.Event()
        self.resolve_main_method_available = threading.Event()

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        """
        Rust 프로젝트에서 무시해야 할 디렉토리 이름을 판단합니다.

        기본 무시 디렉토리(예: .git, node_modules 등)에 더해 Rust 특화된
        디렉토리들을 추가로 무시합니다. Cargo의 빌드 출력 디렉토리를 제외합니다.

        Args:
            dirname: 검사할 디렉토리 이름

        Returns:
            bool: 무시해야 하면 True, 그렇지 않으면 False

        Rust 특화 무시 대상:
        - target: Cargo의 빌드 출력 디렉토리 (거대하고 분석 불필요)
        - 기본 무시 디렉토리들 (.git, node_modules 등)

        Note:
            Rust Analyzer는 Cargo 빌드 시스템과 통합되어 있으므로,
            target 디렉토리를 무시하면 분석 성능이 크게 향상됩니다.
            이는 Rust 프로젝트의 표준 관행입니다.
        """
        return super().is_ignored_dirname(dirname) or dirname in ["target"]

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Rust Analyzer Language Server를 위한 LSP 초기화 파라미터를 생성합니다.

        이 메서드는 Rust Analyzer에 특화된 초기화 파라미터를 구성합니다.
        VS Code와 동일한 수준의 Rust 개발 환경을 제공하도록 설정되어 있습니다.

        Args:
            repository_absolute_path: 초기화할 프로젝트의 절대 경로

        Returns:
            InitializeParams: LSP 초기화 요청에 사용할 파라미터 딕셔너리

        초기화 파라미터 구성 요소:
        - clientInfo: VS Code 호환 클라이언트 정보
        - rootPath/Uri: 프로젝트 루트 경로
        - capabilities: Rust Analyzer의 광범위한 기능 지원 목록
          - workspace: 작업 공간 관련 기능들 (편집, 심볼, 실행 등)
          - textDocument: 문서 관련 기능들 (완료, 정의, 진단 등)
        - workspaceFolders: 작업 공간 폴더 정보

        Rust Analyzer 특화 기능:
        - codeLens: 코드 렌즈 지원 (테스트 실행, 벤치마크 등)
        - semanticTokens: 의미 토큰 (구문 하이라이트)
        - inlineValue: 인라인 값 표시
        - inlayHint: 인레이 힌트 (타입 정보 표시)
        - diagnostics: 실시간 진단 및 오류 검사

        Note:
            Rust Analyzer는 매우 광범위한 LSP 기능을 지원하므로,
            초기화 시점에 모든 표준 LSP 기능이 활성화됩니다.
            이는 VS Code의 Rust 확장과 동일한 수준의 기능을 제공합니다.
        """
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "clientInfo": {"name": "Visual Studio Code - Insiders", "version": "1.82.0-insider"},
            "locale": "en",
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
                    "codeLens": {"refreshSupport": True},
                    "executeCommand": {"dynamicRegistration": True},
                    "didChangeConfiguration": {"dynamicRegistration": True},
                    "workspaceFolders": True,
                    "semanticTokens": {"refreshSupport": True},
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
                    "completion": {
                        "dynamicRegistration": True,
                        "contextSupport": True,
                        "completionItem": {
                            "snippetSupport": True,
                            "commitCharactersSupport": True,
                            "documentationFormat": ["markdown", "plaintext"],
                            "deprecatedSupport": True,
                            "preselectSupport": True,
                            "tagSupport": {"valueSet": [1]},
                            "insertReplaceSupport": True,
                            "resolveSupport": {"properties": ["documentation", "detail", "additionalTextEdits"]},
                            "insertTextModeSupport": {"valueSet": [1, 2]},
                            "labelDetailsSupport": True,
                        },
                        "insertTextMode": 2,
                        "completionItemKind": {
                            "valueSet": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
                        },
                        "completionList": {"itemDefaults": ["commitCharacters", "editRange", "insertTextFormat", "insertTextMode"]},
                    },
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
                    "codeAction": {
                        "dynamicRegistration": True,
                        "isPreferredSupport": True,
                        "disabledSupport": True,
                        "dataSupport": True,
                        "resolveSupport": {"properties": ["edit"]},
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
                        "honorsChangeAnnotations": False,
                    },
                    "codeLens": {"dynamicRegistration": True},
                    "formatting": {"dynamicRegistration": True},
                    "rangeFormatting": {"dynamicRegistration": True},
                    "onTypeFormatting": {"dynamicRegistration": True},
                    "rename": {
                        "dynamicRegistration": True,
                        "prepareSupport": True,
                        "prepareSupportDefaultBehavior": 1,
                        "honorsChangeAnnotations": True,
                    },
                    "documentLink": {"dynamicRegistration": True, "tooltipSupport": True},
                    "typeDefinition": {"dynamicRegistration": True, "linkSupport": True},
                    "implementation": {"dynamicRegistration": True, "linkSupport": True},
                    "colorProvider": {"dynamicRegistration": True},
                    "foldingRange": {
                        "dynamicRegistration": True,
                        "rangeLimit": 5000,
                        "lineFoldingOnly": True,
                        "foldingRangeKind": {"valueSet": ["comment", "imports", "region"]},
                        "foldingRange": {"collapsedText": False},
                    },
                    "declaration": {"dynamicRegistration": True, "linkSupport": True},
                    "selectionRange": {"dynamicRegistration": True},
                    "callHierarchy": {"dynamicRegistration": True},
                    "semanticTokens": {
                        "dynamicRegistration": True,
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
                        "formats": ["relative"],
                        "requests": {"range": True, "full": {"delta": True}},
                        "multilineTokenSupport": False,
                        "overlappingTokenSupport": False,
                        "serverCancelSupport": True,
                        "augmentsSyntaxTokens": False,
                    },
                    "linkedEditingRange": {"dynamicRegistration": True},
                    "typeHierarchy": {"dynamicRegistration": True},
                    "inlineValue": {"dynamicRegistration": True},
                    "inlayHint": {
                        "dynamicRegistration": True,
                        "resolveSupport": {"properties": ["tooltip", "textEdits", "label.tooltip", "label.location", "label.command"]},
                    },
                    "diagnostic": {"dynamicRegistration": True, "relatedDocumentSupport": False},
                },
                "window": {
                    "showMessage": {"messageActionItem": {"additionalPropertiesSupport": True}},
                    "showDocument": {"support": True},
                    "workDoneProgress": True,
                },
                "general": {
                    "staleRequestSupport": {
                        "cancel": True,
                        "retryOnContentModified": [
                            "textDocument/semanticTokens/full",
                            "textDocument/semanticTokens/range",
                            "textDocument/semanticTokens/full/delta",
                        ],
                    },
                    "regularExpressions": {"engine": "ECMAScript", "version": "ES2020"},
                    "markdown": {
                        "parser": "marked",
                        "version": "1.1.0",
                        "allowedTags": [
                            "ul",
                            "li",
                            "p",
                            "code",
                            "blockquote",
                            "ol",
                            "h1",
                            "h2",
                            "h3",
                            "h4",
                            "h5",
                            "h6",
                            "hr",
                            "em",
                            "pre",
                            "table",
                            "thead",
                            "tbody",
                            "tr",
                            "th",
                            "td",
                            "div",
                            "del",
                            "a",
                            "strong",
                            "br",
                            "img",
                            "span",
                        ],
                    },
                    "positionEncodings": ["utf-16"],
                },
                "notebookDocument": {"synchronization": {"dynamicRegistration": True, "executionSummarySupport": True}},
                "experimental": {
                    "snippetTextEdit": True,
                    "codeActionGroup": True,
                    "hoverActions": True,
                    "serverStatusNotification": True,
                    "colorDiagnosticOutput": True,
                    "openServerLogs": True,
                    "localDocs": True,
                    "commands": {
                        "commands": [
                            "rust-analyzer.runSingle",
                            "rust-analyzer.debugSingle",
                            "rust-analyzer.showReferences",
                            "rust-analyzer.gotoLocation",
                            "editor.action.triggerParameterHints",
                        ]
                    },
                },
            },
            "initializationOptions": {
                "cargoRunner": None,
                "runnables": {"extraEnv": None, "problemMatcher": ["$rustc"], "command": None, "extraArgs": []},
                "statusBar": {"clickAction": "openLogs"},
                "server": {"path": None, "extraEnv": None},
                "trace": {"server": "verbose", "extension": False},
                "debug": {
                    "engine": "auto",
                    "sourceFileMap": {"/rustc/<id>": "${env:USERPROFILE}/.rustup/toolchains/<toolchain-id>/lib/rustlib/src/rust"},
                    "openDebugPane": False,
                    "engineSettings": {},
                },
                "restartServerOnConfigChange": False,
                "typing": {"continueCommentsOnNewline": True, "autoClosingAngleBrackets": {"enable": False}},
                "diagnostics": {
                    "previewRustcOutput": False,
                    "useRustcErrorCode": False,
                    "disabled": [],
                    "enable": True,
                    "experimental": {"enable": False},
                    "remapPrefix": {},
                    "warningsAsHint": [],
                    "warningsAsInfo": [],
                },
                "discoverProjectRunner": None,
                "showUnlinkedFileNotification": True,
                "showDependenciesExplorer": True,
                "assist": {"emitMustUse": False, "expressionFillDefault": "todo"},
                "cachePriming": {"enable": True, "numThreads": 0},
                "cargo": {
                    "autoreload": True,
                    "buildScripts": {
                        "enable": True,
                        "invocationLocation": "workspace",
                        "invocationStrategy": "per_workspace",
                        "overrideCommand": None,
                        "useRustcWrapper": True,
                    },
                    "cfgs": {},
                    "extraArgs": [],
                    "extraEnv": {},
                    "features": [],
                    "noDefaultFeatures": False,
                    "sysroot": "discover",
                    "sysrootSrc": None,
                    "target": None,
                    "unsetTest": ["core"],
                },
                "checkOnSave": True,
                "check": {
                    "allTargets": True,
                    "command": "check",
                    "extraArgs": [],
                    "extraEnv": {},
                    "features": None,
                    "ignore": [],
                    "invocationLocation": "workspace",
                    "invocationStrategy": "per_workspace",
                    "noDefaultFeatures": None,
                    "overrideCommand": None,
                    "targets": None,
                },
                "completion": {
                    "autoimport": {"enable": True},
                    "autoself": {"enable": True},
                    "callable": {"snippets": "fill_arguments"},
                    "fullFunctionSignatures": {"enable": False},
                    "limit": None,
                    "postfix": {"enable": True},
                    "privateEditable": {"enable": False},
                    "snippets": {
                        "custom": {
                            "Arc::new": {
                                "postfix": "arc",
                                "body": "Arc::new(${receiver})",
                                "requires": "std::sync::Arc",
                                "description": "Put the expression into an `Arc`",
                                "scope": "expr",
                            },
                            "Rc::new": {
                                "postfix": "rc",
                                "body": "Rc::new(${receiver})",
                                "requires": "std::rc::Rc",
                                "description": "Put the expression into an `Rc`",
                                "scope": "expr",
                            },
                            "Box::pin": {
                                "postfix": "pinbox",
                                "body": "Box::pin(${receiver})",
                                "requires": "std::boxed::Box",
                                "description": "Put the expression into a pinned `Box`",
                                "scope": "expr",
                            },
                            "Ok": {
                                "postfix": "ok",
                                "body": "Ok(${receiver})",
                                "description": "Wrap the expression in a `Result::Ok`",
                                "scope": "expr",
                            },
                            "Err": {
                                "postfix": "err",
                                "body": "Err(${receiver})",
                                "description": "Wrap the expression in a `Result::Err`",
                                "scope": "expr",
                            },
                            "Some": {
                                "postfix": "some",
                                "body": "Some(${receiver})",
                                "description": "Wrap the expression in an `Option::Some`",
                                "scope": "expr",
                            },
                        }
                    },
                },
                "files": {"excludeDirs": [], "watcher": "client"},
                "highlightRelated": {
                    "breakPoints": {"enable": True},
                    "closureCaptures": {"enable": True},
                    "exitPoints": {"enable": True},
                    "references": {"enable": True},
                    "yieldPoints": {"enable": True},
                },
                "hover": {
                    "actions": {
                        "debug": {"enable": True},
                        "enable": True,
                        "gotoTypeDef": {"enable": True},
                        "implementations": {"enable": True},
                        "references": {"enable": False},
                        "run": {"enable": True},
                    },
                    "documentation": {"enable": True, "keywords": {"enable": True}},
                    "links": {"enable": True},
                    "memoryLayout": {"alignment": "hexadecimal", "enable": True, "niches": False, "offset": "hexadecimal", "size": "both"},
                },
                "imports": {
                    "granularity": {"enforce": False, "group": "crate"},
                    "group": {"enable": True},
                    "merge": {"glob": True},
                    "preferNoStd": False,
                    "preferPrelude": False,
                    "prefix": "plain",
                },
                "inlayHints": {
                    "bindingModeHints": {"enable": False},
                    "chainingHints": {"enable": True},
                    "closingBraceHints": {"enable": True, "minLines": 25},
                    "closureCaptureHints": {"enable": False},
                    "closureReturnTypeHints": {"enable": "never"},
                    "closureStyle": "impl_fn",
                    "discriminantHints": {"enable": "never"},
                    "expressionAdjustmentHints": {"enable": "never", "hideOutsideUnsafe": False, "mode": "prefix"},
                    "lifetimeElisionHints": {"enable": "never", "useParameterNames": False},
                    "maxLength": 25,
                    "parameterHints": {"enable": True},
                    "reborrowHints": {"enable": "never"},
                    "renderColons": True,
                    "typeHints": {"enable": True, "hideClosureInitialization": False, "hideNamedConstructor": False},
                },
                "interpret": {"tests": False},
                "joinLines": {"joinAssignments": True, "joinElseIf": True, "removeTrailingComma": True, "unwrapTrivialBlock": True},
                "lens": {
                    "debug": {"enable": True},
                    "enable": True,
                    "forceCustomCommands": True,
                    "implementations": {"enable": True},
                    "location": "above_name",
                    "references": {
                        "adt": {"enable": False},
                        "enumVariant": {"enable": False},
                        "method": {"enable": False},
                        "trait": {"enable": False},
                    },
                    "run": {"enable": True},
                },
                "linkedProjects": [],
                "lru": {"capacity": None, "query": {"capacities": {}}},
                "notifications": {"cargoTomlNotFound": True},
                "numThreads": None,
                "procMacro": {"attributes": {"enable": True}, "enable": True, "ignored": {}, "server": None},
                "references": {"excludeImports": False},
                "rust": {"analyzerTargetDir": None},
                "rustc": {"source": None},
                "rustfmt": {"extraArgs": [], "overrideCommand": None, "rangeFormatting": {"enable": False}},
                "semanticHighlighting": {
                    "doc": {"comment": {"inject": {"enable": True}}},
                    "nonStandardTokens": True,
                    "operator": {"enable": True, "specialization": {"enable": False}},
                    "punctuation": {"enable": False, "separate": {"macro": {"bang": False}}, "specialization": {"enable": False}},
                    "strings": {"enable": True},
                },
                "signatureInfo": {"detail": "full", "documentation": {"enable": True}},
                "workspace": {"symbol": {"search": {"kind": "only_types", "limit": 128, "scope": "workspace"}}},
            },
            "trace": "verbose",
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
        Rust Analyzer Language Server를 시작하고 서버 준비 완료를 기다립니다.

        이 메서드는 Rust Analyzer를 시작하고, 서버가 완전히 준비될 때까지
        기다린 후 클라이언트 요청을 처리할 준비를 완료합니다. Rust Analyzer는
        소유권 시스템과 빌림 검사로 인해 초기화 시간이 다소 걸릴 수 있습니다.

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

        Rust Analyzer 특화 기능:
        - ServiceReady 상태 감지로 초기 인덱싱 완료 확인
        - workspace/executeCommand 등록으로 심볼 검색 기능 활성화
        - 메인 함수 분석 기능 활성화
        - 소유권 및 빌림 검사 (Borrow Checker) 지원
        - Cargo 프로젝트 빌드 연동

        Note:
            Rust Analyzer는 Rust의 소유권 시스템으로 인해 다른 언어 서버들보다
            초기화 시간이 길 수 있습니다. 이는 Rust의 메모리 안전성 검사를 위해
            필요한 과정입니다.
        """

        def register_capability_handler(params):
            """
            클라이언트 기능 등록 핸들러.

            Rust Analyzer가 workspace/executeCommand 기능을 등록하면
            심볼 검색과 메인 함수 분석 기능을 사용할 수 있게 됩니다.
            Rust에서는 이러한 기능들이 특히 중요합니다.
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

            Rust Analyzer의 language/status 알림을 처리하여
            ServiceReady 상태가 되면 서비스 준비 완료를 알립니다.
            이는 Rust 프로젝트의 인덱싱이 완료되었음을 의미합니다.
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
            Rust Analyzer의 명령 실행 기능을 처리합니다.
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
            Rust Analyzer의 상세한 로그 정보를 추적할 수 있습니다.
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

        # Rust Analyzer 서버 프로세스 시작
        self.logger.log("Starting RustAnalyzer server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)

        # Rust Analyzer 특화 기능 검증 - 필수 기능들이 올바르게 설정되었는지 확인
        assert init_response["capabilities"]["textDocumentSync"]["change"] == 2
        assert "completionProvider" in init_response["capabilities"]
        assert init_response["capabilities"]["completionProvider"] == {
            "resolveProvider": True,
            "triggerCharacters": [":", ".", "'", "("],
            "completionItem": {"labelDetailsSupport": True},
        }

        # 초기화 완료 알림 전송 - 서버가 완전히 준비되었음을 알림
        self.server.notify.initialized({})
        self.completions_available.set()

        # Rust Analyzer 준비 완료 대기
        # Rust Analyzer는 소유권 분석으로 인해 다른 서버들보다 시간이 걸릴 수 있음
        self.server_ready.wait()
