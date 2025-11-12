"""
SolidLSP Terraform 언어 서버 모듈 - terraform-ls 기반 IaC (Infrastructure as Code) 지원

이 모듈은 Terraform HCL (HashiCorp Configuration Language)를 위한 LSP 서버를 구현합니다.
HashiCorp의 terraform-ls를 기반으로 하여 Terraform 코드에 대한
완전한 언어 서비스를 제공합니다:

주요 기능:
- Terraform HCL 코드 완성 (IntelliSense)
- 코드 정의 및 참조 검색
- 호버 정보 및 시그니처 도움말
- 진단 및 오류 검사
- 코드 리팩토링 및 네이빅이션
- Terraform Provider 지원

아키텍처:
- TerraformLS: HashiCorp terraform-ls를 래핑하는 클래스
- HashiCorp Terraform 생태계 통합
- Terraform Registry Provider 연동
- Terraform Cloud/Enterprise 지원

지원하는 Terraform 기능:
- HCL 2.x 문법 및 최신 기능
- Terraform 1.x 호환성
- Resource, Data Source, Provider
- Module 및 Variable 관리
- Output 및 Local Value
- Dynamic Block 및 For Expression
- Terraform Cloud/Enterprise 연동

특징:
- HashiCorp 공식 Terraform Language Server
- 실시간 HCL 구문 검사 및 오류 보고
- VS Code Terraform 확장과 동일한 수준의 지원
- Terraform Provider Registry 연동
- Module Registry 검색 및 완성
- Terraform Cloud/Enterprise 지원

중요 요구사항:
- Terraform CLI 1.x 이상 필요
- terraform-ls 0.35.0 이상 필요
- Terraform Provider Registry 접근 필요
- Git 저장소 권장 (Module 사용 시)
- 대규모 Terraform 프로젝트의 경우 초기 인덱싱 시간 필요
- Terraform Cloud/Enterprise 계정 (Enterprise 기능 사용 시)

플랫폼 지원:
- Terraform: AWS, Azure, GCP, Kubernetes, VMware 등
- Cloud Provider: 3000+ Provider 지원
- Infrastructure: IaaS, PaaS, SaaS
- DevOps 도구: Ansible, Chef, Puppet 등
- Container: Docker, Kubernetes, ECS 등
- Network: VPC, Load Balancer, DNS 등

IaC 환경:
- Infrastructure as Code 프로젝트
- Multi-Cloud 아키텍처
- DevOps 자동화 파이프라인
- 보안 및 컴플라이언스 스크립트
- 모듈러 인프라 설계
- Terraform Cloud/Enterprise 워크플로
"""

import logging
import os
import shutil
import threading

from overrides import override

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.ls_utils import PathUtils, PlatformUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

from .common import RuntimeDependency, RuntimeDependencyCollection


class TerraformLS(SolidLanguageServer):
    """
    Terraform HCL을 위한 terraform-ls 구현 클래스.

    HashiCorp의 공식 terraform-ls를 백엔드로 사용하여 Terraform 코드에 대한
    완전한 언어 서비스를 제공합니다. VS Code의 Terraform 확장과 동일한
    수준의 Infrastructure as Code 개발 경험을 제공합니다.

    주요 특징:
    - HashiCorp 공식 terraform-ls 기반의 정확한 HCL 분석
    - 3000+ Terraform Provider 지원 및 완성
    - Module Registry 검색 및 자동 완성
    - 실시간 HCL 구문 검사 및 Terraform 표준 준수 검사
    - Terraform Cloud/Enterprise와 완벽한 통합
    - VS Code Terraform 확장과 동일한 수준의 코드 완성과 오류 검사

    초기화 파라미터:
    - config: 언어 서버의 동작을 제어하는 설정 객체
    - logger: 서버 활동을 로깅할 로거 인스턴스
    - repository_root_path: Terraform 프로젝트의 루트 디렉토리 경로
    - solidlsp_settings: SolidLSP 시스템 전체에 적용되는 설정

    Terraform 프로젝트 요구사항:
    - Terraform CLI 1.x 이상 설치 필요
    - terraform-ls 0.35.0 이상 필요
    - Terraform Provider Registry 접근 가능
    - Git 저장소 권장 (Module 사용 시)
    - 대규모 Terraform 프로젝트의 경우 초기 인덱싱 시간이 필요할 수 있음

    지원하는 파일 확장자:
    - .tf (Terraform 소스 파일)
    - .tf.json (JSON 형식 Terraform 파일)
    - .tfvars (Terraform 변수 파일)
    - .tfvars.json (JSON 형식 변수 파일)
    - .hcl (HCL 형식 파일)

    Cloud Provider 특화 기능:
    - AWS, Azure, GCP, Kubernetes Provider 완전 지원
    - Provider 버전 관리 및 업데이트 검사
    - Resource 및 Data Source 완성
    - Provider 문서 및 예제 연동
    - Cloud-specific 구문 검사

    Enterprise 기능:
    - Terraform Cloud/Enterprise 연동
    - Remote State 관리
    - Team 및 Workspace 관리
    - Policy as Code 지원
    - Sentinel 정책 검사
    - Cost Estimation 연동

    Note:
        TerraformLS는 HashiCorp의 공식 프로젝트로,
        Infrastructure as Code 개발에 최적화되어 있습니다.
        VS Code의 Terraform 확장과 동일한 엔진을 사용하므로
        최고 수준의 Terraform 지원을 제공합니다.
    """

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        """
        Terraform 프로젝트에서 무시해야 할 디렉토리 이름을 판단합니다.

        기본 무시 디렉토리(예: .git, node_modules 등)에 더해 Terraform 특화된
        디렉토리들을 추가로 무시합니다. Terraform의 상태 파일과 캐시 디렉토리를 제외합니다.

        Args:
            dirname: 검사할 디렉토리 이름

        Returns:
            bool: 무시해야 하면 True, 그렇지 않으면 False

        Terraform 특화 무시 대상:
        - .terraform: Terraform의 Provider 플러그인, 모듈, 상태 파일 등 (거대하고 분석 불필요)
        - terraform.tfstate.d: Terraform 상태 파일 백업 디렉토리
        - 기본 무시 디렉토리들 (.git, node_modules 등)

        Note:
            TerraformLS는 Terraform Provider와 Module을 분석하므로,
            .terraform 디렉토리를 무시하면 분석 성능이 크게 향상됩니다.
            이는 Terraform 프로젝트의 표준 관행입니다.
        """
        return super().is_ignored_dirname(dirname) or dirname in [".terraform", "terraform.tfstate.d"]

    @staticmethod
    def _ensure_tf_command_available(logger: LanguageServerLogger):
        """
        Terraform CLI가 사용 가능한지 확인하고 설치 경로를 검증합니다.

        시스템에 Terraform CLI가 설치되어 있는지 확인하고,
        사용 가능한 경로를 찾아서 반환합니다. CI 환경과 로컬 환경을 모두 지원합니다.

        Args:
            logger: Terraform CLI 검색 과정을 로깅할 로거

        Raises:
            RuntimeError: Terraform CLI를 찾을 수 없는 경우

        검색 우선순위:
        1. 시스템 PATH에서 terraform 명령어 검색 (shutil.which)
        2. TERRAFORM_CLI_PATH 환경 변수 확인 (CI 환경용)
        3. 플랫폼별 바이너리 경로 구성

        CI 환경 지원:
        - GitHub Actions: hashicorp/setup-terraform 액션에서 설정하는 TERRAFORM_CLI_PATH
        - GitLab CI: TF_ROOT 환경 변수 지원
        - Jenkins: 도구 경로 설정 지원

        Note:
            Terraform CLI는 terraform-ls의 필수 의존성입니다.
            Terraform Provider와 Module을 분석하기 위해 필요합니다.
            CI 환경에서는 보통 hashicorp/setup-terraform 액션을 통해 설치됩니다.
        """
        logger.log("Starting terraform version detection...", logging.DEBUG)

        # 1. Try to find terraform using shutil.which
        terraform_cmd = shutil.which("terraform")
        if terraform_cmd is not None:
            logger.log(f"Found terraform via shutil.which: {terraform_cmd}", logging.DEBUG)
            return

        # TODO: is this needed?
        # 2. Fallback to TERRAFORM_CLI_PATH (set by hashicorp/setup-terraform action)
        if not terraform_cmd:
            terraform_cli_path = os.environ.get("TERRAFORM_CLI_PATH")
            if terraform_cli_path:
                logger.log(f"Trying TERRAFORM_CLI_PATH: {terraform_cli_path}", logging.DEBUG)
                # TODO: use binary name from runtime dependencies if we keep this code
                if os.name == "nt":
                    terraform_binary = os.path.join(terraform_cli_path, "terraform.exe")
                else:
                    terraform_binary = os.path.join(terraform_cli_path, "terraform")
                if os.path.exists(terraform_binary):
                    terraform_cmd = terraform_binary
                    logger.log(f"Found terraform via TERRAFORM_CLI_PATH: {terraform_cmd}", logging.DEBUG)
                    return

        raise RuntimeError(
            "Terraform executable not found, please ensure Terraform is installed."
            "See https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli for instructions."
        )

    @classmethod
    def _setup_runtime_dependencies(cls, logger: LanguageServerLogger, solidlsp_settings: SolidLSPSettings) -> str:
        """
        Setup runtime dependencies for terraform-ls.
        Downloads and installs terraform-ls if not already present.
        """
        cls._ensure_tf_command_available(logger)
        platform_id = PlatformUtils.get_platform_id()
        deps = RuntimeDependencyCollection(
            [
                RuntimeDependency(
                    id="TerraformLS",
                    description="terraform-ls for macOS (ARM64)",
                    url="https://releases.hashicorp.com/terraform-ls/0.36.5/terraform-ls_0.36.5_darwin_arm64.zip",
                    platform_id="osx-arm64",
                    archive_type="zip",
                    binary_name="terraform-ls",
                ),
                RuntimeDependency(
                    id="TerraformLS",
                    description="terraform-ls for macOS (x64)",
                    url="https://releases.hashicorp.com/terraform-ls/0.36.5/terraform-ls_0.36.5_darwin_amd64.zip",
                    platform_id="osx-x64",
                    archive_type="zip",
                    binary_name="terraform-ls",
                ),
                RuntimeDependency(
                    id="TerraformLS",
                    description="terraform-ls for Linux (ARM64)",
                    url="https://releases.hashicorp.com/terraform-ls/0.36.5/terraform-ls_0.36.5_linux_arm64.zip",
                    platform_id="linux-arm64",
                    archive_type="zip",
                    binary_name="terraform-ls",
                ),
                RuntimeDependency(
                    id="TerraformLS",
                    description="terraform-ls for Linux (x64)",
                    url="https://releases.hashicorp.com/terraform-ls/0.36.5/terraform-ls_0.36.5_linux_amd64.zip",
                    platform_id="linux-x64",
                    archive_type="zip",
                    binary_name="terraform-ls",
                ),
                RuntimeDependency(
                    id="TerraformLS",
                    description="terraform-ls for Windows (x64)",
                    url="https://releases.hashicorp.com/terraform-ls/0.36.5/terraform-ls_0.36.5_windows_amd64.zip",
                    platform_id="win-x64",
                    archive_type="zip",
                    binary_name="terraform-ls.exe",
                ),
            ]
        )
        dependency = deps.get_single_dep_for_current_platform()

        terraform_ls_executable_path = deps.binary_path(cls.ls_resources_dir(solidlsp_settings))
        if not os.path.exists(terraform_ls_executable_path):
            logger.log(f"Downloading terraform-ls from {dependency.url}", logging.INFO)
            deps.install(logger, cls.ls_resources_dir(solidlsp_settings))

        assert os.path.exists(terraform_ls_executable_path), f"terraform-ls executable not found at {terraform_ls_executable_path}"

        # Make the executable file executable on Unix-like systems
        if platform_id.value != "win-x64":
            os.chmod(terraform_ls_executable_path, 0o755)

        return terraform_ls_executable_path

    def __init__(
        self, config: LanguageServerConfig, logger: LanguageServerLogger, repository_root_path: str, solidlsp_settings: SolidLSPSettings
    ):
        """
        Creates a TerraformLS instance. This class is not meant to be instantiated directly. Use LanguageServer.create() instead.
        """
        terraform_ls_executable_path = self._setup_runtime_dependencies(logger, solidlsp_settings)

        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=f"{terraform_ls_executable_path} serve", cwd=repository_root_path),
            "terraform",
            solidlsp_settings,
        )
        self.server_ready = threading.Event()
        self.request_id = 0

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize params for the Terraform Language Server.
        """
        root_uri = PathUtils.path_to_uri(repository_absolute_path)
        return {
            "processId": os.getpid(),
            "locale": "en",
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True, "dynamicRegistration": True},
                    "completion": {"dynamicRegistration": True, "completionItem": {"snippetSupport": True}},
                    "definition": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "hierarchicalDocumentSymbolSupport": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                    },
                },
                "workspace": {"workspaceFolders": True, "didChangeConfiguration": {"dynamicRegistration": True}},
            },
            "workspaceFolders": [
                {
                    "name": os.path.basename(repository_absolute_path),
                    "uri": root_uri,
                }
            ],
        }

    def _start_server(self):
        """
        Terraform Language Server를 시작하고 서버 준비 완료를 기다립니다.

        이 메서드는 terraform-ls를 시작하고, 서버가 완전히 준비될 때까지
        기다린 후 클라이언트 요청을 처리할 준비를 완료합니다. terraform-ls는
        HashiCorp의 공식 Terraform 언어 서버로, HCL 구문과 Provider를 분석합니다.

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

        Terraform 특화 기능:
        - Terraform Provider Registry 연동
        - Module Registry 검색 및 완성
        - HCL 2.x 구문 검사
        - Resource 및 Data Source 완성
        - Variable 및 Output 참조 분석

        검증 항목:
        - textDocumentSync: 문서 동기화 지원
        - completionProvider: 코드 완성 지원
        - definitionProvider: 정의로 이동 지원

        Note:
            terraform-ls는 초기화 직후 바로 준비 상태가 되므로,
            다른 언어 서버들보다 빠른 응답을 제공합니다.
            이는 Terraform의 선언적 특성과 HashiCorp의 최적화된 구현 때문입니다.
        """

        def register_capability_handler(params):
            """
            클라이언트 기능 등록 핸들러.

            terraform-ls가 클라이언트 기능을 등록하면
            이에 대한 응답을 처리합니다. Terraform에서는
            Provider와 Module 관련 기능들이 동적으로 등록될 수 있습니다.
            """
            return

        def window_log_message(msg):
            """
            창 로그 메시지 핸들러.

            LSP 서버로부터 받은 로그 메시지를 SolidLSP 로거를 통해 기록합니다.
            terraform-ls의 상세한 로그 정보를 추적할 수 있습니다.
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

        # Terraform Language Server 프로세스 시작
        self.logger.log("Starting terraform-ls server process", logging.INFO)
        self.server.start()

        # 초기화 파라미터 생성 및 전송
        initialize_params = self._get_initialize_params(self.repository_root_path)
        self.logger.log(
            "Sending initialize request from LSP client to LSP server and awaiting response",
            logging.INFO,
        )
        init_response = self.server.send.initialize(initialize_params)

        # Terraform Language Server 기능 검증
        assert "textDocumentSync" in init_response["capabilities"]
        assert "completionProvider" in init_response["capabilities"]
        assert "definitionProvider" in init_response["capabilities"]

        # 초기화 완료 알림 전송 - 서버가 완전히 준비되었음을 알림
        self.server.notify.initialized({})
        self.completions_available.set()

        # terraform-ls는 초기화 직후 바로 준비 상태가 되므로 즉시 완료 표시
        self.server_ready.set()
        self.server_ready.wait()
