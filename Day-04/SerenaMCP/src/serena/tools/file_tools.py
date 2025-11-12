"""
SerenaMCP 파일 및 파일 시스템 관련 도구들

이 모듈은 파일 시스템 관련 작업을 수행하는 도구들을 제공합니다:
- 디렉토리 내용 목록 조회
- 파일 읽기 및 생성
- 파일 수준 편집 기능
- 텍스트 검색 및 치환

주요 도구 클래스들:
- ReadFileTool: 파일 읽기 도구
- CreateTextFileTool: 새 파일 생성 도구
- ListDirTool: 디렉토리 목록 조회 도구
- FindFileTool: 파일 검색 도구
- ReplaceRegexTool: 정규식 기반 텍스트 치환 도구
- DeleteLinesTool: 파일에서 라인 삭제 도구
- ReplaceLinesTool: 파일에서 라인 치환 도구
- InsertAtLineTool: 파일의 특정 위치에 내용 삽입 도구
- SearchForPatternTool: 패턴 기반 텍스트 검색 도구
"""

import json
import os
import re
from collections import defaultdict
from fnmatch import fnmatch
from pathlib import Path

from serena.text_utils import search_files
from serena.tools import SUCCESS_RESULT, EditedFileContext, Tool, ToolMarkerCanEdit, ToolMarkerOptional
from serena.util.file_system import scan_directory


class ReadFileTool(Tool):
    """
    프로젝트 디렉토리 내의 파일을 읽는 도구.

    이 도구는 파일의 전체 또는 일부를 읽어올 수 있으며,
    심볼 기반 작업(find_symbol, find_referencing_symbols) 대신
    파일 내용 전체를 확인해야 하는 경우에 사용됩니다.

    주요 기능:
    - 전체 파일 읽기
    - 특정 라인 범위 읽기
    - 파일 경로 유효성 검증
    - 읽기 캐시 관리
    - 응답 크기 제한

    Args:
        relative_path: 읽을 파일의 상대 경로 (프로젝트 루트 기준)
        start_line: 읽어올 첫 번째 라인의 0-based 인덱스 (기본값: 0)
        end_line: 읽어올 마지막 라인의 0-based 인덱스 (포함, 기본값: None = 파일 끝까지)
        max_answer_chars: 파일 크기 제한 (기본값: -1 = 제한 없음)

    Returns:
        파일 내용 텍스트

    Note:
        심볼이 어떤 것인지 알고 있다면 find_symbol이나 find_referencing_symbols를
        사용하는 것이 더 효율적입니다. 이 도구는 파일 전체 내용을 확인해야 하는
        경우에만 사용하십시오.
    """

    def apply(self, relative_path: str, start_line: int = 0, end_line: int | None = None, max_answer_chars: int = -1) -> str:
        """
        주어진 파일 또는 파일의 일부를 읽어옵니다.

        심볼 기반 작업(find_symbol, find_referencing_symbols)을 사용하는 것이
        더 효율적이지만, 심볼이 어떤 것인지 모를 때는 이 도구를 사용하십시오.

        Args:
            relative_path: 읽을 파일의 상대 경로
            start_line: 읽어올 첫 번째 라인의 0-based 인덱스
            end_line: 읽어올 마지막 라인의 0-based 인덱스 (포함). None이면 파일 끝까지 읽음
            max_answer_chars: 파일 크기 제한. 이 크기를 초과하면 내용이 반환되지 않음.
                            작업에 필요한 내용이 없을 때만 조정하십시오.

        Returns:
            지정된 상대 경로의 파일 전체 텍스트
        """
        # 1. 파일 경로 유효성 검증 (프로젝트 내 파일인지 확인)
        self.project.validate_relative_path(relative_path)

        # 2. 파일 내용 읽기
        result = self.project.read_file(relative_path)
        result_lines = result.splitlines()

        # 3. 라인 범위에 따른 내용 추출
        if end_line is None:
            # 파일 끝까지 읽기
            result_lines = result_lines[start_line:]
        else:
            # 특정 라인 범위만 읽기 (읽기 캐시에 기록)
            self.lines_read.add_lines_read(relative_path, (start_line, end_line))
            result_lines = result_lines[start_line : end_line + 1]

        # 4. 라인들을 다시 문자열로 결합
        result = "\n".join(result_lines)

        # 5. 응답 크기 제한 적용 (너무 큰 파일은 제한)
        return self._limit_length(result, max_answer_chars)


class CreateTextFileTool(Tool, ToolMarkerCanEdit):
    """
    프로젝트 디렉토리에 새 파일을 생성하거나 기존 파일을 덮어쓰는 도구.

    이 도구는 텍스트 파일을 생성하거나 기존 파일의 내용을 완전히 교체할 때 사용됩니다.
    파일이 이미 존재하는 경우 기존 내용을 완전히 덮어씁니다.

    주요 기능:
    - 새 파일 생성
    - 기존 파일 덮어쓰기
    - 파일 경로 유효성 검증
    - UTF-8 인코딩으로 저장
    - 디렉토리 자동 생성

    Args:
        relative_path: 생성/덮어쓸 파일의 상대 경로
        content: 파일에 작성할 내용 (UTF-8 인코딩)

    Returns:
        성공 또는 실패 메시지
    """

    def apply(self, relative_path: str, content: str) -> str:
        """
        새 파일을 작성하거나 기존 파일을 덮어씁니다.

        Args:
            relative_path: 생성할 파일의 상대 경로
            content: 파일에 작성할 내용 (UTF-8 인코딩)

        Returns:
            성공 또는 실패를 나타내는 메시지
        """
        # 1. 프로젝트 루트에서 절대 경로 계산
        project_root = self.get_project_root()
        abs_path = (Path(project_root) / relative_path).resolve()
        will_overwrite_existing = abs_path.exists()

        # 2. 파일 존재 여부에 따른 처리
        if will_overwrite_existing:
            # 기존 파일 덮어쓰기 - 경로 유효성 검증
            self.project.validate_relative_path(relative_path)
        else:
            # 새 파일 생성 - 프로젝트 디렉토리 내에만 생성 가능하도록 검증
            assert abs_path.is_relative_to(
                self.get_project_root()
            ), f"Cannot create file outside of the project directory, got {relative_path=}"

        # 3. 상위 디렉토리 생성 (존재하지 않는 경우)
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # 4. 파일에 내용 작성 (UTF-8 인코딩)
        abs_path.write_text(content, encoding="utf-8")

        # 5. 결과 메시지 생성
        answer = f"File created: {relative_path}."
        if will_overwrite_existing:
            answer += " Overwrote existing file."
        return json.dumps(answer)


class ListDirTool(Tool):
    """
    Lists files and directories in the given directory (optionally with recursion).
    """

    def apply(self, relative_path: str, recursive: bool, skip_ignored_files: bool = False, max_answer_chars: int = -1) -> str:
        """
        Lists all non-gitignored files and directories in the given directory (optionally with recursion).

        :param relative_path: the relative path to the directory to list; pass "." to scan the project root
        :param recursive: whether to scan subdirectories recursively
        :param skip_ignored_files: whether to skip files and directories that are ignored
        :param max_answer_chars: if the output is longer than this number of characters,
            no content will be returned. -1 means the default value from the config will be used.
            Don't adjust unless there is really no other way to get the content required for the task.
        :return: a JSON object with the names of directories and files within the given directory
        """
        # Check if the directory exists before validation
        if not self.project.relative_path_exists(relative_path):
            error_info = {
                "error": f"Directory not found: {relative_path}",
                "project_root": self.get_project_root(),
                "hint": "Check if the path is correct relative to the project root",
            }
            return json.dumps(error_info)

        self.project.validate_relative_path(relative_path)

        dirs, files = scan_directory(
            os.path.join(self.get_project_root(), relative_path),
            relative_to=self.get_project_root(),
            recursive=recursive,
            is_ignored_dir=self.project.is_ignored_path if skip_ignored_files else None,
            is_ignored_file=self.project.is_ignored_path if skip_ignored_files else None,
        )

        result = json.dumps({"dirs": dirs, "files": files})
        return self._limit_length(result, max_answer_chars)


class FindFileTool(Tool):
    """
    Finds files in the given relative paths
    """

    def apply(self, file_mask: str, relative_path: str) -> str:
        """
        Finds non-gitignored files matching the given file mask within the given relative path

        :param file_mask: the filename or file mask (using the wildcards * or ?) to search for
        :param relative_path: the relative path to the directory to search in; pass "." to scan the project root
        :return: a JSON object with the list of matching files
        """
        self.project.validate_relative_path(relative_path)

        dir_to_scan = os.path.join(self.get_project_root(), relative_path)

        # find the files by ignoring everything that doesn't match
        def is_ignored_file(abs_path: str) -> bool:
            if self.project.is_ignored_path(abs_path):
                return True
            filename = os.path.basename(abs_path)
            return not fnmatch(filename, file_mask)

        _dirs, files = scan_directory(
            path=dir_to_scan,
            recursive=True,
            is_ignored_dir=self.project.is_ignored_path,
            is_ignored_file=is_ignored_file,
            relative_to=self.get_project_root(),
        )

        result = json.dumps({"files": files})
        return result


class ReplaceRegexTool(Tool, ToolMarkerCanEdit):
    """
    Replaces content in a file by using regular expressions.
    """

    def apply(
        self,
        relative_path: str,
        regex: str,
        repl: str,
        allow_multiple_occurrences: bool = False,
    ) -> str:
        r"""
        Replaces one or more occurrences of the given regular expression.
        This is the preferred way to replace content in a file whenever the symbol-level
        tools are not appropriate.
        Even large sections of code can be replaced by providing a concise regular expression of
        the form "beginning.*?end-of-text-to-be-replaced".
        Always try to use wildcards to avoid specifying the exact content of the code to be replaced,
        especially if it spans several lines.

        IMPORTANT: REMEMBER TO USE WILDCARDS WHEN APPROPRIATE! I WILL BE VERY UNHAPPY IF YOU WRITE LONG REGEXES WITHOUT USING WILDCARDS INSTEAD!

        :param relative_path: the relative path to the file
        :param regex: a Python-style regular expression, matches of which will be replaced.
            Dot matches all characters, multi-line matching is enabled.
        :param repl: the string to replace the matched content with, which may contain
            backreferences like \1, \2, etc.
            Make sure to escape special characters appropriately, e.g., use `\\n` for a literal `\n`.
        :param allow_multiple_occurrences: if True, the regex may match multiple occurrences in the file
            and all of them will be replaced.
            If this is set to False and the regex matches multiple occurrences, an error will be returned
            (and you may retry with a revised, more specific regex).
        """
        self.project.validate_relative_path(relative_path)
        with EditedFileContext(relative_path, self.agent) as context:
            original_content = context.get_original_content()
            updated_content, n = re.subn(regex, repl, original_content, flags=re.DOTALL | re.MULTILINE)
            if n == 0:
                return f"Error: No matches found for regex '{regex}' in file '{relative_path}'."
            if not allow_multiple_occurrences and n > 1:
                return (
                    f"Error: Regex '{regex}' matches {n} occurrences in file '{relative_path}'. "
                    "Please revise the regex to be more specific or enable allow_multiple_occurrences if this is expected."
                )
            context.set_updated_content(updated_content)
        return SUCCESS_RESULT


class DeleteLinesTool(Tool, ToolMarkerCanEdit, ToolMarkerOptional):
    """
    Deletes a range of lines within a file.
    """

    def apply(
        self,
        relative_path: str,
        start_line: int,
        end_line: int,
    ) -> str:
        """
        Deletes the given lines in the file.
        Requires that the same range of lines was previously read using the `read_file` tool to verify correctness
        of the operation.

        :param relative_path: the relative path to the file
        :param start_line: the 0-based index of the first line to be deleted
        :param end_line: the 0-based index of the last line to be deleted
        """
        if not self.lines_read.were_lines_read(relative_path, (start_line, end_line)):
            read_lines_tool = self.agent.get_tool(ReadFileTool)
            return f"Error: Must call `{read_lines_tool.get_name_from_cls()}` first to read exactly the affected lines."
        code_editor = self.create_code_editor()
        code_editor.delete_lines(relative_path, start_line, end_line)
        return SUCCESS_RESULT


class ReplaceLinesTool(Tool, ToolMarkerCanEdit, ToolMarkerOptional):
    """
    Replaces a range of lines within a file with new content.
    """

    def apply(
        self,
        relative_path: str,
        start_line: int,
        end_line: int,
        content: str,
    ) -> str:
        """
        Replaces the given range of lines in the given file.
        Requires that the same range of lines was previously read using the `read_file` tool to verify correctness
        of the operation.

        :param relative_path: the relative path to the file
        :param start_line: the 0-based index of the first line to be deleted
        :param end_line: the 0-based index of the last line to be deleted
        :param content: the content to insert
        """
        if not content.endswith("\n"):
            content += "\n"
        result = self.agent.get_tool(DeleteLinesTool).apply(relative_path, start_line, end_line)
        if result != SUCCESS_RESULT:
            return result
        self.agent.get_tool(InsertAtLineTool).apply(relative_path, start_line, content)
        return SUCCESS_RESULT


class InsertAtLineTool(Tool, ToolMarkerCanEdit, ToolMarkerOptional):
    """
    Inserts content at a given line in a file.
    """

    def apply(
        self,
        relative_path: str,
        line: int,
        content: str,
    ) -> str:
        """
        Inserts the given content at the given line in the file, pushing existing content of the line down.
        In general, symbolic insert operations like insert_after_symbol or insert_before_symbol should be preferred if you know which
        symbol you are looking for.
        However, this can also be useful for small targeted edits of the body of a longer symbol (without replacing the entire body).

        :param relative_path: the relative path to the file
        :param line: the 0-based index of the line to insert content at
        :param content: the content to be inserted
        """
        if not content.endswith("\n"):
            content += "\n"
        code_editor = self.create_code_editor()
        code_editor.insert_at_line(relative_path, line, content)
        return SUCCESS_RESULT


class SearchForPatternTool(Tool):
    """
    Performs a search for a pattern in the project.
    """

    def apply(
        self,
        substring_pattern: str,
        context_lines_before: int = 0,
        context_lines_after: int = 0,
        paths_include_glob: str = "",
        paths_exclude_glob: str = "",
        relative_path: str = "",
        restrict_search_to_code_files: bool = False,
        max_answer_chars: int = -1,
    ) -> str:
        """
        Offers a flexible search for arbitrary patterns in the codebase, including the
        possibility to search in non-code files.
        Generally, symbolic operations like find_symbol or find_referencing_symbols
        should be preferred if you know which symbols you are looking for.

        Pattern Matching Logic:
            For each match, the returned result will contain the full lines where the
            substring pattern is found, as well as optionally some lines before and after it. The pattern will be compiled with
            DOTALL, meaning that the dot will match all characters including newlines.
            This also means that it never makes sense to have .* at the beginning or end of the pattern,
            but it may make sense to have it in the middle for complex patterns.
            If a pattern matches multiple lines, all those lines will be part of the match.
            Be careful to not use greedy quantifiers unnecessarily, it is usually better to use non-greedy quantifiers like .*? to avoid
            matching too much content.

        File Selection Logic:
            The files in which the search is performed can be restricted very flexibly.
            Using `restrict_search_to_code_files` is useful if you are only interested in code symbols (i.e., those
            symbols that can be manipulated with symbolic tools like find_symbol).
            You can also restrict the search to a specific file or directory,
            and provide glob patterns to include or exclude certain files on top of that.
            The globs are matched against relative file paths from the project root (not to the `relative_path` parameter that
            is used to further restrict the search).
            Smartly combining the various restrictions allows you to perform very targeted searches.


        :param substring_pattern: Regular expression for a substring pattern to search for
        :param context_lines_before: Number of lines of context to include before each match
        :param context_lines_after: Number of lines of context to include after each match
        :param paths_include_glob: optional glob pattern specifying files to include in the search.
            Matches against relative file paths from the project root (e.g., "*.py", "src/**/*.ts").
            Only matches files, not directories. If left empty, all non-ignored files will be included.
        :param paths_exclude_glob: optional glob pattern specifying files to exclude from the search.
            Matches against relative file paths from the project root (e.g., "*test*", "**/*_generated.py").
            Takes precedence over paths_include_glob. Only matches files, not directories. If left empty, no files are excluded.
        :param relative_path: only subpaths of this path (relative to the repo root) will be analyzed. If a path to a single
            file is passed, only that will be searched. The path must exist, otherwise a `FileNotFoundError` is raised.
        :param max_answer_chars: if the output is longer than this number of characters,
            no content will be returned.
            -1 means the default value from the config will be used.
            Don't adjust unless there is really no other way to get the content
            required for the task. Instead, if the output is too long, you should
            make a stricter query.
        :param restrict_search_to_code_files: whether to restrict the search to only those files where
            analyzed code symbols can be found. Otherwise, will search all non-ignored files.
            Set this to True if your search is only meant to discover code that can be manipulated with symbolic tools.
            For example, for finding classes or methods from a name pattern.
            Setting to False is a better choice if you also want to search in non-code files, like in html or yaml files,
            which is why it is the default.
        :return: A mapping of file paths to lists of matched consecutive lines.
        """
        abs_path = os.path.join(self.get_project_root(), relative_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Relative path {relative_path} does not exist.")

        if restrict_search_to_code_files:
            matches = self.project.search_source_files_for_pattern(
                pattern=substring_pattern,
                relative_path=relative_path,
                context_lines_before=context_lines_before,
                context_lines_after=context_lines_after,
                paths_include_glob=paths_include_glob.strip(),
                paths_exclude_glob=paths_exclude_glob.strip(),
            )
        else:
            if os.path.isfile(abs_path):
                rel_paths_to_search = [relative_path]
            else:
                _dirs, rel_paths_to_search = scan_directory(
                    path=abs_path,
                    recursive=True,
                    is_ignored_dir=self.project.is_ignored_path,
                    is_ignored_file=self.project.is_ignored_path,
                    relative_to=self.get_project_root(),
                )
            # TODO (maybe): not super efficient to walk through the files again and filter if glob patterns are provided
            #   but it probably never matters and this version required no further refactoring
            matches = search_files(
                rel_paths_to_search,
                substring_pattern,
                root_path=self.get_project_root(),
                paths_include_glob=paths_include_glob,
                paths_exclude_glob=paths_exclude_glob,
            )
        # group matches by file
        file_to_matches: dict[str, list[str]] = defaultdict(list)
        for match in matches:
            assert match.source_file_path is not None
            file_to_matches[match.source_file_path].append(match.to_display_string())
        result = json.dumps(file_to_matches)
        return self._limit_length(result, max_answer_chars)
