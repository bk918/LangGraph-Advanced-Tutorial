"""
SerenaMCP 심볼 조작 도구 시스템

이 파일은 SerenaMCP의 언어 서버 기반 심볼 조작 도구들을 구현합니다.
심볼 검색, 편집, 참조 찾기 등의 고급 코드 분석 기능을 제공합니다.

주요 도구 클래스:
- RestartLanguageServerTool: 언어 서버 재시작 도구
- GetSymbolsOverviewTool: 심볼 개요 조회 도구
- FindSymbolTool: 심볼 검색 도구
- FindReferencingSymbolsTool: 심볼 참조 찾기 도구
- ReplaceSymbolBodyTool: 심볼 본체 교체 도구
- InsertAfterSymbolTool: 심볼 뒤에 코드 삽입 도구
- InsertBeforeSymbolTool: 심볼 앞에 코드 삽입 도구

주요 기능:
- 언어 서버를 통한 정확한 심볼 분석
- 이름 기반 및 위치 기반 심볼 검색
- 심볼 본체의 정밀한 편집
- 참조 관계 추적
- 타입 안전성을 위한 마커 시스템

아키텍처:
- LSP(Language Server Protocol) 기반 심볼 분석
- ToolMarker를 통한 도구 속성 분류
- 언어 서버 통신을 통한 정확한 위치 정보 활용
- 심볼 데이터 정제 및 최적화
"""

import dataclasses
import json
import os
from collections.abc import Sequence
from copy import copy
from typing import Any

from serena.tools import (
    SUCCESS_RESULT,
    Tool,
    ToolMarkerSymbolicEdit,
    ToolMarkerSymbolicRead,
)
from serena.tools.tools_base import ToolMarkerOptional
from solidlsp.ls_types import SymbolKind


def _sanitize_symbol_dict(symbol_dict: dict[str, Any]) -> dict[str, Any]:
    """
    심볼 딕셔너리를 정리하여 불필요한 정보를 제거합니다.

    심볼 딕셔너리에서 중복되거나 불필요한 정보를 제거하여
    더 효율적인 데이터 구조를 만듭니다. 위치 정보나 중복 필드를
    정리하여 반환합니다.

    Args:
        symbol_dict (dict[str, Any]): 정리할 원본 심볼 딕셔너리

    Returns:
        dict[str, Any]: 정리된 심볼 딕셔너리

    정리 작업:
    - location 필드를 relative_path로 대체
    - 중복되는 name 필드 제거 (name_path로 충분)
    - 불필요한 세부 위치 정보 제거

    Example:
        >>> original = {
        ...     "name": "MyClass",
        ...     "name_path": "com.example.MyClass",
        ...     "location": {"relative_path": "src/MyClass.java", "line": 10, "column": 5}
        ... }
        >>> result = _sanitize_symbol_dict(original)
        >>> result["relative_path"]
        "src/MyClass.java"
    """
    # 위치 정보에서 중복되는 라인 정보와 불필요한 컬럼 정보를 제거하고
    # 상대 경로만 남김
    symbol_dict = copy(symbol_dict)
    s_relative_path = symbol_dict.get("location", {}).get("relative_path")
    if s_relative_path is not None:
        symbol_dict["relative_path"] = s_relative_path
    symbol_dict.pop("location", None)
    # name_path가 충분하므로 name도 제거
    symbol_dict.pop("name")
    return symbol_dict


class RestartLanguageServerTool(Tool, ToolMarkerOptional):
    """
    언어 서버 재시작 도구

    Serena를 통하지 않고 이루어진 코드 편집으로 인해 언어 서버가
    동기화되지 않았거나 응답하지 않는 경우에 사용됩니다.
    언어 서버를 완전히 재시작하여 심볼 정보의 정확성을 보장합니다.

    주요 기능:
    - 언어 서버 완전 재시작
    - 심볼 캐시 초기화
    - LSP 연결 재설정

    Note:
        이 도구는 명시적인 사용자 요청이나 확인 후에만 사용하세요.
        언어 서버가 멈춘 경우에만 필요합니다.
    """

    def apply(self) -> str:
        """
        언어 서버를 재시작합니다.

        에이전트의 언어 서버를 완전히 재시작하여
        심볼 정보와 편집 상태를 초기화합니다.

        Returns:
            str: 작업 성공 결과 메시지

        Note:
            언어 서버 재시작은 시간이 걸릴 수 있으며,
            진행 중인 다른 작업에 영향을 줄 수 있습니다.
        """
        self.agent.reset_language_server()
        return SUCCESS_RESULT


class GetSymbolsOverviewTool(Tool, ToolMarkerSymbolicRead):
    """
    지정된 파일의 최상위 심볼 개요를 조회하는 도구

    파일 내에 정의된 최상위 레벨의 심볼들(클래스, 함수, 인터페이스 등)에 대한
    개요 정보를 반환합니다. 새로운 파일을 이해하고자 할 때 가장 먼저 호출해야 하는 도구입니다.

    주요 기능:
    - 파일 내 최상위 심볼 목록 조회
    - 심볼의 이름, 종류, 위치 정보 제공
    - JSON 형식으로 구조화된 결과 반환

    Note:
        심볼 정보를 정확하게 얻기 위해 언어 서버를 사용합니다.
        파일이 존재하지 않거나 디렉토리인 경우 오류를 발생시킵니다.
    """

    def apply(self, relative_path: str, max_answer_chars: int = -1) -> str:
        """
        지정된 파일의 심볼 개요를 조회합니다.

        언어 서버를 통해 파일 내 최상위 심볼들의 개요 정보를 수집하고,
        JSON 형태로 반환합니다. 새로운 파일을 분석할 때 가장 먼저 사용해야 하는 도구입니다.

        Args:
            relative_path (str): 심볼 개요를 조회할 파일의 상대 경로
            max_answer_chars (int): 응답 문자열의 최대 길이. -1이면 설정된 기본값 사용.
                작업에 필요한 내용을 얻을 수 있는 다른 방법이 없을 때만 조정하세요.

        Returns:
            str: 파일 내 최상위 심볼들에 대한 정보를 담은 JSON 문자열

        Raises:
            FileNotFoundError: 지정된 파일이 존재하지 않는 경우
            ValueError: 지정된 경로가 디렉토리인 경우

        Example:
            >>> tool = GetSymbolsOverviewTool(agent)
            >>> result = tool.apply("src/main.py")
            >>> import json
            >>> symbols = json.loads(result)
            >>> for symbol in symbols:
            ...     print(f"{symbol['name']} ({SymbolKind(symbol['kind']).name})")

        동작 과정:
        1. 언어 서버 심볼 검색기 생성
        2. 파일 존재 여부 및 타입 검증
        3. 심볼 개요 정보 조회
        4. 결과를 JSON 형태로 변환 및 길이 제한 적용
        """
        symbol_retriever = self.create_language_server_symbol_retriever()
        file_path = os.path.join(self.project.project_root, relative_path)

        # The symbol overview is capable of working with both files and directories,
        # but we want to ensure that the user provides a file path.
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File or directory {relative_path} does not exist in the project.")
        if os.path.isdir(file_path):
            raise ValueError(f"Expected a file path, but got a directory path: {relative_path}. ")
        result = symbol_retriever.get_symbol_overview(relative_path)[relative_path]
        result_json_str = json.dumps([dataclasses.asdict(i) for i in result])
        return self._limit_length(result_json_str, max_answer_chars)


class FindSymbolTool(Tool, ToolMarkerSymbolicRead):
    """
    Performs a global (or local) search for symbols with/containing a given name/substring (optionally filtered by type).
    """

    def apply(
        self,
        name_path: str,
        depth: int = 0,
        relative_path: str = "",
        include_body: bool = False,
        include_kinds: list[int] = [],  # noqa: B006
        exclude_kinds: list[int] = [],  # noqa: B006
        substring_matching: bool = False,
        max_answer_chars: int = -1,
    ) -> str:
        """
        Retrieves information on all symbols/code entities (classes, methods, etc.) based on the given `name_path`,
        which represents a pattern for the symbol's path within the symbol tree of a single file.
        The returned symbol location can be used for edits or further queries.
        Specify `depth > 0` to retrieve children (e.g., methods of a class).

        The matching behavior is determined by the structure of `name_path`, which can
        either be a simple name (e.g. "method") or a name path like "class/method" (relative name path)
        or "/class/method" (absolute name path). Note that the name path is not a path in the file system
        but rather a path in the symbol tree **within a single file**. Thus, file or directory names should never
        be included in the `name_path`. For restricting the search to a single file or directory,
        the `within_relative_path` parameter should be used instead. The retrieved symbols' `name_path` attribute
        will always be composed of symbol names, never file or directory names.

        Key aspects of the name path matching behavior:
        - Trailing slashes in `name_path` play no role and are ignored.
        - The name of the retrieved symbols will match (either exactly or as a substring)
          the last segment of `name_path`, while other segments will restrict the search to symbols that
          have a desired sequence of ancestors.
        - If there is no starting or intermediate slash in `name_path`, there is no
          restriction on the ancestor symbols. For example, passing `method` will match
          against symbols with name paths like `method`, `class/method`, `class/nested_class/method`, etc.
        - If `name_path` contains a `/` but doesn't start with a `/`, the matching is restricted to symbols
          with the same ancestors as the last segment of `name_path`. For example, passing `class/method` will match against
          `class/method` as well as `nested_class/class/method` but not `method`.
        - If `name_path` starts with a `/`, it will be treated as an absolute name path pattern, meaning
          that the first segment of it must match the first segment of the symbol's name path.
          For example, passing `/class` will match only against top-level symbols like `class` but not against `nested_class/class`.
          Passing `/class/method` will match against `class/method` but not `nested_class/class/method` or `method`.


        :param name_path: The name path pattern to search for, see above for details.
        :param depth: Depth to retrieve descendants (e.g., 1 for class methods/attributes).
        :param relative_path: Optional. Restrict search to this file or directory. If None, searches entire codebase.
            If a directory is passed, the search will be restricted to the files in that directory.
            If a file is passed, the search will be restricted to that file.
            If you have some knowledge about the codebase, you should use this parameter, as it will significantly
            speed up the search as well as reduce the number of results.
        :param include_body: If True, include the symbol's source code. Use judiciously.
        :param include_kinds: Optional. List of LSP symbol kind integers to include. (e.g., 5 for Class, 12 for Function).
            Valid kinds: 1=file, 2=module, 3=namespace, 4=package, 5=class, 6=method, 7=property, 8=field, 9=constructor, 10=enum,
            11=interface, 12=function, 13=variable, 14=constant, 15=string, 16=number, 17=boolean, 18=array, 19=object,
            20=key, 21=null, 22=enum member, 23=struct, 24=event, 25=operator, 26=type parameter.
            If not provided, all kinds are included.
        :param exclude_kinds: Optional. List of LSP symbol kind integers to exclude. Takes precedence over `include_kinds`.
            If not provided, no kinds are excluded.
        :param substring_matching: If True, use substring matching for the last segment of `name`.
        :param max_answer_chars: Max characters for the JSON result. If exceeded, no content is returned.
            -1 means the default value from the config will be used.
        :return: a list of symbols (with locations) matching the name.
        """
        parsed_include_kinds: Sequence[SymbolKind] | None = [SymbolKind(k) for k in include_kinds] if include_kinds else None
        parsed_exclude_kinds: Sequence[SymbolKind] | None = [SymbolKind(k) for k in exclude_kinds] if exclude_kinds else None
        symbol_retriever = self.create_language_server_symbol_retriever()
        symbols = symbol_retriever.find_by_name(
            name_path,
            include_body=include_body,
            include_kinds=parsed_include_kinds,
            exclude_kinds=parsed_exclude_kinds,
            substring_matching=substring_matching,
            within_relative_path=relative_path,
        )
        symbol_dicts = [_sanitize_symbol_dict(s.to_dict(kind=True, location=True, depth=depth, include_body=include_body)) for s in symbols]
        result = json.dumps(symbol_dicts)
        return self._limit_length(result, max_answer_chars)


class FindReferencingSymbolsTool(Tool, ToolMarkerSymbolicRead):
    """
    Finds symbols that reference the symbol at the given location (optionally filtered by type).
    """

    def apply(
        self,
        name_path: str,
        relative_path: str,
        include_kinds: list[int] = [],  # noqa: B006
        exclude_kinds: list[int] = [],  # noqa: B006
        max_answer_chars: int = -1,
    ) -> str:
        """
        Finds references to the symbol at the given `name_path`. The result will contain metadata about the referencing symbols
        as well as a short code snippet around the reference.

        :param name_path: for finding the symbol to find references for, same logic as in the `find_symbol` tool.
        :param relative_path: the relative path to the file containing the symbol for which to find references.
            Note that here you can't pass a directory but must pass a file.
        :param include_kinds: same as in the `find_symbol` tool.
        :param exclude_kinds: same as in the `find_symbol` tool.
        :param max_answer_chars: same as in the `find_symbol` tool.
        :return: a list of JSON objects with the symbols referencing the requested symbol
        """
        include_body = False  # It is probably never a good idea to include the body of the referencing symbols
        parsed_include_kinds: Sequence[SymbolKind] | None = [SymbolKind(k) for k in include_kinds] if include_kinds else None
        parsed_exclude_kinds: Sequence[SymbolKind] | None = [SymbolKind(k) for k in exclude_kinds] if exclude_kinds else None
        symbol_retriever = self.create_language_server_symbol_retriever()
        references_in_symbols = symbol_retriever.find_referencing_symbols(
            name_path,
            relative_file_path=relative_path,
            include_body=include_body,
            include_kinds=parsed_include_kinds,
            exclude_kinds=parsed_exclude_kinds,
        )
        reference_dicts = []
        for ref in references_in_symbols:
            ref_dict = ref.symbol.to_dict(kind=True, location=True, depth=0, include_body=include_body)
            ref_dict = _sanitize_symbol_dict(ref_dict)
            if not include_body:
                ref_relative_path = ref.symbol.location.relative_path
                assert ref_relative_path is not None, f"Referencing symbol {ref.symbol.name} has no relative path, this is likely a bug."
                content_around_ref = self.project.retrieve_content_around_line(
                    relative_file_path=ref_relative_path, line=ref.line, context_lines_before=1, context_lines_after=1
                )
                ref_dict["content_around_reference"] = content_around_ref.to_display_string()
            reference_dicts.append(ref_dict)
        result = json.dumps(reference_dicts)
        return self._limit_length(result, max_answer_chars)


class ReplaceSymbolBodyTool(Tool, ToolMarkerSymbolicEdit):
    """
    Replaces the full definition of a symbol.
    """

    def apply(
        self,
        name_path: str,
        relative_path: str,
        body: str,
    ) -> str:
        r"""
        Replaces the body of the symbol with the given `name_path`.

        The tool shall be used to replace symbol bodies that have been previously retrieved
        (e.g. via `find_symbol`), such that it is clear what constitutes the body of the symbol.

        :param name_path: for finding the symbol to replace, same logic as in the `find_symbol` tool.
        :param relative_path: the relative path to the file containing the symbol
        :param body: the new symbol body. Important: The symbol body is the full definition of a symbol
            in the programming language, including e.g. the signature line for functions,
            but it does NOT include any preceding comments or imports, in particular.
        """
        code_editor = self.create_code_editor()
        code_editor.replace_body(
            name_path,
            relative_file_path=relative_path,
            body=body,
        )
        return SUCCESS_RESULT


class InsertAfterSymbolTool(Tool, ToolMarkerSymbolicEdit):
    """
    Inserts content after the end of the definition of a given symbol.
    """

    def apply(
        self,
        name_path: str,
        relative_path: str,
        body: str,
    ) -> str:
        """
        Inserts the given body/content after the end of the definition of the given symbol (via the symbol's location).
        A typical use case is to insert a new class, function, method, field or variable assignment.

        :param name_path: name path of the symbol after which to insert content (definitions in the `find_symbol` tool apply)
        :param relative_path: the relative path to the file containing the symbol
        :param body: the body/content to be inserted. The inserted code shall begin with the next line after
            the symbol.
        """
        code_editor = self.create_code_editor()
        code_editor.insert_after_symbol(name_path, relative_file_path=relative_path, body=body)
        return SUCCESS_RESULT


class InsertBeforeSymbolTool(Tool, ToolMarkerSymbolicEdit):
    """
    Inserts content before the beginning of the definition of a given symbol.
    """

    def apply(
        self,
        name_path: str,
        relative_path: str,
        body: str,
    ) -> str:
        """
        Inserts the given content before the beginning of the definition of the given symbol (via the symbol's location).
        A typical use case is to insert a new class, function, method, field or variable assignment; or
        a new import statement before the first symbol in the file.

        :param name_path: name path of the symbol before which to insert content (definitions in the `find_symbol` tool apply)
        :param relative_path: the relative path to the file containing the symbol
        :param body: the body/content to be inserted before the line in which the referenced symbol is defined
        """
        code_editor = self.create_code_editor()
        code_editor.insert_before_symbol(name_path, relative_file_path=relative_path, body=body)
        return SUCCESS_RESULT
