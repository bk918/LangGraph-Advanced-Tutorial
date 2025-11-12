"""
serena/tools/jetbrains_tools.py - JetBrains IDE 연동 도구

이 파일은 Serena 에이전트가 JetBrains IDE(예: IntelliJ, PyCharm)의 플러그인과
통신하여 코드 분석 기능을 수행할 수 있도록 하는 도구들을 포함합니다.
이 도구들은 LSP(언어 서버 프로토콜) 기반 도구들의 대안으로, IDE의 강력한 인덱싱 및
심볼 분석 능력을 활용합니다.

주요 클래스:
- JetBrainsFindSymbolTool: JetBrains IDE의 인덱스를 사용하여 심볼을 검색합니다.
- JetBrainsFindReferencingSymbolsTool: 특정 심볼을 참조하는 모든 곳을 찾습니다.
- JetBrainsGetSymbolsOverviewTool: 파일 내의 최상위 심볼 목록을 가져옵니다.

아키텍처 노트:
- 이 도구들은 `JetBrainsPluginClient`를 통해 IDE 플러그인과 소켓 통신을 수행합니다.
- 모든 도구는 `ToolMarkerOptional`로 표시되어 있어, 기본적으로는 비활성화되어 있으며
  `jetbrains` 모드가 활성화될 때만 사용할 수 있습니다.
- 이는 사용자가 LSP 기반 분석과 JetBrains IDE 기반 분석 중 하나를 선택할 수 있도록 하는
  유연한 구조를 제공합니다.
- LSP 기반 도구들과 유사한 인터페이스를 제공하여, 에이전트가 일관된 방식으로
  심볼 관련 작업을 수행할 수 있도록 합니다.
"""

import json

from serena.tools import Tool, ToolMarkerOptional, ToolMarkerSymbolicRead
from serena.tools.jetbrains_plugin_client import JetBrainsPluginClient


class JetBrainsFindSymbolTool(Tool, ToolMarkerSymbolicRead, ToolMarkerOptional):
    """
    주어진 이름/부분 문자열을 포함하는 심볼을 전역(또는 지역)적으로 검색합니다 (선택적으로 타입으로 필터링).
    이 도구는 JetBrains IDE의 심볼 분석 기능을 활용합니다.
    """

    def apply(
        self,
        name_path: str,
        depth: int = 0,
        relative_path: str | None = None,
        include_body: bool = False,
        max_answer_chars: int = -1,
    ) -> str:
        """
        주어진 `name_path`를 기반으로 모든 심볼/코드 엔티티(클래스, 메서드 등)에 대한 정보를 검색합니다.

        `name_path`는 단일 파일 내의 심볼 트리에 있는 심볼의 경로 패턴을 나타냅니다.
        반환된 심볼 위치는 편집이나 추가 쿼리에 사용될 수 있습니다.
        자식(예: 클래스의 메서드)을 검색하려면 `depth > 0`을 지정하십시오.

        매칭 동작은 `name_path`의 구조에 의해 결정되며, 단순한 이름(예: "method") 또는
        "class/method"(상대 이름 경로)나 "/class/method"(절대 이름 경로)와 같은 이름 경로일 수 있습니다.
        `name_path`는 파일 시스템의 경로가 아니라 단일 파일 내의 심볼 트리 경로이므로,
        파일이나 디렉토리 이름은 `name_path`에 포함되어서는 안 됩니다.

        Args:
            name_path (str): 검색할 이름 경로 패턴. 자세한 내용은 위 설명을 참조하십시오.
            depth (int): 자손을 검색할 깊이 (예: 클래스 메서드/속성의 경우 1).
            relative_path (str | None): 선택 사항. 검색을 이 파일 또는 디렉토리로 제한합니다.
                None이면 전체 코드베이스를 검색합니다.
            include_body (bool): True이면 심볼의 소스 코드를 포함합니다. 신중하게 사용하십시오.
            max_answer_chars (int): JSON 결과의 최대 문자 수. 초과하면 내용이 반환되지 않습니다.
                -1은 설정의 기본값을 사용함을 의미합니다.

        Returns:
            str: 이름과 일치하는 심볼(위치 포함) 목록의 JSON 문자열.
        """
        with JetBrainsPluginClient.from_project(self.project) as client:
            response_dict = client.find_symbol(
                name_path=name_path,
                relative_path=relative_path,
                depth=depth,
                include_body=include_body,
            )
            result = json.dumps(response_dict)
        return self._limit_length(result, max_answer_chars)


class JetBrainsFindReferencingSymbolsTool(Tool, ToolMarkerSymbolicRead, ToolMarkerOptional):
    """
    주어진 심볼을 참조하는 심볼들을 찾습니다.
    """

    def apply(
        self,
        name_path: str,
        relative_path: str,
        max_answer_chars: int = -1,
    ) -> str:
        """
        주어진 `name_path`에 있는 심볼을 참조하는 다른 심볼들을 찾습니다.
        결과에는 참조하는 심볼들에 대한 메타데이터가 포함됩니다.

        Args:
            name_path (str): 참조를 찾을 심볼의 이름 경로. 매칭 로직은 `find_symbol` 도구에 설명된 것과 같습니다.
            relative_path (str): 참조를 찾을 심볼이 포함된 파일의 상대 경로.
                디렉토리가 아닌 파일 경로를 전달해야 합니다.
            max_answer_chars (int): JSON 결과의 최대 문자 수. 초과하면 내용이 반환되지 않습니다.
                -1은 설정의 기본값을 사용함을 의미합니다.

        Returns:
            str: 요청된 심볼을 참조하는 심볼들의 JSON 객체 목록.
        """
        with JetBrainsPluginClient.from_project(self.project) as client:
            response_dict = client.find_references(
                name_path=name_path,
                relative_path=relative_path,
            )
            result = json.dumps(response_dict)
        return self._limit_length(result, max_answer_chars)


class JetBrainsGetSymbolsOverviewTool(Tool, ToolMarkerSymbolicRead, ToolMarkerOptional):
    """
    지정된 파일 내의 최상위 심볼 개요를 검색합니다.
    """

    def apply(
        self,
        relative_path: str,
        max_answer_chars: int = -1,
    ) -> str:
        """
        주어진 파일의 최상위 심볼 개요를 가져옵니다.

        더 대상화된 읽기, 검색 또는 편집 작업을 수행하기 전에 이 도구를 호출하는 것이 좋습니다.
        심볼 개요를 요청하기 전에, 메모리나 `list_dir`, `find_file`과 같은 도구를 사용하여
        리포지토리의 기본 디렉토리 구조를 먼저 파악하여 개요의 범위를 좁히는 것이 좋습니다.

        Args:
            relative_path (str): 개요를 가져올 파일의 상대 경로.
            max_answer_chars (int): JSON 결과의 최대 문자 수. 초과하면 내용이 반환되지 않습니다.
                -1은 설정의 기본값을 사용함을 의미합니다.

        Returns:
            str: 심볼을 포함하는 JSON 객체.
        """
        with JetBrainsPluginClient.from_project(self.project) as client:
            response_dict = client.get_symbols_overview(
                relative_path=relative_path,
            )
            result = json.dumps(response_dict)
        return self._limit_length(result, max_answer_chars)