"""
SolidLSP Java 언어 서버 모듈 - Eclipse JDT Language Server 기반

이 모듈은 Java 프로그래밍 언어를 위한 LSP 서버를 구현합니다.
Eclipse JDT (Java Development Tools) Language Server를 기반으로 하여 Java 코드에 대한
완전한 언어 서비스를 제공합니다:

주요 기능:
- Java 코드 완성 (IntelliSense)
- 코드 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사 (컴파일러 수준)
- 코드 리팩토링 및 네비게이션
- Maven/Gradle 프로젝트 지원

아키텍처:
- EclipseJDTLS: Eclipse JDT 공식 LSP 서버를 래핑하는 클래스
- 다중 플랫폼 지원 (Linux, macOS, Windows)
- JRE (Java Runtime Environment) 의존성 관리
- Workspace 및 프로젝트 설정 관리

지원하는 Java 기능:
- 표준 Java 문법 및 라이브러리
- Spring Framework, Jakarta EE 등 프레임워크 지원
- Maven, Gradle 등 빌드 도구 연동
- JUnit 등 테스트 프레임워크 지원
- Lombok, IntelliCode 등 확장 기능 지원

특징:
- Eclipse IDE와 동일한 수준의 Java 지원
- 실시간 컴파일 및 오류 검사
- 고급 리팩토링 기능 (변수 추출, 메서드 이동 등)
- 타입 계층 구조 탐색
- 상세한 코드 분석 및 메트릭

중요 요구사항:
- Java 11 이상 필요
- Maven 또는 Gradle 프로젝트 권장
- Spring Boot 등 프레임워크 프로젝트에서 최적 성능
- 대규모 프로젝트의 경우 초기 인덱싱 시간 필요
"""

import dataclasses
import logging
import os
import pathlib
import shutil
import threading
import uuid
from pathlib import PurePath

from overrides import override

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.ls_utils import FileUtils, PlatformUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings


@dataclasses.dataclass
class RuntimeDependencyPaths:
    """
    Eclipse JDT Language Server의 런타임 의존성 경로들을 저장하는 데이터 클래스.

    Java 프로젝트를 위한 모든 필수 컴포넌트들의 경로를 관리하며,
    각 컴포넌트가 올바른 위치에 설치되어 있는지 추적합니다.

    Attributes:
        gradle_path: Gradle 래퍼 실행 파일 경로
        lombok_jar_path: Lombok JAR 파일 경로 (선택적 기능)
        jre_path: Java Runtime Environment 실행 파일 경로
        jre_home_path: JRE 홈 디렉토리 경로
        jdtls_launcher_jar_path: JDT Language Server 시작 JAR 파일 경로
        jdtls_readonly_config_path: 읽기 전용 설정 디렉토리 경로
        intellicode_jar_path: IntelliCode JAR 파일 경로 (AI 코드 완성)
        intellisense_members_path: IntelliSense 멤버 정보 경로
    """

    gradle_path: str
    lombok_jar_path: str
    jre_path: str
    jre_home_path: str
    jdtls_launcher_jar_path: str
    jdtls_readonly_config_path: str
    intellicode_jar_path: str
    intellisense_members_path: str


class EclipseJDTLS(SolidLanguageServer):
    """
    Java 언어를 위한 Eclipse JDT Language Server 구현 클래스.

    Eclipse IDE의 Java Development Tools (JDT)를 기반으로 하는 LSP 서버를 제공합니다.
    Java 프로젝트에서 Eclipse IDE와 동일한 수준의 언어 서비스를 사용할 수 있게 합니다.

    주요 특징:
    - Eclipse JDT 코어 엔진 기반의 정확한 Java 언어 분석
    - Java 11 이상의 모든 최신 기능 지원
    - Spring Boot, Jakarta EE 등 주요 프레임워크 지원
    - Maven, Gradle 등 빌드 도구와 완벽한 연동
    - 실시간 컴파일 및 상세한 오류 보고
    - 고급 리팩토링 기능 (Extract Variable, Move Method 등)

    초기화 파라미터:
    - config: 언어 서버의 동작을 제어하는 설정 객체
    - logger: 서버 활동을 로깅할 로거 인스턴스
    - repository_root_path: Java 프로젝트의 루트 디렉토리 경로
    - solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

    Java 프로젝트 요구사항:
    - Java 11 이상의 JDK 설치 필요
    - Maven (pom.xml) 또는 Gradle (build.gradle) 프로젝트 권장
    - Spring Boot 등 프레임워크 프로젝트에서 최적 성능
    - 대규모 프로젝트의 경우 초기 인덱싱 시간이 필요할 수 있음

    지원하는 파일 확장자:
    - .java (Java 소스 파일)
    - .class (Java 클래스 파일, 읽기 전용)
    - pom.xml (Maven 프로젝트)
    - build.gradle (Gradle 프로젝트)
    - application.properties/yml (Spring Boot 설정)

    Note:
        Eclipse JDT Language Server는 상업용 프로젝트에서도 무료로 사용 가능하며,
        Eclipse 공식 프로젝트의 일부입니다. 대규모 Java 프로젝트에서 특히 강력한 성능을 발휘합니다.
    """

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        EclipseJDTLS 인스턴스를 생성하고 언어 서버 설정을 초기화합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. Eclipse JDT Language Server를 위한 모든 런타임 의존성을
        설정하고 작업 공간을 준비합니다.

        초기화 과정:
        1. 런타임 의존성(Gradle, JRE, JDT LS 등) 설치 및 설정
        2. 고유한 작업 공간 디렉토리 생성 (UUID 기반)
        3. 공유 인덱스 캐시 디렉토리 생성
        4. JDT LS 설정 파일 복사
        5. 모든 필수 경로 존재 확인
        6. 환경 변수 설정 (JAVA_HOME 등)

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: Java 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Environment Variables:
            syntaxserver: Eclipse JDT LS의 구문 서버 모드를 비활성화
            JAVA_HOME: Java Runtime Environment 홈 디렉토리 경로

        Workspace Setup:
            - 각 인스턴스마다 고유한 UUID 기반 작업 공간 생성
            - 공유 인덱스 캐시를 통한 성능 최적화
            - 설정 파일을 읽기 전용에서 쓰기 가능한 위치로 복사

        Note:
            Eclipse JDT LS는 각 인스턴스마다 독립된 작업 공간을 사용하므로,
            여러 프로젝트를 동시에 작업할 때 충돌이 발생하지 않습니다.
            공유 인덱스를 통해 첫 번째 프로젝트 이후 빠른 시작이 가능합니다.
        """
        runtime_dependency_paths = self._setupRuntimeDependencies(logger, config, solidlsp_settings)
        self.runtime_dependency_paths = runtime_dependency_paths

        # ws_dir is the workspace directory for the EclipseJDTLS server
        ws_dir = str(
            PurePath(
                solidlsp_settings.ls_resources_dir,
                "EclipseJDTLS",
                "workspaces",
                uuid.uuid4().hex,
            )
        )

        # shared_cache_location is the global cache used by Eclipse JDTLS across all workspaces
        shared_cache_location = str(PurePath(solidlsp_settings.ls_resources_dir, "lsp", "EclipseJDTLS", "sharedIndex"))
        os.makedirs(shared_cache_location, exist_ok=True)
        os.makedirs(ws_dir, exist_ok=True)

        jre_path = self.runtime_dependency_paths.jre_path
        lombok_jar_path = self.runtime_dependency_paths.lombok_jar_path

        jdtls_launcher_jar = self.runtime_dependency_paths.jdtls_launcher_jar_path

        data_dir = str(PurePath(ws_dir, "data_dir"))
        jdtls_config_path = str(PurePath(ws_dir, "config_path"))

        jdtls_readonly_config_path = self.runtime_dependency_paths.jdtls_readonly_config_path

        if not os.path.exists(jdtls_config_path):
            shutil.copytree(jdtls_readonly_config_path, jdtls_config_path)

        for static_path in [
            jre_path,
            lombok_jar_path,
            jdtls_launcher_jar,
            jdtls_config_path,
            jdtls_readonly_config_path,
        ]:
            assert os.path.exists(static_path), static_path

        # TODO: Add "self.runtime_dependency_paths.jre_home_path"/bin to $PATH as well
        proc_env = {"syntaxserver": "false", "JAVA_HOME": self.runtime_dependency_paths.jre_home_path}
        proc_cwd = repository_root_path
        cmd = " ".join(
            [
                jre_path,
                "--add-modules=ALL-SYSTEM",
                "--add-opens",
                "java.base/java.util=ALL-UNNAMED",
                "--add-opens",
                "java.base/java.lang=ALL-UNNAMED",
                "--add-opens",
                "java.base/sun.nio.fs=ALL-UNNAMED",
                "-Declipse.application=org.eclipse.jdt.ls.core.id1",
                "-Dosgi.bundles.defaultStartLevel=4",
                "-Declipse.product=org.eclipse.jdt.ls.core.product",
                "-Djava.import.generatesMetadataFilesAtProjectRoot=false",
                "-Dfile.encoding=utf8",
                "-noverify",
                "-XX:+UseParallelGC",
                "-XX:GCTimeRatio=4",
                "-XX:AdaptiveSizePolicyWeight=90",
                "-Dsun.zip.disableMemoryMapping=true",
                "-Djava.lsp.joinOnCompletion=true",
                "-Xmx3G",
                "-Xms100m",
                "-Xlog:disable",
                "-Dlog.level=ALL",
                f'"-javaagent:{lombok_jar_path}"',
                f'"-Djdt.core.sharedIndexLocation={shared_cache_location}"',
                "-jar",
                f'"{jdtls_launcher_jar}"',
                "-configuration",
                f'"{jdtls_config_path}"',
                "-data",
                f'"{data_dir}"',
            ]
        )

        self.service_ready_event = threading.Event()
        self.intellicode_enable_command_available = threading.Event()
        self.initialize_searcher_command_available = threading.Event()

        super().__init__(
            config, logger, repository_root_path, ProcessLaunchInfo(cmd, proc_env, proc_cwd), "java", solidlsp_settings=solidlsp_settings
        )

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        # Ignore common Java build directories from different build tools:
        # - Maven: target
        # - Gradle: build, .gradle
        # - Eclipse: bin, .settings
        # - IntelliJ IDEA: out, .idea
        # - General: classes, dist, lib
        return super().is_ignored_dirname(dirname) or dirname in [
            "target",  # Maven
            "build",  # Gradle
            "bin",  # Eclipse
            "out",  # IntelliJ IDEA
            "classes",  # General
            "dist",  # General
            "lib",  # General
        ]

    @classmethod
    def _setupRuntimeDependencies(
        cls, logger: LanguageServerLogger, config: LanguageServerConfig, solidlsp_settings: SolidLSPSettings
    ) -> RuntimeDependencyPaths:
        """
        Eclipse JDT Language Server의 런타임 의존성을 설정하고 경로들을 반환합니다.

        이 메서드는 Java 개발을 위한 모든 필수 컴포넌트들을 설치하고 설정합니다.
        Red Hat의 vscode-java 확장을 기반으로 하며, 각 플랫폼별로 최적화된
        구성 요소들을 제공합니다.

        지원 플랫폼:
        - macOS (Intel, Apple Silicon)
        - Linux (x64, ARM64)
        - Windows (x64, ARM64)

        Args:
            logger: 설치 과정을 로깅할 로거
            config: 언어 서버 설정 (사용되지 않음)
            solidlsp_settings: SolidLSP 시스템 설정

        Returns:
            RuntimeDependencyPaths: 설치된 모든 컴포넌트들의 경로 정보

        설치되는 컴포넌트들:
        1. **Gradle 8.14.2**: Java 빌드 도구 (래퍼 형태)
        2. **Java Runtime Environment 21.0.7**: 최신 LTS Java 런타임
        3. **Lombok 1.18.36**: Java 코드 생성 라이브러리
        4. **JDT Language Server**: Eclipse JDT 코어 LSP 서버
        5. **IntelliCode**: AI 기반 코드 완성 (VSCode Java 확장 포함)

        플랫폼별 최적화:
        - macOS: Apple Silicon (ARM64)과 Intel (x64) 네이티브 지원
        - Linux: x64 및 ARM64 아키텍처 지원
        - Windows: x64 및 ARM64 아키텍처 지원

        Note:
            모든 컴포넌트는 Red Hat의 공식 vscode-java 확장에서 제공되며,
            상업용 프로젝트에서도 무료로 사용 가능합니다.
            JRE 21은 최신 장기 지원 버전으로, Java 11-23까지 호환됩니다.
        """
        platformId = PlatformUtils.get_platform_id()

        runtime_dependencies = {
            "gradle": {
                "platform-agnostic": {
                    "url": "https://services.gradle.org/distributions/gradle-8.14.2-bin.zip",
                    "archiveType": "zip",
                    "relative_extraction_path": ".",
                }
            },
            "vscode-java": {
                "darwin-arm64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-arm64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "relative_extraction_path": "vscode-java",
                },
                "osx-arm64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-arm64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "relative_extraction_path": "vscode-java",
                    "jre_home_path": "extension/jre/21.0.7-macosx-aarch64",
                    "jre_path": "extension/jre/21.0.7-macosx-aarch64/bin/java",
                    "lombok_jar_path": "extension/lombok/lombok-1.18.36.jar",
                    "jdtls_launcher_jar_path": "extension/server/plugins/org.eclipse.equinox.launcher_1.7.0.v20250424-1814.jar",
                    "jdtls_readonly_config_path": "extension/server/config_mac_arm",
                },
                "osx-x64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-x64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "relative_extraction_path": "vscode-java",
                    "jre_home_path": "extension/jre/21.0.7-macosx-x86_64",
                    "jre_path": "extension/jre/21.0.7-macosx-x86_64/bin/java",
                    "lombok_jar_path": "extension/lombok/lombok-1.18.36.jar",
                    "jdtls_launcher_jar_path": "extension/server/plugins/org.eclipse.equinox.launcher_1.7.0.v20250424-1814.jar",
                    "jdtls_readonly_config_path": "extension/server/config_mac",
                },
                "linux-arm64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-arm64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "relative_extraction_path": "vscode-java",
                },
                "linux-x64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-x64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "relative_extraction_path": "vscode-java",
                    "jre_home_path": "extension/jre/21.0.7-linux-x86_64",
                    "jre_path": "extension/jre/21.0.7-linux-x86_64/bin/java",
                    "lombok_jar_path": "extension/lombok/lombok-1.18.36.jar",
                    "jdtls_launcher_jar_path": "extension/server/plugins/org.eclipse.equinox.launcher_1.7.0.v20250424-1814.jar",
                    "jdtls_readonly_config_path": "extension/server/config_linux",
                },
                "win-x64": {
                    "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-win32-x64-1.42.0-561.vsix",
                    "archiveType": "zip",
                    "relative_extraction_path": "vscode-java",
                    "jre_home_path": "extension/jre/21.0.7-win32-x86_64",
                    "jre_path": "extension/jre/21.0.7-win32-x86_64/bin/java.exe",
                    "lombok_jar_path": "extension/lombok/lombok-1.18.36.jar",
                    "jdtls_launcher_jar_path": "extension/server/plugins/org.eclipse.equinox.launcher_1.7.0.v20250424-1814.jar",
                    "jdtls_readonly_config_path": "extension/server/config_win",
                },
            },
            "intellicode": {
                "platform-agnostic": {
                    "url": "https://VisualStudioExptTeam.gallery.vsassets.io/_apis/public/gallery/publisher/VisualStudioExptTeam/extension/vscodeintellicode/1.2.30/assetbyname/Microsoft.VisualStudio.Services.VSIXPackage",
                    "alternate_url": "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/VisualStudioExptTeam/vsextensions/vscodeintellicode/1.2.30/vspackage",
                    "archiveType": "zip",
                    "relative_extraction_path": "intellicode",
                    "intellicode_jar_path": "extension/dist/com.microsoft.jdtls.intellicode.core-0.7.0.jar",
                    "intellisense_members_path": "extension/dist/bundledModels/java_intellisense-members",
                }
            },
        }

        # assert platformId.value in [
        #     "linux-x64",
        #     "win-x64",
        # ], "Only linux-x64 platform is supported for in multilspy at the moment"

        gradle_path = str(
            PurePath(
                cls.ls_resources_dir(solidlsp_settings),
                "gradle-8.14.2",
            )
        )

        if not os.path.exists(gradle_path):
            FileUtils.download_and_extract_archive(
                logger,
                runtime_dependencies["gradle"]["platform-agnostic"]["url"],
                str(PurePath(gradle_path).parent),
                runtime_dependencies["gradle"]["platform-agnostic"]["archiveType"],
            )

        assert os.path.exists(gradle_path)

        dependency = runtime_dependencies["vscode-java"][platformId.value]
        vscode_java_path = str(PurePath(cls.ls_resources_dir(solidlsp_settings), dependency["relative_extraction_path"]))
        os.makedirs(vscode_java_path, exist_ok=True)
        jre_home_path = str(PurePath(vscode_java_path, dependency["jre_home_path"]))
        jre_path = str(PurePath(vscode_java_path, dependency["jre_path"]))
        lombok_jar_path = str(PurePath(vscode_java_path, dependency["lombok_jar_path"]))
        jdtls_launcher_jar_path = str(PurePath(vscode_java_path, dependency["jdtls_launcher_jar_path"]))
        jdtls_readonly_config_path = str(PurePath(vscode_java_path, dependency["jdtls_readonly_config_path"]))
        if not all(
            [
                os.path.exists(vscode_java_path),
                os.path.exists(jre_home_path),
                os.path.exists(jre_path),
                os.path.exists(lombok_jar_path),
                os.path.exists(jdtls_launcher_jar_path),
                os.path.exists(jdtls_readonly_config_path),
            ]
        ):
            FileUtils.download_and_extract_archive(logger, dependency["url"], vscode_java_path, dependency["archiveType"])

        os.chmod(jre_path, 0o755)

        assert os.path.exists(vscode_java_path)
        assert os.path.exists(jre_home_path)
        assert os.path.exists(jre_path)
        assert os.path.exists(lombok_jar_path)
        assert os.path.exists(jdtls_launcher_jar_path)
        assert os.path.exists(jdtls_readonly_config_path)

        dependency = runtime_dependencies["intellicode"]["platform-agnostic"]
        intellicode_directory_path = str(PurePath(cls.ls_resources_dir(solidlsp_settings), dependency["relative_extraction_path"]))
        os.makedirs(intellicode_directory_path, exist_ok=True)
        intellicode_jar_path = str(PurePath(intellicode_directory_path, dependency["intellicode_jar_path"]))
        intellisense_members_path = str(PurePath(intellicode_directory_path, dependency["intellisense_members_path"]))
        if not all(
            [
                os.path.exists(intellicode_directory_path),
                os.path.exists(intellicode_jar_path),
                os.path.exists(intellisense_members_path),
            ]
        ):
            FileUtils.download_and_extract_archive(logger, dependency["url"], intellicode_directory_path, dependency["archiveType"])

        assert os.path.exists(intellicode_directory_path)
        assert os.path.exists(intellicode_jar_path)
        assert os.path.exists(intellisense_members_path)

        return RuntimeDependencyPaths(
            gradle_path=gradle_path,
            lombok_jar_path=lombok_jar_path,
            jre_path=jre_path,
            jre_home_path=jre_home_path,
            jdtls_launcher_jar_path=jdtls_launcher_jar_path,
            jdtls_readonly_config_path=jdtls_readonly_config_path,
            intellicode_jar_path=intellicode_jar_path,
            intellisense_members_path=intellisense_members_path,
        )

    def _get_initialize_params(self, repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize parameters for the EclipseJDTLS server.
        """
        # Look into https://github.com/eclipse/eclipse.jdt.ls/blob/master/org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/preferences/Preferences.java to understand all the options available

        if not os.path.isabs(repository_absolute_path):
            repository_absolute_path = os.path.abspath(repository_absolute_path)
        repo_uri = pathlib.Path(repository_absolute_path).as_uri()

        initialize_params = {
            "locale": "en",
            "rootPath": repository_absolute_path,
            "rootUri": pathlib.Path(repository_absolute_path).as_uri(),
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
                    # TODO: we have an assert that completion provider is not included in the capabilities at server startup
                    #   Removing this will cause the assert to fail. Investigate why this is the case, simplify config
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
                    },
                    "definition": {"dynamicRegistration": True, "linkSupport": True},
                    "references": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                        "hierarchicalDocumentSymbolSupport": True,
                        "tagSupport": {"valueSet": [1]},
                        "labelSupport": True,
                    },
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
                    "typeHierarchy": {"dynamicRegistration": True},
                    "inlineValue": {"dynamicRegistration": True},
                    "diagnostic": {"dynamicRegistration": True, "relatedDocumentSupport": False},
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
                    "positionEncodings": ["utf-16"],
                },
                "notebookDocument": {"synchronization": {"dynamicRegistration": True, "executionSummarySupport": True}},
            },
            "initializationOptions": {
                "bundles": ["intellicode-core.jar"],
                "settings": {
                    "java": {
                        "home": None,
                        "jdt": {
                            "ls": {
                                "java": {"home": None},
                                "vmargs": "-XX:+UseParallelGC -XX:GCTimeRatio=4 -XX:AdaptiveSizePolicyWeight=90 -Dsun.zip.disableMemoryMapping=true -Xmx1G -Xms100m -Xlog:disable",
                                "lombokSupport": {"enabled": True},
                                "protobufSupport": {"enabled": True},
                                "androidSupport": {"enabled": True},
                            }
                        },
                        "errors": {"incompleteClasspath": {"severity": "error"}},
                        "configuration": {
                            "checkProjectSettingsExclusions": False,
                            "updateBuildConfiguration": "interactive",
                            "maven": {
                                "userSettings": None,
                                "globalSettings": None,
                                "notCoveredPluginExecutionSeverity": "warning",
                                "defaultMojoExecutionAction": "ignore",
                            },
                            "workspaceCacheLimit": 90,
                            "runtimes": [
                                {"name": "JavaSE-21", "path": "static/vscode-java/extension/jre/21.0.7-linux-x86_64", "default": True}
                            ],
                        },
                        "trace": {"server": "verbose"},
                        "import": {
                            "maven": {
                                "enabled": True,
                                "offline": {"enabled": False},
                                "disableTestClasspathFlag": False,
                            },
                            "gradle": {
                                "enabled": True,
                                "wrapper": {"enabled": False},
                                "version": None,
                                "home": "abs(static/gradle-7.3.3)",
                                "java": {"home": "abs(static/launch_jres/21.0.7-linux-x86_64)"},
                                "offline": {"enabled": False},
                                "arguments": None,
                                "jvmArguments": None,
                                "user": {"home": None},
                                "annotationProcessing": {"enabled": True},
                            },
                            "exclusions": [
                                "**/node_modules/**",
                                "**/.metadata/**",
                                "**/archetype-resources/**",
                                "**/META-INF/maven/**",
                            ],
                            "generatesMetadataFilesAtProjectRoot": False,
                        },
                        "maven": {"downloadSources": True, "updateSnapshots": True},
                        "eclipse": {"downloadSources": True},
                        "signatureHelp": {"enabled": True, "description": {"enabled": True}},
                        "implementationsCodeLens": {"enabled": True},
                        "format": {
                            "enabled": True,
                            "settings": {"url": None, "profile": None},
                            "comments": {"enabled": True},
                            "onType": {"enabled": True},
                            "insertSpaces": True,
                            "tabSize": 4,
                        },
                        "saveActions": {"organizeImports": False},
                        "project": {
                            "referencedLibraries": ["lib/**/*.jar"],
                            "importOnFirstTimeStartup": "automatic",
                            "importHint": True,
                            "resourceFilters": ["node_modules", "\\.git"],
                            "encoding": "ignore",
                            "exportJar": {"targetPath": "${workspaceFolder}/${workspaceFolderBasename}.jar"},
                        },
                        "contentProvider": {"preferred": None},
                        "autobuild": {"enabled": True},
                        "maxConcurrentBuilds": 1,
                        "selectionRange": {"enabled": True},
                        "showBuildStatusOnStart": {"enabled": "notification"},
                        "server": {"launchMode": "Standard"},
                        "sources": {"organizeImports": {"starThreshold": 99, "staticStarThreshold": 99}},
                        "imports": {"gradle": {"wrapper": {"checksums": []}}},
                        "templates": {"fileHeader": [], "typeComment": []},
                        "references": {"includeAccessors": True, "includeDecompiledSources": True},
                        "typeHierarchy": {"lazyLoad": False},
                        "settings": {"url": None},
                        "symbols": {"includeSourceMethodDeclarations": False},
                        "inlayHints": {"parameterNames": {"enabled": "literals", "exclusions": []}},
                        "codeAction": {"sortMembers": {"avoidVolatileChanges": True}},
                        "compile": {
                            "nullAnalysis": {
                                "nonnull": [
                                    "javax.annotation.Nonnull",
                                    "org.eclipse.jdt.annotation.NonNull",
                                    "org.springframework.lang.NonNull",
                                ],
                                "nullable": [
                                    "javax.annotation.Nullable",
                                    "org.eclipse.jdt.annotation.Nullable",
                                    "org.springframework.lang.Nullable",
                                ],
                                "mode": "automatic",
                            }
                        },
                        "sharedIndexes": {"enabled": "auto", "location": ""},
                        "silentNotification": False,
                        "dependency": {
                            "showMembers": False,
                            "syncWithFolderExplorer": True,
                            "autoRefresh": True,
                            "refreshDelay": 2000,
                            "packagePresentation": "flat",
                        },
                        "help": {"firstView": "auto", "showReleaseNotes": True, "collectErrorLog": False},
                        "test": {"defaultConfig": "", "config": {}},
                    }
                },
            },
            "trace": "verbose",
            "processId": os.getpid(),
            "workspaceFolders": [
                {
                    "uri": repo_uri,
                    "name": os.path.basename(repository_absolute_path),
                }
            ],
        }

        initialize_params["initializationOptions"]["workspaceFolders"] = [repo_uri]
        bundles = [self.runtime_dependency_paths.intellicode_jar_path]
        initialize_params["initializationOptions"]["bundles"] = bundles
        initialize_params["initializationOptions"]["settings"]["java"]["configuration"]["runtimes"] = [
            {"name": "JavaSE-21", "path": self.runtime_dependency_paths.jre_home_path, "default": True}
        ]

        for runtime in initialize_params["initializationOptions"]["settings"]["java"]["configuration"]["runtimes"]:
            assert "name" in runtime
            assert "path" in runtime
            assert os.path.exists(runtime["path"]), f"Runtime required for eclipse_jdtls at path {runtime['path']} does not exist"

        gradle_settings = initialize_params["initializationOptions"]["settings"]["java"]["import"]["gradle"]
        gradle_settings["home"] = self.runtime_dependency_paths.gradle_path
        gradle_settings["java"]["home"] = self.runtime_dependency_paths.jre_path
        return initialize_params

    def _start_server(self):
        """
        Starts the Eclipse JDTLS Language Server
        """

        def register_capability_handler(params):
            assert "registrations" in params
            for registration in params["registrations"]:
                if registration["method"] == "textDocument/completion":
                    assert registration["registerOptions"]["resolveProvider"] == True
                    assert registration["registerOptions"]["triggerCharacters"] == [
                        ".",
                        "@",
                        "#",
                        "*",
                        " ",
                    ]
                    self.completions_available.set()
                if registration["method"] == "workspace/executeCommand":
                    if "java.intellicode.enable" in registration["registerOptions"]["commands"]:
                        self.intellicode_enable_command_available.set()
            return

        def lang_status_handler(params):
            # TODO: Should we wait for
            # server -> client: {'jsonrpc': '2.0', 'method': 'language/status', 'params': {'type': 'ProjectStatus', 'message': 'OK'}}
            # Before proceeding?
            if params["type"] == "ServiceReady" and params["message"] == "ServiceReady":
                self.service_ready_event.set()

        def execute_client_command_handler(params):
            assert params["command"] == "_java.reloadBundles.command"
            assert params["arguments"] == []
            return []

        def window_log_message(msg):
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        def do_nothing(params):
            return

        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_notification("language/status", lang_status_handler)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("language/actionableNotification", do_nothing)

        self.logger.log("Starting EclipseJDTLS server process", logging.INFO)
        self.server.start()
        initialize_params = self._get_initialize_params(self.repository_root_path)

        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)
        assert init_response["capabilities"]["textDocumentSync"]["change"] == 2
        assert "completionProvider" not in init_response["capabilities"]
        assert "executeCommandProvider" not in init_response["capabilities"]

        self.server.notify.initialized({})

        self.server.notify.workspace_did_change_configuration({"settings": initialize_params["initializationOptions"]["settings"]})

        self.intellicode_enable_command_available.wait()

        java_intellisense_members_path = self.runtime_dependency_paths.intellisense_members_path
        assert os.path.exists(java_intellisense_members_path)
        intellicode_enable_result = self.server.send.execute_command(
            {
                "command": "java.intellicode.enable",
                "arguments": [True, java_intellisense_members_path],
            }
        )
        assert intellicode_enable_result

        # TODO: Add comments about why we wait here, and how this can be optimized
        self.service_ready_event.wait()
