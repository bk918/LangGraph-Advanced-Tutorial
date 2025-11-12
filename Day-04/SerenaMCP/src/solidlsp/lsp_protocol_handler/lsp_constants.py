"""
solidlsp/lsp_protocol_handler/lsp_constants.py - LSP 프로토콜 상수

이 모듈은 언어 서버 프로토콜(LSP)에서 사용되는 다양한 상수들을 정의합니다.
LSP 메시지의 JSON-RPC 페이로드에서 사용되는 키(key)들을 상수로 관리하여,
코드의 가독성을 높이고 잠재적인 오타 실수를 방지합니다.

주요 상수 그룹:
- 문서 및 위치 관련: URI, RANGE, POSITION, TEXT_DOCUMENT 등
- 심볼 관련: NAME, KIND, CHILDREN, LOCATION 등
- 진단(Diagnostics) 관련: SEVERITY, MESSAGE 등
"""


class LSPConstants:
    """
    LSP 프로토콜에서 사용되는 상수들을 포함하는 클래스.

    각 상수는 LSP 메시지 본문에서 사용되는 JSON 필드의 키 이름에 해당합니다.
    """

    # 경로를 나타내는 데 사용되는 uri의 키
    URI = "uri"

    # 텍스트 문서 내의 시작과 끝 위치인 range의 키
    RANGE = "range"

    # LocationLink 타입에서 사용되는 키, 원본 링크의 범위를 나타냄
    ORIGIN_SELECTION_RANGE = "originSelectionRange"

    # LocationLink 타입에서 사용되는 키, 링크의 대상 uri를 나타냄
    TARGET_URI = "targetUri"

    # LocationLink 타입에서 사용되는 키, 링크의 대상 범위를 나타냄
    TARGET_RANGE = "targetRange"

    # LocationLink 타입에서 사용되는 키, 링크의 대상 선택 범위를 나타냄
    TARGET_SELECTION_RANGE = "targetSelectionRange"

    # 요청에서 textDocument 필드의 키
    TEXT_DOCUMENT = "textDocument"

    # 문서의 언어를 나타내는 데 사용되는 키 - "java", "csharp" 등
    LANGUAGE_ID = "languageId"

    # 문서의 버전을 나타내는 데 사용되는 키 (클라이언트와 서버 간의 공유 값)
    VERSION = "version"

    # 클라이언트에서 서버로 열 때 전송되는 문서의 텍스트를 나타내는 데 사용되는 키
    TEXT = "text"

    # 텍스트 문서 내의 위치(줄 및 열 번호)를 나타내는 데 사용되는 키
    POSITION = "position"

    # 위치의 줄 번호를 나타내는 데 사용되는 키
    LINE = "line"

    # 위치의 열 번호를 나타내는 데 사용되는 키
    CHARACTER = "character"

    # 문서에 적용된 변경 사항을 나타내는 데 사용되는 키
    CONTENT_CHANGES = "contentChanges"

    # 심볼의 이름을 나타내는 데 사용되는 키
    NAME = "name"

    # 심볼의 종류를 나타내는 데 사용되는 키
    KIND = "kind"

    # 문서 심볼에서 자식을 나타내는 데 사용되는 키
    CHILDREN = "children"

    # 심볼에서 위치를 나타내는 데 사용되는 키
    LOCATION = "location"

    # 진단의 심각도 수준
    SEVERITY = "severity"

    # 진단의 메시지
    MESSAGE = "message"