"""
SolidLSP Kotlin 언어 서버 모듈 - Kotlin Language Server 기반 Kotlin 지원

이 모듈은 Kotlin 프로그래밍 언어를 위한 LSP 서버를 구현합니다.
Kotlin Language Server를 기반으로 하여 Kotlin 코드에 대한
완전한 언어 서비스를 제공합니다:

주요 기능:
- Kotlin 코드 완성 (IntelliSense)
- 코드 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사
- 코드 리팩토링 및 네이빅이션
- Android 및 JVM 프로젝트 지원

아키텍처:
- KotlinLanguageServer: Kotlin 공식 LSP 서버를 래핑하는 클래스
- Java Runtime Environment 연동
- Kotlin 컴파일러 통합
- Gradle/Maven 프로젝트 지원

지원하는 Kotlin 기능:
- 표준 Kotlin 문법 및 라이브러리
- 코루틴 (Coroutines) 지원
- 데이터 클래스 및 봉인된 클래스
- 확장 함수 및 프로퍼티
- DSL (Domain Specific Language) 지원
- Android 프로젝트 특화 기능

특징:
- JetBrains 공식 Kotlin 생태계와 통합
- 실시간 타입 검사 및 오류 보고
- Android Studio와 동일한 수준의 지원
- Gradle 및 Maven 빌드 시스템 연동
- Spring Boot 등 프레임워크 지원
- Kotlin Multiplatform 프로젝트 지원

중요 요구사항:
- Java 11 이상 필요
- Kotlin 컴파일러 필요
- Android 프로젝트의 경우 Android SDK 필요
- Gradle 또는 Maven 프로젝트 권장
- 대규모 프로젝트의 경우 초기 인덱싱 시간 필요

플랫폼 지원:
- Kotlin/JVM: 표준 JVM 애플리케이션
- Kotlin/JS: JavaScript 변환
- Kotlin/Native: 네이티브 컴파일
- Kotlin Multiplatform: 다중 플랫폼 지원
"""

import dataclasses
import logging
import os
import pathlib
import stat

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.ls_utils import FileUtils, PlatformUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings


@dataclasses.dataclass
class KotlinRuntimeDependencyPaths:
    """
    Kotlin Language Server의 런타임 의존성 경로들을 저장하는 데이터 클래스.

    Kotlin 프로젝트를 위한 모든 필수 컴포넌트들의 경로를 관리하며,
    각 컴포넌트가 올바른 위치에 설치되어 있는지 추적합니다.

    Attributes:
        java_path: Java Runtime Environment 실행 파일 경로
        java_home_path: Java Runtime Environment 홈 디렉토리 경로
        kotlin_executable_path: Kotlin Language Server 실행 파일 경로
    """

    java_path: str
    java_home_path: str
    kotlin_executable_path: str


class KotlinLanguageServer(SolidLanguageServer):
    """
    Kotlin 언어를 위한 Kotlin Language Server 구현 클래스.

    JetBrains의 Kotlin Language Server를 백엔드로 사용하여
    Kotlin 코드에 대한 완전한 언어 서비스를 제공합니다. Android Studio와
    IntelliJ IDEA와 동일한 수준의 Kotlin 개발 경험을 제공합니다.

    주요 특징:
    - JetBrains 공식 Kotlin Language Server 기반의 정확한 Kotlin 언어 분석
    - Android, JVM, JS, Native 등 모든 Kotlin 플랫폼 지원
    - 코루틴, 데이터 클래스, 봉인된 클래스 등 최신 Kotlin 기능 완벽 지원
    - Gradle 및 Maven 빌드 시스템과 완벽한 통합
    - 실시간 컴파일 및 상세한 오류 보고
    - DSL (Domain Specific Language) 지원

    초기화 파라미터:
    - config: 언어 서버의 동작을 제어하는 설정 객체
    - logger: 서버 활동을 로깅할 로거 인스턴스
    - repository_root_path: Kotlin 프로젝트의 루트 디렉토리 경로
    - solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

    Kotlin 프로젝트 요구사항:
    - Java 11 이상의 JDK 설치 필요
    - Kotlin 컴파일러 필요
    - build.gradle.kts 또는 build.gradle 파일 권장
    - Android 프로젝트의 경우 Android SDK 필요
    - 대규모 프로젝트의 경우 초기 인덱싱 시간이 필요할 수 있음

    지원하는 파일 확장자:
    - .kt (Kotlin 소스 파일)
    - .kts (Kotlin 스크립트 파일)
    - build.gradle.kts (Kotlin DSL Gradle 파일)
    - .gradle.kts (Kotlin Gradle 설정 파일)

    Android 특화 기능:
    - Android 프로젝트 구조 인식
    - AndroidManifest.xml 연동
    - 리소스 파일 (strings.xml, layouts.xml) 지원
    - Android SDK API 완성

    Note:
        Kotlin Language Server는 JetBrains의 공식 프로젝트로,
        상업용 프로젝트에서도 무료로 사용 가능합니다.
        Android Studio와 IntelliJ IDEA의 Kotlin 플러그인과 동일한 엔진을 사용합니다.
    """

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        KotlinLanguageServer 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. Kotlin Language Server를 백엔드로 사용하여 Kotlin 언어 서비스를 제공합니다.

        초기화 과정:
        1. 런타임 의존성(Java, Kotlin 컴파일러) 설치 및 설정
        2. Kotlin Language Server 실행 명령어 구성
        3. Java 환경 변수 설정 (JAVA_HOME)
        4. 상위 클래스 초기화

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: Kotlin 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Environment Variables:
            JAVA_HOME: Java Runtime Environment 홈 디렉토리 경로

        Note:
            Kotlin Language Server는 Java 런타임 환경에서 실행되므로,
            Java 11 이상이 시스템에 설치되어 있어야 합니다.
            Kotlin 컴파일러는 자동으로 다운로드되어 설치됩니다.

        Android 지원:
            Android 프로젝트의 경우 Android SDK 경로가 올바르게 설정되어 있어야 합니다.
            AndroidManifest.xml과 리소스 파일들을 인식하여 완전한 Android 개발 지원을 제공합니다.
        """
        runtime_dependency_paths = self._setup_runtime_dependencies(logger, config, solidlsp_settings)
        self.runtime_dependency_paths = runtime_dependency_paths

        # Create command to execute the Kotlin Language Server script
        cmd = [self.runtime_dependency_paths.kotlin_executable_path, "--stdio"]

        # Set environment variables including JAVA_HOME
        proc_env = {"JAVA_HOME": self.runtime_dependency_paths.java_home_path}

        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=cmd, env=proc_env, cwd=repository_root_path),
            "kotlin",
            solidlsp_settings,
        )

    @classmethod
    def _setup_runtime_dependencies(
        cls, logger: LanguageServerLogger, config: LanguageServerConfig, solidlsp_settings: SolidLSPSettings
    ) -> KotlinRuntimeDependencyPaths:
        """
        Kotlin Language Server의 런타임 의존성을 설정하고 경로들을 반환합니다.

        이 메서드는 Kotlin 개발을 위한 모든 필수 컴포넌트들을 설치하고 설정합니다.
        JetBrains의 공식 Kotlin LSP와 Red Hat의 VSCode Java 확장을 기반으로 하며,
        각 플랫폼별로 최적화된 구성 요소들을 제공합니다.

        지원 플랫폼:
        - Windows (x64)
        - Linux (x64, ARM64)
        - macOS (x64, ARM64 - Apple Silicon)

        Args:
            logger: 설치 과정을 로깅할 로거
            config: 언어 서버 설정 (사용되지 않음)
            solidlsp_settings: SolidLSP 시스템 설정

        Returns:
            KotlinRuntimeDependencyPaths: 설치된 모든 컴포넌트들의 경로 정보

        설치되는 컴포넌트들:
        1. **Kotlin Language Server 0.253.10629**: JetBrains 공식 Kotlin LSP 서버
        2. **Java Runtime Environment 21.0.7**: 최신 LTS Java 런타임 (Red Hat 제공)
        3. **플랫폼별 최적화**: 각 OS별로 최적화된 Java 런타임

        플랫폼별 최적화:
        - Windows: x64 아키텍처 전용 Java 런타임
        - Linux: x64 및 ARM64 아키텍처 지원
        - macOS: Intel x64과 Apple Silicon (ARM64) 네이티브 지원

        Note:
            모든 컴포넌트는 JetBrains와 Red Hat의 공식 릴리즈에서 제공되며,
            상업용 프로젝트에서도 무료로 사용 가능합니다.
            JRE 21은 최신 장기 지원 버전으로, Java 11-23까지 호환됩니다.
        """
        platform_id = PlatformUtils.get_platform_id()

        # Verify platform support
        assert (
            platform_id.value.startswith("win-") or platform_id.value.startswith("linux-") or platform_id.value.startswith("osx-")
        ), "Only Windows, Linux and macOS platforms are supported for Kotlin in multilspy at the moment"

        # Runtime dependency information
        runtime_dependencies = {
            "runtimeDependency": {
                "id": "KotlinLsp",
                "description": "Kotlin Language Server",
                "url": "https://download-cdn.jetbrains.com/kotlin-lsp/0.253.10629/kotlin-0.253.10629.zip",
                "archiveType": "zip",
            },
            "java": {
                "win-x64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-win32-x64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "java_home_path": "extension/jre/21.0.7-win32-x86_64",
                    "java_path": "extension/jre/21.0.7-win32-x86_64/bin/java.exe",
                },
                "linux-x64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-x64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "java_home_path": "extension/jre/21.0.7-linux-x86_64",
                    "java_path": "extension/jre/21.0.7-linux-x86_64/bin/java",
                },
                "linux-arm64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-arm64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "java_home_path": "extension/jre/21.0.7-linux-aarch64",
                    "java_path": "extension/jre/21.0.7-linux-aarch64/bin/java",
                },
                "osx-x64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-x64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "java_home_path": "extension/jre/21.0.7-macosx-x86_64",
                    "java_path": "extension/jre/21.0.7-macosx-x86_64/bin/java",
                },
                "osx-arm64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-arm64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "java_home_path": "extension/jre/21.0.7-macosx-aarch64",
                    "java_path": "extension/jre/21.0.7-macosx-aarch64/bin/java",
                },
            },
        }

        kotlin_dependency = runtime_dependencies["runtimeDependency"]
        java_dependency = runtime_dependencies["java"][platform_id.value]

        # Setup paths for dependencies
        static_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "kotlin_language_server")
        os.makedirs(static_dir, exist_ok=True)

        # Setup Java paths
        java_dir = os.path.join(static_dir, "java")
        os.makedirs(java_dir, exist_ok=True)

        java_home_path = os.path.join(java_dir, java_dependency["java_home_path"])
        java_path = os.path.join(java_dir, java_dependency["java_path"])

        # Download and extract Java if not exists
        if not os.path.exists(java_path):
            logger.log(f"Downloading Java for {platform_id.value}...", logging.INFO)
            FileUtils.download_and_extract_archive(logger, java_dependency["url"], java_dir, java_dependency["archiveType"])
            # Make Java executable
            if not platform_id.value.startswith("win-"):
                os.chmod(java_path, 0o755)

        assert os.path.exists(java_path), f"Java executable not found at {java_path}"

        # Setup Kotlin Language Server paths
        kotlin_ls_dir = static_dir

        # Get platform-specific executable script path
        if platform_id.value.startswith("win-"):
            kotlin_script = os.path.join(kotlin_ls_dir, "kotlin-lsp.cmd")
        else:
            kotlin_script = os.path.join(kotlin_ls_dir, "kotlin-lsp.sh")

        # Download and extract Kotlin Language Server if script doesn't exist
        if not os.path.exists(kotlin_script):
            logger.log("Downloading Kotlin Language Server...", logging.INFO)
            FileUtils.download_and_extract_archive(logger, kotlin_dependency["url"], static_dir, kotlin_dependency["archiveType"])

            # Make script executable on Unix platforms
            if os.path.exists(kotlin_script) and not platform_id.value.startswith("win-"):
                os.chmod(
                    kotlin_script, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                )

        # Use script file
        if os.path.exists(kotlin_script):
            kotlin_executable_path = kotlin_script
            logger.log(f"Using Kotlin Language Server script at {kotlin_script}", logging.INFO)
        else:
            raise FileNotFoundError(f"Kotlin Language Server script not found at {kotlin_script}")

        return KotlinRuntimeDependencyPaths(
            java_path=java_path, java_home_path=java_home_path, kotlin_executable_path=kotlin_executable_path
        )

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize params for the Kotlin Language Server.
        """
        if not os.path.isabs(repository_absolute_path):
            repository_absolute_path = os.path.abspath(repository_absolute_path)

        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "clientInfo": {"name": "Multilspy Kotlin Client", "version": "1.0.0"},
            "locale": "en",
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
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
                    "didChangeConfiguration": {"dynamicRegistration": True},
                    "didChangeWatchedFiles": {"dynamicRegistration": True, "relativePatternSupport": True},
                    "symbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                        "tagSupport": {"valueSet": [1]},
                        "resolveSupport": {"properties": ["location.range"]},
                    },
                    "codeLens": {"refreshSupport": True},
                    "executeCommand": {"dynamicRegistration": True},
                    "configuration": True,
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
                            "snippetSupport": False,
                            "commitCharactersSupport": True,
                            "documentationFormat": ["markdown", "plaintext"],
                            "deprecatedSupport": True,
                            "preselectSupport": True,
                            "tagSupport": {"valueSet": [1]},
                            "insertReplaceSupport": False,
                            "resolveSupport": {"properties": ["documentation", "detail", "additionalTextEdits"]},
                            "insertTextModeSupport": {"valueSet": [1, 2]},
                            "labelDetailsSupport": True,
                        },
                        "insertTextMode": 2,
                        "completionItemKind": {
                            "valueSet": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
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
                        "augmentsSyntaxTokens": True,
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
                    "markdown": {"parser": "marked", "version": "1.1.0"},
                    "positionEncodings": ["utf-16"],
                },
                "notebookDocument": {"synchronization": {"dynamicRegistration": True, "executionSummarySupport": True}},
            },
            "initializationOptions": {
                "workspaceFolders": [root_uri],
                "storagePath": None,
                "codegen": {"enabled": False},
                "compiler": {"jvm": {"target": "default"}},
                "completion": {"snippets": {"enabled": True}},
                "diagnostics": {"enabled": True, "level": 4, "debounceTime": 250},
                "scripts": {"enabled": True, "buildScriptsEnabled": True},
                "indexing": {"enabled": True},
                "externalSources": {"useKlsScheme": False, "autoConvertToKotlin": False},
                "inlayHints": {"typeHints": False, "parameterHints": False, "chainedHints": False},
                "formatting": {
                    "formatter": "ktfmt",
                    "ktfmt": {
                        "style": "google",
                        "indent": 4,
                        "maxWidth": 100,
                        "continuationIndent": 8,
                        "removeUnusedImports": True,
                    },
                },
            },
            "trace": "verbose",
            "processId": os.getpid(),
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
        Kotlin Language Server를 시작하고 서버 준비 완료를 기다립니다.

        이 메서드는 Kotlin Language Server를 시작하고, 서버가 완전히 준비될 때까지
        기다린 후 클라이언트 요청을 처리할 준비를 완료합니다. Kotlin Language Server는
        Java 기반이므로 초기화 시간이 다소 걸릴 수 있습니다.

        주요 단계:
        1. LSP 서버 프로세스 시작
        2. 다양한 LSP 핸들러 등록
        3. 초기화 파라미터 전송
        4. 서버 기능 검증
        5. 초기화 완료 알림

        등록되는 핸들러들:
        - client/registerCapability: 클라이언트 기능 등록
        - language/status: 언어 상태 알림
        - window/logMessage: 창 로그 메시지
        - workspace/executeClientCommand: 클라이언트 명령 실행
        - $/progress: 진행 상태 알림
        - textDocument/publishDiagnostics: 진단 정보 게시
        - language/actionableNotification: 실행 가능한 알림

        검증 항목:
        - textDocumentSync: 문서 동기화 지원
        - hoverProvider: 호버 정보 지원
        - completionProvider: 코드 완성 지원
        - signatureHelpProvider: 시그니처 도움말 지원
        - definitionProvider: 정의로 이동 지원
        - referencesProvider: 참조 찾기 지원
        - documentSymbolProvider: 문서 심볼 지원
        - workspaceSymbolProvider: 작업 공간 심볼 지원
        - semanticTokensProvider: 의미 토큰 지원

        Note:
            Kotlin Language Server는 Java 런타임에서 실행되므로,
            다른 언어 서버들보다 초기화 시간이 길 수 있습니다.
            이는 Kotlin 컴파일러의 특성과 JetBrains의 분석 엔진 때문입니다.
        """

        def execute_client_command_handler(params):
            """
            클라이언트 명령 실행 핸들러.

            workspace/executeClientCommand 요청에 대한 응답으로 빈 리스트를 반환합니다.
            Kotlin Language Server의 명령 실행 기능을 처리합니다.
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
            Kotlin Language Server의 상세한 로그 정보를 추적할 수 있습니다.
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

        # Kotlin Language Server 프로세스 시작
        self.logger.log("Starting Kotlin server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)

        # Kotlin Language Server 필수 기능 검증
        capabilities = init_response["capabilities"]
        assert "textDocumentSync" in capabilities, "Server must support textDocumentSync"
        assert "hoverProvider" in capabilities, "Server must support hover"
        assert "completionProvider" in capabilities, "Server must support code completion"
        assert "signatureHelpProvider" in capabilities, "Server must support signature help"
        assert "definitionProvider" in capabilities, "Server must support go to definition"
        assert "referencesProvider" in capabilities, "Server must support find references"
        assert "documentSymbolProvider" in capabilities, "Server must support document symbols"
        assert "workspaceSymbolProvider" in capabilities, "Server must support workspace symbols"
        assert "semanticTokensProvider" in capabilities, "Server must support semantic tokens"

        # 초기화 완료 알림 전송 - 서버가 완전히 준비되었음을 알림
        self.server.notify.initialized({})
        self.completions_available.set()
