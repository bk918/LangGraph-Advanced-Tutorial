"serena/code_editor.py - 추상화된 코드 편집기

이 파일은 Serena 에이전트가 소스 코드를 수정하기 위해 사용하는 코드 편집기 기능을 추상화합니다.
`CodeEditor`라는 추상 기본 클래스를 정의하고, 이를 상속받는 구체적인 편집기 클래스들을 포함합니다.

주요 컴포넌트:
- CodeEditor: 코드 편집을 위한 기본 인터페이스를 정의하는 추상 클래스. 심볼의 본문 교체,
  심볼 앞/뒤에 코드 삽입 등의 고수준 편집 기능을 제공합니다.
- LanguageServerCodeEditor: `solidlsp`를 사용하여 언어 서버 프로토콜(LSP)을 통해 코드를 수정하는 편집기.
  LSP의 텍스트 편집 기능을 활용하여 정확하고 안전한 코드 변경을 수행합니다.
- JetBrainsCodeEditor: JetBrains IDE 플러그인과의 통신을 통해 코드를 수정하는 편집기.
  IDE의 강력한 코드 분석 및 리팩토링 기능을 활용합니다.

주요 기능:
- 심볼 기반 코드 수정: `replace_body`, `insert_after_symbol`, `insert_before_symbol` 등
  텍스트 위치가 아닌 코드의 의미론적 구조(심볼)를 기준으로 편집합니다.
- 컨텍스트 관리자 기반 파일 처리: `_edited_file_context`를 통해 파일을 열고, 수정하고,
  안전하게 저장하는 과정을 관리합니다.
- 수정 후 알림: 코드 수정이 완료되면 `SerenaAgent`에 알려 파일 상태를 갱신하도록 합니다.

아키텍처 노트:
- `CodeEditor`는 전략 패턴(Strategy Pattern)의 일종으로, 코드 편집 방식을 추상화하여
  LSP 기반 편집과 JetBrains IDE 기반 편집을 동일한 인터페이스로 다룰 수 있게 합니다.
- `EditedFile` 내부 클래스는 실제 파일 내용에 대한 버퍼 역할을 하며, 각 편집기 구현체는
  자신만의 방식으로 이 버퍼를 관리합니다 (예: LSP의 가상 파일 버퍼 또는 로컬 문자열 버퍼).
- 제네릭 타입 `TSymbol`을 사용하여 각 편집기가 다루는 심볼의 타입(LanguageServerSymbol 또는
  JetBrainsSymbol)을 명확히 합니다.
"

import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Reversible
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generic, Optional, TypeVar

from serena.symbol import JetBrainsSymbol, LanguageServerSymbol, LanguageServerSymbolRetriever, PositionInFile, Symbol
from solidlsp import SolidLanguageServer
from solidlsp.ls import LSPFileBuffer
from solidlsp.ls_utils import TextUtils

from .project import Project
from .tools.jetbrains_plugin_client import JetBrainsPluginClient

if TYPE_CHECKING:
    from .agent import SerenaAgent


log = logging.getLogger(__name__)
TSymbol = TypeVar("TSymbol", bound=Symbol)


class CodeEditor(Generic[TSymbol], ABC):
    """
    코드 편집을 위한 기능을 제공하는 추상 기본 클래스.

    이 클래스는 특정 심볼을 기준으로 코드를 삽입, 교체, 삭제하는 고수준의 API를 정의합니다.
    실제 파일 수정 로직은 서브클래스에서 구현됩니다.
    """

    def __init__(self, project_root: str, agent: Optional["SerenaAgent"] = None) -> None:
        """
        CodeEditor를 초기화합니다.

        Args:
            project_root (str): 프로젝트의 루트 디렉토리 경로.
            agent (Optional["SerenaAgent"]): 코드 수정 후 알림을 받을 SerenaAgent 인스턴스.
        """
        self.project_root = project_root
        self.agent = agent

    class EditedFile(ABC):
        """
        편집 중인 파일의 내용을 나타내는 추상 내부 클래스.
        파일 내용에 대한 버퍼 역할을 하며, 텍스트 조작을 위한 메서드를 정의합니다.
        """

        @abstractmethod
        def get_contents(self) -> str:
            """파일의 현재 내용을 반환합니다."""

        @abstractmethod
        def delete_text_between_positions(self, start_pos: PositionInFile, end_pos: PositionInFile) -> None:
            """지정된 두 위치 사이의 텍스트를 삭제합니다."""
            pass

        @abstractmethod
        def insert_text_at_position(self, pos: PositionInFile, text: str) -> None:
            """지정된 위치에 텍스트를 삽입합니다."""
            pass

    @contextmanager
    def _open_file_context(self, relative_path: str) -> Iterator["CodeEditor.EditedFile"]:
        """파일을 열기 위한 컨텍스트 관리자입니다. 서브클래스에서 구현해야 합니다."""
        raise NotImplementedError("이 메서드는 각 서브클래스에 맞게 재정의되어야 합니다.")

    @contextmanager
    def _edited_file_context(self, relative_path: str) -> Iterator["CodeEditor.EditedFile"]:
        """
        파일 편집을 위한 컨텍스트 관리자입니다.

        파일을 열고, `EditedFile` 객체를 yield한 후, 컨텍스트를 빠져나갈 때
        변경 내용을 실제 파일에 저장하고 에이전트에 알립니다.
        """
        with self._open_file_context(relative_path) as edited_file:
            yield edited_file
            abs_path = os.path.join(self.project_root, relative_path)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(edited_file.get_contents())
            if self.agent is not None:
                self.agent.mark_file_modified(relative_path)

    @abstractmethod
    def _find_unique_symbol(self, name_path: str, relative_file_path: str) -> TSymbol:
        """
        주어진 파일에서 지정된 이름 경로를 가진 유일한 심볼을 찾습니다.
        심볼이 없거나 여러 개일 경우 ValueError를 발생시킵니다.

        Args:
            name_path (str): 찾을 심볼의 이름 경로.
            relative_file_path (str): 심볼을 검색할 파일의 상대 경로.

        Returns:
            TSymbol: 찾은 유일한 심볼 객체.
        """

    def replace_body(self, name_path: str, relative_file_path: str, body: str) -> None:
        """
        지정된 파일에 있는 심볼의 본문을 교체합니다.

        Args:
            name_path (str): 교체할 심볼의 이름 경로.
            relative_file_path (str): 심볼이 정의된 파일의 상대 경로.
            body (str): 새로운 본문 내용.
        """
        symbol = self._find_unique_symbol(name_path, relative_file_path)
        start_pos = symbol.get_body_start_position_or_raise()
        end_pos = symbol.get_body_end_position_or_raise()

        with self._edited_file_context(relative_file_path) as edited_file:
            body = body.strip()
            edited_file.delete_text_between_positions(start_pos, end_pos)
            edited_file.insert_text_at_position(start_pos, body)

    @staticmethod
    def _count_leading_newlines(text: Iterable) -> int:
        """텍스트 시작 부분의 개행 문자 수를 셉니다."""
        cnt = 0
        for c in text:
            if c == "\n":
                cnt += 1
            elif c == "\r":
                continue
            else:
                break
        return cnt

    @classmethod
    def _count_trailing_newlines(cls, text: Reversible) -> int:
        """텍스트 끝 부분의 개행 문자 수를 셉니다."""
        return cls._count_leading_newlines(reversed(text))

    def insert_after_symbol(self, name_path: str, relative_file_path: str, body: str) -> None:
        """
        지정된 심볼 뒤에 새로운 코드를 삽입합니다.

        삽입되는 코드의 앞뒤에 적절한 수의 빈 줄을 추가하여 코드 스타일을 유지합니다.
        """
        symbol = self._find_unique_symbol(name_path, relative_file_path)

        if not body.endswith("\n"):
            body += "\n"

        pos = symbol.get_body_end_position_or_raise()
        col = 0
        line = pos.line + 1

        original_leading_newlines = self._count_leading_newlines(body)
        body = body.lstrip("\r\n")
        min_empty_lines = 1 if symbol.is_neighbouring_definition_separated_by_empty_line() else 0
        num_leading_empty_lines = max(min_empty_lines, original_leading_newlines)
        if num_leading_empty_lines:
            body = ("\n" * num_leading_empty_lines) + body

        body = body.rstrip("\r\n") + "\n"

        with self._edited_file_context(relative_file_path) as edited_file:
            edited_file.insert_text_at_position(PositionInFile(line, col), body)

    def insert_before_symbol(self, name_path: str, relative_file_path: str, body: str) -> None:
        """
        지정된 심볼 앞에 새로운 코드를 삽입합니다.

        삽입되는 코드의 앞뒤에 적절한 수의 빈 줄을 추가하여 코드 스타일을 유지합니다.
        """
        symbol = self._find_unique_symbol(name_path, relative_file_path)
        symbol_start_pos = symbol.get_body_start_position_or_raise()

        line = symbol_start_pos.line
        col = 0

        original_trailing_empty_lines = self._count_trailing_newlines(body) - 1
        body = body.rstrip() + "\n"

        min_trailing_empty_lines = 1 if symbol.is_neighbouring_definition_separated_by_empty_line() else 0
        num_trailing_newlines = max(min_trailing_empty_lines, original_trailing_empty_lines)
        body += "\n" * num_trailing_newlines

        with self._edited_file_context(relative_file_path) as edited_file:
            edited_file.insert_text_at_position(PositionInFile(line=line, col=col), body)

    def insert_at_line(self, relative_path: str, line: int, content: str) -> None:
        """지정된 파일의 특정 줄에 내용을 삽입합니다."""
        with self._edited_file_context(relative_path) as edited_file:
            edited_file.insert_text_at_position(PositionInFile(line, 0), content)

    def delete_lines(self, relative_path: str, start_line: int, end_line: int) -> None:
        """지정된 파일에서 특정 범위의 줄들을 삭제합니다."""
        with self._edited_file_context(relative_path) as edited_file:
            start_pos = PositionInFile(line=start_line, col=0)
            end_pos = PositionInFile(line=end_line + 1, col=0)
            edited_file.delete_text_between_positions(start_pos, end_pos)

    def delete_symbol(self, name_path: str, relative_file_path: str) -> None:
        """지정된 파일에서 심볼을 삭제합니다."""
        symbol = self._find_unique_symbol(name_path, relative_file_path)
        start_pos = symbol.get_body_start_position_or_raise()
        end_pos = symbol.get_body_end_position_or_raise()
        with self._edited_file_context(relative_file_path) as edited_file:
            edited_file.delete_text_between_positions(start_pos, end_pos)


class LanguageServerCodeEditor(CodeEditor[LanguageServerSymbol]):
    """
    언어 서버 프로토콜(LSP)을 사용하여 코드를 편집하는 `CodeEditor`의 구체적인 구현체.
    """

    def __init__(self, symbol_retriever: LanguageServerSymbolRetriever, agent: Optional["SerenaAgent"] = None):
        super().__init__(project_root=symbol_retriever.get_language_server().repository_root_path, agent=agent)
        self._symbol_retriever = symbol_retriever

    @property
    def _lang_server(self) -> SolidLanguageServer:
        return self._symbol_retriever.get_language_server()

    class EditedFile(CodeEditor.EditedFile):
        """LSP 기반 편집을 위한 `EditedFile` 구현체."""

        def __init__(self, lang_server: SolidLanguageServer, relative_path: str, file_buffer: LSPFileBuffer):
            self._lang_server = lang_server
            self._relative_path = relative_path
            self._file_buffer = file_buffer

        def get_contents(self) -> str:
            return self._file_buffer.contents

        def delete_text_between_positions(self, start_pos: PositionInFile, end_pos: PositionInFile) -> None:
            self._lang_server.delete_text_between_positions(self._relative_path, start_pos.to_lsp_position(), end_pos.to_lsp_position())

        def insert_text_at_position(self, pos: PositionInFile, text: str) -> None:
            self._lang_server.insert_text_at_position(self._relative_path, pos.line, pos.col, text)

    @contextmanager
    def _open_file_context(self, relative_path: str) -> Iterator["CodeEditor.EditedFile"]:
        """언어 서버를 통해 파일을 열고 파일 버퍼를 제공합니다."""
        with self._lang_server.open_file(relative_path) as file_buffer:
            yield self.EditedFile(self._lang_server, relative_path, file_buffer)

    def _get_code_file_content(self, relative_path: str) -> str:
        """언어 서버를 사용하여 파일 내용을 가져옵니다."""
        return self._lang_server.language_server.retrieve_full_file_content(relative_path)

    def _find_unique_symbol(self, name_path: str, relative_file_path: str) -> LanguageServerSymbol:
        """심볼 검색기를 사용하여 유일한 심볼을 찾습니다."""
        symbol_candidates = self._symbol_retriever.find_by_name(name_path, within_relative_path=relative_file_path)
        if not symbol_candidates:
            raise ValueError(f"파일 {relative_file_path}에서 {name_path} 이름을 가진 심볼을 찾을 수 없습니다.")
        if len(symbol_candidates) > 1:
            raise ValueError(
                f"파일 {relative_file_path}에서 {name_path} 이름을 가진 심볼을 여러 개({len(symbol_candidates)}개) 찾았습니다.\n"
                f"위치: \n {json.dumps([s.location.to_dict() for s in symbol_candidates], indent=2)}"
            )
        return symbol_candidates[0]


class JetBrainsCodeEditor(CodeEditor[JetBrainsSymbol]):
    """
    JetBrains IDE 플러그인을 통해 코드를 편집하는 `CodeEditor`의 구체적인 구현체.
    """

    def __init__(self, project: Project, agent: Optional["SerenaAgent"] = None):
        self._project = project
        super().__init__(project_root=project.project_root, agent=agent)

    class EditedFile(CodeEditor.EditedFile):
        """JetBrains 기반 편집을 위한 `EditedFile` 구현체."""

        def __init__(self, relative_path: str, project: Project):
            path = os.path.join(project.project_root, relative_path)
            log.info("파일 편집: %s", path)
            with open(path, encoding=project.project_config.encoding) as f:
                self._content = f.read()

        def get_contents(self) -> str:
            return self._content

        def delete_text_between_positions(self, start_pos: PositionInFile, end_pos: PositionInFile) -> None:
            self._content, _ = TextUtils.delete_text_between_positions(
                self._content, start_pos.line, start_pos.col, end_pos.line, end_pos.col
            )

        def insert_text_at_position(self, pos: PositionInFile, text: str) -> None:
            self._content, _, _ = TextUtils.insert_text_at_position(self._content, pos.line, pos.col, text)

    @contextmanager
    def _open_file_context(self, relative_path: str) -> Iterator["CodeEditor.EditedFile"]:
        """로컬 파일 시스템에서 직접 파일을 열어 `EditedFile` 객체를 생성합니다."""
        yield self.EditedFile(relative_path, self._project)

    def _find_unique_symbol(self, name_path: str, relative_file_path: str) -> JetBrainsSymbol:
        """JetBrains 플러그인 클라이언트를 사용하여 유일한 심볼을 찾습니다."""
        with JetBrainsPluginClient.from_project(self._project) as client:
            result = client.find_symbol(name_path, relative_path=relative_file_path, include_body=False, depth=0, include_location=True)
            symbols = result["symbols"]
            if not symbols:
                raise ValueError(f"파일 {relative_file_path}에서 {name_path} 이름을 가진 심볼을 찾을 수 없습니다.")
            if len(symbols) > 1:
                raise ValueError(
                    f"파일 {relative_file_path}에서 {name_path} 이름을 가진 심볼을 여러 개({len(symbols)}개) 찾았습니다.\n"
                    f"위치: \n {json.dumps([s['location'] for s in symbols], indent=2)}"
                )
            return JetBrainsSymbol(symbols[0], self._project)