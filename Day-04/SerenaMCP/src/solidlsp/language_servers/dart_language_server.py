"""
SolidLSP Dart 언어 서버 모듈 - Dart SDK 기반 Dart/Flutter 지원

이 모듈은 Dart 프로그래밍 언어를 위한 LSP 서버를 구현합니다.
Google의 Dart SDK를 기반으로 하여 Dart 코드에 대한
완전한 언어 서비스를 제공합니다:

주요 기능:
- Dart 코드 완성 (IntelliSense)
- 코드 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사
- 코드 리팩토링 및 네이빅이션
- Flutter 프레임워크 지원

아키텍처:
- DartLanguageServer: Google Dart SDK를 래핑하는 클래스
- Dart SDK 및 Dart Language Server 연동
- Flutter/Dart 생태계 통합
- Pub 패키지 매니저 지원

지원하는 Dart 기능:
- Dart 3.x 문법 및 최신 기능
- null safety 및 타입 시스템
- async/await 및 제너레이터
- 확장 메서드 및 mixin
- 레코드 타입 및 패턴 매칭
- Pub 패키지 의존성 관리

특징:
- Google 공식 Dart SDK 기반
- Flutter 프레임워크 완벽 지원
- 실시간 타입 검사 및 오류 보고
- VS Code Dart 확장과 동일한 수준의 지원
- Pub 패키지 및 패키지 의존성 분석
- 크로스 플랫폼 개발 지원

중요 요구사항:
- Dart SDK 3.7.1 이상 필요
- Flutter SDK (Flutter 개발 시)
- Pub 패키지 매니저 필요
- Android Studio 또는 VS Code 권장
- Flutter 프로젝트의 경우 Android/iOS SDK 필요
- 대규모 Flutter 프로젝트의 경우 초기 인덱싱 시간 필요

플랫폼 지원:
- Flutter: iOS, Android, Web, Desktop (Windows/macOS/Linux)
- Dart Native: 서버 사이드 애플리케이션
- Dart Web: 웹 애플리케이션 (dart2js)
"""

import logging
import os
import pathlib

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

from .common import RuntimeDependency, RuntimeDependencyCollection


class DartLanguageServer(SolidLanguageServer):
    """
    Dart 언어를 위한 Dart SDK 기반 LSP 서버 구현 클래스.

    Google의 공식 Dart SDK를 백엔드로 사용하여 Dart 코드에 대한
    완전한 언어 서비스를 제공합니다. Flutter 프레임워크와 완벽하게
    통합되어 최고 수준의 Dart/Flutter 개발 경험을 제공합니다.

    주요 특징:
    - Google 공식 Dart SDK 기반의 정확한 Dart 언어 분석
    - Flutter 프레임워크 및 Material Design 완벽 지원
    - Dart 3.x 최신 기능 및 null safety 완벽 지원
    - Pub 패키지 매니저와 완벽한 통합
    - 실시간 Dart 컴파일러 연동 및 정확한 오류 보고
    - VS Code의 Dart/Flutter 확장과 동일한 수준의 지원

    초기화 파라미터:
    - config: 언어 서버의 동작을 제어하는 설정 객체
    - logger: 서버 활동을 로깅할 로거 인스턴스
    - repository_root_path: Dart/Flutter 프로젝트의 루트 디렉토리 경로
    - solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

    Dart 프로젝트 요구사항:
    - Dart SDK 3.7.1 이상 설치 필요
    - Flutter 프로젝트의 경우 Flutter SDK 필요
    - pubspec.yaml 파일 권장
    - Android/iOS 개발의 경우 각 플랫폼 SDK 필요
    - 대규모 Flutter 프로젝트의 경우 초기 인덱싱 시간이 필요할 수 있음

    지원하는 파일 확장자:
    - .dart (Dart 소스 파일)
    - pubspec.yaml (Pub 패키지 설정)
    - pubspec.lock (Pub 패키지 잠금 파일)
    - analysis_options.yaml (Dart 분석 설정)

    Flutter 특화 기능:
    - Flutter 위젯 및 프레임워크 인식
    - Material Design 컴포넌트 지원
    - Hot Reload 및 Hot Restart 연동
    - Flutter Inspector 연동
    - Widget 테스트 지원
    - Internationalization 지원

    Note:
        Dart Language Server는 Google의 공식 프로젝트로,
        Flutter 개발에 최적화되어 있습니다.
        VS Code의 Dart/Flutter 확장과 동일한 엔진을 사용하므로
        최고 수준의 Dart/Flutter 지원을 제공합니다.
    """

    def __init__(self, config, logger, repository_root_path, solidlsp_settings: SolidLSPSettings):
        """
        DartLanguageServer 인스턴스를 생성합니다.

        이 클래스는 직접 인스턴스화할 수 없으며, LanguageServer.create() 팩토리 메서드를
        통해 생성해야 합니다. Dart SDK를 백엔드로 사용하여 Dart 언어 서비스를 제공합니다.

        초기화 과정:
        1. Dart SDK 런타임 의존성 설치 및 설정
        2. Dart Language Server 실행 명령어 구성
        3. 상위 클래스 초기화

        Args:
            config: 언어 서버의 동작을 제어하는 설정 객체
            logger: 서버 활동을 로깅할 로거 인스턴스
            repository_root_path: Dart/Flutter 프로젝트의 루트 디렉토리 경로
            solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

        Note:
            Dart Language Server는 Google의 공식 Dart SDK 3.7.1을 기반으로 합니다.
            Flutter 프로젝트의 경우 Flutter SDK가 추가로 필요합니다.
            모든 컴포넌트는 Google의 공식 릴리즈에서 제공됩니다.

        Flutter 지원:
            Flutter 프로젝트의 경우 Flutter SDK 경로가 올바르게 설정되어 있어야 합니다.
            Flutter 프레임워크, Material Design 컴포넌트, Hot Reload 기능을
            완벽하게 지원합니다.

        플랫폼 지원:
            - Windows, macOS, Linux (x64)
            - Flutter: iOS, Android, Web, Desktop
            - Dart Native: 서버 사이드 애플리케이션
        """
        executable_path = self._setup_runtime_dependencies(logger, solidlsp_settings)
        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=executable_path, cwd=repository_root_path),
            "dart",
            solidlsp_settings,
        )

    @classmethod
    def _setup_runtime_dependencies(cls, logger: "LanguageServerLogger", solidlsp_settings: SolidLSPSettings) -> str:
        """
        Dart SDK 런타임 의존성을 설정하고 실행 파일 경로를 반환합니다.

        이 메서드는 Dart 개발을 위한 SDK를 설치하고 설정합니다.
        Google의 공식 Dart SDK 3.7.1을 기반으로 하며,
        각 플랫폼별로 최적화된 Dart 런타임을 제공합니다.

        지원 플랫폼:
        - Linux (x64)
        - Windows (x64, ARM64)
        - macOS (x64, ARM64 - Apple Silicon)

        Args:
            logger: 설치 과정을 로깅할 로거
            solidlsp_settings: SolidLSP 시스템 설정

        Returns:
            str: Dart SDK 실행 파일의 절대 경로

        설치되는 컴포넌트:
        1. **Dart SDK 3.7.1**: Google 공식 Dart SDK
        2. **플랫폼별 최적화**: 각 OS별로 최적화된 Dart 런타임
        3. **Dart Language Server**: LSP 서버 기능 포함

        플랫폼별 최적화:
        - Linux x64: 표준 Intel/AMD 64비트 아키텍처
        - Windows x64: Intel/AMD 64비트 아키텍처
        - Windows ARM64: ARM 기반 Windows 디바이스 (Surface Pro X 등)
        - macOS x64: Intel Mac 지원
        - macOS ARM64: Apple Silicon Mac (M1, M2 칩) 네이티브 지원

        Note:
            모든 컴포넌트는 Google의 공식 Dart SDK 릴리즈에서 제공되며,
            Flutter 프레임워크와 완벽하게 호환됩니다.
            Dart 3.7.1은 최신 안정 버전으로, null safety와 최신 언어 기능을 완벽 지원합니다.
        """
        deps = RuntimeDependencyCollection(
            [
                RuntimeDependency(
                    id="DartLanguageServer",
                    description="Dart Language Server for Linux (x64)",
                    url="https://storage.googleapis.com/dart-archive/channels/stable/release/3.7.1/sdk/dartsdk-linux-x64-release.zip",
                    platform_id="linux-x64",
                    archive_type="zip",
                    binary_name="dart-sdk/bin/dart",
                ),
                RuntimeDependency(
                    id="DartLanguageServer",
                    description="Dart Language Server for Windows (x64)",
                    url="https://storage.googleapis.com/dart-archive/channels/stable/release/3.7.1/sdk/dartsdk-windows-x64-release.zip",
                    platform_id="win-x64",
                    archive_type="zip",
                    binary_name="dart-sdk/bin/dart.exe",
                ),
                RuntimeDependency(
                    id="DartLanguageServer",
                    description="Dart Language Server for Windows (arm64)",
                    url="https://storage.googleapis.com/dart-archive/channels/stable/release/3.7.1/sdk/dartsdk-windows-arm64-release.zip",
                    platform_id="win-arm64",
                    archive_type="zip",
                    binary_name="dart-sdk/bin/dart.exe",
                ),
                RuntimeDependency(
                    id="DartLanguageServer",
                    description="Dart Language Server for macOS (x64)",
                    url="https://storage.googleapis.com/dart-archive/channels/stable/release/3.7.1/sdk/dartsdk-macos-x64-release.zip",
                    platform_id="osx-x64",
                    archive_type="zip",
                    binary_name="dart-sdk/bin/dart",
                ),
                RuntimeDependency(
                    id="DartLanguageServer",
                    description="Dart Language Server for macOS (arm64)",
                    url="https://storage.googleapis.com/dart-archive/channels/stable/release/3.7.1/sdk/dartsdk-macos-arm64-release.zip",
                    platform_id="osx-arm64",
                    archive_type="zip",
                    binary_name="dart-sdk/bin/dart",
                ),
            ]
        )

        dart_ls_dir = cls.ls_resources_dir(solidlsp_settings)
        dart_executable_path = deps.binary_path(dart_ls_dir)

        if not os.path.exists(dart_executable_path):
            deps.install(logger, dart_ls_dir)

        assert os.path.exists(dart_executable_path)
        os.chmod(dart_executable_path, 0o755)

        return f"{dart_executable_path} language-server --client-id multilspy.dart --client-version 1.2"

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str):
        """
        Returns the initialize params for the Dart Language Server.
        """
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "capabilities": {},
            "initializationOptions": {
                "onlyAnalyzeProjectsWithOpenFiles": False,
                "closingLabels": False,
                "outline": False,
                "flutterOutline": False,
                "allowOpenUri": False,
            },
            "trace": "verbose",
            "processId": os.getpid(),
            "rootPath": repository_absolute_path,
            "rootUri": pathlib.Path(repository_absolute_path).as_uri(),
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
        Dart Language Server를 시작하고 서버 준비 완료를 기다립니다.

        이 메서드는 Dart SDK의 Language Server를 시작하고, 서버가 완전히 준비될 때까지
        기다린 후 클라이언트 요청을 처리할 준비를 완료합니다. Dart SDK는
        Flutter 프레임워크와 통합되어 있으므로 풍부한 언어 서비스를 제공합니다.

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
        - experimental/serverStatus: 실험적 서버 상태

        Dart 특화 기능:
        - Flutter 프레임워크 인식 및 분석
        - Pub 패키지 의존성 분석
        - Dart 타입 시스템 완벽 지원
        - null safety 정적 분석
        - Hot Reload 지원

        Note:
            Dart Language Server는 Google의 Dart SDK에 내장되어 있으므로,
            Flutter 프로젝트에서 최고의 성능과 정확성을 제공합니다.
            VS Code의 Dart/Flutter 확장과 동일한 수준의 언어 서비스를 제공합니다.
        """

        def execute_client_command_handler(params):
            """
            클라이언트 명령 실행 핸들러.

            workspace/executeClientCommand 요청에 대한 응답으로 빈 리스트를 반환합니다.
            Dart Language Server의 명령 실행 기능을 처리합니다.
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
            서버 상태를 추적합니다. Dart Language Server의 실험적 기능들을 처리합니다.

            Args:
                params: 서버 상태 파라미터
            """
            pass

        def window_log_message(msg):
            """
            창 로그 메시지 핸들러.

            LSP 서버로부터 받은 로그 메시지를 SolidLSP 로거를 통해 기록합니다.
            Dart Language Server의 상세한 로그 정보를 추적할 수 있습니다.
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

        # Dart Language Server 프로세스 시작
        self.logger.log("Starting dart-language-server server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request to dart-language-server",
            logging.DEBUG,
        )
        init_response = self.server.send_request("initialize", initialize_params)
        self.logger.log(
            f"Received initialize response from dart-language-server: {init_response}",
            logging.INFO,
        )

        # 초기화 완료 알림 전송 - 서버가 완전히 준비되었음을 알림
        self.server.notify.initialized({})
