"""
serena/text_utils.py - 텍스트 처리 및 검색 유틸리티

이 파일은 텍스트 검색, 필터링, 형식화 등 텍스트 데이터를 처리하기 위한
다양한 유틸리티 클래스와 함수들을 제공합니다.

주요 컴포넌트:
- LineType: 텍스트 검색 결과에서 각 줄의 유형(매치, 이전, 이후)을 나타내는 열거형.
- TextLine: 줄 번호, 내용, 유형 정보를 포함하는 단일 텍스트 줄을 나타내는 데이터 클래스.
- MatchedConsecutiveLines: 검색 패턴과 일치하는 연속된 텍스트 줄들과 그 주변 컨텍스트를
  캡슐화하는 데이터 클래스.
- search_text: 단일 텍스트 콘텐츠 내에서 정규식 또는 글로브(glob) 패턴을 검색합니다.
- search_files: 여러 파일에 걸쳐 병렬로 텍스트 검색을 수행합니다.
- glob_to_regex: 글로브 패턴을 정규식으로 변환합니다.

아키텍처 노트:
- `joblib` 라이브러리를 사용하여 `search_files` 함수에서 파일 검색을 병렬로 처리함으로써,
  대규모 코드베이스에서도 빠른 검색 성능을 제공합니다.
- `MatchedConsecutiveLines`와 같은 데이터 클래스를 사용하여 검색 결과를 구조화된 형태로
  반환하므로, 호출하는 쪽에서 결과를 쉽게 처리하고 활용할 수 있습니다.
- `search_text`와 `search_files`는 컨텍스트 라인(before/after)을 포함하여 검색 결과를
  제공하는 기능을 지원하여, LLM이 코드의 맥락을 더 잘 이해하도록 돕습니다.
"""

import fnmatch
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self

from joblib import Parallel, delayed

log = logging.getLogger(__name__)


class LineType(StrEnum):
    """검색 결과의 줄 유형에 대한 열거형입니다."""

    MATCH = "match"
    """일치하는 줄의 일부"""
    BEFORE_MATCH = "prefix"
    """일치 항목 이전 줄"""
    AFTER_MATCH = "postfix"
    """일치 항목 이후 줄"""


@dataclass(kw_only=True)
class TextLine:
    """일치 항목과의 관계에 대한 정보가 포함된 텍스트 한 줄을 나타냅니다."""

    line_number: int
    line_content: str
    match_type: LineType
    """줄 유형(일치, 접두사, 접미사)을 나타냅니다."""

    def get_display_prefix(self) -> str:
        """일치 유형에 따라 이 줄의 표시 접두사를 가져옵니다."""
        if self.match_type == LineType.MATCH:
            return "  >"
        return "..."

    def format_line(self, include_line_numbers: bool = True) -> str:
        """표시용으로 줄의 형식을 지정합니다(예: 로깅 또는 LLM에 전달용).

        :param include_line_numbers: 결과에 줄 번호를 포함할지 여부.
        """
        prefix = self.get_display_prefix()
        if include_line_numbers:
            line_num = str(self.line_number).rjust(4)
            prefix = f"{prefix}{line_num}"
        return f"{prefix}:{self.line_content}"


@dataclass(kw_only=True)
class MatchedConsecutiveLines:
    """텍스트 파일이나 문자열에서 어떤 기준으로 찾은 연속된 줄의 모음을 나타냅니다.
    일치 항목 이전, 이후, 그리고 일치하는 줄을 포함할 수 있습니다.
    """

    lines: list[TextLine]
    """일치 항목의 컨텍스트에 있는 모든 줄. 그중 적어도 하나는 `match_type`이 `MATCH`입니다."""
    source_file_path: str | None = None
    """일치 항목이 발견된 파일 경로 (메타데이터)."""

    # post-init에서 설정
    lines_before_matched: list[TextLine] = field(default_factory=list)
    matched_lines: list[TextLine] = field(default_factory=list)
    lines_after_matched: list[TextLine] = field(default_factory=list)

    def __post_init__(self) -> None:
        for line in self.lines:
            if line.match_type == LineType.BEFORE_MATCH:
                self.lines_before_matched.append(line)
            elif line.match_type == LineType.MATCH:
                self.matched_lines.append(line)
            elif line.match_type == LineType.AFTER_MATCH:
                self.lines_after_matched.append(line)

        assert len(self.matched_lines) > 0, "일치하는 줄이 하나 이상 필요합니다."

    @property
    def start_line(self) -> int:
        return self.lines[0].line_number

    @property
    def end_line(self) -> int:
        return self.lines[-1].line_number

    @property
    def num_matched_lines(self) -> int:
        return len(self.matched_lines)

    def to_display_string(self, include_line_numbers: bool = True) -> str:
        return "\n".join([line.format_line(include_line_numbers) for line in self.lines])

    @classmethod
    def from_file_contents(
        cls, file_contents: str, line: int, context_lines_before: int = 0, context_lines_after: int = 0, source_file_path: str | None = None
    ) -> Self:
        line_contents = file_contents.split("\n")
        start_lineno = max(0, line - context_lines_before)
        end_lineno = min(len(line_contents) - 1, line + context_lines_after)
        text_lines: list[TextLine] = []
        # 줄 이전
        for lineno in range(start_lineno, line):
            text_lines.append(TextLine(line_number=lineno, line_content=line_contents[lineno], match_type=LineType.BEFORE_MATCH))
        # 해당 줄
        text_lines.append(TextLine(line_number=line, line_content=line_contents[line], match_type=LineType.MATCH))
        # 줄 이후
        for lineno in range(line + 1, end_lineno + 1):
            text_lines.append(TextLine(line_number=lineno, line_content=line_contents[lineno], match_type=LineType.AFTER_MATCH))

        return cls(lines=text_lines, source_file_path=source_file_path)


def glob_to_regex(glob_pat: str) -> str:
    regex_parts: list[str] = []
    i = 0
    while i < len(glob_pat):
        ch = glob_pat[i]
        if ch == "*":
            regex_parts.append(".*")
        elif ch == "?":
            regex_parts.append(".")
        elif ch == "\\":
            i += 1
            if i < len(glob_pat):
                regex_parts.append(re.escape(glob_pat[i]))
            else:
                regex_parts.append("\\")
        else:
            regex_parts.append(re.escape(ch))
        i += 1
    return "".join(regex_parts)


def search_text(
    pattern: str,
    content: str | None = None,
    source_file_path: str | None = None,
    allow_multiline_match: bool = False,
    context_lines_before: int = 0,
    context_lines_after: int = 0,
    is_glob: bool = False,
) -> list[MatchedConsecutiveLines]:
    """
    텍스트 내용에서 패턴을 검색합니다. 정규식 및 glob 유사 패턴을 모두 지원합니다.

    :param pattern: 검색할 패턴 (정규식 또는 glob 유사 패턴)
    :param content: 검색할 텍스트 내용. source_file_path가 제공되면 None일 수 있습니다.
    :param source_file_path: 소스 파일의 선택적 경로. content가 None이면
        이것을 전달해야 하며 파일이 읽힙니다.
    :param allow_multiline_match: 여러 줄에 걸쳐 검색할지 여부. 현재 기본
        옵션(False)은 매우 비효율적이므로 True로 설정하는 것이 좋습니다.
    :param context_lines_before: 일치 항목 앞에 포함할 컨텍스트 줄 수
    :param context_lines_after: 일치 항목 뒤에 포함할 컨텍스트 줄 수
    :param is_glob: True이면 패턴이 glob 유사 패턴(예: "*.py", "test_??.py")으로 처리되어
             내부적으로 정규식으로 변환됩니다.

    :return: `TextSearchMatch` 객체 목록

    :raises: 패턴이 유효하지 않은 경우 ValueError

    """
    if source_file_path and content is None:
        with open(source_file_path) as f:
            content = f.read()

    if content is None:
        raise ValueError("content 또는 source_file_path를 전달해야 합니다.")

    matches = []
    lines = content.splitlines()
    total_lines = len(lines)

    # 패턴이 문자열인 경우 컴파일된 정규식으로 변환
    if is_glob:
        pattern = glob_to_regex(pattern)
    if allow_multiline_match:
        # 여러 줄 일치를 위해 DOTALL 플래그를 사용하여 '.'이 개행 문자와 일치하도록 해야 합니다.
        compiled_pattern = re.compile(pattern, re.DOTALL)
        # 전체 내용을 단일 문자열로 검색
        for match in compiled_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()

            # 시작 및 끝 위치의 줄 번호 찾기
            start_line_num = content[:start_pos].count("\n") + 1
            end_line_num = content[:end_pos].count("\n") + 1

            # 컨텍스트에 포함할 줄 범위 계산
            context_start = max(1, start_line_num - context_lines_before)
            context_end = min(total_lines, end_line_num + context_lines_after)

            # 컨텍스트에 대한 TextLine 객체 생성
            context_lines = []
            for i in range(context_start - 1, context_end):
                line_num = i + 1
                if context_start <= line_num < start_line_num:
                    match_type = LineType.BEFORE_MATCH
                elif end_line_num < line_num <= context_end:
                    match_type = LineType.AFTER_MATCH
                else:
                    match_type = LineType.MATCH

                context_lines.append(TextLine(line_number=line_num, line_content=lines[i], match_type=match_type))

            matches.append(MatchedConsecutiveLines(lines=context_lines, source_file_path=source_file_path))
    else:
        # TODO: 매우 비효율적입니다! 현재 SerenaAgent나 LanguageServer에서 이 옵션을 사용하지 않으므로
        #   수정이 시급하지는 않지만 개선하거나 옵션을 제거해야 합니다.
        # 줄 단위로 검색, DOTALL 없이 일반 컴파일
        compiled_pattern = re.compile(pattern)
        for i, line in enumerate(lines):
            line_num = i + 1
            if compiled_pattern.search(line):
                # 컨텍스트에 포함할 줄 범위 계산
                context_start = max(0, i - context_lines_before)
                context_end = min(total_lines - 1, i + context_lines_after)

                # 컨텍스트에 대한 TextLine 객체 생성
                context_lines = []
                for j in range(context_start, context_end + 1):
                    context_line_num = j + 1
                    if j < i:
                        match_type = LineType.BEFORE_MATCH
                    elif j > i:
                        match_type = LineType.AFTER_MATCH
                    else:
                        match_type = LineType.MATCH

                    context_lines.append(TextLine(line_number=context_line_num, line_content=lines[j], match_type=match_type))

                matches.append(MatchedConsecutiveLines(lines=context_lines, source_file_path=source_file_path))

    return matches


def default_file_reader(file_path: str) -> str:
    """utf-8 인코딩을 사용하여 읽습니다."""
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def glob_match(pattern: str, path: str) -> bool:
    """
    파일 경로를 glob 패턴과 비교합니다.

    표준 glob 패턴 지원:
    - *는 /를 제외한 모든 문자와 일치
    - **는 0개 이상의 디렉토리와 일치
    - ?는 /를 제외한 단일 문자와 일치
    - [seq]는 seq의 모든 문자와 일치

    :param pattern: Glob 패턴 (예: 'src/**/*.py', '**agent.py')
    :param path: 비교할 파일 경로
    :return: 경로가 패턴과 일치하면 True
    """
    pattern = pattern.replace("\\", "/")  # 백슬래시를 슬래시로 정규화
    path = path.replace("\\", "/")  # 경로 백슬래시를 슬래시로 정규화

    # 0개 이상의 디렉토리와 일치해야 하는 ** 패턴 처리
    if "**" in pattern:
        # 방법 1: 표준 fnmatch (하나 이상의 디렉토리와 일치)
        regex1 = fnmatch.translate(pattern)
        if re.match(regex1, path):
            return True

        # 방법 2: /**/를 완전히 제거하여 0-디렉토리 경우 처리
        # "src/**/test.py"를 "src/test.py"로 변환
        if "/**/" in pattern:
            zero_dir_pattern = pattern.replace("/**/", "/")
            regex2 = fnmatch.translate(zero_dir_pattern)
            if re.match(regex2, path):
                return True

        # 방법 3: **/를 제거하여 선행 ** 경우 처리
        # "**/test.py"를 "test.py"로 변환
        if pattern.startswith("**/",):
            zero_dir_pattern = pattern[3:]  # "**\/" 제거
            regex3 = fnmatch.translate(zero_dir_pattern)
            if re.match(regex3, path):
                return True

        return False
    else:
        # **가 없는 단순 패턴, fnmatch 직접 사용
        return fnmatch.fnmatch(path, pattern)


def search_files(
    relative_file_paths: list[str],
    pattern: str,
    root_path: str = "",
    file_reader: Callable[[str], str] = default_file_reader,
    context_lines_before: int = 0,
    context_lines_after: int = 0,
    paths_include_glob: str | None = None,
    paths_exclude_glob: str | None = None,
) -> list[MatchedConsecutiveLines]:
    """
    파일 목록에서 패턴을 검색합니다.

    :param relative_file_paths: 검색할 상대 파일 경로 목록
    :param pattern: 검색할 패턴
    :param root_path: 상대 경로를 확인할 루트 경로 (기본값: 현재 작업 디렉토리).
    :param file_reader: 파일을 읽는 함수, 기본적으로 os.open을 사용합니다.
        읽을 수 없는 모든 파일은 건너뜁니다.
    :param context_lines_before: 일치 항목 앞에 포함할 컨텍스트 줄 수
    :param context_lines_after: 일치 항목 뒤에 포함할 컨텍스트 줄 수
    :param paths_include_glob: 목록에서 파일을 포함할 선택적 glob 패턴
    :param paths_exclude_glob: 목록에서 파일을 제외할 선택적 glob 패턴. paths_include_glob보다 우선합니다.
    :return: MatchedConsecutiveLines 객체 목록
    """
    # 경로 사전 필터링 (오버헤드를 피하기 위해 순차적으로 수행)
    # gitignore 패턴 대신 적절한 glob 일치 사용
    filtered_paths = []
    for path in relative_file_paths:
        if paths_include_glob and not glob_match(paths_include_glob, path):
            log.debug(f"{path} 건너뛰기: 포함 패턴 {paths_include_glob}과 일치하지 않음")
            continue
        if paths_exclude_glob and glob_match(paths_exclude_glob, path):
            log.debug(f"{path} 건너뛰기: 제외 패턴 {paths_exclude_glob}과 일치함")
            continue
        filtered_paths.append(path)

    log.info(f"{len(filtered_paths)}개 파일 처리 중.")

    def process_single_file(path: str) -> dict[str, Any]:
        """단일 파일 처리 - 이 함수는 병렬화됩니다."""
        try:
            abs_path = os.path.join(root_path, path)
            file_content = file_reader(abs_path)
            search_results = search_text(
                pattern,
                content=file_content,
                source_file_path=path,
                allow_multiline_match=True,
                context_lines_before=context_lines_before,
                context_lines_after=context_lines_after,
            )
            if len(search_results) > 0:
                log.debug(f"{path}에서 {len(search_results)}개 일치 항목 찾음")
            return {"path": path, "results": search_results, "error": None}
        except Exception as e:
            log.debug(f"{path} 처리 중 오류: {e}")
            return {"path": path, "results": [], "error": str(e)}

    # joblib을 사용하여 병렬 실행
    results = Parallel(
        n_jobs=-1,
        backend="threading",
    )(delayed(process_single_file)(path) for path in filtered_paths)

    # 결과 및 오류 수집
    matches = []
    skipped_file_error_tuples = []

    for result in results:
        if result["error"]:
            skipped_file_error_tuples.append((result["path"], result["error"]))
        else:
            matches.extend(result["results"])

    if skipped_file_error_tuples:
        log.debug(f"{len(skipped_file_error_tuples)}개 파일 읽기 실패: {skipped_file_error_tuples}")

    log.info(f"{len(filtered_paths)}개 파일에서 총 {len(matches)}개 일치 항목 찾음")
    return matches