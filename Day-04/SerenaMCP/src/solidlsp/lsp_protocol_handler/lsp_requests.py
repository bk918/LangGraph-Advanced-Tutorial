# Code generated. DO NOT EDIT.
# LSP v3.17.0
# TODO: Look into use of https://pypi.org/project/ts2python/ to generate the types for https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/

"""
solidlsp/lsp_protocol_handler/lsp_requests.py - LSP 요청 및 알림 인터페이스

이 파일은 언어 서버 프로토콜(LSP)에 정의된 요청(Request)과 알림(Notification)에 해당하는
파이썬 인터페이스를 제공합니다. 클라이언트(SolidLSP)가 언어 서버에 메시지를 보낼 때
사용되는 메서드들을 정의합니다.

주요 클래스:
- LspRequest: 서버에 응답을 요구하는 요청(예: `textDocument/definition`)을 보내는 메서드들을 포함합니다.
- LspNotification: 서버에 응답을 요구하지 않는 알림(예: `textDocument/didOpen`)을 보내는 메서드들을 포함합니다.

참고:
- 이 파일의 코드는 https://github.com/predragnikolic/OLSP 프로젝트에서 가져온 것이며,
  LSP 사양 v3.17.0을 기반으로 합니다. 코드 생성기로 만들어졌으므로 직접적인 수정은 권장되지 않습니다.
- 각 메서드의 docstring은 LSP 공식 사양의 설명을 따릅니다.

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

from typing import Union

from solidlsp.lsp_protocol_handler import lsp_types


class LspRequest:
    def __init__(self, send_request):
        self.send_request = send_request

    async def implementation(self, params: lsp_types.ImplementationParams) -> Union["lsp_types.Definition", list["lsp_types.LocationLink"], None]:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 구현 위치를 확인하기 위한 요청입니다.

        요청 매개변수는 [TextDocumentPositionParams] 타입이며,
        응답은 {@link Definition} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/implementation", params)

    async def type_definition(self, params: lsp_types.TypeDefinitionParams) -> Union["lsp_types.Definition", list["lsp_types.LocationLink"], None]:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 타입 정의 위치를 확인하기 위한 요청입니다.

        요청 매개변수는 [TextDocumentPositionParams] 타입이며,
        응답은 {@link Definition} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/typeDefinition", params)

    async def document_color(self, params: lsp_types.DocumentColorParams) -> list["lsp_types.ColorInformation"]:
        """
        주어진 텍스트 문서에서 발견된 모든 색상 심볼을 나열하기 위한 요청입니다.

        요청 매개변수는 {@link DocumentColorParams} 타입이며,
        응답은 {@link ColorInformation ColorInformation[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/documentColor", params)

    async def color_presentation(self, params: lsp_types.ColorPresentationParams) -> list["lsp_types.ColorPresentation"]:
        """
        색상에 대한 모든 표현을 나열하기 위한 요청입니다.

        요청 매개변수는 {@link ColorPresentationParams} 타입이며,
        응답은 {@link ColorInformation ColorInformation[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/colorPresentation", params)

    async def folding_range(self, params: lsp_types.FoldingRangeParams) -> list["lsp_types.FoldingRange"] | None:
        """
        문서의 접기 범위를 제공하기 위한 요청입니다.

        요청 매개변수는 {@link FoldingRangeParams} 타입이며,
        응답은 {@link FoldingRangeList} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/foldingRange", params)

    async def declaration(self, params: lsp_types.DeclarationParams) -> Union["lsp_types.Declaration", list["lsp_types.LocationLink"], None]:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 타입 정의 위치를 확인하기 위한 요청입니다.

        요청 매개변수는 [TextDocumentPositionParams] 타입이며,
        응답은 {@link Declaration} 타입, {@link DeclarationLink}의 타입 배열 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/declaration", params)

    async def selection_range(self, params: lsp_types.SelectionRangeParams) -> list["lsp_types.SelectionRange"] | None:
        """
        문서의 선택 범위를 제공하기 위한 요청입니다.

        요청 매개변수는 {@link SelectionRangeParams} 타입이며,
        응답은 {@link SelectionRange SelectionRange[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/selectionRange", params)

    async def prepare_call_hierarchy(self, params: lsp_types.CallHierarchyPrepareParams) -> list["lsp_types.CallHierarchyItem"] | None:
        """
        주어진 위치의 문서에서 `CallHierarchyItem`을 반환하기 위한 요청입니다.
        들어오거나 나가는 호출 계층 구조의 입력으로 사용될 수 있습니다.

        @since 3.16.0
        """
        return await self.send_request("textDocument/prepareCallHierarchy", params)

    async def incoming_calls(self, params: lsp_types.CallHierarchyIncomingCallsParams) -> list["lsp_types.CallHierarchyIncomingCall"] | None:
        """
        주어진 `CallHierarchyItem`에 대한 들어오는 호출을 확인하기 위한 요청입니다.

        @since 3.16.0
        """
        return await self.send_request("callHierarchy/incomingCalls", params)

    async def outgoing_calls(self, params: lsp_types.CallHierarchyOutgoingCallsParams) -> list["lsp_types.CallHierarchyOutgoingCall"] | None:
        """
        주어진 `CallHierarchyItem`에 대한 나가는 호출을 확인하기 위한 요청입니다.

        @since 3.16.0
        """
        return await self.send_request("callHierarchy/outgoingCalls", params)

    async def semantic_tokens_full(self, params: lsp_types.SemanticTokensParams) -> Union["lsp_types.SemanticTokens", None]:
        """@since 3.16.0"""
        return await self.send_request("textDocument/semanticTokens/full", params)

    async def semantic_tokens_delta(self, params: lsp_types.SemanticTokensDeltaParams) -> Union["lsp_types.SemanticTokens", "lsp_types.SemanticTokensDelta", None]:
        """@since 3.16.0"""
        return await self.send_request("textDocument/semanticTokens/full/delta", params)

    async def semantic_tokens_range(self, params: lsp_types.SemanticTokensRangeParams) -> Union["lsp_types.SemanticTokens", None]:
        """@since 3.16.0"""
        return await self.send_request("textDocument/semanticTokens/range", params)

    async def linked_editing_range(self, params: lsp_types.LinkedEditingRangeParams) -> Union["lsp_types.LinkedEditingRanges", None]:
        """
        함께 편집할 수 있는 범위를 제공하기 위한 요청입니다.

        @since 3.16.0
        """
        return await self.send_request("textDocument/linkedEditingRange", params)

    async def will_create_files(self, params: lsp_types.CreateFilesParams) -> Union["lsp_types.WorkspaceEdit", None]:
        """
        파일 생성 요청은 클라이언트 내에서 생성이 트리거되는 한, 파일이 실제로 생성되기 전에
        클라이언트에서 서버로 전송됩니다.

        @since 3.16.0
        """
        return await self.send_request("workspace/willCreateFiles", params)

    async def will_rename_files(self, params: lsp_types.RenameFilesParams) -> Union["lsp_types.WorkspaceEdit", None]:
        """
        파일 이름 변경 요청은 클라이언트 내에서 이름 변경이 트리거되는 한, 파일 이름이 실제로 변경되기 전에
        클라이언트에서 서버로 전송됩니다.

        @since 3.16.0
        """
        return await self.send_request("workspace/willRenameFiles", params)

    async def will_delete_files(self, params: lsp_types.DeleteFilesParams) -> Union["lsp_types.WorkspaceEdit", None]:
        """
        파일 삭제 알림은 클라이언트 내에서 파일이 삭제되었을 때
        클라이언트에서 서버로 전송됩니다.

        @since 3.16.0
        """
        return await self.send_request("workspace/willDeleteFiles", params)

    async def moniker(self, params: lsp_types.MonikerParams) -> list["lsp_types.Moniker"] | None:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 모니커를 가져오기 위한 요청입니다.

        요청 매개변수는 {@link TextDocumentPositionParams} 타입이며,
        응답은 {@link Moniker Moniker[]} 타입 또는 `null`입니다.
        """
        return await self.send_request("textDocument/moniker", params)

    async def prepare_type_hierarchy(self, params: lsp_types.TypeHierarchyPrepareParams) -> list["lsp_types.TypeHierarchyItem"] | None]:
        """
        주어진 위치의 문서에서 `TypeHierarchyItem`을 반환하기 위한 요청입니다.
        하위 타입 또는 상위 타입 계층 구조의 입력으로 사용될 수 있습니다.

        @since 3.17.0
        """
        return await self.send_request("textDocument/prepareTypeHierarchy", params)

    async def type_hierarchy_supertypes(self, params: lsp_types.TypeHierarchySupertypesParams) -> list["lsp_types.TypeHierarchyItem"] | None:
        """
        주어진 `TypeHierarchyItem`에 대한 상위 타입을 확인하기 위한 요청입니다.

        @since 3.17.0
        """
        return await self.send_request("typeHierarchy/supertypes", params)

    async def type_hierarchy_subtypes(self, params: lsp_types.TypeHierarchySubtypesParams) -> list["lsp_types.TypeHierarchyItem"] | None:
        """
        주어진 `TypeHierarchyItem`에 대한 하위 타입을 확인하기 위한 요청입니다.

        @since 3.17.0
        """
        return await self.send_request("typeHierarchy/subtypes", params)

    async def inline_value(self, params: lsp_types.InlineValueParams) -> list["lsp_types.InlineValue"] | None:
        """
        문서의 인라인 값을 제공하기 위한 요청입니다.

        요청 매개변수는 {@link InlineValueParams} 타입이며,
        응답은 {@link InlineValue InlineValue[]} 타입 또는 이를 resolve하는 Thenable입니다.

        @since 3.17.0
        """
        return await self.send_request("textDocument/inlineValue", params)

    async def inlay_hint(self, params: lsp_types.InlayHintParams) -> list["lsp_types.InlayHint"] | None:
        """
        문서의 인레이 힌트를 제공하기 위한 요청입니다.

        요청 매개변수는 {@link InlayHintsParams} 타입이며,
        응답은 {@link InlayHint InlayHint[]} 타입 또는 이를 resolve하는 Thenable입니다.

        @since 3.17.0
        """
        return await self.send_request("textDocument/inlayHint", params)

    async def resolve_inlay_hint(self, params: lsp_types.InlayHint) -> "lsp_types.InlayHint":
        """
        인레이 힌트에 대한 추가 속성을 확인하기 위한 요청입니다.

        요청 매개변수는 {@link InlayHint} 타입이며,
        응답은 {@link InlayHint} 타입 또는 이를 resolve하는 Thenable입니다.

        @since 3.17.0
        """
        return await self.send_request("inlayHint/resolve", params)

    async def text_document_diagnostic(self, params: lsp_types.DocumentDiagnosticParams) -> "lsp_types.DocumentDiagnosticReport":
        """
        문서 진단 요청 정의입니다.

        @since 3.17.0
        """
        return await self.send_request("textDocument/diagnostic", params)

    async def workspace_diagnostic(self, params: lsp_types.WorkspaceDiagnosticParams) -> "lsp_types.WorkspaceDiagnosticReport":
        """
        작업 공간 진단 요청 정의입니다.

        @since 3.17.0
        """
        return await self.send_request("workspace/diagnostic", params)

    async def initialize(self, params: lsp_types.InitializeParams) -> "lsp_types.InitializeResult":
        """
        초기화 요청은 클라이언트에서 서버로 전송됩니다.
        서버 시작 후 요청으로 한 번 전송됩니다.
        요청 매개변수는 {@link InitializeParams} 타입이며,
        응답은 {@link InitializeResult} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("initialize", params)

    async def shutdown(self) -> None:
        """
        종료 요청은 클라이언트에서 서버로 전송됩니다.
        클라이언트가 서버를 종료하기로 결정했을 때 한 번 전송됩니다.
        종료 요청 후 전송되는 유일한 알림은 exit 이벤트입니다.
        """
        return await self.send_request("shutdown")

    async def will_save_wait_until(self, params: lsp_types.WillSaveTextDocumentParams) -> list["lsp_types.TextEdit"] | None:
        """
        문서 저장 전 요청은 문서가 실제로 저장되기 전에 클라이언트에서 서버로 전송됩니다.
        요청은 저장되기 전에 텍스트 문서에 적용될 TextEdits 배열을 반환할 수 있습니다.
        클라이언트는 텍스트 편집 계산에 너무 오래 걸리거나 서버가 이 요청에 지속적으로 실패하는 경우
        결과를 삭제할 수 있습니다. 이는 저장을 빠르고 안정적으로 유지하기 위함입니다.
        """
        return await self.send_request("textDocument/willSaveWaitUntil", params)

    async def completion(self, params: lsp_types.CompletionParams) -> Union[list["lsp_types.CompletionItem"], "lsp_types.CompletionList", None]:
        """
        주어진 텍스트 문서 위치에서 완성을 요청하기 위한 요청입니다.

        요청 매개변수는 {@link TextDocumentPosition} 타입이며,
        응답은 {@link CompletionItem CompletionItem[]} 또는 {@link CompletionList} 타입 또는 이를 resolve하는 Thenable입니다.

        요청은 `completionItem/resolve` 요청에 대한 {@link CompletionItem.detail `detail`} 및
        {@link CompletionItem.documentation `documentation`} 속성의 계산을 지연시킬 수 있습니다.
        그러나 `sortText`, `filterText`, `insertText`, `textEdit`와 같이 초기 정렬 및 필터링에
        필요한 속성은 resolve 중에 변경되어서는 안 됩니다.
        """
        return await self.send_request("textDocument/completion", params)

    async def resolve_completion_item(self, params: lsp_types.CompletionItem) -> "lsp_types.CompletionItem":
        """
        주어진 완성 항목에 대한 추가 정보를 확인하기 위한 요청입니다.

        요청 매개변수는 {@link CompletionItem} 타입이며,
        응답은 {@link CompletionItem} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("completionItem/resolve", params)

    async def hover(self, params: lsp_types.HoverParams) -> Union["lsp_types.Hover", None]:
        """
        주어진 텍스트 문서 위치에서 호버 정보를 요청하기 위한 요청입니다.

        요청 매개변수는 {@link TextDocumentPosition} 타입이며,
        응답은 {@link Hover} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/hover", params)

    async def signature_help(self, params: lsp_types.SignatureHelpParams) -> Union["lsp_types.SignatureHelp", None]:
        return await self.send_request("textDocument/signatureHelp", params)

    async def definition(self, params: lsp_types.DefinitionParams) -> Union["lsp_types.Definition", list["lsp_types.LocationLink"], None]:
        """
        주어진 텍스트 문서 위치에 있는 심볼의 정의 위치를 확인하기 위한 요청입니다.

        요청 매개변수는 [TextDocumentPosition] 타입이며,
        응답은 {@link Definition} 타입, {@link DefinitionLink}의 타입 배열 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/definition", params)

    async def references(self, params: lsp_types.ReferenceParams) -> list["lsp_types.Location"] | None:
        """
        주어진 텍스트 문서 위치로 표시된 심볼에 대한 프로젝트 전체 참조를 확인하기 위한 요청입니다.

        요청 매개변수는 {@link ReferenceParams} 타입이며,
        응답은 {@link Location Location[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/references", params)

    async def document_highlight(self, params: lsp_types.DocumentHighlightParams) -> list["lsp_types.DocumentHighlight"] | None:
        """
        주어진 텍스트 문서 위치에 대한 {@link DocumentHighlight}를 확인하기 위한 요청입니다.

        요청 매개변수는 [TextDocumentPosition] 타입이며,
        요청 응답은 [DocumentHighlight[]] 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/documentHighlight", params)

    async def document_symbol(self, params: lsp_types.DocumentSymbolParams) -> list["lsp_types.SymbolInformation"] | list["lsp_types.DocumentSymbol"] | None:
        """
        주어진 텍스트 문서에서 발견된 모든 심볼을 나열하기 위한 요청입니다.

        요청 매개변수는 {@link TextDocumentIdentifier} 타입이며,
        응답은 {@link SymbolInformation SymbolInformation[]} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("textDocument/documentSymbol", params)

    async def code_action(self, params: lsp_types.CodeActionParams) -> list[Union["lsp_types.Command", "lsp_types.CodeAction"]] | None:
        """주어진 텍스트 문서 및 범위에 대한 명령을 제공하기 위한 요청입니다."""
        return await self.send_request("textDocument/codeAction", params)

    async def resolve_code_action(self, params: lsp_types.CodeAction) -> "lsp_types.CodeAction":
        """
        주어진 코드 액션에 대한 추가 정보를 확인하기 위한 요청입니다.

        요청 매개변수는 {@link CodeAction} 타입이며,
        응답은 {@link CodeAction} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("codeAction/resolve", params)

    async def workspace_symbol(self, params: lsp_types.WorkspaceSymbolParams) -> list["lsp_types.SymbolInformation"] | list["lsp_types.WorkspaceSymbol"] | None:
        """
        {@link WorkspaceSymbolParams}에 의해 주어진 쿼리 문자열과 일치하는 프로젝트 전체 심볼을 나열하기 위한 요청입니다.

        응답은 {@link SymbolInformation SymbolInformation[]} 타입 또는 이를 resolve하는 Thenable입니다.

        @since 3.17.0 - 반환된 데이터에서 WorkspaceSymbol 지원. 클라이언트는
         `workspace.symbol.resolveSupport` 클라이언트 기능을 통해 WorkspaceSymbols에 대한 지원을 알려야 합니다.
        """
        return await self.send_request("workspace/symbol", params)

    async def resolve_workspace_symbol(self, params: lsp_types.WorkspaceSymbol) -> "lsp_types.WorkspaceSymbol":
        """
        작업 공간 심볼의 위치 내 범위를 확인하기 위한 요청입니다.

        @since 3.17.0
        """
        return await self.send_request("workspaceSymbol/resolve", params)

    async def code_lens(self, params: lsp_types.CodeLensParams) -> list["lsp_types.CodeLens"] | None:
        """주어진 텍스트 문서에 대한 코드 렌즈를 제공하기 위한 요청입니다."""
        return await self.send_request("textDocument/codeLens", params)

    async def resolve_code_lens(self, params: lsp_types.CodeLens) -> "lsp_types.CodeLens":
        """주어진 코드 렌즈에 대한 명령을 확인하기 위한 요청입니다."""
        return await self.send_request("codeLens/resolve", params)

    async def document_link(self, params: lsp_types.DocumentLinkParams) -> list["lsp_types.DocumentLink"] | None:
        """문서 링크를 제공하기 위한 요청입니다."""
        return await self.send_request("textDocument/documentLink", params)

    async def resolve_document_link(self, params: lsp_types.DocumentLink) -> "lsp_types.DocumentLink":
        """
        주어진 문서 링크에 대한 추가 정보를 확인하기 위한 요청입니다.

        요청 매개변수는 {@link DocumentLink} 타입이며,
        응답은 {@link DocumentLink} 타입 또는 이를 resolve하는 Thenable입니다.
        """
        return await self.send_request("documentLink/resolve", params)

    async def formatting(self, params: lsp_types.DocumentFormattingParams) -> list["lsp_types.TextEdit"] | None:
        """전체 문서의 형식을 지정하기 위한 요청입니다."""
        return await self.send_request("textDocument/formatting", params)

    async def range_formatting(self, params: lsp_types.DocumentRangeFormattingParams) -> list["lsp_types.TextEdit"] | None:
        """문서의 범위 형식을 지정하기 위한 요청입니다."""
        return await self.send_request("textDocument/rangeFormatting", params)

    async def on_type_formatting(self, params: lsp_types.DocumentOnTypeFormattingParams) -> list["lsp_types.TextEdit"] | None:
        """타이핑 시 문서 형식을 지정하기 위한 요청입니다."""
        return await self.send_request("textDocument/onTypeFormatting", params)

    async def rename(self, params: lsp_types.RenameParams) -> Union["lsp_types.WorkspaceEdit", None]:
        """심볼의 이름을 바꾸기 위한 요청입니다."""
        return await self.send_request("textDocument/rename", params)

    async def prepare_rename(self, params: lsp_types.PrepareRenameParams) -> Union["lsp_types.PrepareRenameResult", None]:
        """
        이름 변경에 필요한 설정을 테스트하고 수행하기 위한 요청입니다.

        @since 3.16 - 기본 동작 지원
        """
        return await self.send_request("textDocument/prepareRename", params)

    async def execute_command(self, params: lsp_types.ExecuteCommandParams) -> Union["lsp_types.LSPAny", None]:
        """
        명령을 실행하기 위해 클라이언트에서 서버로 보내는 요청입니다.
        요청은 클라이언트가 작업 공간에 적용할 작업 공간 편집을 반환할 수 있습니다.
        """
        return await self.send_request("workspace/executeCommand", params)


class LspNotification:
    def __init__(self, send_notification):
        self.send_notification = send_notification

    def did_change_workspace_folders(self, params: lsp_types.DidChangeWorkspaceFoldersParams) -> None:
        """
        `workspace/didChangeWorkspaceFolders` 알림은 작업 공간 폴더 구성이 변경될 때
        클라이언트에서 서버로 전송됩니다.
        """
        return self.send_notification("workspace/didChangeWorkspaceFolders", params)

    def cancel_work_done_progress(self, params: lsp_types.WorkDoneProgressCancelParams) -> None:
        """
        `window/workDoneProgress/cancel` 알림은 서버 측에서 시작된 진행 상황을 취소하기 위해
        클라이언트에서 서버로 전송됩니다.
        """
        return self.send_notification("window/workDoneProgress/cancel", params)

    def did_create_files(self, params: lsp_types.CreateFilesParams) -> None:
        """
        파일 생성 알림은 클라이언트 내에서 파일이 생성되었을 때
        클라이언트에서 서버로 전송됩니다.

        @since 3.16.0
        """
        return self.send_notification("workspace/didCreateFiles", params)

    def did_rename_files(self, params: lsp_types.RenameFilesParams) -> None:
        """
        파일 이름 변경 알림은 클라이언트 내에서 파일 이름이 변경되었을 때
        클라이언트에서 서버로 전송됩니다.

        @since 3.16.0
        """
        return self.send_notification("workspace/didRenameFiles", params)

    def did_delete_files(self, params: lsp_types.DeleteFilesParams) -> None:
        """
        파일 삭제 요청은 삭제가 클라이언트 내에서 트리거되는 한, 파일이 실제로 삭제되기 전에
        클라이언트에서 서버로 전송됩니다.

        @since 3.16.0
        """
        return self.send_notification("workspace/didDeleteFiles", params)

    def did_open_notebook_document(self, params: lsp_types.DidOpenNotebookDocumentParams) -> None:
        """
        노트북이 열릴 때 전송되는 알림입니다.

        @since 3.17.0
        """
        return self.send_notification("notebookDocument/didOpen", params)

    def did_change_notebook_document(self, params: lsp_types.DidChangeNotebookDocumentParams) -> None:
        return self.send_notification("notebookDocument/didChange", params)

    def did_save_notebook_document(self, params: lsp_types.DidSaveNotebookDocumentParams) -> None:
        """
        노트북 문서가 저장될 때 전송되는 알림입니다.

        @since 3.17.0
        """
        return self.send_notification("notebookDocument/didSave", params)

    def did_close_notebook_document(self, params: lsp_types.DidCloseNotebookDocumentParams) -> None:
        """
        노트북이 닫힐 때 전송되는 알림입니다.

        @since 3.17.0
        """
        return self.send_notification("notebookDocument/didClose", params)

    def initialized(self, params: lsp_types.InitializedParams) -> None:
        """
        초기화 알림은 클라이언트가 완전히 초기화된 후
        서버가 클라이언트로 요청을 보낼 수 있을 때 클라이언트에서 서버로 전송됩니다.
        """
        return self.send_notification("initialized", params)

    def exit(self) -> None:
        """
        종료 이벤트는 서버에 프로세스를 종료하도록 요청하기 위해
        클라이언트에서 서버로 전송됩니다.
        """
        return self.send_notification("exit")

    def workspace_did_change_configuration(self, params: lsp_types.DidChangeConfigurationParams) -> None:
        """
        구성 변경 알림은 클라이언트의 구성이 변경되었을 때
        클라이언트에서 서버로 전송됩니다. 알림에는
        언어 클라이언트에 의해 정의된 변경된 구성이 포함됩니다.
        """
        return self.send_notification("workspace/didChangeConfiguration", params)

    def did_open_text_document(self, params: lsp_types.DidOpenTextDocumentParams) -> None:
        """
        문서 열림 알림은 새로 열린 텍스트 문서를 알리기 위해
        클라이언트에서 서버로 전송됩니다. 문서의 실제 내용은 이제 클라이언트가 관리하며
        서버는 문서의 uri를 사용하여 문서의 실제 내용을 읽으려고 시도해서는 안 됩니다.
        여기서 열림은 클라이언트에 의해 관리됨을 의미합니다. 반드시 편집기에서
        그 내용이 표시됨을 의미하지는 않습니다. 열림 알림은 해당 닫힘 알림이
        전송되기 전에 두 번 이상 전송되어서는 안 됩니다. 이는 열림 및 닫힘 알림이
        균형을 이루어야 하며 최대 열림 횟수는 1임을 의미합니다.
        """
        return self.send_notification("textDocument/didOpen", params)

    def did_change_text_document(self, params: lsp_types.DidChangeTextDocumentParams) -> None:
        """
        문서 변경 알림은 텍스트 문서의 변경 사항을 알리기 위해
        클라이언트에서 서버로 전송됩니다.
        """
        return self.send_notification("textDocument/didChange", params)

    def did_close_text_document(self, params: lsp_types.DidCloseTextDocumentParams) -> None:
        """
        문서 닫힘 알림은 클라이언트에서 문서가 닫혔을 때
        클라이언트에서 서버로 전송됩니다. 문서의 실제 내용은 이제
        문서의 uri가 가리키는 곳에 존재합니다 (예: 문서의 uri가 파일 uri인 경우
        실제 내용은 이제 디스크에 존재함). 열림 알림과 마찬가지로 닫힘 알림은
        문서 내용 관리에 관한 것입니다. 닫힘 알림을 받았다고 해서
        문서가 이전에 편집기에서 열려 있었다는 의미는 아닙니다. 닫힘 알림은
        이전 열림 알림이 전송되었어야 합니다.
        """
        return self.send_notification("textDocument/didClose", params)

    def did_save_text_document(self, params: lsp_types.DidSaveTextDocumentParams) -> None:
        """
        문서 저장 알림은 클라이언트에서 문서가 저장되었을 때
        클라이언트에서 서버로 전송됩니다.
        """
        return self.send_notification("textDocument/didSave", params)

    def will_save_text_document(self, params: lsp_types.WillSaveTextDocumentParams) -> None:
        """
        문서 저장 전 알림은 문서가 실제로 저장되기 전에
        클라이언트에서 서버로 전송됩니다.
        """
        return self.send_notification("textDocument/willSave", params)

    def did_change_watched_files(self, params: lsp_types.DidChangeWatchedFilesParams) -> None:
        """
        감시 파일 변경 알림은 언어 클라이언트에 의해 감시되는 파일의 변경 사항을
        클라이언트가 감지했을 때 클라이언트에서 서버로 전송됩니다.
        """
        return self.send_notification("workspace/didChangeWatchedFiles", params)

    def set_trace(self, params: lsp_types.SetTraceParams) -> None:
        return self.send_notification("$/setTrace", params)

    def cancel_request(self, params: lsp_types.CancelParams) -> None:
        return self.send_notification("$/cancelRequest", params)

    def progress(self, params: lsp_types.ProgressParams) -> None:
        return self.send_notification("$/progress", params)