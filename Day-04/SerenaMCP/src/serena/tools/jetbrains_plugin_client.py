"""
serena/tools/jetbrains_plugin_client.py - Serena JetBrains 플러그인 클라이언트

이 파일은 Serena 에이전트가 JetBrains IDE(IntelliJ, PyCharm 등)에 설치된
Serena 플러그인의 백엔드 서비스와 통신하기 위한 클라이언트를 구현합니다.

주요 컴포넌트:
- 예외 클래스: SerenaClientError, ConnectionError, APIError, ServerNotFoundError 등
  클라이언트 통신 과정에서 발생할 수 있는 다양한 오류 상황을 정의합니다.
- JetBrainsPluginClient: 플러그인 서비스의 REST API 엔드포인트와 상호작용하기 위한
  메서드들을 제공하는 핵심 클라이언트 클래스입니다.

주요 기능:
- 서비스 탐색: 로컬호스트의 특정 포트 범위(0x5EA2부터)를 스캔하여 실행 중인
  JetBrains IDE의 Serena 플러그인 서비스를 자동으로 찾습니다.
- API 요청: `requests` 라이브러리를 사용하여 심볼 검색, 참조 찾기, 상태 확인 등
  플러그인이 제공하는 다양한 API를 호출합니다.
- 응답 처리: API 응답(JSON)의 키를 camelCase에서 snake_case로 변환하여
  파이썬 코드에서 일관되게 사용할 수 있도록 합니다.
- 컨텍스트 관리자 지원: `with` 구문을 사용하여 클라이언트 세션을 안전하게 관리할 수 있습니다.

아키텍처 노트:
- 이 클라이언트는 JetBrains IDE의 강력한 코드 인덱싱 및 분석 기능을 활용하기 위한
  브릿지 역할을 합니다. LSP(언어 서버 프로토콜) 기반 분석의 대안을 제공합니다.
- `from_project` 클래스 메서드는 프로젝트 경로를 기반으로 해당 프로젝트를 열고 있는
  올바른 JetBrains IDE 인스턴스를 찾아 연결하는 로직을 포함하고 있어, 다중 IDE 실행 환경에서도
  정확한 타겟팅을 가능하게 합니다.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional, Self, TypeVar

import requests
from sensai.util.string import ToStringMixin

from serena.project import Project

T = TypeVar("T")
log = logging.getLogger(__name__)


class SerenaClientError(Exception):
    """Serena 클라이언트 오류의 기본 예외 클래스입니다."""


class ConnectionError(SerenaClientError):
    """서비스 연결 실패 시 발생합니다."""


class APIError(SerenaClientError):
    """API가 오류 응답을 반환할 때 발생합니다."""


class ServerNotFoundError(Exception):
    """플러그인의 서비스를 찾을 수 없을 때 발생합니다."""


class JetBrainsPluginClient(ToStringMixin):
    """
    Serena 백엔드 서비스를 위한 파이썬 클라이언트입니다.

    사용 가능한 모든 엔드포인트와 상호 작용하는 간단한 메서드를 제공합니다.
    """

    BASE_PORT = 0x5EA2
    last_port: int | None = None

    def __init__(self, port: int, timeout: int = 30):
        self.base_url = f"http://127.0.0.1:{port}"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    def _tostring_includes(self) -> list[str]:
        return ["base_url", "timeout"]

    @classmethod
    def from_project(cls, project: Project) -> Self:
        resolved_path = Path(project.project_root).resolve()

        if cls.last_port is not None:
            client = JetBrainsPluginClient(cls.last_port)
            if client.matches(resolved_path):
                return client

        for port in range(cls.BASE_PORT, cls.BASE_PORT + 20):
            client = JetBrainsPluginClient(port)
            if client.matches(resolved_path):
                log.info("프로젝트 %s에 대해 포트 %d에서 JetBrains IDE 서비스를 찾았습니다.", port, resolved_path)
                cls.last_port = port
                return client

        raise ServerNotFoundError("프로젝트 경로 " + str(resolved_path) + "에 대한 JetBrains IDE 인스턴스에서 Serena 서비스를 찾을 수 없습니다.")

    def matches(self, resolved_path: Path) -> bool:
        try:
            return Path(self.project_root()).resolve() == resolved_path
        except ConnectionError:
            return False

    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"

        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=self.timeout)
            elif method.upper() == "POST":
                json_data = json.dumps(data) if data else None
                response = self.session.post(url, data=json_data, timeout=self.timeout)
            else:
                raise ValueError(f"지원되지 않는 HTTP 메서드: {method}")

            response.raise_for_status()

            # JSON 응답 파싱 시도
            try:
                return self._pythonify_response(response.json())
            except json.JSONDecodeError:
                # 응답이 JSON이 아니면 원시 텍스트 반환
                return {"response": response.text}

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"{url}의 Serena 서비스에 연결하지 못했습니다: {e}")
        except requests.exceptions.Timeout as e:
            raise ConnectionError(f"{url}로의 요청 시간 초과: {e}")
        except requests.exceptions.HTTPError:
            raise APIError(f"API 요청이 상태 코드 {response.status_code}로 실패했습니다: {response.text}")
        except requests.exceptions.RequestException as e:
            raise SerenaClientError(f"요청 실패: {e}")

    @staticmethod
    def _pythonify_response(response: T) -> T:
        """
        딕셔너리 키를 camelCase에서 snake_case로 재귀적으로 변환합니다.

        :response: 키를 변환할 응답 (딕셔너리 또는 리스트)
        """
        to_snake_case = lambda s: "".join(["_" + c.lower() if c.isupper() else c for c in s])

        def convert(x):  # type: ignore
            if isinstance(x, dict):
                return {to_snake_case(k): convert(v) for k, v in x.items()}
            elif isinstance(x, list):
                return [convert(item) for item in x]
            else:
                return x

        return convert(response)

    def project_root(self) -> str:
        response = self._make_request("GET", "/status")
        return response["project_root"]

    def find_symbol(
        self, name_path: str, relative_path: str | None = None, include_body: bool = False, depth: int = 0, include_location: bool = False
    ) -> dict[str, Any]:
        """
        이름으로 심볼을 찾습니다.

        :param name_path: 일치시킬 이름 경로
        :param relative_path: 검색을 제한할 상대 경로
        :param include_body: 심볼 본문 내용을 포함할지 여부
        :param depth: 포함할 자식의 깊이 (0 = 자식 없음)

        :return: 일치하는 심볼이 포함된 'symbols' 리스트를 가진 딕셔너리
        """
        request_data = {
            "namePath": name_path,
            "relativePath": relative_path,
            "includeBody": include_body,
            "depth": depth,
            "includeLocation": include_location,
        }
        return self._make_request("POST", "/findSymbol", request_data)

    def find_references(self, name_path: str, relative_path: str) -> dict[str, Any]:
        """
        심볼에 대한 참조를 찾습니다.

        :param name_path: 심볼의 이름 경로
        :param relative_path: 상대 경로
        :return: 심볼 참조가 포함된 'symbols' 리스트를 가진 딕셔너리
        """
        request_data = {"namePath": name_path, "relativePath": relative_path}
        return self._make_request("POST", "/findReferences", request_data)

    def get_symbols_overview(self, relative_path: str) -> dict[str, Any]:
        """
        :param relative_path: 소스 파일의 상대 경로
        """
        request_data = {"relativePath": relative_path}
        return self._make_request("POST", "/getSymbolsOverview", request_data)

    def is_service_available(self) -> bool:
        try:
            response = self.heartbeat()
            return response.get("status") == "OK"
        except (ConnectionError, APIError):
            return False

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        self.close()