"""
solidlsp/ls_request.py - 언어 서버 요청(Request) 래퍼

이 파일은 `SolidLanguageServerHandler`를 통해 언어 서버에 동기적인 요청을 보내기 위한
편의 래퍼(wrapper) 클래스인 `LanguageServerRequest`를 정의합니다.
`lsp_requests.py`의 비동기(async) 인터페이스와 달리, 이 클래스의 메서드들은
서버로부터 응답이 올 때까지 블로킹됩니다.

주요 클래스:
- LanguageServerRequest: 각 LSP 요청에 해당하는 동기 메서드들을 제공합니다.
  내부적으로 `SolidLanguageServerHandler.send_request`를 호출합니다.

아키텍처 노트:
- 이 클래스는 `lsp_requests.py`와 유사한 구조를 가지지만, `async` 키워드가 없습니다.
- 각 메서드는 LSP 사양에 정의된 요청의 이름과 파라미터 타입을 따르며,
  `_send_request` 헬퍼 메서드를 통해 실제 요청을 전송합니다.
- 이를 통해 `SolidLanguageServer`의 사용자는 LSP의 복잡한 비동기 통신을 신경 쓰지 않고,
  간단한 메서드 호출만으로 언어 서버의 기능을 사용할 수 있습니다.
"""

from typing import TYPE_CHECKING, Any, Union

from solidlsp.lsp_protocol_handler import lsp_types

if TYPE_CHECKING:
    from .ls_handler import SolidLanguageServerHandler


class LanguageServerRequest:
    def __init__(self, handler: "SolidLanguageServerHandler"):
        self.handler = handler

    def _send_request(self, method: str, params: Any | None = None) -> Any:
        return self.handler.send_request(method, params)

    def implementation(self, params: lsp_types.ImplementationParams) -> Union["lsp_types.Definition", list["lsp_types.LocationLink"], None]:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 구현 위치를 확인하기 위한 요청입니다.

        요청 매개변수는 [TextDocumentPositionParams] 타입이며,
        응답은 {@link Definition} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/implementation", params)

    def type_definition(
        self, params: lsp_types.TypeDefinitionParams
    ) -> Union["lsp_types.Definition", list["lsp_types.LocationLink"], None]:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 타입 정의 위치를 확인하기 위한 요청입니다.

        요청 매개변수는 [TextDocumentPositionParams] 타입이며,
        응답은 {@link Definition} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/typeDefinition", params)

    def document_color(self, params: lsp_types.DocumentColorParams) -> list["lsp_types.ColorInformation"]:
        """
        주어진 텍스트 문서에서 발견된 모든 색상 심볼을 나열하기 위한 요청입니다.

        요청 매개변수는 {@link DocumentColorParams} 타입이며,
        응답은 {@link ColorInformation ColorInformation[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/documentColor", params)

    def color_presentation(self, params: lsp_types.ColorPresentationParams) -> list["lsp_types.ColorPresentation"]:
        """
        색상에 대한 모든 표현을 나열하기 위한 요청입니다.

        요청 매개변수는 {@link ColorPresentationParams} 타입이며,
        응답은 {@link ColorInformation ColorInformation[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/colorPresentation", params)

    def folding_range(self, params: lsp_types.FoldingRangeParams) -> list["lsp_types.FoldingRange"] | None:
        """
        문서의 접기 범위를 제공하기 위한 요청입니다.

        요청 매개변수는 {@link FoldingRangeParams} 타입이며,
        응답은 {@link FoldingRangeList} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/foldingRange", params)

    def declaration(self, params: lsp_types.DeclarationParams) -> Union["lsp_types.Declaration", list["lsp_types.LocationLink"], None]:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 타입 정의 위치를 확인하기 위한 요청입니다.

        요청 매개변수는 [TextDocumentPositionParams] 타입이며,
        응답은 {@link Declaration} 타입, {@link DeclarationLink}의 타입 배열 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/declaration", params)

    def selection_range(self, params: lsp_types.SelectionRangeParams) -> list["lsp_types.SelectionRange"] | None:
        """
        문서의 선택 범위를 제공하기 위한 요청입니다.

        요청 매개변수는 {@link SelectionRangeParams} 타입이며,
        응답은 {@link SelectionRange SelectionRange[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/selectionRange", params)

    def prepare_call_hierarchy(self, params: lsp_types.CallHierarchyPrepareParams) -> list["lsp_types.CallHierarchyItem"] | None:
        """
        주어진 위치의 문서에서 `CallHierarchyItem`을 반환하기 위한 요청입니다.
        들어오거나 나가는 호출 계층 구조의 입력으로 사용될 수 있습니다.

        @since 3.16.0
        """
        return self._send_request("textDocument/prepareCallHierarchy", params)

    def incoming_calls(self, params: lsp_types.CallHierarchyIncomingCallsParams) -> list["lsp_types.CallHierarchyIncomingCall"] | None:
        """
        주어진 `CallHierarchyItem`에 대한 들어오는 호출을 확인하기 위한 요청입니다.

        @since 3.16.0
        """
        return self._send_request("callHierarchy/incomingCalls", params)

    def outgoing_calls(self, params: lsp_types.CallHierarchyOutgoingCallsParams) -> list["lsp_types.CallHierarchyOutgoingCall"] | None:
        """
        주어진 `CallHierarchyItem`에 대한 나가는 호출을 확인하기 위한 요청입니다.

        @since 3.16.0
        """
        return self._send_request("callHierarchy/outgoingCalls", params)

    def semantic_tokens_full(self, params: lsp_types.SemanticTokensParams) -> Union["lsp_types.SemanticTokens", None]:
        """@since 3.16.0"""
        return self._send_request("textDocument/semanticTokens/full", params)

    def semantic_tokens_delta(
        self, params: lsp_types.SemanticTokensDeltaParams
    ) -> Union["lsp_types.SemanticTokens", "lsp_types.SemanticTokensDelta", None]:
        """@since 3.16.0"""
        return self._send_request("textDocument/semanticTokens/full/delta", params)

    def semantic_tokens_range(self, params: lsp_types.SemanticTokensRangeParams) -> Union["lsp_types.SemanticTokens", None]:
        """@since 3.16.0"""
        return self._send_request("textDocument/semanticTokens/range", params)

    def linked_editing_range(self, params: lsp_types.LinkedEditingRangeParams) -> Union["lsp_types.LinkedEditingRanges", None]:
        """
        함께 편집할 수 있는 범위를 제공하기 위한 요청입니다.

        @since 3.16.0
        """
        return self._send_request("textDocument/linkedEditingRange", params)

    def will_create_files(self, params: lsp_types.CreateFilesParams) -> Union["lsp_types.WorkspaceEdit", None]:
        """
        파일 생성 요청은 클라이언트 내에서 생성이 트리거되는 한, 파일이 실제로 생성되기 전에
        클라이언트에서 서버로 전송됩니다.

        @since 3.16.0
        """
        return self._send_request("workspace/willCreateFiles", params)

    def will_rename_files(self, params: lsp_types.RenameFilesParams) -> Union["lsp_types.WorkspaceEdit", None]:
        """
        파일 이름 변경 요청은 클라이언트 내에서 이름 변경이 트리거되는 한, 파일 이름이 실제로 변경되기 전에
        클라이언트에서 서버로 전송됩니다.

        @since 3.16.0
        """
        return self._send_request("workspace/willRenameFiles", params)

    def will_delete_files(self, params: lsp_types.DeleteFilesParams) -> Union["lsp_types.WorkspaceEdit", None]:
        """
        파일 삭제 알림은 클라이언트 내에서 파일이 삭제되었을 때
        클라이언트에서 서버로 전송됩니다.

        @since 3.16.0
        """
        return self._send_request("workspace/willDeleteFiles", params)

    def moniker(self, params: lsp_types.MonikerParams) -> list["lsp_types.Moniker"] | None:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 모니커를 가져오기 위한 요청입니다.
        요청 매개변수는 {@link TextDocumentPositionParams} 타입이며,
        응답은 {@link Moniker Moniker[]} 타입 또는 `null`입니다.
        """
        return self._send_request("textDocument/moniker", params)

    def prepare_type_hierarchy(self, params: lsp_types.TypeHierarchyPrepareParams) -> list["lsp_types.TypeHierarchyItem"] | None:
        """
        주어진 위치의 문서에서 `TypeHierarchyItem`을 반환하기 위한 요청입니다.
        하위 타입 또는 상위 타입 계층 구조의 입력으로 사용될 수 있습니다.

        @since 3.17.0
        """
        return self._send_request("textDocument/prepareTypeHierarchy", params)

    def type_hierarchy_supertypes(self, params: lsp_types.TypeHierarchySupertypesParams) -> list["lsp_types.TypeHierarchyItem"] | None:
        """
        주어진 `TypeHierarchyItem`에 대한 상위 타입을 확인하기 위한 요청입니다.

        @since 3.17.0
        """
        return self._send_request("typeHierarchy/supertypes", params)

    def type_hierarchy_subtypes(self, params: lsp_types.TypeHierarchySubtypesParams) -> list["lsp_types.TypeHierarchyItem"] | None:
        """
        주어진 `TypeHierarchyItem`에 대한 하위 타입을 확인하기 위한 요청입니다.

        @since 3.17.0
        """
        return self._send_request("typeHierarchy/subtypes", params)

    def inline_value(self, params: lsp_types.InlineValueParams) -> list["lsp_types.InlineValue"] | None:
        """
        문서의 인라인 값을 제공하기 위한 요청입니다. 요청 매개변수는
        {@link InlineValueParams} 타입이며, 응답은
        {@link InlineValue InlineValue[]} 타입 또는 이를 resolve하는 Thenable입니다.

        @since 3.17.0
        """
        return self._send_request("textDocument/inlineValue", params)

    def inlay_hint(self, params: lsp_types.InlayHintParams) -> list["lsp_types.InlayHint"] | None:
        """
        문서의 인레이 힌트를 제공하기 위한 요청입니다. 요청 매개변수는
        {@link InlayHintsParams} 타입이며, 응답은
        {@link InlayHint InlayHint[]} 타입 또는 이를 resolve하는 Thenable입니다.

        @since 3.17.0
        """
        return self._send_request("textDocument/inlayHint", params)

    def resolve_inlay_hint(self, params: lsp_types.InlayHint) -> "lsp_types.InlayHint":
        """
        인레이 힌트에 대한 추가 속성을 확인하기 위한 요청입니다.
        요청 매개변수는 {@link InlayHint} 타입이며, 응답은
        {@link InlayHint} 타입 또는 이를 resolve하는 Thenable입니다.

        @since 3.17.0
        """
        return self._send_request("inlayHint/resolve", params)

    def text_document_diagnostic(self, params: lsp_types.DocumentDiagnosticParams) -> "lsp_types.DocumentDiagnosticReport":
        """
        문서 진단 요청 정의입니다.

        @since 3.17.0
        """
        return self._send_request("textDocument/diagnostic", params)

    def workspace_diagnostic(self, params: lsp_types.WorkspaceDiagnosticParams) -> "lsp_types.WorkspaceDiagnosticReport":
        """
        작업 공간 진단 요청 정의입니다.

        @since 3.17.0
        """
        return self._send_request("workspace/diagnostic", params)

    def initialize(self, params: lsp_types.InitializeParams) -> "lsp_types.InitializeResult":
        """
        초기화 요청은 클라이언트에서 서버로 전송됩니다.
        서버 시작 후 요청으로 한 번 전송됩니다.
        요청 매개변수는 {@link InitializeParams} 타입이며,
        응답은 {@link InitializeResult} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("initialize", params)

    def shutdown(self) -> None:
        """
        종료 요청은 클라이언트에서 서버로 전송됩니다.
        클라이언트가 서버를 종료하기로 결정했을 때 한 번 전송됩니다.
        종료 요청 후 전송되는 유일한 알림은 exit 이벤트입니다.
        """
        return self._send_request("shutdown")

    def will_save_wait_until(self, params: lsp_types.WillSaveTextDocumentParams) -> list["lsp_types.TextEdit"] | None:
        """
        문서 저장 전 요청은 문서가 실제로 저장되기 전에 클라이언트에서 서버로 전송됩니다.
        요청은 저장되기 전에 텍스트 문서에 적용될 TextEdits 배열을 반환할 수 있습니다. 클라이언트는
        텍스트 편집 계산에 너무 오래 걸리거나 서버가 이 요청에 지속적으로 실패하는 경우
        결과를 삭제할 수 있습니다. 이는 저장을 빠르고 안정적으로 유지하기 위함입니다.
        """
        return self._send_request("textDocument/willSaveWaitUntil", params)

    def completion(self, params: lsp_types.CompletionParams) -> Union[list["lsp_types.CompletionItem"], "lsp_types.CompletionList", None]:
        """
        주어진 텍스트 문서 위치에서 완성을 요청하기 위한 요청입니다. 요청의
        매개변수는 {@link TextDocumentPosition} 타입이며, 응답은
        {@link CompletionItem CompletionItem[]} 또는 {@link CompletionList} 타입
        또는 이를 resolve하는 Thenable입니다.

        요청은 `completionItem/resolve` 요청에 대한 {@link CompletionItem.detail `detail`} 및
        {@link CompletionItem.documentation `documentation`} 속성의 계산을 지연시킬 수 있습니다.
        그러나 `sortText`, `filterText`, `insertText`, `textEdit`와 같이 초기 정렬 및 필터링에
        필요한 속성은 resolve 중에 변경되어서는 안 됩니다.
        """
        return self._send_request("textDocument/completion", params)

    def resolve_completion_item(self, params: lsp_types.CompletionItem) -> "lsp_types.CompletionItem":
        """
        주어진 완성 항목에 대한 추가 정보를 확인하기 위한 요청입니다. 요청의
        매개변수는 {@link CompletionItem} 타입이며, 응답은
        {@link CompletionItem} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("completionItem/resolve", params)

    def hover(self, params: lsp_types.HoverParams) -> Union["lsp_types.Hover", None]:
        """
        주어진 텍스트 문서 위치에서 호버 정보를 요청하기 위한 요청입니다. 요청의
        매개변수는 {@link TextDocumentPosition} 타입이며, 응답은
        {@link Hover} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/hover", params)

    def signature_help(self, params: lsp_types.SignatureHelpParams) -> Union["lsp_types.SignatureHelp", None]:
        return self._send_request("textDocument/signatureHelp", params)

    def definition(self, params: lsp_types.DefinitionParams) -> Union["lsp_types.Definition", list["lsp_types.LocationLink"], None]:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 정의 위치를 확인하기 위한 요청입니다.
        요청 매개변수는 [TextDocumentPosition] 타입이며,
        응답은 {@link Definition} 타입, {@link DefinitionLink}의 타입 배열 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/definition", params)

    def references(self, params: lsp_types.ReferenceParams) -> list["lsp_types.Location"] | None:
        """
        주어진 텍스트 문서 위치로 표시된 심볼에 대한 프로젝트 전체 참조를 확인하기 위한 요청입니다.
        요청 매개변수는 {@link ReferenceParams} 타입이며, 응답은
        {@link Location Location[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/references", params)

    def document_highlight(self, params: lsp_types.DocumentHighlightParams) -> list["lsp_types.DocumentHighlight"] | None:
        """
        주어진 텍스트 문서 위치에 대한 {@link DocumentHighlight}를 확인하기 위한 요청입니다.
        요청 매개변수는 [TextDocumentPosition] 타입이며,
        요청 응답은 [DocumentHighlight[]] 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/documentHighlight", params)

    def document_symbol(
        self, params: lsp_types.DocumentSymbolParams
    ) -> list["lsp_types.SymbolInformation"] | list["lsp_types.DocumentSymbol"] | None:
        """
        주어진 텍스트 문서에서 발견된 모든 심볼을 나열하기 위한 요청입니다. 요청의
        매개변수는 {@link TextDocumentIdentifier} 타입이며,
        응답은 {@link SymbolInformation SymbolInformation[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("textDocument/documentSymbol", params)

    def code_action(self, params: lsp_types.CodeActionParams) -> list[Union["lsp_types.Command", "lsp_types.CodeAction"]] | None:
        """주어진 텍스트 문서 및 범위에 대한 명령을 제공하기 위한 요청입니다."""
        return self._send_request("textDocument/codeAction", params)

    def resolve_code_action(self, params: lsp_types.CodeAction) -> "lsp_types.CodeAction":
        """
        주어진 코드 액션에 대한 추가 정보를 확인하기 위한 요청입니다. 요청의
        매개변수는 {@link CodeAction} 타입이며, 응답은
        {@link CodeAction} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("codeAction/resolve", params)

    def workspace_symbol(
        self, params: lsp_types.WorkspaceSymbolParams
    ) -> list["lsp_types.SymbolInformation"] | list["lsp_types.WorkspaceSymbol"] | None:
        """
        {@link WorkspaceSymbolParams}에 의해 주어진 쿼리 문자열과 일치하는 프로젝트 전체 심볼을 나열하기 위한 요청입니다.
        응답은 {@link SymbolInformation SymbolInformation[]} 타입 또는 이를 resolve하는 Thenable입니다.

        @since 3.17.0 - 반환된 데이터에서 WorkspaceSymbol 지원. 클라이언트는
         `workspace.symbol.resolveSupport` 클라이언트 기능을 통해 WorkspaceSymbols에 대한 지원을 알려야 합니다.
        """
        return self._send_request("workspace/symbol", params)

    def resolve_workspace_symbol(self, params: lsp_types.WorkspaceSymbol) -> "lsp_types.WorkspaceSymbol":
        """
        작업 공간 심볼의 위치 내 범위를 확인하기 위한 요청입니다.

        @since 3.17.0
        """
        return self._send_request("workspaceSymbol/resolve", params)

    def code_lens(self, params: lsp_types.CodeLensParams) -> list["lsp_types.CodeLens"] | None:
        """주어진 텍스트 문서에 대한 코드 렌즈를 제공하기 위한 요청입니다."""
        return self._send_request("textDocument/codeLens", params)

    def resolve_code_lens(self, params: lsp_types.CodeLens) -> "lsp_types.CodeLens":
        """주어진 코드 렌즈에 대한 명령을 확인하기 위한 요청입니다."""
        return self._send_request("codeLens/resolve", params)

    def document_link(self, params: lsp_types.DocumentLinkParams) -> list["lsp_types.DocumentLink"] | None:
        """문서 링크를 제공하기 위한 요청입니다."""
        return self._send_request("textDocument/documentLink", params)

    def resolve_document_link(self, params: lsp_types.DocumentLink) -> "lsp_types.DocumentLink":
        """
        주어진 문서 링크에 대한 추가 정보를 확인하기 위한 요청입니다. 요청의
        매개변수는 {@link DocumentLink} 타입이며, 응답은
        {@link DocumentLink} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return self._send_request("documentLink/resolve", params)

    def formatting(self, params: lsp_types.DocumentFormattingParams) -> list["lsp_types.TextEdit"] | None:
        """전체 문서의 형식을 지정하기 위한 요청입니다."""
        return self._send_request("textDocument/formatting", params)

    def range_formatting(self, params: lsp_types.DocumentRangeFormattingParams) -> list["lsp_types.TextEdit"] | None:
        """문서의 범위 형식을 지정하기 위한 요청입니다."""
        return self._send_request("textDocument/rangeFormatting", params)

    def on_type_formatting(self, params: lsp_types.DocumentOnTypeFormattingParams) -> list["lsp_types.TextEdit"] | None:
        """타이핑 시 문서 형식을 지정하기 위한 요청입니다."""
        return self._send_request("textDocument/onTypeFormatting", params)

    def rename(self, params: lsp_types.RenameParams) -> Union["lsp_types.WorkspaceEdit", None]:
        """심볼의 이름을 바꾸기 위한 요청입니다."""
        return self._send_request("textDocument/rename", params)

    def prepare_rename(self, params: lsp_types.PrepareRenameParams) -> Union["lsp_types.PrepareRenameResult", None]:
        """
        이름 변경에 필요한 설정을 테스트하고 수행하기 위한 요청입니다.

        @since 3.16 - 기본 동작 지원
        """
        return self._send_request("textDocument/prepareRename", params)

    def execute_command(self, params: lsp_types.ExecuteCommandParams) -> Union["lsp_types.LSPAny", None]:
        """
        명령을 실행하기 위해 클라이언트에서 서버로 보내는 요청입니다. 요청은
        클라이언트가 작업 공간에 적용할 작업 공간 편집을 반환할 수 있습니다.
        """
        return self._send_request("workspace/executeCommand", params)