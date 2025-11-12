# Code generated. DO NOT EDIT.
# LSP v3.17.0
# TODO: Look into use of https://pypi.org/project/ts2python/ to generate the types for https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/

"""
solidlsp/lsp_protocol_handler/lsp_types.py - LSP 자료 구조 타입 정의

이 파일은 언어 서버 프로토콜(LSP) 사양에 정의된 데이터 구조에 해당하는
파이썬 타입(주로 `TypedDict`와 `Enum`)들을 제공합니다. LSP 메시지에서 사용되는
복잡한 객체들의 형태를 정의하여 타입 안정성을 보장합니다.

주요 내용:
- 열거형(Enum): `SemanticTokenTypes`, `SymbolKind`, `MessageType` 등 LSP에서 사용되는 각종 상수 값들을 정의합니다.
- 타입 딕셔너리(TypedDict): `Location`, `Range`, `Position`, `CompletionItem` 등 LSP 메시지의 페이로드를 구성하는
  객체들의 구조를 정의합니다.
- 유니온 타입(Union): 여러 타입이 될 수 있는 필드들을 정의합니다 (예: `Definition`).

참고:
- 이 파일의 코드는 https://github.com/predragnikolic/OLSP 프로젝트에서 가져온 것이며,
  LSP 사양 v3.17.0을 기반으로 합니다. 코드 생성기로 만들어졌으므로 직접적인 수정은 권장되지 않습니다.
- 각 타입의 docstring은 LSP 공식 사양의 설명을 따릅니다.

MIT License

Copyright (c) 2023 Предраг Николић

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from enum import Enum, IntEnum, IntFlag
from typing import Literal, NotRequired, Union

from typing_extensions import TypedDict

URI = str
DocumentUri = str
Uint = int
RegExp = str


class SemanticTokenTypes(Enum):
    """
    사전 정의된 토큰 타입의 집합입니다. 이 집합은 고정되어 있지 않으며,
    클라이언트는 해당 클라이언트 기능을 통해 추가적인 토큰 타입을 지정할 수 있습니다.

    @since 3.16.0
    """

    Namespace = "namespace"
    Type = "type"
    """ 클래스나 열거형과 같은 특정 타입으로 매핑할 수 없는 타입의 대체 역할을 하는 제네릭 타입을 나타냅니다. """
    Class = "class"
    Enum = "enum"
    Interface = "interface"
    Struct = "struct"
    TypeParameter = "typeParameter"
    Parameter = "parameter"
    Variable = "variable"
    Property = "property"
    EnumMember = "enumMember"
    Event = "event"
    Function = "function"
    Method = "method"
    Macro = "macro"
    Keyword = "keyword"
    Modifier = "modifier"
    Comment = "comment"
    String = "string"
    Number = "number"
    Regexp = "regexp"
    Operator = "operator"
    Decorator = "decorator"
    """ @since 3.17.0 """


class SemanticTokenModifiers(Enum):
    """
    사전 정의된 토큰 수정자의 집합입니다. 이 집합은 고정되어 있지 않으며,
    클라이언트는 해당 클라이언트 기능을 통해 추가적인 토큰 타입을 지정할 수 있습니다.

    @since 3.16.0
    """

    Declaration = "declaration"
    Definition = "definition"
    Readonly = "readonly"
    Static = "static"
    Deprecated = "deprecated"
    Abstract = "abstract"
    Async = "async"
    Modification = "modification"
    Documentation = "documentation"
    DefaultLibrary = "defaultLibrary"


class DocumentDiagnosticReportKind(Enum):
    """
    문서 진단 보고서 종류입니다.

    @since 3.17.0
    """

    Full = "full"
    """ 전체 문제 집합을 포함하는 진단 보고서입니다. """
    Unchanged = "unchanged"
    """ 마지막으로 반환된 보고서가 여전히 정확함을 나타내는 보고서입니다. """


class ErrorCodes(IntEnum):
    """사전 정의된 오류 코드입니다."""

    ParseError = -32700
    InvalidRequest = -32600
    MethodNotFound = -32601
    InvalidParams = -32602
    InternalError = -32603
    ServerNotInitialized = -32002
    """ 서버가 `initialize` 요청을 받기 전에 알림이나 요청을 받았음을 나타내는 오류 코드입니다. """
    UnknownErrorCode = -32001


class LSPErrorCodes(IntEnum):
    RequestFailed = -32803
    """ 요청이 실패했지만 구문적으로는 올바른 경우입니다. 예: 메서드 이름이 알려져 있고 매개변수가 유효한 경우.
    오류 메시지에는 요청이 실패한 이유에 대한 사람이 읽을 수 있는 정보가 포함되어야 합니다.

    @since 3.17.0 """
    ServerCancelled = -32802
    """ 서버가 요청을 취소했습니다. 이 오류 코드는
    명시적으로 서버 취소를 지원하는 요청에만 사용해야 합니다.

    @since 3.17.0 """
    ContentModified = -32801
    """ 서버가 문서 내용이 정상적인 조건 밖에서
    수정되었음을 감지했습니다. 서버는 처리되지 않은 메시지에서 내용 변경을 감지하더라도
    이 오류 코드를 보내서는 안 됩니다. 이전 상태에서 계산된 결과라도
    클라이언트에게 유용할 수 있습니다.

    클라이언트가 결과가 더 이상 유용하지 않다고 판단하면
    클라이언트는 요청을 취소해야 합니다. """
    RequestCancelled = -32800
    """ 클라이언트가 요청을 취소했고 서버가
    취소를 감지했습니다. """


class FoldingRangeKind(Enum):
    """사전 정의된 범위 종류의 집합입니다."""

    Comment = "comment"
    """ 주석에 대한 접기 범위 """
    Imports = "imports"
    """ 가져오기 또는 포함에 대한 접기 범위 """
    Region = "region"
    """ 영역에 대한 접기 범위 (예: `#region`) """


class SymbolKind(IntEnum):
    """심볼 종류입니다."""

    File = 1
    Module = 2
    Namespace = 3
    Package = 4
    """
    패키지 또는 파일 시스템의 디렉토리를 나타냅니다.
    """
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

    @classmethod
    def from_int(cls, value: int) -> "SymbolKind":
        for symbol_kind in cls:
            if symbol_kind.value == value:
                return symbol_kind
        raise ValueError(f"잘못된 심볼 종류: {value}")


class SymbolTag(IntEnum):
    """
    심볼 태그는 심볼의 렌더링을 조정하는 추가적인 주석입니다.

    @since 3.16
    """

    Deprecated = 1
    """ 심볼을 더 이상 사용되지 않는 것으로 렌더링합니다. 보통 취소선을 사용합니다. """


class UniquenessLevel(Enum):
    """
    모니커의 범위를 정의하는 모니커 고유성 수준입니다.

    @since 3.16.0
    """

    Document = "document"
    """ 모니커는 문서 내에서만 고유합니다. """
    Project = "project"
    """ 모니커는 덤프가 생성된 프로젝트 내에서 고유합니다. """
    Group = "group"
    """ 모니커는 프로젝트가 속한 그룹 내에서 고유합니다. """
    Scheme = "scheme"
    """ 모니커는 모니커 체계 내에서 고유합니다. """
    Global = "global"
    """ 모니커는 전역적으로 고유합니다. """


class MonikerKind(Enum):
    """
    모니커 종류입니다.

    @since 3.16.0
    """

    Import = "import"
    """ 모니커는 프로젝트로 가져온 심볼을 나타냅니다. """
    Export = "export"
    """ 모니커는 프로젝트에서 내보낸 심볼을 나타냅니다. """
    Local = "local"
    """ 모니커는 프로젝트에 로컬인 심볼을 나타냅니다 (예: 함수의 지역 변수, 프로젝트 외부에서 보이지 않는 클래스 등). """


class InlayHintKind(IntEnum):
    """
    인레이 힌트 종류입니다.

    @since 3.17.0
    """

    Type = 1
    """ 타입 주석에 대한 인레이 힌트입니다. """
    Parameter = 2
    """ 매개변수에 대한 인레이 힌트입니다. """


class MessageType(IntEnum):
    """메시지 타입입니다."""

    Error = 1
    """ 오류 메시지입니다. """
    Warning = 2
    """ 경고 메시지입니다. """
    Info = 3
    """ 정보 메시지입니다. """
    Log = 4
    """ 로그 메시지입니다. """


class TextDocumentSyncKind(IntEnum):
    """
    호스트(편집기)가 언어 서버에 문서 변경 사항을
    동기화하는 방법을 정의합니다.
    """

    None_ = 0
    """ 문서는 전혀 동기화되지 않아야 합니다. """
    Full = 1
    """ 문서는 항상 문서의 전체 내용을 전송하여 동기화됩니다. """
    Incremental = 2
    """ 문서는 열 때 전체 내용을 전송하여 동기화됩니다.
    그 후에는 문서에 대한 증분 업데이트만 전송됩니다. """


class TextDocumentSaveReason(IntEnum):
    """텍스트 문서가 저장되는 이유를 나타냅니다."""

    Manual = 1
    """ 사용자가 저장을 누르거나, 디버깅을 시작하거나, API 호출에 의해 수동으로 트리거됩니다. """
    AfterDelay = 2
    """ 지연 후 자동으로 저장됩니다. """
    FocusOut = 3
    """ 편집기가 포커스를 잃었을 때 저장됩니다. """


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


class CompletionItemTag(IntEnum):
    """
    완성 항목 태그는 완성 항목의 렌더링을 조정하는 추가적인 주석입니다.

    @since 3.15.0
    """

    Deprecated = 1
    """ 완성을 더 이상 사용되지 않는 것으로 렌더링합니다. 보통 취소선을 사용합니다. """


class InsertTextFormat(IntEnum):
    """
    완성 항목의 삽입 텍스트를 일반 텍스트로 해석할지 스니펫으로 해석할지 정의합니다.
    """

    PlainText = 1
    """ 삽입할 기본 텍스트는 일반 문자열로 처리됩니다. """
    Snippet = 2
    """ 삽입할 기본 텍스트는 스니펫으로 처리됩니다.

    스니펫은 `$1`, `$2` 및 `${3:foo}`로 탭 정지 및 자리 표시자를 정의할 수 있습니다.
    `$0`은 최종 탭 정지를 정의하며, 기본값은 스니펫의 끝입니다. 동일한 식별자를 가진 자리 표시자는
    연결되어 있어 하나를 입력하면 다른 것도 업데이트됩니다.

    참조: https://microsoft.github.io/language-server-protocol/specifications/specification-current/#snippet_syntax """


class InsertTextMode(IntEnum):
    """
    완성 항목 삽입 중 공백 및 들여쓰기 처리 방법입니다.

    @since 3.16.0
    """

    AsIs = 1
    """ 삽입 또는 교체 문자열은 그대로 사용됩니다. 값이
    여러 줄인 경우 커서 아래의 줄은 문자열 값에 정의된 들여쓰기를 사용하여
    삽입됩니다. 클라이언트는 문자열에 어떤 종류의 조정도 적용하지 않습니다. """
    AdjustIndentation = 2
    """ 편집기는 새 줄의 선행 공백을 조정하여
    항목이 수락된 줄의 커서까지의 들여쓰기와 일치하도록 합니다.

    `<2tabs><cursor><3tabs>foo`와 같은 줄을 고려해보세요. 여러 줄 완성 항목을 수락하면
    2개의 탭으로 들여쓰기되고 삽입된 모든 다음 줄도 2개의 탭으로 들여쓰기됩니다. """


class DocumentHighlightKind(IntEnum):
    """문서 하이라이트 종류입니다."""

    Text = 1
    """ 텍스트 발생입니다. """
    Read = 2
    """ 변수 읽기와 같은 심볼의 읽기 액세스입니다. """
    Write = 3
    """ 변수에 쓰기와 같은 심볼의 쓰기 액세스입니다. """


class CodeActionKind(Enum):
    """사전 정의된 코드 액션 종류의 집합입니다."""

    Empty = ""
    """ 빈 종류입니다. """
    QuickFix = "quickfix"
    """ 빠른 수정 액션의 기본 종류: 'quickfix' """
    Refactor = "refactor"
    """ 리팩토링 액션의 기본 종류: 'refactor' """
    RefactorExtract = "refactor.extract"
    """ 리팩토링 추출 액션의 기본 종류: 'refactor.extract'

    예제 추출 액션:

    - 메서드 추출
    - 함수 추출
    - 변수 추출
    - 클래스에서 인터페이스 추출
    - ... """
    RefactorInline = "refactor.inline"
    """ 리팩토링 인라인 액션의 기본 종류: 'refactor.inline'

    예제 인라인 액션:

    - 함수 인라인
    - 변수 인라인
    - 상수 인라인
    - ... """
    RefactorRewrite = "refactor.rewrite"
    """ 리팩토링 재작성 액션의 기본 종류: 'refactor.rewrite'

    예제 재작성 액션:

    - JavaScript 함수를 클래스로 변환
    - 매개변수 추가 또는 제거
    - 필드 캡슐화
    - 메서드를 정적으로 만들기
    - 메서드를 기본 클래스로 이동
    - ... """
    Source = "source"
    """ 소스 액션의 기본 종류: `source`

    소스 코드 액션은 전체 파일에 적용됩니다. """
    SourceOrganizeImports = "source.organizeImports"
    """ import 정렬 소스 액션의 기본 종류: `source.organizeImports` """
    SourceFixAll = "source.fixAll"
    """ 자동 수정 소스 액션의 기본 종류: `source.fixAll`.

    모두 수정 액션은 사용자 입력이 필요 없는 명확한 수정 방법이 있는 오류를 자동으로 수정합니다.
    오류를 억제하거나 새 타입이나 클래스를 생성하는 것과 같은 안전하지 않은 수정은 수행해서는 안 됩니다.

    @since 3.15.0 """


class TraceValues(Enum):
    Off = "off"
    """ 추적 끄기. """
    Messages = "messages"
    """ 메시지만 추적. """
    Verbose = "verbose"
    """ 상세 메시지 추적. """


class MarkupKind(Enum):
    """
    `Hover`, `ParameterInfo` 또는 `CompletionItem`과 같은 다양한 결과 리터럴에서
    클라이언트가 지원하는 콘텐츠 타입을 설명합니다.

    `MarkupKinds`는 `$`로 시작해서는 안 됩니다. 이 종류는
    내부 사용을 위해 예약되어 있습니다.
    """

    PlainText = "plaintext"
    """ 일반 텍스트가 콘텐츠 형식으로 지원됩니다. """
    Markdown = "markdown"
    """ 마크다운이 콘텐츠 형식으로 지원됩니다. """


class PositionEncodingKind(Enum):
    """
    사전 정의된 위치 인코딩 종류의 집합입니다.

    @since 3.17.0
    """

    UTF8 = "utf-8"
    """ 문자 오프셋은 UTF-8 코드 단위를 셉니다. """
    UTF16 = "utf-16"
    """ 문자 오프셋은 UTF-16 코드 단위를 셉니다.

    이것이 기본값이며 서버에서 항상 지원해야 합니다. """
    UTF32 = "utf-32"
    """ 문자 오프셋은 UTF-32 코드 단위를 셉니다.

    구현 참고: 이것은 유니코드 코드 포인트와 동일하므로,
    이 `PositionEncodingKind`는 문자 오프셋의 인코딩에 구애받지 않는
    표현에도 사용될 수 있습니다. """


class FileChangeType(IntEnum):
    """파일 이벤트 타입입니다."""

    Created = 1
    """ 파일이 생성되었습니다. """
    Changed = 2
    """ 파일이 변경되었습니다. """
    Deleted = 3
    """ 파일이 삭제되었습니다. """


class WatchKind(IntFlag):
    Create = 1
    """ 생성 이벤트에 관심이 있습니다. """
    Change = 2
    """ 변경 이벤트에 관심이 있습니다. """
    Delete = 4
    """ 삭제 이벤트에 관심이 있습니다. """


class DiagnosticSeverity(IntEnum):
    """진단의 심각도입니다."""

    Error = 1
    """ 오류를 보고합니다. """
    Warning = 2
    """ 경고를 보고합니다. """
    Information = 3
    """ 정보를 보고합니다. """
    Hint = 4
    """ 힌트를 보고합니다. """


class DiagnosticTag(IntEnum):
    """
    진단 태그입니다.

    @since 3.15.0
    """

    Unnecessary = 1
    """ 사용되지 않거나 불필요한 코드입니다.

    클라이언트는 이 태그가 있는 진단을 오류 물결선 대신
    흐리게 렌더링할 수 있습니다. """
    Deprecated = 2
    """ 더 이상 사용되지 않거나 구식인 코드입니다.

    클라이언트는 이 태그가 있는 진단을 취소선으로 렌더링할 수 있습니다. """


class CompletionTriggerKind(IntEnum):
    """완성이 어떻게 트리거되었는지 나타냅니다."""

    Invoked = 1
    """ 식별자 입력(24x7 코드 완성), 수동 호출(예: Ctrl+Space) 또는 API를 통해 완성이 트리거되었습니다. """
    TriggerCharacter = 2
    """ `CompletionRegistrationOptions`의 `triggerCharacters` 속성에 지정된 트리거 문자에 의해 완성이 트리거되었습니다. """
    TriggerForIncompleteCompletions = 3
    """ 현재 완성 목록이 불완전하여 완성이 다시 트리거되었습니다. """


class SignatureHelpTriggerKind(IntEnum):
    """
    서명 도움이 어떻게 트리거되었는지 나타냅니다.

    @since 3.15.0
    """

    Invoked = 1
    """ 서명 도움이 사용자에 의해 수동으로 또는 명령에 의해 호출되었습니다. """
    TriggerCharacter = 2
    """ 서명 도움이 트리거 문자에 의해 트리거되었습니다. """
    ContentChange = 3
    """ 서명 도움이 커서 이동 또는 문서 내용 변경에 의해 트리거되었습니다. """


class CodeActionTriggerKind(IntEnum):
    """
    코드 액션이 요청된 이유입니다.

    @since 3.17.0
    """

    Invoked = 1
    """ 코드 액션이 사용자에 의해 또는 확장에 의해 명시적으로 요청되었습니다. """
    Automatic = 2
    """ 코드 액션이 자동으로 요청되었습니다.

    이는 일반적으로 파일의 현재 선택이 변경될 때 발생하지만,
    파일 내용이 변경될 때도 트리거될 수 있습니다. """


class FileOperationPatternKind(Enum):
    """
    glob 패턴이 파일, 폴더 또는 둘 다와 일치하는지 설명하는 패턴 종류입니다.

    @since 3.16.0
    """

    File = "file"
    """ 패턴이 파일만 일치합니다. """
    Folder = "folder"
    """ 패턴이 폴더만 일치합니다. """


class NotebookCellKind(IntEnum):
    """
    노트북 셀 종류입니다.

    @since 3.17.0
    """

    Markup = 1
    """ 마크업 셀은 표시에 사용되는 형식화된 소스입니다. """
    Code = 2
    """ 코드 셀은 소스 코드입니다. """


class ResourceOperationKind(Enum):
    Create = "create"
    """ 새 파일 및 폴더 생성을 지원합니다. """
    Rename = "rename"
    """ 기존 파일 및 폴더 이름 변경을 지원합니다. """
    Delete = "delete"
    """ 기존 파일 및 폴더 삭제를 지원합니다. """


class FailureHandlingKind(Enum):
    Abort = "abort"
    """ 제공된 변경 사항 중 하나가 실패하면 작업 공간 변경 적용이 중단됩니다.
    실패한 작업 이전에 실행된 모든 작업은 실행된 상태로 유지됩니다. """
    Transactional = "transactional"
    """ 모든 작업은 트랜잭션으로 실행됩니다. 즉, 모두 성공하거나
    작업 공간에 전혀 변경 사항이 적용되지 않습니다. """
    TextOnlyTransactional = "textOnlyTransactional"
    """ 작업 공간 편집에 텍스트 파일 변경만 포함된 경우 트랜잭션으로 실행됩니다.
    리소스 변경(파일 생성, 이름 변경 또는 삭제)이 변경의 일부인 경우
    실패 처리 전략은 중단입니다. """
    Undo = "undo"
    """ 클라이언트는 이미 실행된 작업을 되돌리려고 시도합니다. 그러나
    이것이 성공한다는 보장은 없습니다. """


class PrepareSupportDefaultBehavior(IntEnum):
    Identifier = 1
    """ 클라이언트의 기본 동작은 언어의 구문 규칙에 따라
    식별자를 선택하는 것입니다. """


class TokenFormat(Enum):
    Relative = "relative"


Definition = Union["Location", list["Location"]]
""" 하나 또는 여러 개의 {@link Location 위치}로 표현되는 심볼의 정의입니다.
대부분의 프로그래밍 언어에서는 심볼이 정의된 위치가 하나뿐입니다.

서버는 클라이언트에서 지원하는 경우 `Definition`보다 `DefinitionLink`를 반환하는 것을 선호해야 합니다. """

DefinitionLink = "LocationLink"
""" 심볼이 정의된 위치에 대한 정보입니다.

정의 심볼의 범위를 포함하여 일반 {@link Location 위치} 정의보다 추가적인 메타데이터를 제공합니다. """

LSPArray = list["LSPAny"]
""" LSP 배열입니다.
@since 3.17.0 """

LSPAny = Union["LSPObject", "LSPArray", str, int, Uint, float, bool, None]
""" LSP any 타입입니다.
엄밀히 말해 `undefined` 값을 가진 속성은 속성 이름을 유지하면서
JSON으로 변환할 수 없습니다. 그러나 편의를 위해 허용되며
이러한 모든 속성은 선택 사항으로 간주됩니다.
@since 3.17.0 """

Declaration = Union["Location", list["Location"]]
""" 하나 또는 여러 개의 {@link Location 위치}로 표현되는 심볼의 선언입니다. """

DeclarationLink = "LocationLink"
""" 심볼이 선언된 위치에 대한 정보입니다.

선언 심볼의 범위를 포함하여 일반 {@link Location 위치} 선언보다 추가적인 메타데이터를 제공합니다.

서버는 클라이언트에서 지원하는 경우 `Declaration`보다 `DeclarationLink`를 반환하는 것을 선호해야 합니다. """

InlineValue = Union["InlineValueText", "InlineValueVariableLookup", "InlineValueEvaluatableExpression"]
""" 인라인 값 정보는 다른 방법으로 제공될 수 있습니다:
- 텍스트 값으로 직접 (클래스 InlineValueText).
- 변수 조회를 위한 이름으로 (클래스 InlineValueVariableLookup)
- 평가 가능한 표현식으로 (클래스 InlineValueEvaluatableExpression)
InlineValue 타입은 모든 인라인 값 타입을 하나의 타입으로 결합합니다.

@since 3.17.0 """

DocumentDiagnosticReport = Union["RelatedFullDocumentDiagnosticReport", "RelatedUnchangedDocumentDiagnosticReport"]
""" 문서 진단 풀 요청의 결과입니다. 보고서는
요청된 문서에 대한 모든 진단을 포함하는 전체 보고서이거나
마지막 풀 요청과 비교하여 진단 측면에서 아무것도 변경되지 않았음을
나타내는 변경되지 않은 보고서일 수 있습니다.

@since 3.17.0 """

PrepareRenameResult = Union["Range", "__PrepareRenameResult_Type_1", "__PrepareRenameResult_Type_2"]

DocumentSelector = list["DocumentFilter"]
""" 문서 선택기는 하나 또는 여러 문서 필터의 조합입니다.

@sample `let sel:DocumentSelector = [{ language: 'typescript' }, { language: 'json', pattern: '**/tsconfig.json' }]`;

문서 필터로 문자열을 사용하는 것은 @since 3.16.0부터 사용되지 않습니다. """

ProgressToken = Union[int, str]

ChangeAnnotationIdentifier = str
""" 작업 공간 편집과 함께 저장된 변경 주석을 참조하는 식별자입니다. """

WorkspaceDocumentDiagnosticReport = Union[
    "WorkspaceFullDocumentDiagnosticReport",
    "WorkspaceUnchangedDocumentDiagnosticReport",
]
""" 작업 공간 진단 문서 보고서입니다.

@since 3.17.0 """

TextDocumentContentChangeEvent = Union["__TextDocumentContentChangeEvent_Type_1", "__TextDocumentContentChangeEvent_Type_2"]
""" 텍스트 문서 변경을 설명하는 이벤트입니다. 텍스트만 제공되면
문서의 전체 내용으로 간주됩니다. """

MarkedString = Union[str, "__MarkedString_Type_1"]
""" MarkedString은 사람이 읽을 수 있는 텍스트를 렌더링하는 데 사용할 수 있습니다.
마크다운 문자열이거나 언어와 코드 스니펫을 제공하는 코드 블록입니다. 언어 식별자는
GitHub 이슈의 펜스 코드 블록에 있는 선택적 언어 식별자와 의미상 동일합니다.
https://help.github.com/articles/creating-and-highlighting-code-blocks/#syntax-highlighting 참조

언어와 값의 쌍은 마크다운과 동일합니다:
```${language}
${value}
```

마크다운 문자열은 살균 처리됩니다. 즉, html이 이스케이프됩니다.
@deprecated 대신 MarkupContent를 사용하세요. """

DocumentFilter = Union["TextDocumentFilter", "NotebookCellTextDocumentFilter"]
""" 문서 필터는 최상위 텍스트 문서 또는
노트북 셀 문서를 나타냅니다.

@since 3.17.0 - NotebookCellTextDocumentFilter에 대한 제안된 지원. """

LSPObject = dict[str, "LSPAny"]
""" LSP 객체 정의입니다.
@since 3.17.0 """

GlobPattern = Union["Pattern", "RelativePattern"]
""" glob 패턴입니다. 문자열 패턴 또는 상대 패턴입니다.

@since 3.17.0 """

TextDocumentFilter = Union[
    "__TextDocumentFilter_Type_1",
    "__TextDocumentFilter_Type_2",
    "__TextDocumentFilter_Type_3",
]
""" 문서 필터는 {@link TextDocument.languageId 언어}, 리소스의 {@link Uri.scheme 스킴} 또는
{@link TextDocument.fileName 경로}에 적용되는 glob 패턴과 같은 다른 속성으로 문서를 나타냅니다.

Glob 패턴은 다음 구문을 가질 수 있습니다:
- `*`는 경로 세그먼트에서 하나 이상의 문자와 일치합니다.
- `?`는 경로 세그먼트에서 하나의 문자와 일치합니다.
- `**`는 없음을 포함하여 임의의 수의 경로 세그먼트와 일치합니다.
- `{}`는 하위 패턴을 OR 표현식으로 그룹화합니다. (예: `**\u200b/*.{ts,js}`는 모든 TypeScript 및 JavaScript 파일과 일치합니다.)
- `[]`는 경로 세그먼트에서 일치할 문자 범위를 선언합니다. (예: `example.[0-9]`는 `example.0`, `example.1`, ...과 일치합니다.)
- `[!...]`는 경로 세그먼트에서 일치할 문자 범위를 부정합니다. (예: `example.[!0-9]`는 `example.a`, `example.b`와 일치하지만 `example.0`과는 일치하지 않습니다.)

@sample 디스크의 타입스크립트 파일에 적용되는 언어 필터: `{ language: 'typescript', scheme: 'file' }`
@sample 모든 package.json 경로에 적용되는 언어 필터: `{ language: 'json', pattern: '**package.json' }`

@since 3.17.0 """

NotebookDocumentFilter = Union[
    "__NotebookDocumentFilter_Type_1",
    "__NotebookDocumentFilter_Type_2",
    "__NotebookDocumentFilter_Type_3",
]
""" 노트북 문서 필터는 다른 속성으로 노트북 문서를 나타냅니다.
속성은 노트북의 URI와 일치합니다 (문서와 동일).

@since 3.17.0 """

Pattern = str
""" 기본 경로에 상대적인 감시할 glob 패턴입니다. Glob 패턴은 다음 구문을 가질 수 있습니다:
- `*`는 경로 세그먼트에서 하나 이상의 문자와 일치합니다.
- `?`는 경로 세그먼트에서 하나의 문자와 일치합니다.
- `**`는 없음을 포함하여 임의의 수의 경로 세그먼트와 일치합니다.
- `{}`는 조건을 그룹화합니다. (예: `**\u200b/*.{ts,js}`는 모든 TypeScript 및 JavaScript 파일과 일치합니다.)
- `[]`는 경로 세그먼트에서 일치할 문자 범위를 선언합니다. (예: `example.[0-9]`는 `example.0`, `example.1`, ...과 일치합니다.)
- `[!...]`는 경로 세그먼트에서 일치할 문자 범위를 부정합니다. (예: `example.[!0-9]`는 `example.a`, `example.b`와 일치하지만 `example.0`과는 일치하지 않습니다.)

@since 3.17.0 """


class ImplementationParams(TypedDict):
    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    position: "Position"
    """ 텍스트 문서 내의 위치입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class Location(TypedDict):
    """리소스 내의 위치를 나타냅니다. 예: 텍스트 파일 내의 줄."""

    uri: "DocumentUri"
    range: "Range"


class ImplementationRegistrationOptions(TypedDict):
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class TypeDefinitionParams(TypedDict):
    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    position: "Position"
    """ 텍스트 문서 내의 위치입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class TypeDefinitionRegistrationOptions(TypedDict):
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class WorkspaceFolder(TypedDict):
    """클라이언트 내의 작업 공간 폴더입니다."""

    uri: "URI"
    """ 이 작업 공간 폴더와 관련된 URI입니다. """
    name: str
    """ 작업 공간 폴더의 이름입니다. 사용자 인터페이스에서
    이 작업 공간 폴더를 참조하는 데 사용됩니다. """


class DidChangeWorkspaceFoldersParams(TypedDict):
    """`workspace/didChangeWorkspaceFolders` 알림의 매개변수입니다."""

    event: "WorkspaceFoldersChangeEvent"
    """ 실제 작업 공간 폴더 변경 이벤트입니다. """


class ConfigurationParams(TypedDict):
    """구성 요청의 매개변수입니다."""

    items: list["ConfigurationItem"]


class DocumentColorParams(TypedDict):
    """{@link DocumentColorRequest}의 매개변수입니다."""

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class ColorInformation(TypedDict):
    """문서의 색상 범위를 나타냅니다."""

    range: "Range"
    """ 이 색상이 나타나는 문서의 범위입니다. """
    color: "Color"
    """ 이 색상 범위의 실제 색상 값입니다. """


class DocumentColorRegistrationOptions(TypedDict):
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class ColorPresentationParams(TypedDict):
    """{@link ColorPresentationRequest}의 매개변수입니다."""

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    color: "Color"
    """ 표현을 요청할 색상입니다. """
    range: "Range"
    """ 색상이 삽입될 범위입니다. 컨텍스트 역할을 합니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class ColorPresentation(TypedDict):
    label: str
    """ 이 색상 표현의 레이블입니다. 색상 선택기 헤더에
    표시됩니다. 기본적으로 이 색상 표현을 선택할 때 삽입되는
    텍스트이기도 합니다. """
    textEdit: NotRequired["TextEdit"]
    """ 이 색상에 대한 이 표현을 선택할 때 문서에 적용되는
    {@link TextEdit 편집}입니다. `falsy`인 경우 {@link ColorPresentation.label 레이블}이
    사용됩니다. """
    additionalTextEdits: NotRequired[list["TextEdit"]]
    """ 이 색상 표현을 선택할 때 적용되는 추가적인 {@link TextEdit 텍스트 편집}의
    선택적 배열입니다. 편집은 기본 {@link ColorPresentation.textEdit 편집}과
    겹치거나 서로 겹쳐서는 안 됩니다. """


class WorkDoneProgressOptions(TypedDict):
    workDoneProgress: NotRequired[bool]


class TextDocumentRegistrationOptions(TypedDict):
    """일반 텍스트 문서 등록 옵션입니다."""

    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """


class FoldingRangeParams(TypedDict):
    """{@link FoldingRangeRequest}의 매개변수입니다."""

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class FoldingRange(TypedDict):
    """접기 범위를 나타냅니다. 유효하려면 시작 및 끝 줄이 0보다 크고
    문서의 줄 수보다 작아야 합니다. 클라이언트는 유효하지 않은 범위를 무시할 수 있습니다.
    """

    startLine: Uint
    """ 접을 범위의 0부터 시작하는 시작 줄입니다. 접힌 영역은 줄의 마지막 문자 뒤에서 시작됩니다.
    유효하려면 끝이 0 이상이고 문서의 줄 수보다 작아야 합니다. """
    startCharacter: NotRequired[Uint]
    """ 접힌 범위가 시작되는 0부터 시작하는 문자 오프셋입니다. 정의되지 않은 경우 시작 줄의 길이로 기본 설정됩니다. """
    endLine: Uint
    """ 접을 범위의 0부터 시작하는 끝 줄입니다. 접힌 영역은 줄의 마지막 문자로 끝납니다.
    유효하려면 끝이 0 이상이고 문서의 줄 수보다 작아야 합니다. """
    endCharacter: NotRequired[Uint]
    """ 접힌 범위가 끝나기 전의 0부터 시작하는 문자 오프셋입니다. 정의되지 않은 경우 끝 줄의 길이로 기본 설정됩니다. """
    kind: NotRequired["FoldingRangeKind"]
    """ `comment` 또는 `region`과 같은 접기 범위의 종류를 설명합니다. 종류는
    접기 범주를 분류하고 '모든 주석 접기'와 같은 명령에 사용됩니다.
    표준화된 종류의 열거는 {@link FoldingRangeKind}를 참조하세요. """
    collapsedText: NotRequired[str]
    """ 지정된 범위가 축소될 때 클라이언트가 표시해야 하는 텍스트입니다.
    정의되지 않았거나 클라이언트에서 지원하지 않는 경우 클라이언트가 기본값을
    선택합니다.

    @since 3.17.0 """


class FoldingRangeRegistrationOptions(TypedDict):
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class DeclarationParams(TypedDict):
    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    position: "Position"
    """ 텍스트 문서 내의 위치입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class DeclarationRegistrationOptions(TypedDict):
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class SelectionRangeParams(TypedDict):
    """선택 범위 요청에 사용되는 매개변수 리터럴입니다."""

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    positions: list["Position"]
    """ 텍스트 문서 내의 위치입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class SelectionRange(TypedDict):
    """선택 범위는 선택 계층의 일부를 나타냅니다. 선택 범위는
    그것을 포함하는 부모 선택 범위를 가질 수 있습니다.
    """

    range: "Range"
    """ 이 선택 범위의 {@link Range 범위}입니다. """
    parent: NotRequired["SelectionRange"]
    """ 이 범위를 포함하는 부모 선택 범위입니다. 따라서 `parent.range`는 `this.range`를 포함해야 합니다. """


class SelectionRangeRegistrationOptions(TypedDict):
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class WorkDoneProgressCreateParams(TypedDict):
    token: "ProgressToken"
    """ 진행 상황을 보고하는 데 사용할 토큰입니다. """


class WorkDoneProgressCancelParams(TypedDict):
    token: "ProgressToken"
    """ 진행 상황을 보고하는 데 사용할 토큰입니다. """


class CallHierarchyPrepareParams(TypedDict):
    """`textDocument/prepareCallHierarchy` 요청의 매개변수입니다.

    @since 3.16.0
    """

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    position: "Position"
    """ 텍스트 문서 내의 위치입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class CallHierarchyItem(TypedDict):
    """호출 계층 구조의 컨텍스트에서 함수나 생성자와 같은 프로그래밍 구문을
    나타냅니다.

    @since 3.16.0
    """

    name: str
    """ 이 항목의 이름입니다. """
    kind: "SymbolKind"
    """ 이 항목의 종류입니다. """
    tags: NotRequired[list["SymbolTag"]]
    """ 이 항목에 대한 태그입니다. """
    detail: NotRequired[str]
    """ 이 항목에 대한 자세한 내용입니다. 예: 함수의 서명. """
    uri: "DocumentUri"
    """ 이 항목의 리소스 식별자입니다. """
    range: "Range"
    """ 선행/후행 공백을 제외하고 주석 및 코드와 같은 모든 것을 포함하여
    이 심볼을 둘러싸는 범위입니다. """
    selectionRange: "Range"
    """ 이 심볼을 선택하고 표시해야 하는 범위입니다. 예: 함수의 이름.
    {@link CallHierarchyItem.range `range`}에 포함되어야 합니다. """
    data: NotRequired["LSPAny"]
    """ 호출 계층 준비와 들어오는 호출 또는 나가는 호출 요청 사이에
    보존되는 데이터 입력 필드입니다. """


class CallHierarchyRegistrationOptions(TypedDict):
    """정적 또는 동적 등록 중에 사용되는 호출 계층 옵션입니다.

    @since 3.16.0
    """

    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class CallHierarchyIncomingCallsParams(TypedDict):
    """`callHierarchy/incomingCalls` 요청의 매개변수입니다.

    @since 3.16.0
    """

    item: "CallHierarchyItem"
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


CallHierarchyIncomingCall = TypedDict(
    "CallHierarchyIncomingCall",
    {
        # 호출하는 항목입니다.
        "from": "CallHierarchyItem",
        # 호출이 나타나는 범위입니다. 이것은 호출자를 기준으로 합니다.
        # {@link CallHierarchyIncomingCall.from `this.from`}으로 표시됩니다.
        "fromRanges": list["Range"],
    },
)
""" 들어오는 호출을 나타냅니다. 예: 메서드 또는 생성자의 호출자.

@since 3.16.0 """


class CallHierarchyOutgoingCallsParams(TypedDict):
    """`callHierarchy/outgoingCalls` 요청의 매개변수입니다.

    @since 3.16.0
    """

    item: "CallHierarchyItem"
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class CallHierarchyOutgoingCall(TypedDict):
    """나가는 호출을 나타냅니다. 예: 메서드에서 getter를 호출하거나 생성자에서 메서드를 호출하는 등.

    @since 3.16.0
    """

    to: "CallHierarchyItem"
    """ 호출되는 항목입니다. """
    fromRanges: list["Range"]
    """ 이 항목이 호출되는 범위입니다. 이것은 호출자를 기준으로 한 범위입니다.
    예: {@link CallHierarchyItemProvider.provideCallHierarchyOutgoingCalls `provideCallHierarchyOutgoingCalls`}에
    전달된 항목이며 {@link CallHierarchyOutgoingCall.to `this.to`}가 아닙니다. """


class SemanticTokensParams(TypedDict):
    """@since 3.16.0"""

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class SemanticTokens(TypedDict):
    """@since 3.16.0"""

    resultId: NotRequired[str]
    """ 선택적 결과 ID입니다. 제공되고 클라이언트가 델타 업데이트를 지원하는 경우
    클라이언트는 다음 시맨틱 토큰 요청에 결과 ID를 포함합니다.
    그러면 서버는 모든 시맨틱 토큰을 다시 계산하는 대신
    델타를 보낼 수 있습니다. """
    data: list[Uint]
    """ 실제 토큰입니다. """


class SemanticTokensPartialResult(TypedDict):
    """@since 3.16.0"""

    data: list[Uint]


class SemanticTokensRegistrationOptions(TypedDict):
    """@since 3.16.0"""

    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    legend: "SemanticTokensLegend"
    """ 서버에서 사용하는 범례입니다. """
    range: NotRequired[bool | dict]
    """ 서버는 문서의 특정 범위에 대한 시맨틱 토큰 제공을 지원합니다. """
    full: NotRequired[Union[bool, "__SemanticTokensOptions_full_Type_1"]]
    """ 서버는 전체 문서에 대한 시맨틱 토큰 제공을 지원합니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class SemanticTokensDeltaParams(TypedDict):
    """@since 3.16.0"""

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    previousResultId: str
    """ 이전 응답의 결과 ID입니다. 결과 ID는 마지막으로 받은 내용에 따라
    전체 응답 또는 델타 응답을 가리킬 수 있습니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class SemanticTokensDelta(TypedDict):
    """@since 3.16.0"""

    resultId: NotRequired[str]
    edits: list["SemanticTokensEdit"]
    """ 이전 결과를 새 결과로 변환하기 위한 시맨틱 토큰 편집입니다. """


class SemanticTokensDeltaPartialResult(TypedDict):
    """@since 3.16.0"""

    edits: list["SemanticTokensEdit"]


class SemanticTokensRangeParams(TypedDict):
    """@since 3.16.0"""

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    range: "Range"
    """ 시맨틱 토큰이 요청된 범위입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class ShowDocumentParams(TypedDict):
    """문서를 표시하기 위한 매개변수입니다.

    @since 3.16.0
    """

    uri: "URI"
    """ 표시할 문서 uri입니다. """
    external: NotRequired[bool]
    """ 외부 프로그램에서 리소스를 표시할지 나타냅니다.
    예를 들어 기본 웹 브라우저에서 `https://code.visualstudio.com/`을
    표시하려면 `external`을 `true`로 설정합니다. """
    takeFocus: NotRequired[bool]
    """ 문서를 표시하는 편집기가 포커스를 가져와야 하는지 여부를
    나타내는 선택적 속성입니다.
    클라이언트는 외부 프로그램이 시작되면 이 속성을 무시할 수 있습니다. """
    selection: NotRequired["Range"]
    """ 문서가 텍스트 문서인 경우 선택적 선택 범위입니다.
    클라이언트는 외부 프로그램이 시작되거나 파일이 텍스트 파일이 아닌 경우
    속성을 무시할 수 있습니다. """


class ShowDocumentResult(TypedDict):
    """showDocument 요청의 결과입니다.

    @since 3.16.0
    """

    success: bool
    """ 표시가 성공했는지 여부를 나타내는 부울 값입니다. """


class LinkedEditingRangeParams(TypedDict):
    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    position: "Position"
    """ 텍스트 문서 내의 위치입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class LinkedEditingRanges(TypedDict):
    """연결된 편집 범위 요청의 결과입니다.

    @since 3.16.0
    """

    ranges: list["Range"]
    """ 함께 편집할 수 있는 범위 목록입니다. 범위는
    동일한 길이를 가져야 하며 동일한 텍스트 내용을 포함해야 합니다. 범위는 겹칠 수 없습니다. """
    wordPattern: NotRequired[str]
    """ 주어진 범위에 대한 유효한 내용을 설명하는 선택적 단어 패턴(정규식)입니다.
    패턴이 제공되지 않으면 클라이언트 구성의 단어 패턴이 사용됩니다. """


class LinkedEditingRangeRegistrationOptions(TypedDict):
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class CreateFilesParams(TypedDict):
    """사용자 시작 파일 생성에 대한 알림/요청으로 전송된 매개변수입니다.

    @since 3.16.0
    """

    files: list["FileCreate"]
    """ 이 작업에서 생성된 모든 파일/폴더의 배열입니다. """


class WorkspaceEdit(TypedDict):
    """작업 공간 편집은 작업 공간에서 관리되는 많은 리소스에 대한 변경 사항을 나타냅니다. 편집은
    `changes` 또는 `documentChanges`를 제공해야 합니다. documentChanges가 있는 경우
    클라이언트가 버전이 지정된 문서 편집을 처리할 수 있으면 `changes`보다 우선적으로 적용됩니다.

    버전 3.13.0부터 작업 공간 편집에는 리소스 작업도 포함될 수 있습니다. 리소스 작업이
    있는 경우 클라이언트는 제공된 순서대로 작업을 실행해야 합니다. 따라서 작업 공간 편집은
    예를 들어 다음과 같은 두 가지 변경 사항으로 구성될 수 있습니다.
    (1) a.txt 파일 생성 및 (2) a.txt 파일에 텍스트를 삽입하는 텍스트 문서 편집.

    잘못된 시퀀스(예: (1) a.txt 파일 삭제 및 (2) a.txt 파일에 텍스트 삽입)는
    작업 실패를 유발합니다. 클라이언트가 실패에서 복구하는 방법은
    클라이언트 기능 `workspace.workspaceEdit.failureHandling`에 의해 설명됩니다.
    """

    changes: NotRequired[dict["DocumentUri", list["TextEdit"]]]
    """ 기존 리소스에 대한 변경 사항을 보유합니다. """
    documentChanges: NotRequired[list[Union["TextDocumentEdit", "CreateFile", "RenameFile", "DeleteFile"]]]
    """ 클라이언트 기능 `workspace.workspaceEdit.resourceOperations`에 따라 문서 변경은
    각 텍스트 문서 편집이 특정 버전의 텍스트 문서를 다루는 n개의 다른 텍스트 문서에 대한 변경을 표현하기 위한
    `TextDocumentEdit` 배열이거나, 생성, 이름 변경 및 삭제 파일/폴더 작업과 혼합된
    위의 `TextDocumentEdit`를 포함할 수 있습니다.

    클라이언트가 버전이 지정된 문서 편집을 지원하는지 여부는
    `workspace.workspaceEdit.documentChanges` 클라이언트 기능을 통해 표현됩니다.

    클라이언트가 `documentChanges`나 `workspace.workspaceEdit.resourceOperations`를 지원하지 않는 경우
    `changes` 속성을 사용하는 일반 `TextEdit`만 지원됩니다. """
    changeAnnotations: NotRequired[dict["ChangeAnnotationIdentifier", "ChangeAnnotation"]]
    """ `AnnotatedTextEdit` 또는 생성, 이름 변경 및 삭제 파일/폴더 작업에서 참조할 수 있는
    변경 주석 맵입니다.

    클라이언트가 이 속성을 존중하는지 여부는 클라이언트 기능 `workspace.changeAnnotationSupport`에 따라 다릅니다.

    @since 3.16.0 """


class FileOperationRegistrationOptions(TypedDict):
    """파일 작업 등록 옵션입니다.

    @since 3.16.0
    """

    filters: list["FileOperationFilter"]
    """ 실제 필터입니다. """


class RenameFilesParams(TypedDict):
    """사용자 시작 파일 이름 변경에 대한 알림/요청으로 전송된 매개변수입니다.

    @since 3.16.0
    """

    files: list["FileRename"]
    """ 이 작업에서 이름이 변경된 모든 파일/폴더의 배열입니다. 폴더 이름이 변경되면
    폴더만 포함되고 하위 항목은 포함되지 않습니다. """


class DeleteFilesParams(TypedDict):
    """사용자 시작 파일 삭제에 대한 알림/요청으로 전송된 매개변수입니다.

    @since 3.16.0
    """

    files: list["FileDelete"]
    """ 이 작업에서 삭제된 모든 파일/폴더의 배열입니다. """


class MonikerParams(TypedDict):
    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    position: "Position"
    """ 텍스트 문서 내의 위치입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class Moniker(TypedDict):
    """LSIF 0.5 모니커 정의와 일치하는 모니커 정의입니다.

    @since 3.16.0
    """

    scheme: str
    """ 모니커의 체계입니다. 예: tsc 또는 .Net """
    identifier: str
    """ 모니커의 식별자입니다. 값은 LSIF에서 불투명하지만
    스키마 소유자는 원하는 경우 구조를 정의할 수 있습니다. """
    unique: "UniquenessLevel"
    """ 모니커가 고유한 범위입니다. """
    kind: NotRequired["MonikerKind"]
    """ 알려진 경우 모니커 종류입니다. """


class MonikerRegistrationOptions(TypedDict):
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """


class TypeHierarchyPrepareParams(TypedDict):
    """`textDocument/prepareTypeHierarchy` 요청의 매개변수입니다.

    @since 3.17.0
    """

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    position: "Position"
    """ 텍스트 문서 내의 위치입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class TypeHierarchyItem(TypedDict):
    """@since 3.17.0"""

    name: str
    """ 이 항목의 이름입니다. """
    kind: "SymbolKind"
    """ 이 항목의 종류입니다. """
    tags: NotRequired[list["SymbolTag"]]
    """ 이 항목에 대한 태그입니다. """
    detail: NotRequired[str]
    """ 이 항목에 대한 자세한 내용입니다. 예: 함수의 서명. """
    uri: "DocumentUri"
    """ 이 항목의 리소스 식별자입니다. """
    range: "Range"
    """ 선행/후행 공백을 제외하고 주석 및 코드와 같은 모든 것을 포함하여
    이 심볼을 둘러싸는 범위입니다. """
    selectionRange: "Range"
    """ 이 심볼을 선택하고 표시해야 하는 범위입니다.
    예: 함수의 이름. {@link TypeHierarchyItem.range `range`}에
    포함되어야 합니다. """
    data: NotRequired["LSPAny"]
    """ 타입 계층 준비와 상위 타입 또는 하위 타입 요청 사이에
    보존되는 데이터 입력 필드입니다. 서버에서 타입 계층을
    식별하는 데 사용될 수도 있으며, 상위 타입 및 하위 타입 확인 성능을
    향상시키는 데 도움이 될 수 있습니다. """


class TypeHierarchyRegistrationOptions(TypedDict):
    """정적 또는 동적 등록 중에 사용되는 타입 계층 옵션입니다.

    @since 3.17.0
    """

    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class TypeHierarchySupertypesParams(TypedDict):
    """`typeHierarchy/supertypes` 요청의 매개변수입니다.

    @since 3.17.0
    """

    item: "TypeHierarchyItem"
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class TypeHierarchySubtypesParams(TypedDict):
    """`typeHierarchy/subtypes` 요청의 매개변수입니다.

    @since 3.17.0
    """

    item: "TypeHierarchyItem"
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class InlineValueParams(TypedDict):
    """인라인 값 요청에 사용되는 매개변수 리터럴입니다.

    @since 3.17.0
    """

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    range: "Range"
    """ 인라인 값을 계산해야 하는 문서 범위입니다. """
    context: "InlineValueContext"
    """ 인라인 값이 요청된 컨텍스트에 대한 추가 정보입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class InlineValueRegistrationOptions(TypedDict):
    """정적 또는 동적 등록 중에 사용되는 인라인 값 옵션입니다.

    @since 3.17.0
    """

    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class InlayHintParams(TypedDict):
    """인레이 힌트 요청에 사용되는 매개변수 리터럴입니다.

    @since 3.17.0
    """

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    range: "Range"
    """ 인레이 힌트를 계산해야 하는 문서 범위입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class InlayHint(TypedDict):
    """인레이 힌트 정보입니다.

    @since 3.17.0
    """

    position: "Position"
    """ 이 힌트의 위치입니다. """
    label: str | list["InlayHintLabelPart"]
    """ 이 힌트의 레이블입니다. 사람이 읽을 수 있는 문자열 또는
    InlayHintLabelPart 레이블 부분의 배열입니다.

    *참고* 문자열이나 레이블 부분은 비어 있을 수 없습니다. """
    kind: NotRequired["InlayHintKind"]
    """ 이 힌트의 종류입니다. 생략하면 클라이언트가
    합리적인 기본값으로 대체해야 합니다. """
    textEdits: NotRequired[list["TextEdit"]]
    """ 이 인레이 힌트를 수락할 때 수행되는 선택적 텍스트 편집입니다.

    *참고* 편집은 인레이 힌트(또는 가장 가까운 변형)가 이제
    문서의 일부가 되고 인레이 힌트 자체가 더 이상 사용되지 않도록
    문서를 변경할 것으로 예상됩니다. """
    tooltip: NotRequired[Union[str, "MarkupContent"]]
    """ 이 항목 위로 마우스를 가져가면 표시되는 툴팁 텍스트입니다. """
    paddingLeft: NotRequired[bool]
    """ 힌트 앞에 패딩을 렌더링합니다.

    참고: 패딩은 힌트 자체의 배경색이 아닌 편집기의
    배경색을 사용해야 합니다. 즉, 패딩을 사용하여
    인레이 힌트를 시각적으로 정렬/분리할 수 있습니다. """
    paddingRight: NotRequired[bool]
    """ 힌트 뒤에 패딩을 렌더링합니다.

    참고: 패딩은 힌트 자체의 배경색이 아닌 편집기의
    배경색을 사용해야 합니다. 즉, 패딩을 사용하여
    인레이 힌트를 시각적으로 정렬/분리할 수 있습니다. """
    data: NotRequired["LSPAny"]
    """ `textDocument/inlayHint`와 `inlayHint/resolve` 요청 사이에
    인레이 힌트에 보존되는 데이터 입력 필드입니다. """


class InlayHintRegistrationOptions(TypedDict):
    """정적 또는 동적 등록 중에 사용되는 인레이 힌트 옵션입니다.

    @since 3.17.0
    """

    resolveProvider: NotRequired[bool]
    """ 서버는 인레이 힌트 항목에 대한 추가 정보를
    확인하는 지원을 제공합니다. """
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class DocumentDiagnosticParams(TypedDict):
    """문서 진단 요청의 매개변수입니다.

    @since 3.17.0
    """

    textDocument: "TextDocumentIdentifier"
    """ 텍스트 문서입니다. """
    identifier: NotRequired[str]
    """ 등록 중에 제공된 추가 식별자입니다. """
    previousResultId: NotRequired[str]
    """ 제공된 경우 이전 응답의 결과 ID입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class DocumentDiagnosticReportPartialResult(TypedDict):
    """문서 진단 보고서의 부분 결과입니다.

    @since 3.17.0
    """

    relatedDocuments: dict[
        "DocumentUri",
        Union["FullDocumentDiagnosticReport", "UnchangedDocumentDiagnosticReport"],
    ]


class DiagnosticServerCancellationData(TypedDict):
    """진단 요청에서 반환된 취소 데이터입니다.

    @since 3.17.0
    """

    retriggerRequest: bool


class DiagnosticRegistrationOptions(TypedDict):
    """진단 등록 옵션입니다.

    @since 3.17.0
    """

    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    identifier: NotRequired[str]
    """ 클라이언트가 진단을 관리하는 데 사용하는 선택적 식별자입니다. """
    interFileDependencies: bool
    """ 언어에 파일 간 종속성이 있는지 여부입니다. 즉,
    한 파일의 코드를 편집하면 다른 파일에서 다른 진단 세트가
    발생할 수 있습니다. 파일 간 종속성은 대부분의 프로그래밍 언어에서
    일반적이며 일반적으로 린터에서는 드뭅니다. """
    workspaceDiagnostics: bool
    """ 서버는 작업 공간 진단도 지원합니다. """
    id: NotRequired[str]
    """ 요청을 등록하는 데 사용되는 ID입니다. ID는 요청을 다시 등록 취소하는 데
    사용할 수 있습니다. Registration#id도 참조하세요. """


class WorkspaceDiagnosticParams(TypedDict):
    """작업 공간 진단 요청의 매개변수입니다.

    @since 3.17.0
    """

    identifier: NotRequired[str]
    """ 등록 중에 제공된 추가 식별자입니다. """
    previousResultIds: list["PreviousResultId"]
    """ 현재 알려진 진단 보고서와 이전 결과 ID입니다. """
    workDoneToken: NotRequired["ProgressToken"]
    """ 서버가 작업 진행 상황을 보고하는 데 사용할 수 있는 선택적 토큰입니다. """
    partialResultToken: NotRequired["ProgressToken"]
    """ 서버가 부분 결과(예: 스트리밍)를 클라이언트에 보고하는 데 사용할 수 있는 선택적 토큰입니다. """


class WorkspaceDiagnosticReport(TypedDict):
    """작업 공간 진단 보고서입니다.

    @since 3.17.0
    """

    items: list["WorkspaceDocumentDiagnosticReport"]


class WorkspaceDiagnosticReportPartialResult(TypedDict):
    """작업 공간 진단 보고서의 부분 결과입니다.

    @since 3.17.0
    """

    items: list["WorkspaceDocumentDiagnosticReport"]


class DidOpenNotebookDocumentParams(TypedDict):
    """노트북 문서 열림 알림으로 전송된 매개변수입니다.

    @since 3.17.0
    """

    notebookDocument: "NotebookDocument"
    """ 열린 노트북 문서입니다. """
    cellTextDocuments: list["TextDocumentItem"]
    """ 노트북 셀의 내용을 나타내는 텍스트 문서입니다. """


class DidChangeNotebookDocumentParams(TypedDict):
    """노트북 문서 변경 알림으로 전송된 매개변수입니다.

    @since 3.17.0
    """

    notebookDocument: "VersionedNotebookDocumentIdentifier"
    """ 변경된 노트북 문서입니다. 버전 번호는
    제공된 모든 변경 사항이 적용된 후의 버전을 가리킵니다. 셀의
    텍스트 문서 내용만 변경되는 경우 노트북 버전이
    반드시 변경될 필요는 없습니다. """
    change: "NotebookDocumentChangeEvent"
    """ 노트북 문서에 대한 실제 변경 사항입니다.

    변경 사항은 노트북 문서에 대한 단일 상태 변경을 설명합니다.
    따라서 상태 S의 노트북에 대해 두 가지 변경 사항 c1(배열 인덱스 0)과
    c2(배열 인덱스 1)가 있는 경우 c1은 노트북을 S에서 S'로 이동하고
    c2는 S'에서 S''로 이동합니다. 따라서 c1은 상태 S에서 계산되고
    c2는 상태 S'에서 계산됩니다.

    변경 이벤트를 사용하여 노트북의 내용을 미러링하려면 다음 접근 방식을 사용하세요:
    - 동일한 초기 내용으로 시작합니다.
    - 받는 순서대로 'notebookDocument/didChange' 알림을 적용합니다.
    - 단일 알림의 `NotebookChangeEvent`를 받는 순서대로 적용합니다. """


class DidSaveNotebookDocumentParams(TypedDict):
    """노트북 문서 저장 알림으로 전송된 매개변수입니다.

    @since 3.17.0
    """

    notebookDocument: "NotebookDocumentIdentifier"
    """ 저장된 노트북 문서입니다. """


class DidCloseNotebookDocumentParams(TypedDict):
    """노트북 문서 닫힘 알림으로 전송된 매개변수입니다.

    @since 3.17.0
    """

    notebookDocument: "NotebookDocumentIdentifier"
    """ 닫힌 노트북 문서입니다. """
    cellTextDocuments: list["TextDocumentIdentifier"]
    """ 닫힌 노트북 셀의 내용을 나타내는 텍스트 문서입니다. """


class RegistrationParams(TypedDict):
    registrations: list["Registration"]


class UnregistrationParams(TypedDict):
    unregisterations: list["Unregistration"]


class InitializeParams(TypedDict):
    processId: int | None
    """ 서버를 시작한 부모 프로세스의 프로세스 ID입니다.

    프로세스가 다른 프로세스에 의해 시작되지 않은 경우 `null`입니다.
    부모 프로세스가 활성 상태가 아니면 서버는 종료해야 합니다. """
    clientInfo: NotRequired["___InitializeParams_clientInfo_Type_1"]
    """ 클라이언트에 대한 정보입니다.

    @since 3.15.0 """
    locale: NotRequired[str]
    """ 클라이언트가 현재 사용자 인터페이스를 표시하는 로케일입니다.
    이것은 반드시 운영 체제의 로케일일 필요는 없습니다.

    값의 구문으로 IETF 언어 태그를 사용합니다.
    (https://en.wikipedia.org/wiki/IETF_language_tag 참조)

    @since 3.16.0 """
    rootPath: NotRequired[str | None]
    """ 작업 공간의 rootPath입니다. 폴더가 열려 있지 않으면
    null입니다.

    @deprecated rootUri를 선호합니다. """
    rootUri: Union["DocumentUri", None]
    """ 작업 공간의 rootUri입니다. 폴더가 열려 있지 않으면
    null입니다. `rootPath`와 `rootUri`가 모두 설정된 경우
    `rootUri`가 우선합니다.

    @deprecated workspaceFolders를 선호합니다. """
    capabilities: "ClientCapabilities"
    """ 클라이언트(편집기 또는 도구)에서 제공하는 기능입니다. """
    initializationOptions: NotRequired["LSPAny"]
    """ 사용자가 제공한 초기화 옵션입니다. """
    trace: NotRequired["TraceValues"]
    """ 초기 추적 설정입니다. 생략하면 추적이 비활성화됩니다('off'). """
    workspaceFolders: NotRequired[list["WorkspaceFolder"] | None]
    """ 서버가 시작될 때 클라이언트에 구성된 작업 공간 폴더입니다.

    이 속성은 클라이언트가 작업 공간 폴더를 지원하는 경우에만 사용할 수 있습니다.
    클라이언트가 작업 공간 폴더를 지원하지만 구성된 폴더가 없는 경우
    `null`일 수 있습니다.

    @since 3.6.0 """


class InitializeResult(TypedDict):
    """초기화 요청에서 반환된 결과입니다."""

    capabilities: "ServerCapabilities"
    """ 언어 서버가 제공하는 기능입니다. """
    serverInfo: NotRequired["__InitializeResult_serverInfo_Type_1"]
    """ 서버에 대한 정보입니다.

    @since 3.15.0 """


class InitializeError(TypedDict):
    """
    초기화 요청이 실패한 경우 ResponseError의 데이터 타입입니다.
    """

    retry: bool
    """ 클라이언트가 다음 재시도 논리를 실행할지 여부를 나타냅니다:
    (1) ResponseError에서 제공한 메시지를 사용자에게 표시합니다.
    (2) 사용자가 재시도 또는 취소를 선택합니다.
    (3) 사용자가 재시도를 선택하면 초기화 메서드가 다시 전송됩니다. """


class InitializedParams(TypedDict):
    pass


class DidChangeConfigurationParams(TypedDict):
    """구성 변경 알림의 매개변수입니다."""

    settings: "LSPAny"
    """ 실제로 변경된 설정입니다. """


class DidChangeConfigurationRegistrationOptions(TypedDict):
    section: NotRequired[str | list[str]]


class ShowMessageParams(TypedDict):
    """알림 메시지의 매개변수입니다."""

    type: "MessageType"
    """ 메시지 타입입니다. {@link MessageType} 참조 """
    message: str
    """ 실제 메시지입니다. """


class ShowMessageRequestParams(TypedDict):
    type: "MessageType"
    """ 메시지 타입입니다. {@link MessageType} 참조 """
    message: str
    """ 실제 메시지입니다. """
    actions: NotRequired[list["MessageActionItem"]]
    """ 표시할 메시지 액션 항목입니다. """


class MessageActionItem(TypedDict):
    title: str
    """ '재시도', '로그 열기' 등과 같은 짧은 제목입니다. """


class LogMessageParams(TypedDict):
    """로그 메시지 매개변수입니다."""

    type: "MessageType"
    """ 메시지 타입입니다. {@link MessageType} 참조 """
    message: str
    """ 실제 메시지입니다. """


class DidOpenTextDocumentParams(TypedDict):
    """텍스트 문서 열림 알림으로 전송된 매개변수입니다."""

    textDocument: "TextDocumentItem"
    """ 열린 문서입니다. """


class DidChangeTextDocumentParams(TypedDict):
    """텍스트 문서 변경 알림의 매개변수입니다."""

    textDocument: "VersionedTextDocumentIdentifier"
    """ 변경된 문서입니다. 버전 번호는
    제공된 모든 내용 변경이 적용된 후의 버전을 가리킵니다. """
    contentChanges: list["TextDocumentContentChangeEvent"]
    """ 실제 내용 변경입니다. 내용 변경은 문서에 대한
    단일 상태 변경을 설명합니다. 따라서 상태 S의 문서에 대해
    두 가지 내용 변경 c1(배열 인덱스 0)과 c2(배열 인덱스 1)가 있는 경우
    c1은 문서를 S에서 S'로 이동하고 c2는 S'에서 S''로 이동합니다.
    따라서 c1은 상태 S에서 계산되고 c2는 상태 S'에서 계산됩니다.

    변경 이벤트를 사용하여 문서의 내용을 미러링하려면 다음 접근 방식을 사용하세요:
    - 동일한 초기 내용으로 시작합니다.
    - 받는 순서대로 'textDocument/didChange' 알림을 적용합니다.
    - 단일 알림의 `TextDocumentContentChangeEvent`를 받는 순서대로 적용합니다. """


class TextDocumentChangeRegistrationOptions(TypedDict):
    """텍스트 문서 변경 이벤트에 등록할 때 사용할 옵션을 설명합니다."""

    syncKind: "TextDocumentSyncKind"
    """ 문서가 서버에 동기화되는 방법입니다. """
    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """


class DidCloseTextDocumentParams(TypedDict):
    """텍스트 문서 닫힘 알림으로 전송된 매개변수입니다."""

    textDocument: "TextDocumentIdentifier"
    """ 닫힌 문서입니다. """


class DidSaveTextDocumentParams(TypedDict):
    """텍스트 문서 저장 알림으로 전송된 매개변수입니다."""

    textDocument: "TextDocumentIdentifier"
    """ 저장된 문서입니다. """
    text: NotRequired[str]
    """ 저장 시 선택적 내용입니다. 저장 알림이 요청될 때
    includeText 값에 따라 다릅니다. """


class TextDocumentSaveRegistrationOptions(TypedDict):
    """저장 등록 옵션입니다."""

    documentSelector: Union["DocumentSelector", None]
    """ 등록 범위를 식별하는 문서 선택기입니다. null로 설정하면
    클라이언트 측에서 제공된 문서 선택기가 사용됩니다. """
    includeText: NotRequired[bool]
    """ 클라이언트는 저장 시 내용을 포함해야 합니다. """


class WillSaveTextDocumentParams(TypedDict):
    """텍스트 문서 저장 전 알림으로 전송된 매개변수입니다."""

    textDocument: "TextDocumentIdentifier"
    """ 저장될 문서입니다. """
    reason: "TextDocumentSaveReason"
    """ 'TextDocumentSaveReason'입니다. """


class TextEdit(TypedDict):
    """텍스트 문서에 적용할 수 있는 텍스트 편집입니다."""

    range: "Range"
    """ 조작할 텍스트 문서의 범위입니다. 텍스트를
    문서에 삽입하려면 시작 === 끝인 범위를 만듭니다. """