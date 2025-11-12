"""
solidlsp/ls_types.py - SolidLSP 커스텀 타입 정의

이 파일은 LSP가 반환하는 기본 타입들을 `solidlsp` 라이브러리 내부에서
더 편리하게 사용하기 위해 래핑(wrapping)하거나 확장한 커스텀 타입들을 정의합니다.
LSP 버전 변경에 따른 영향을 최소화하고, 추가적인 정보(예: 절대/상대 경로)를
포함하기 위한 목적으로 사용됩니다.

주요 타입:
- Position, Range, Location: LSP의 기본 위치 정보 타입에 `absolutePath`, `relativePath` 등의
  경로 정보를 추가한 확장 타입.
- CompletionItem: 코드 완성 항목에 대한 정보를 담는 타입.
- SymbolKind, SymbolTag: LSP 심볼 종류와 태그를 나타내는 열거형.
- UnifiedSymbolInformation: `SymbolInformation`과 `DocumentSymbol`을 통합하고,
  `parent`, `children`, `body` 등의 추가 정보를 포함하는 `solidlsp`의 핵심 심볼 타입.
- MarkupKind, MarkupContent, Hover: 마크다운 형식의 호버 정보를 처리하기 위한 타입.
- Diagnostic: 코드 진단(오류, 경고 등) 정보를 담는 타입.
"""

from __future__ import annotations

from enum import Enum, IntEnum
from typing import NotRequired, Union

from typing_extensions import TypedDict

URI = str
DocumentUri = str
Uint = int
RegExp = str


class Position(TypedDict):
    r"""텍스트 문서 내의 위치를 0부터 시작하는 줄과 문자 오프셋으로 표현합니다.
    3.17 이전에는 오프셋이 항상 UTF-16 문자열 표현을 기반으로 했습니다.
    따라서 `a𐐀b` 형태의 문자열에서 문자 `a`의 오프셋은 0, `𐐀`의 오프셋은 1, b의 오프셋은 3입니다.
    `𐐀`는 UTF-16에서 두 개의 코드 단위를 사용하여 표현되기 때문입니다.
    3.17부터 클라이언트와 서버는 다른 문자열 인코딩 표현(예: UTF-8)에 동의할 수 있습니다.
    클라이언트는 [`general.positionEncodings`](#clientCapabilities) 클라이언트 기능을 통해 지원하는 인코딩을 알립니다.
    값은 클라이언트가 지원하는 위치 인코딩의 배열이며, 선호도가 감소하는 순서입니다(예: 인덱스 `0`의 인코딩이 가장 선호됨).
    하위 호환성을 유지하기 위해 유일한 필수 인코딩은 문자열 `utf-16`으로 표현되는 UTF-16입니다.
    서버는 클라이언트가 제공하는 인코딩 중 하나를 선택하고, 초기화 결과의 속성
    [`capabilities.positionEncoding`](#serverCapabilities)을 통해 해당 인코딩을 클라이언트에 다시 알립니다.
    문자열 값 `utf-16`이 클라이언트의 기능 `general.positionEncodings`에 없는 경우
    서버는 클라이언트가 UTF-16을 지원한다고 안전하게 가정할 수 있습니다. 서버가
    초기화 결과에서 위치 인코딩을 생략하면 인코딩은 기본적으로 문자열 값 `utf-16`이 됩니다.
    구현 고려 사항: 한 인코딩에서 다른 인코딩으로 변환하려면 파일/줄의 내용이 필요하므로
    변환은 일반적으로 서버 측에서 파일을 읽는 곳에서 가장 잘 수행됩니다.

    위치는 줄 끝 문자에 구애받지 않습니다. 따라서 `|
` 또는 `
|`를 나타내는 위치를 지정할 수 없습니다.
    여기서 `|`는 문자 오프셋을 나타냅니다.

    @since 3.17.0 - 협상된 위치 인코딩 지원.
    """

    line: Uint
    """ 문서의 줄 위치 (0부터 시작).

    If a line number is greater than the number of lines in a document, it defaults back to the number of lines in the document.
    If a line number is negative, it defaults to 0. """
    character: Uint
    """ 문서의 한 줄에 있는 문자 오프셋 (0부터 시작).

    The meaning of this offset is determined by the negotiated
    `PositionEncodingKind`.

    If the character value is greater than the line length it defaults back to the
    line length. """


class Range(TypedDict):
    """텍스트 문서 내의 범위를 (0부터 시작하는) 시작 및 끝 위치로 표현합니다.

    줄 끝 문자를 포함하는 범위를 지정하려면 다음 줄의 시작을 나타내는 끝 위치를 사용하세요.
    예를 들어:
    ```ts
    {
        start: { line: 5, character: 23 }
        end : { line 6, character : 0 }
    }
    ```
    """

    start: Position
    """ 범위의 시작 위치입니다. """
    end: Position
    """ 범위의 끝 위치입니다. """


class Location(TypedDict):
    """리소스 내의 위치를 나타냅니다. 예: 텍스트 파일 내의 줄.
    """

    uri: DocumentUri
    range: Range
    absolutePath: str
    relativePath: str | None


class CompletionItemKind(IntEnum):
    """완성 항목의 종류입니다."""

    Text = 1
    Method = 2
    Function = 3
    Constructor = 4
    Field = 5
    Variable = 6
    Class = 7
    Interface = 8
    Module = 9
    Property = 10
    Unit = 11
    Value = 12
    Enum = 13
    Keyword = 14
    Snippet = 15
    Color = 16
    File = 17
    Reference = 18
    Folder = 19
    EnumMember = 20
    Constant = 21
    Struct = 22
    Event = 23
    Operator = 24
    TypeParameter = 25


class CompletionItem(TypedDict):
    """완성 항목은 입력 중인 텍스트를 완성하기 위해
    제안되는 텍스트 스니펫을 나타냅니다.
    """

    completionText: str
    """ 이 완성 항목의 completionText입니다.

    The completionText property is also by default the text that
    is inserted when selecting this completion."""

    kind: CompletionItemKind
    """ 이 완성 항목의 종류입니다. 종류에 따라
    편집기에서 아이콘이 선택됩니다. """

    detail: NotRequired[str]
    """ 타입이나 심볼 정보와 같이 이 항목에 대한
    추가 정보가 포함된 사람이 읽을 수 있는 문자열입니다. """


class SymbolKind(IntEnum):
    """심볼 종류입니다."""

    File = 1
    Module = 2
    Namespace = 3
    Package = 4
    Class = 5
    Method = 6
    Property = 7
    Field = 8
    Constructor = 9
    Enum = 10
    Interface = 11
    Function = 12
    Variable = 13
    Constant = 14
    String = 15
    Number = 16
    Boolean = 17
    Array = 18
    Object = 19
    Key = 20
    Null = 21
    EnumMember = 22
    Struct = 23
    Event = 24
    Operator = 25
    TypeParameter = 26


class SymbolTag(IntEnum):
    """심볼 태그는 심볼의 렌더링을 조정하는 추가적인 주석입니다.

    @since 3.16
    """

    Deprecated = 1
    """ 심볼을 더 이상 사용되지 않는 것으로 렌더링합니다. 보통 취소선을 사용합니다. """


class UnifiedSymbolInformation(TypedDict):
    """변수, 클래스, 인터페이스 등과 같은 프로그래밍 구문에 대한 정보를 나타냅니다."""

    deprecated: NotRequired[bool]
    """ 이 심볼이 더 이상 사용되지 않는지 나타냅니다.

    @deprecated 대신 태그를 사용하세요. """
    location: NotRequired[Location]
    """ 이 심볼의 위치입니다. 위치의 범위는 도구에서
    편집기에서 위치를 표시하는 데 사용됩니다. 심볼이 도구에서
    선택되면 범위의 시작 정보가 커서를 배치하는 데 사용됩니다. 따라서
    범위는 일반적으로 실제 심볼의 이름보다 더 넓게 확장되며
    일반적으로 가시성 수정자와 같은 것을 포함합니다.

    범위는 추상 구문 트리의 의미에서 노드 범위를
    나타낼 필요는 없습니다. 따라서 문서 심볼의 계층 구조를
    재구성하는 데 사용할 수 없습니다.
    """
    name: str
    """ 이 심볼의 이름입니다. """
    kind: SymbolKind
    """ 이 심볼의 종류입니다. """
    tags: NotRequired[list[SymbolTag]]
    """ 이 심볼에 대한 태그입니다.

    @since 3.16.0 """
    containerName: NotRequired[str]
    """ 이 심볼을 포함하는 심볼의 이름입니다. 이 정보는
    사용자 인터페이스 목적(예: 필요한 경우 사용자 인터페이스에서
    한정자를 렌더링하기 위해)입니다. 문서 심볼의 계층 구조를
    다시 추론하는 데 사용할 수 없습니다.
    
    참고: Serena 내에서는 parent 속성이 추가되었으며 대신 사용해야 합니다.
    대부분의 LS는 containerName을 제공하지 않습니다.
    """

    detail: NotRequired[str]
    """ 이 심볼에 대한 자세한 내용입니다. 예: 함수의 서명. """

    range: NotRequired[Range]
    """ 주석과 같은 모든 것을 포함하지만 선행/후행 공백은 제외하고
    이 심볼을 둘러싸는 범위입니다. 이 정보는 일반적으로 클라이언트 커서가
    UI에서 심볼을 표시하기 위해 심볼 내에 있는지 확인하는 데 사용됩니다. """
    selectionRange: NotRequired[Range]
    """ 이 심볼을 선택하고 표시해야 하는 범위입니다. 예: 함수의 이름.
    `range`에 포함되어야 합니다. """

    body: NotRequired[str]
    """ 심볼의 본문입니다. """

    children: list[UnifiedSymbolInformation]
    """ 심볼의 자식입니다.
    `lsp_types.DocumentSymbol`과 호환되도록 추가되었습니다.
    심볼의 자식을 사용자 대면 기능으로 사용하는 것이 유용할 때가 있기 때문입니다."""

    parent: NotRequired[UnifiedSymbolInformation | None]
    """심볼의 부모입니다(있는 경우). LSP의 일부가 아닌 Serena와 함께 추가되었습니다.
    루트 패키지를 제외한 모든 심볼에는 부모가 있습니다.
    """


class MarkupKind(Enum):
    """`Hover`, `ParameterInfo` 또는 `CompletionItem`과 같은 다양한 결과 리터럴에서
    클라이언트가 지원하는 콘텐츠 타입을 설명합니다.

    `MarkupKinds`는 `$`로 시작해서는 안 됩니다. 이 종류는
    내부 사용을 위해 예약되어 있습니다.
    """

    PlainText = "plaintext"
    """ 일반 텍스트가 콘텐츠 형식으로 지원됩니다. """
    Markdown = "markdown"
    """ 마크다운이 콘텐츠 형식으로 지원됩니다. """


class __MarkedString_Type_1(TypedDict):
    language: str
    value: str


MarkedString = Union[str, "__MarkedString_Type_1"]
""" MarkedString은 사람이 읽을 수 있는 텍스트를 렌더링하는 데 사용할 수 있습니다. 마크다운 문자열이거나
언어와 코드 스니펫을 제공하는 코드 블록입니다. 언어 식별자는
GitHub 이슈의 펜스 코드 블록에 있는 선택적 언어 식별자와 의미상 동일합니다.
https://help.github.com/articles/creating-and-highlighting-code-blocks/#syntax-highlighting 참조

언어와 값의 쌍은 마크다운과 동일합니다:
```${language}
${value}
```

마크다운 문자열은 살균 처리됩니다. 즉, html이 이스케이프됩니다.
@deprecated 대신 MarkupContent를 사용하세요. """


class MarkupContent(TypedDict):
    r""`MarkupContent` 리터럴은 내용이
    종류 플래그에 따라 해석되는 문자열 값을 나타냅니다.
    현재 프로토콜은 마크업 종류로 `plaintext`와 `markdown`을 지원합니다.

    종류가 `markdown`이면 값에 GitHub 이슈와 같은 펜스 코드 블록이 포함될 수 있습니다.
    https://help.github.com/articles/creating-and-highlighting-code-blocks/#syntax-highlighting 참조

    다음은 JavaScript / TypeScript를 사용하여 이러한 문자열을 구성하는 방법의 예입니다:
    ```ts
    let markdown: MarkdownContent = {
     kind: MarkupKind.Markdown,
     value: [
       '# Header',
       'Some text',
       '```typescript',
       'someCode();',
       '```'
     ].join('\n')
    };
    ```

    *참고* 클라이언트는 반환된 마크다운을 살균 처리할 수 있습니다. 클라이언트는
    스크립트 실행을 피하기 위해 마크다운에서 HTML을 제거하기로 결정할 수 있습니다.
    """

    kind: MarkupKind
    """ 마크업의 타입입니다. """
    value: str
    """ 내용 자체입니다. """


class Hover(TypedDict):
    """호버 요청의 결과입니다."""

    contents: MarkupContent | MarkedString | list[MarkedString]
    """ 호버의 내용입니다. """
    range: NotRequired[Range]
    """ 텍스트 문서 내의 선택적 범위로,
    배경색을 변경하는 등 호버를 시각화하는 데 사용됩니다. """


class DiagnosticsSeverity(IntEnum):
    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


class Diagnostic(TypedDict):
    """텍스트 문서에 대한 진단 정보입니다."""

    uri: DocumentUri
    """ 진단이 적용되는 텍스트 문서의 URI입니다. """
    range: Range
    """ 진단이 적용되는 텍스트 문서의 범위입니다. """
    severity: NotRequired[DiagnosticsSeverity]
    """ 진단의 심각도입니다. """
    message: str
    """ 진단 메시지입니다. """
    code: str
    """ 진단의 코드입니다. """
    source: NotRequired[str]
    """ 진단의 출처입니다. 예: 진단을 생성한 도구의 이름. """