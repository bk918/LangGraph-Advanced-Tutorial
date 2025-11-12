"""
serena/util/file_system.py - 파일 시스템 유틸리티

이 파일은 파일 시스템을 탐색하고, `.gitignore` 규칙에 따라 파일을 필터링하는 등
파일 시스템과 관련된 저수준 유틸리티 함수들을 제공합니다.

주요 컴포넌트:
- scan_directory: 디렉토리를 재귀적으로 또는 비재귀적으로 스캔하여 파일 및 디렉토리 목록을 반환합니다.
- find_all_non_ignored_files: `.gitignore` 파일을 모두 찾아, 무시되지 않는 모든 파일 목록을 반환합니다.
- GitignoreParser: 리포지토리 내의 모든 `.gitignore` 파일을 파싱하고, 특정 경로가 무시되어야 하는지
  판단하는 핵심 클래스입니다.
- GitignoreSpec: 단일 `.gitignore` 파일의 규칙을 캡슐화하는 데이터 클래스입니다.

아키텍처 노트:
- `GitignoreParser`는 리포지토리 루트부터 시작하여 모든 하위 디렉토리의 `.gitignore` 파일을
  계층적으로 로드하고 적용합니다. 이는 실제 `git`의 동작 방식을 모방한 것입니다.
- `pathspec` 라이브러리를 사용하여 `.gitignore` 패턴 매칭을 효율적으로 수행합니다.
- `scan_directory` 함수는 `is_ignored_dir`와 `is_ignored_file` 콜백 함수를 인자로 받아,
  유연한 필터링 로직을 적용할 수 있도록 설계되었습니다.
- `match_path` 함수는 `pathspec` 라이브러리의 디렉토리 매칭 관련 한계를 해결하기 위한
  래퍼(wrapper) 함수를 제공합니다.
"""

import logging
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import pathspec
from pathspec import PathSpec
from sensai.util.logging import LogTime

log = logging.getLogger(__name__)


class ScanResult(NamedTuple):
    """디렉토리 스캔 결과를 담는 NamedTuple."""

    directories: list[str]
    files: list[str]


def scan_directory(
    path: str,
    recursive: bool = False,
    relative_to: str | None = None,
    is_ignored_dir: Callable[[str], bool] | None = None,
    is_ignored_file: Callable[[str], bool] | None = None,
) -> ScanResult:
    """
    지정된 경로를 스캔하여 디렉토리와 파일 목록을 반환합니다.

    Args:
        path (str): 스캔할 경로.
        recursive (bool): 하위 디렉토리를 재귀적으로 스캔할지 여부.
        relative_to (str | None): 결과를 상대 경로로 만들 기준 경로. None이면 절대 경로를 반환합니다.
        is_ignored_dir (Callable | None): 특정 디렉토리(절대 경로)를 무시할지 결정하는 함수.
        is_ignored_file (Callable | None): 특정 파일(절대 경로)을 무시할지 결정하는 함수.

    Returns:
        ScanResult: 디렉토리 목록과 파일 목록을 담은 튜플.
    """
    is_ignored_file = is_ignored_file or (lambda x: False)
    is_ignored_dir = is_ignored_dir or (lambda x: False)

    files = []
    directories = []

    abs_path = os.path.abspath(path)
    rel_base = os.path.abspath(relative_to) if relative_to else None

    try:
        with os.scandir(abs_path) as entries:
            for entry in entries:
                try:
                    entry_path = entry.path
                    result_path = os.path.relpath(entry_path, rel_base) if rel_base else entry_path

                    if entry.is_file():
                        if not is_ignored_file(entry_path):
                            files.append(result_path)
                    elif entry.is_dir():
                        if not is_ignored_dir(entry_path):
                            directories.append(result_path)
                            if recursive:
                                sub_result = scan_directory(
                                    entry_path,
                                    recursive=True,
                                    relative_to=relative_to,
                                    is_ignored_dir=is_ignored_dir,
                                    is_ignored_file=is_ignored_file,
                                )
                                files.extend(sub_result.files)
                                directories.extend(sub_result.directories)
                except PermissionError as ex:
                    log.debug(f"권한 오류로 항목을 건너뜁니다: {entry.path}", exc_info=ex)
                    continue
    except PermissionError as ex:
        log.debug(f"권한 오류로 디렉토리를 건너뜁니다: {abs_path}", exc_info=ex)
        return ScanResult([], [])

    return ScanResult(directories, files)


def find_all_non_ignored_files(repo_root: str) -> list[str]:
    """
    리포지토리 내의 모든 .gitignore 파일을 존중하여, 무시되지 않는 모든 파일을 찾습니다.

    Args:
        repo_root (str): 리포지토리의 루트 디렉토리.

    Returns:
        list[str]: 리포지토리 내에서 무시되지 않는 모든 파일의 목록.
    """
    gitignore_parser = GitignoreParser(repo_root)
    _, files = scan_directory(
        repo_root, recursive=True, is_ignored_dir=gitignore_parser.should_ignore, is_ignored_file=gitignore_parser.should_ignore
    )
    return files


@dataclass
class GitignoreSpec:
    """단일 .gitignore 파일의 규칙을 나타내는 데이터 클래스."""

    file_path: str
    """gitignore 파일의 경로."""
    patterns: list[str] = field(default_factory=list)
    """gitignore 파일의 패턴 목록. 위치에 따라 조정됩니다."""
    pathspec: PathSpec = field(init=False)
    """패턴 매칭을 위한 컴파일된 PathSpec 객체."""

    def __post_init__(self) -> None:
        """패턴으로부터 PathSpec을 초기화합니다."""
        self.pathspec = PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, self.patterns)

    def matches(self, relative_path: str) -> bool:
        """
        주어진 경로가 이 gitignore 명세의 패턴과 일치하는지 확인합니다.

        Args:
            relative_path (str): 확인할 경로 (리포지토리 루트에 대한 상대 경로여야 함).

        Returns:
            bool: 경로가 패턴과 일치하면 True.
        """
        return match_path(relative_path, self.pathspec, root_path=os.path.dirname(self.file_path))


class GitignoreParser:
    """
    리포지토리의 .gitignore 파일들을 위한 파서.

    리포지토리 전체에 걸쳐 여러 .gitignore 파일을 파싱하고,
    경로가 무시되어야 하는지 확인하는 메서드를 제공합니다.
    """

    def __init__(self, repo_root: str) -> None:
        """
        리포지토리에 대한 파서를 초기화합니다.

        Args:
            repo_root (str): 리포지토리의 루트 디렉토리.
        """
        self.repo_root = os.path.abspath(repo_root)
        self.ignore_specs: list[GitignoreSpec] = []
        self._load_gitignore_files()

    def _load_gitignore_files(self) -> None:
        """리포지토리에서 모든 gitignore 파일을 로드합니다."""
        with LogTime(".gitignore 파일 로딩", logger=log):
            for gitignore_path in self._iter_gitignore_files():
                log.info(".gitignore 파일 처리 중: %s", gitignore_path)
                spec = self._create_ignore_spec(gitignore_path)
                if spec.patterns:
                    self.ignore_specs.append(spec)

    def _iter_gitignore_files(self, follow_symlinks: bool = False) -> Iterator[str]:
        """
        리포지토리 루트부터 시작하여 .gitignore 파일을 하향식으로 탐색합니다.
        이미 로드된 무시 패턴과 일치하는 디렉토리 경로는 건너뜁니다.

        Returns:
            Iterator[str]: .gitignore 파일 경로를 반환하는 이터레이터 (하향식).
        """
        queue: list[str] = [self.repo_root]

        def scan(abs_path: str | None) -> Iterator[str]:
            for entry in os.scandir(abs_path):
                if entry.is_dir(follow_symlinks=follow_symlinks):
                    queue.append(entry.path)
                elif entry.is_file(follow_symlinks=follow_symlinks) and entry.name == ".gitignore":
                    yield entry.path

        while queue:
            next_abs_path = queue.pop(0)
            if next_abs_path != self.repo_root:
                rel_path = os.path.relpath(next_abs_path, self.repo_root)
                if self.should_ignore(rel_path):
                    continue
            yield from scan(next_abs_path)

    def _create_ignore_spec(self, gitignore_file_path: str) -> GitignoreSpec:
        """단일 gitignore 파일로부터 GitignoreSpec을 생성합니다."""
        try:
            with open(gitignore_file_path, encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return GitignoreSpec(gitignore_file_path, [])

        gitignore_dir = os.path.dirname(gitignore_file_path)
        patterns = self._parse_gitignore_content(content, gitignore_dir)
        return GitignoreSpec(gitignore_file_path, patterns)

    def _parse_gitignore_content(self, content: str, gitignore_dir: str) -> list[str]:
        """gitignore 내용을 파싱하고 파일 위치에 따라 패턴을 조정합니다."""
        patterns = []
        rel_dir = os.path.relpath(gitignore_dir, self.repo_root)
        if rel_dir == ".":
            rel_dir = ""

        for line in content.splitlines():
            line = line.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue

            is_negation = line.startswith("!")
            if is_negation:
                line = line[1:]

            line = line.strip()
            if not line:
                continue

            if line.startswith((r"\#", r"\!")):
                line = line[1:]

            is_anchored = line.startswith("/")
            if is_anchored:
                line = line[1:]

            if rel_dir:
                if is_anchored:
                    adjusted_pattern = os.path.join(rel_dir, line)
                else:
                    if line.startswith("**/",):
                        adjusted_pattern = os.path.join(rel_dir, line)
                    else:
                        adjusted_pattern = os.path.join(rel_dir, "**", line)
            else:
                if is_anchored:
                    adjusted_pattern = "/" + line
                else:
                    adjusted_pattern = line

            if is_negation:
                adjusted_pattern = "!" + adjusted_pattern

            adjusted_pattern = adjusted_pattern.replace(os.sep, "/")
            patterns.append(adjusted_pattern)

        return patterns

    def should_ignore(self, path: str) -> bool:
        """
        gitignore 규칙에 따라 경로를 무시해야 하는지 확인합니다.

        Args:
            path (str): 확인할 경로 (절대 또는 repo_root에 대한 상대 경로).

        Returns:
            bool: 경로를 무시해야 하면 True, 그렇지 않으면 False.
        """
        if os.path.isabs(path):
            try:
                rel_path = os.path.relpath(path, self.repo_root)
            except Exception as e:
                log.info("리포지토리 루트(%s) 외부에 있는 경로 '%s'를 무시합니다 (%s)", self.repo_root, path, e)
                return True
        else:
            rel_path = path

        if Path(rel_path).parts and Path(rel_path).parts[0] == ".git":
            return True

        abs_path = os.path.join(self.repo_root, rel_path)
        rel_path = rel_path.replace(os.sep, "/")

        if os.path.exists(abs_path) and os.path.isdir(abs_path) and not rel_path.endswith("/"):
            rel_path += "/"

        for spec in self.ignore_specs:
            if spec.matches(rel_path):
                return True

        return False

    def get_ignore_specs(self) -> list[GitignoreSpec]:
        """로드된 모든 gitignore 명세를 가져옵니다."""
        return self.ignore_specs

    def reload(self) -> None:
        """리포지토리에서 모든 gitignore 파일을 다시 로드합니다."""
        self.ignore_specs.clear()
        self._load_gitignore_files()


def match_path(relative_path: str, path_spec: PathSpec, root_path: str = "") -> bool:
    """
    주어진 pathspec에 대해 상대 경로를 매칭합니다.
    `pathspec.match_file()`만으로는 부족하며, pathspec 매칭 문제를 해결하기 위해
    약간의 추가 처리가 필요합니다.

    Args:
        relative_path (str): pathspec에 매칭할 상대 경로.
        path_spec (PathSpec): 매칭할 pathspec.
        root_path (str): 상대 경로가 파생된 루트 경로.

    Returns:
        bool: 경로가 명세와 일치하면 True.
    """
    normalized_path = str(relative_path).replace(os.sep, "/")

    if not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path

    abs_path = os.path.abspath(os.path.join(root_path, relative_path))
    if os.path.isdir(abs_path) and not normalized_path.endswith("/"):
        normalized_path += "/"
    return path_spec.match_file(normalized_path)