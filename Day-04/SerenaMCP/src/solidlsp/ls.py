"""
SolidLSP - 언어 서버 프로토콜 통합 추상화 레이어

이 파일은 다양한 프로그래밍 언어의 Language Server Protocol(LSP) 서버들을
통합하여 사용하는 추상화 레이어를 구현합니다. 20개 이상의 프로그래밍 언어를
단일 API로 접근할 수 있도록 하며, 고급 코드 분석 및 편집 기능을 제공합니다.

주요 컴포넌트:
- SolidLanguageServer: LSP 서버 통합 추상화의 핵심 클래스
- ReferenceInSymbol: 심볼 참조 위치 정보
- SymbolUpdate: 심볼 업데이트 정보
- LSP 통신 및 프로토콜 처리
- 심볼 캐싱 및 최적화
- 다국어 지원

주요 기능:
- 20+ 프로그래밍 언어 지원 (Python, Java, C++, TypeScript 등)
- 통합 심볼 분석 API
- 정확한 코드 편집 기능 (라인/컬럼 기반)
- 참조 관계 추적
- 점진적 코드 분석
- 오류 복구 및 재시도 메커니즘

아키텍처:
- LSP 프로토콜을 추상화하여 언어 독립적 API 제공
- 캐싱 메커니즘을 통한 성능 최적화
- 비동기 처리 및 타임아웃 관리
- 플러그인 가능한 언어 서버 지원
- 강력한 오류 처리 및 복구 시스템

지원 언어:
- Python (Jedi LSP)
- Java (Eclipse JDT LS)
- C/C++ (clangd)
- TypeScript/JavaScript (TypeScript LSP)
- Go (gopls)
- Rust (rust-analyzer)
- C# (OmniSharp)
- PHP (Intelephense)
- Ruby (Solargraph)
- Swift (sourcekit-lsp)
- Kotlin (kotlin-language-server)
- 그리고 10개 이상의 추가 언어

Note:
    이 모듈은 매우 큰 파일이며, 다양한 LSP 서버들과의 통신,
    심볼 분석, 코드 편집 등의 복잡한 기능을 담당합니다.
"""

import dataclasses
import hashlib
import json
import logging
import os
import pathlib
import pickle
import shutil
import subprocess
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from copy import copy
from pathlib import Path, PurePath
from time import sleep
from typing import Self, Union, cast

import pathspec

from serena.text_utils import MatchedConsecutiveLines
from serena.util.file_system import match_path
from solidlsp import ls_types
from solidlsp.ls_config import Language, LanguageServerConfig
from solidlsp.ls_exceptions import SolidLSPException
from solidlsp.ls_handler import SolidLanguageServerHandler
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.ls_types import UnifiedSymbolInformation
from solidlsp.ls_utils import FileUtils, PathUtils, TextUtils
from solidlsp.lsp_protocol_handler import lsp_types
from solidlsp.lsp_protocol_handler import lsp_types as LSPTypes
from solidlsp.lsp_protocol_handler.lsp_constants import LSPConstants
from solidlsp.lsp_protocol_handler.lsp_types import Definition, DefinitionParams, LocationLink, SymbolKind
from solidlsp.lsp_protocol_handler.server import (
    LSPError,
    ProcessLaunchInfo,
    StringDict,
)
from solidlsp.settings import SolidLSPSettings

GenericDocumentSymbol = Union[LSPTypes.DocumentSymbol, LSPTypes.SymbolInformation, ls_types.UnifiedSymbolInformation]


@dataclasses.dataclass(kw_only=True)
class ReferenceInSymbol:
    """
    심볼 참조 정보를 담는 데이터 클래스

    다른 심볼을 참조하는 위치와 함께 조회된 심볼 정보를 포함합니다.
    코드에서 특정 심볼이 어디서 어떻게 사용되는지 추적할 때 사용됩니다.

    주요 용도:
    - 변수나 함수의 사용처 찾기
    - 의존관계 분석
    - 리팩토링 지원
    - 코드 탐색 및 이해

    Attributes:
        symbol (ls_types.UnifiedSymbolInformation): 참조된 심볼의 정보
        line (int): 참조가 발생한 라인 번호 (0-based)
        character (int): 참조가 발생한 문자 위치 (0-based)

    Example:
        >>> # MyClass를 사용하는 코드에서
        >>> reference = ReferenceInSymbol(
        ...     symbol=my_class_symbol,
        ...     line=10,
        ...     character=5
        ... )
    """

    symbol: ls_types.UnifiedSymbolInformation
    line: int
    character: int


@dataclasses.dataclass
class LSPFileBuffer:
    """
    메모리에 열려 있는 LSP 파일의 내용을 저장하는 데 사용되는 클래스입니다.
    """

    # 파일의 uri
    uri: str

    # 파일의 내용
    contents: str

    # 파일의 버전
    version: int

    # 파일의 언어 ID
    language_id: str

    # 파일의 참조 카운트
    ref_count: int

    content_hash: str = ""

    def __post_init__(self):
        self.content_hash = hashlib.md5(self.contents.encode("utf-8")).hexdigest()


class SolidLanguageServer(ABC):
    """
    LanguageServer 클래스는 언어 서버 프로토콜에 대한 언어에 구애받지 않는 인터페이스를 제공합니다.
    다양한 프로그래밍 언어의 언어 서버와 통신하는 데 사용됩니다.
    """

    CACHE_FOLDER_NAME = "cache"

    # 하위 클래스에서 재정의하고 확장해야 함
    def is_ignored_dirname(self, dirname: str) -> bool:
        """
        항상 무시해야 하는 디렉토리에 대한 언어별 조건입니다. 예를 들어, Python의 venv와
        JS/TS의 node_modules는 항상 무시해야 합니다.
        """
        return dirname.startswith(".")

    @classmethod
    def get_language_enum_instance(cls) -> Language:
        return Language.from_ls_class(cls)

    @classmethod
    def ls_resources_dir(cls, solidlsp_settings: SolidLSPSettings, mkdir: bool = True) -> str:
        """
        언어 서버 리소스가 다운로드되는 디렉토리를 반환합니다.
        이 디렉토리는 언어 서버 바이너리, 설정 파일 등을 저장하는 데 사용됩니다.
        """
        result = os.path.join(solidlsp_settings.ls_resources_dir, cls.__name__)

        # 이전에 solidlsp의 하위 디렉토리가 아닌 사용자 홈에 다운로드된 LS 리소스 마이그레이션
        pre_migration_ls_resources_dir = os.path.join(os.path.dirname(__file__), "language_servers", "static", cls.__name__)
        if os.path.exists(pre_migration_ls_resources_dir):
            if os.path.exists(result):
                # 디렉토리가 이미 존재하면 이전 리소스를 제거합니다.
                shutil.rmtree(result, ignore_errors=True)
            else:
                # 이전 리소스를 새 위치로 이동합니다.
                shutil.move(pre_migration_ls_resources_dir, result)
        if mkdir:
            os.makedirs(result, exist_ok=True)
        return result

    @classmethod
    def create(
        cls,
        config: LanguageServerConfig,
        logger: LanguageServerLogger,
        repository_root_path: str,
        timeout: float | None = None,
        solidlsp_settings: SolidLSPSettings | None = None,
    ) -> "SolidLanguageServer":
        """
        주어진 설정과 프로그래밍 언어에 적합한 설정을 기반으로 언어별 LanguageServer 인스턴스를 생성합니다.

        언어가 Java인 경우 jdk-17.0.6 이상이 설치되어 있고, `java`가 PATH에 있으며, JAVA_HOME이 설치 디렉토리로 설정되어 있는지 확인합니다.
        언어가 JS/TS인 경우 node (v18.16.0 이상)가 설치되어 있고 PATH에 있는지 확인합니다.

        :param repository_root_path: 리포지토리의 루트 경로.
        :param config: 언어 서버 설정.
        :param logger: 사용할 로거.
        :param timeout: 언어 서버에 대한 요청 시간 초과. None이면 시간 초과를 사용하지 않습니다.
        :param solidlsp_settings: 추가 설정
        :return LanguageServer: 언어별 LanguageServer 인스턴스.
        """
        ls: SolidLanguageServer
        if solidlsp_settings is None:
            solidlsp_settings = SolidLSPSettings()

        ls_class = config.code_language.get_ls_class()
        # 현재로서는 모든 언어 서버 구현이 동일한 생성자 시그니처를 가지고 있다고 가정합니다
        # (불행히도 기본 클래스의 시그니처와는 다릅니다).
        # 이 가정이 위반되면 여기에 분기 로직이 필요합니다.
        ls = ls_class(config, logger, repository_root_path, solidlsp_settings)  # type: ignore
        ls.set_request_timeout(timeout)
        return ls

    def __init__(
        self,
        config: LanguageServerConfig,
        logger: LanguageServerLogger,
        repository_root_path: str,
        process_launch_info: ProcessLaunchInfo,
        language_id: str,
        solidlsp_settings: SolidLSPSettings,
    ):
        """
        LanguageServer 인스턴스를 초기화합니다.

        이 클래스를 직접 인스턴스화하지 마세요. 대신 `LanguageServer.create` 메서드를 사용하세요.

        :param config: Multilspy 설정.
        :param logger: 사용할 로거.
        :param repository_root_path: 리포지토리의 루트 경로.
        :param process_launch_info: 각 언어 서버에는 서버를 시작하는 데 사용되는 특정 명령이 있습니다.
                    이 매개변수는 언어 서버 프로세스를 시작하는 명령입니다.
                    명령은 바이너리에 적절한 플래그를 전달하여 일부 언어 서버에서 지원하는 HTTP, TCP 모드와 달리
                    stdio 모드에서 실행되도록 해야 합니다.
        """
        self._solidlsp_settings = solidlsp_settings
        self.logger = logger
        self.repository_root_path: str = repository_root_path
        self.logger.log(
            f"{repository_root_path=} 및 {language_id=}와 프로세스 시작 정보: {process_launch_info}로 언어 서버 인스턴스 생성 중",
            logging.DEBUG,
        )

        self.language_id = language_id
        self.open_file_buffers: dict[str, LSPFileBuffer] = {}
        self.language = Language(language_id)

        # 비동기 문제로 인한 경쟁 조건을 방지하기 위해 먼저 캐시 로드
        self._document_symbols_cache: dict[
            str, tuple[str, tuple[list[ls_types.UnifiedSymbolInformation], list[ls_types.UnifiedSymbolInformation]]]
        ] = {}
        """파일 경로를 (file_content_hash, request_document_symbols의 결과) 튜플에 매핑합니다."""
        self._cache_lock = threading.Lock()
        self._cache_has_changed: bool = False
        self.load_cache()

        self.server_started = False
        self.completions_available = threading.Event()
        if config.trace_lsp_communication:

            def logging_fn(source: str, target: str, msg: StringDict | str):
                self.logger.log(f"LSP: {source} -> {target}: {msg!s}", self.logger.logger.level)

        else:
            logging_fn = None

        # cmd는 언어 서버를 시작하는 언어별 명령을 제공하는 자식 클래스에서 가져옵니다.
        # LanguageServerHandler는 언어 서버를 시작하고 통신하는 기능을 제공합니다.
        self.logger.log(
            f"{language_id=} 및 프로세스 시작 정보: {process_launch_info}로 언어 서버 인스턴스 생성 중", logging.DEBUG
        )
        self.server = SolidLanguageServerHandler(
            process_launch_info,
            logger=logging_fn,
            start_independent_lsp_process=config.start_independent_lsp_process,
        )

        # 무시된 경로에 대한 pathspec 매처 설정
        # ignored_paths의 모든 절대 경로에 대해 상대 경로로 변환
        processed_patterns = []
        for pattern in set(config.ignored_paths):
            # 구분자 정규화 (pathspec은 슬래시를 예상함)
            pattern = pattern.replace(os.path.sep, "/")
            processed_patterns.append(pattern)
        self.logger.log(f"설정에서 {len(processed_patterns)}개의 무시된 경로 처리 중", logging.DEBUG)

        # 처리된 패턴에서 pathspec 매처 생성
        self._ignore_spec = pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, processed_patterns)

        self._server_context = None
        self._request_timeout: float | None = None

        self._has_waited_for_cross_file_references = False

    def _get_wait_time_for_cross_file_referencing(self) -> float:
        """신뢰할 수 있는 "초기화 완료" 신호가 없는 LS에 대해 하위 클래스에서 재정의하기 위한 것입니다.

        LS는 아직 완전히 초기화되지 않은 경우 `request_references` 호출 시 불완전한 결과를 반환할 수 있습니다
        (동일한 파일에서만 참조를 찾음).
        """
        return 2

    def set_request_timeout(self, timeout: float | None) -> None:
        """
        :param timeout: 언어 서버에 대한 요청 시간 초과(초).
        """
        self.server.set_request_timeout(timeout)

    def get_ignore_spec(self) -> pathspec.PathSpec:
        """multilspy 설정을 통해 구성된 무시된 경로에 대한 pathspec 매처를 반환합니다.

        이는 언어 서버와 관련된 파일을 결정하는 전체 언어별 무시 사양의 하위 집합입니다.

        이 매처는 프로젝트에서 관련 없는 비언어 파일을 검색하는 등 언어 서버 외부 작업에 유용합니다.
        """
        return self._ignore_spec

    def is_ignored_path(self, relative_path: str, ignore_unsupported_files: bool = True) -> bool:
        """
        파일 유형 및 무시 패턴을 기반으로 경로를 무시해야 하는지 확인합니다.

        :param relative_path: 확인할 상대 경로
        :param ignore_unsupported_files: 지원되지 않는 소스 파일인 경우 무시할지 여부

        :return: 경로를 무시해야 하면 True, 그렇지 않으면 False
        """
        abs_path = os.path.join(self.repository_root_path, relative_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"파일 {abs_path}를 찾을 수 없어 무시 확인을 수행할 수 없습니다.")

        # 파일인 경우 파일 확장자 확인
        is_file = os.path.isfile(abs_path)
        if is_file and ignore_unsupported_files:
            fn_matcher = self.language.get_source_fn_matcher()
            if not fn_matcher.is_relevant_filename(abs_path):
                return True

        # 일관된 처리를 위해 정규화된 경로 생성
        rel_path = Path(relative_path)

        # 항상 충족되는 무시 조건에 대해 경로의 각 부분 확인
        dir_parts = rel_path.parts
        if is_file:
            dir_parts = dir_parts[:-1]
        for part in dir_parts:
            if not part:  # 빈 부분 건너뛰기 (예: 선행 '/')
                continue
            if self.is_ignored_dirname(part):
                return True

        return match_path(relative_path, self.get_ignore_spec(), root_path=self.repository_root_path)

    def _shutdown(self, timeout: float = 5.0):
        """
        모든 I/O 파이프를 명시적으로 닫아 Windows를 포함한 모든 플랫폼에서 깔끔하게 종료되도록 설계된 강력한 종료 프로세스입니다.
        """
        if not self.server.is_running():
            self.logger.log("서버 프로세스가 실행 중이 아니므로 종료를 건너뜁니다.", logging.DEBUG)
            return

        self.logger.log(f"{timeout}초 시간 초과로 최종 강력한 종료 시작 중...", logging.INFO)
        process = self.server.process

        # --- 주 종료 로직 ---
        # 1단계: 정상 종료 요청
        # LSP 종료를 보내고 더 이상 입력이 없음을 알리기 위해 stdin을 닫습니다.
        try:
            self.logger.log("LSP 종료 요청 보내는 중...", logging.DEBUG)
            # 중단될 수 있으므로 LSP 종료 호출 시간 초과를 위해 스레드 사용
            shutdown_thread = threading.Thread(target=self.server.shutdown)
            shutdown_thread.daemon = True
            shutdown_thread.start()
            shutdown_thread.join(timeout=2.0)  # LSP 종료에 2초 시간 초과

            if shutdown_thread.is_alive():
                self.logger.log("LSP 종료 요청 시간 초과, 종료 진행 중...", logging.DEBUG)
            else:
                self.logger.log("LSP 종료 요청 완료.", logging.DEBUG)

            if process.stdin and not process.stdin.is_closing():
                process.stdin.close()
            self.logger.log("1단계 종료 완료.", logging.DEBUG)
        except Exception as e:
            self.logger.log(f"정상 종료 중 예외 발생: {e}", logging.DEBUG)
            # 어쨌든 종료를 진행하므로 여기서는 오류를 무시합니다.

        # 2단계: 프로세스 종료 및 종료 대기
        self.logger.log(f"프로세스 {process.pid} 종료 중, 현재 상태: {process.poll()}", logging.DEBUG)
        process.terminate()

        # 3단계: 시간 초과와 함께 프로세스 종료 대기
        try:
            self.logger.log(f"프로세스 {process.pid} 종료 대기 중...", logging.DEBUG)
            exit_code = process.wait(timeout=timeout)
            self.logger.log(f"언어 서버 프로세스가 종료 코드 {exit_code}로 성공적으로 종료되었습니다.", logging.INFO)
        except subprocess.TimeoutExpired:
            # 종료에 실패하면 프로세스를 강제로 종료합니다.
            self.logger.log(f"프로세스 {process.pid} 종료 시간 초과, 프로세스를 강제로 종료합니다...", logging.WARNING)
            process.kill()
            try:
                exit_code = process.wait(timeout=2.0)
                self.logger.log(f"언어 서버 프로세스가 종료 코드 {exit_code}로 성공적으로 강제 종료되었습니다.", logging.INFO)
            except subprocess.TimeoutExpired:
                self.logger.log(f"프로세스 {process.pid}가 시간 초과 내에 강제 종료될 수 없습니다.", logging.ERROR)
        except Exception as e:
            self.logger.log(f"프로세스 종료 중 오류: {e}", logging.ERROR)

    @contextmanager
    def start_server(self) -> Iterator["SolidLanguageServer"]:
        self.start()
        yield self
        self.stop()

    def _start_server_process(self) -> None:
        self.server_started = True
        self._start_server()

    @abstractmethod
    def _start_server(self):
        pass

    @contextmanager
    def open_file(self, relative_file_path: str) -> Iterator[LSPFileBuffer]:
        """
        언어 서버에서 파일을 엽니다. 언어 서버에 요청하기 전에 이 작업이 필요합니다.

        :param relative_file_path: 열 파일의 상대 경로.
        """
        if not self.server_started:
            self.logger.log(
                "언어 서버가 시작되기 전에 open_file이 호출되었습니다.",
                logging.ERROR,
            )
            raise SolidLSPException("언어 서버가 시작되지 않았습니다.")

        absolute_file_path = str(PurePath(self.repository_root_path, relative_file_path))
        uri = pathlib.Path(absolute_file_path).as_uri()

        if uri in self.open_file_buffers:
            assert self.open_file_buffers[uri].uri == uri
            assert self.open_file_buffers[uri].ref_count >= 1

            self.open_file_buffers[uri].ref_count += 1
            yield self.open_file_buffers[uri]
            self.open_file_buffers[uri].ref_count -= 1
        else:
            contents = FileUtils.read_file(self.logger, absolute_file_path)

            version = 0
            self.open_file_buffers[uri] = LSPFileBuffer(uri, contents, version, self.language_id, 1)

            self.server.notify.did_open_text_document(
                {
                    LSPConstants.TEXT_DOCUMENT: {
                        LSPConstants.URI: uri,
                        LSPConstants.LANGUAGE_ID: self.language_id,
                        LSPConstants.VERSION: 0,
                        LSPConstants.TEXT: contents,
                    }
                }
            )
            yield self.open_file_buffers[uri]
            self.open_file_buffers[uri].ref_count -= 1

        if self.open_file_buffers[uri].ref_count == 0:
            self.server.notify.did_close_text_document(
                {
                    LSPConstants.TEXT_DOCUMENT: {
                        LSPConstants.URI: uri,
                    }
                }
            )
            del self.open_file_buffers[uri]

    def insert_text_at_position(self, relative_file_path: str, line: int, column: int, text_to_be_inserted: str) -> ls_types.Position:
        """
        주어진 파일의 주어진 줄과 열에 텍스트를 삽입하고 텍스트를 삽입한 후
        업데이트된 커서 위치를 반환합니다.

        :param relative_file_path: 열 파일의 상대 경로.
        :param line: 텍스트를 삽입할 줄 번호.
        :param column: 텍스트를 삽입할 열 번호.
        :param text_to_be_inserted: 삽입할 텍스트.
        """
        if not self.server_started:
            self.logger.log(
                "언어 서버가 시작되기 전에 insert_text_at_position이 호출되었습니다.",
                logging.ERROR,
            )
            raise SolidLSPException("언어 서버가 시작되지 않았습니다.")

        absolute_file_path = str(PurePath(self.repository_root_path, relative_file_path))
        uri = pathlib.Path(absolute_file_path).as_uri()

        # 파일이 열려 있는지 확인
        assert uri in self.open_file_buffers

        file_buffer = self.open_file_buffers[uri]
        file_buffer.version += 1

        new_contents, new_l, new_c = TextUtils.insert_text_at_position(file_buffer.contents, line, column, text_to_be_inserted)
        file_buffer.contents = new_contents
        self.server.notify.did_change_text_document(
            {
                LSPConstants.TEXT_DOCUMENT: {
                    LSPConstants.VERSION: file_buffer.version,
                    LSPConstants.URI: file_buffer.uri,
                },
                LSPConstants.CONTENT_CHANGES: [
                    {
                        LSPConstants.RANGE: {
                            "start": {"line": line, "character": column},
                            "end": {"line": line, "character": column},
                        },
                        "text": text_to_be_inserted,
                    }
                ],
            }
        )
        return ls_types.Position(line=new_l, character=new_c)

    def delete_text_between_positions(
        self,
        relative_file_path: str,
        start: ls_types.Position,
        end: ls_types.Position,
    ) -> str:
        """
        주어진 파일의 주어진 시작 및 끝 위치 사이의 텍스트를 삭제하고 삭제된 텍스트를 반환합니다.
        """
        if not self.server_started:
            self.logger.log(
                "언어 서버가 시작되기 전에 insert_text_at_position이 호출되었습니다.",
                logging.ERROR,
            )
            raise SolidLSPException("언어 서버가 시작되지 않았습니다.")

        absolute_file_path = str(PurePath(self.repository_root_path, relative_file_path))
        uri = pathlib.Path(absolute_file_path).as_uri()

        # 파일이 열려 있는지 확인
        assert uri in self.open_file_buffers

        file_buffer = self.open_file_buffers[uri]
        file_buffer.version += 1
        new_contents, deleted_text = TextUtils.delete_text_between_positions(
            file_buffer.contents, start_line=start["line"], start_col=start["character"], end_line=end["line"], end_col=end["character"]
        )
        file_buffer.contents = new_contents
        self.server.notify.did_change_text_document(
            {
                LSPConstants.TEXT_DOCUMENT: {
                    LSPConstants.VERSION: file_buffer.version,
                    LSPConstants.URI: file_buffer.uri,
                },
                LSPConstants.CONTENT_CHANGES: [{LSPConstants.RANGE: {"start": start, "end": end}, "text": ""}],
            }
        )
        return deleted_text

    def _send_definition_request(self, definition_params: DefinitionParams) -> Definition | list[LocationLink] | None:
        return self.server.send.definition(definition_params)

    def request_definition(self, relative_file_path: str, line: int, column: int) -> list[ls_types.Location]:
        """
        주어진 파일의 주어진 줄과 열에 있는 심볼에 대해 언어 서버에 [textDocument/definition](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_definition) 요청을 보냅니다.
        응답을 기다린 후 결과를 반환합니다.

        :param relative_file_path: 정의를 조회할 심볼이 있는 파일의 상대 경로
        :param line: 심볼의 줄 번호
        :param column: 심볼의 열 번호

        :return List[multilspy_types.Location]: 심볼이 정의된 위치 목록
        """
        if not self.server_started:
            self.logger.log(
                "언어 서버가 시작되기 전에 request_definition이 호출되었습니다.",
                logging.ERROR,
            )
            raise SolidLSPException("언어 서버가 시작되지 않았습니다.")

        if not self._has_waited_for_cross_file_references:
            # 일부 LS는 교차 파일 정의를 반환하기 전에 잠시 기다려야 합니다.
            # 이는 신뢰할 수 있는 "초기화 완료" 신호가 없는 LS에 대한 해결 방법입니다.
            sleep(self._get_wait_time_for_cross_file_referencing())
            self._has_waited_for_cross_file_references = True

        with self.open_file(relative_file_path):
            # 언어 서버에 요청을 보내고 응답을 기다립니다.
            definition_params = cast(
                DefinitionParams,
                {
                    LSPConstants.TEXT_DOCUMENT: {
                        LSPConstants.URI: pathlib.Path(str(PurePath(self.repository_root_path, relative_file_path))).as_uri()
                    },
                    LSPConstants.POSITION: {
                        LSPConstants.LINE: line,
                        LSPConstants.CHARACTER: column,
                    },
                },
            )
            response = self._send_definition_request(definition_params)

        ret: list[ls_types.Location] = []
        if isinstance(response, list):
            # 응답은 Location[] 또는 LocationLink[] 타입입니다.
            for item in response:
                assert isinstance(item, dict)
                if LSPConstants.URI in item and LSPConstants.RANGE in item:
                    new_item: ls_types.Location = {}
                    new_item.update(item)
                    new_item["absolutePath"] = PathUtils.uri_to_path(new_item["uri"])
                    new_item["relativePath"] = PathUtils.get_relative_path(new_item["absolutePath"], self.repository_root_path)
                    ret.append(ls_types.Location(new_item))
                elif LSPConstants.TARGET_URI in item and LSPConstants.TARGET_RANGE in item and LSPConstants.TARGET_SELECTION_RANGE in item:
                    new_item: ls_types.Location = {}
                    new_item["uri"] = item[LSPConstants.TARGET_URI]
                    new_item["absolutePath"] = PathUtils.uri_to_path(new_item["uri"])
                    new_item["relativePath"] = PathUtils.get_relative_path(new_item["absolutePath"], self.repository_root_path)
                    new_item["range"] = item[LSPConstants.TARGET_SELECTION_RANGE]
                    ret.append(ls_types.Location(**new_item))
                else:
                    assert False, f"언어 서버로부터 예기치 않은 응답: {item}"
        elif isinstance(response, dict):
            # 응답은 Location 타입입니다.
            assert LSPConstants.URI in response
            assert LSPConstants.RANGE in response

            new_item: ls_types.Location = {}
            new_item.update(response)
            new_item["absolutePath"] = PathUtils.uri_to_path(new_item["uri"])
            new_item["relativePath"] = PathUtils.get_relative_path(new_item["absolutePath"], self.repository_root_path)
            ret.append(ls_types.Location(**new_item))
        elif response is None:
            # 일부 언어 서버는 정의를 찾을 수 없을 때 None을 반환합니다.
            # 이는 제네릭이나 불완전한 정보가 있는 타입과 같은 특정 심볼 유형에 대해 예상되는 동작입니다.
            self.logger.log(
                f"{relative_file_path}:{line}:{column}에서 정의 요청에 대해 언어 서버가 None을 반환했습니다.",
                logging.WARNING,
            )
        else:
            assert False, f"언어 서버로부터 예기치 않은 응답: {response}"

        return ret

    # 일부 LS는 이로 인해 문제가 발생하므로 호출은 나머지 부분과 분리되어 하위 클래스에서 재정의할 수 있습니다.
    def _send_references_request(self, relative_file_path: str, line: int, column: int) -> list[lsp_types.Location] | None:
        return self.server.send.references(
            {
                "textDocument": {"uri": PathUtils.path_to_uri(os.path.join(self.repository_root_path, relative_file_path))},
                "position": {"line": line, "character": column},
                "context": {"includeDeclaration": False},
            }
        )

    def request_references(self, relative_file_path: str, line: int, column: int) -> list[ls_types.Location]:
        """
        주어진 파일의 주어진 줄과 열에 있는 심볼에 대한 참조를 찾기 위해 언어 서버에 [textDocument/references](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_references) 요청을 보냅니다.
        응답을 기다린 후 결과를 반환합니다.
        무시된 디렉토리에 있는 참조는 필터링합니다.

        :param relative_file_path: 참조를 조회할 심볼이 있는 파일의 상대 경로
        :param line: 심볼의 줄 번호
        :param column: 심볼의 열 번호

        :return: 심볼이 참조된 위치 목록 (무시된 디렉토리 제외)
        """
        if not self.server_started:
            self.logger.log(
                "언어 서버가 시작되기 전에 request_references가 호출되었습니다.",
                logging.ERROR,
            )
            raise SolidLSPException("언어 서버가 시작되지 않았습니다.")

        if not self._has_waited_for_cross_file_references:
            # 일부 LS는 교차 파일 참조를 반환하기 전에 잠시 기다려야 합니다.
            # 이는 신뢰할 수 있는 "초기화 완료" 신호가 없는 LS에 대한 해결 방법입니다.
            sleep(self._get_wait_time_for_cross_file_referencing())
            self._has_waited_for_cross_file_references = True

        with self.open_file(relative_file_path):
            try:
                response = self._send_references_request(relative_file_path, line=line, column=column)
            except Exception as e:
                # LSP 내부 오류(-32603)를 포착하고 더 유용한 예외를 발생시킵니다.
                if isinstance(e, LSPError) and getattr(e, "code", None) == -32603:
                    raise RuntimeError(
                        f"{relative_file_path}:{line}:{column}에 대한 참조를 요청할 때 LSP 내부 오류(-32603)가 발생했습니다. "
                        "이는 종종 예상치 못한 방식으로 참조된 심볼에 대한 참조를 요청할 때 발생합니다. "
                    ) from e
                raise
        if response is None:
            return []

        ret: list[ls_types.Location] = []
        assert isinstance(response, list), f"언어 서버로부터 예기치 않은 응답 (list 예상, {type(response)} 받음): {response}"
        for item in response:
            assert isinstance(item, dict), f"언어 서버로부터 예기치 않은 응답 (dict 예상, {type(item)} 받음): {item}"
            assert LSPConstants.URI in item
            assert LSPConstants.RANGE in item

            abs_path = PathUtils.uri_to_path(item[LSPConstants.URI])
            if not Path(abs_path).is_relative_to(self.repository_root_path):
                self.logger.log(
                    f"리포지토리 외부 경로에서 참조를 찾았습니다. 아마도 LS가 설치된 패키지나 표준 라이브러리에서 구문 분석을 하고 있을 것입니다! "
                    f"경로: {abs_path}. 이것은 버그이지만 현재는 이러한 참조를 단순히 건너뜁니다.",
                    logging.WARNING,
                )
                continue

            rel_path = Path(abs_path).relative_to(self.repository_root_path)
            if self.is_ignored_path(str(rel_path)):
                self.logger.log(f"{rel_path}의 참조를 무시해야 하므로 무시합니다.", logging.DEBUG)
                continue

            new_item: ls_types.Location = {}
            new_item.update(item)
            new_item["absolutePath"] = str(abs_path)
            new_item["relativePath"] = str(rel_path)
            ret.append(ls_types.Location(**new_item))

        return ret

    def request_text_document_diagnostics(self, relative_file_path: str) -> list[ls_types.Diagnostic]:
        """
        주어진 파일에 대한 진단을 찾기 위해 언어 서버에 [textDocument/diagnostic](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_diagnostic) 요청을 보냅니다.
        응답을 기다린 후 결과를 반환합니다.

        :param relative_file_path: 진단을 검색할 파일의 상대 경로

        :return: 파일에 대한 진단 목록
        """
        if not self.server_started:
            self.logger.log(
                "언어 서버가 시작되기 전에 request_text_document_diagnostics가 호출되었습니다.",
                logging.ERROR,
            )
            raise SolidLSPException("언어 서버가 시작되지 않았습니다.")

        with self.open_file(relative_file_path):
            response = self.server.send.text_document_diagnostic(
                {
                    LSPConstants.TEXT_DOCUMENT: {
                        LSPConstants.URI: pathlib.Path(str(PurePath(self.repository_root_path, relative_file_path))).as_uri()
                    }
                }
            )

        if response is None:
            return []

        assert isinstance(response, dict), f"언어 서버로부터 예기치 않은 응답 (list 예상, {type(response)} 받음): {response}"
        ret: list[ls_types.Diagnostic] = []
        for item in response["items"]:
            new_item: ls_types.Diagnostic = {
                "uri": pathlib.Path(str(PurePath(self.repository_root_path, relative_file_path))).as_uri(),
                "severity": item["severity"],
                "message": item["message"],
                "range": item["range"],
                "code": item["code"],
            }
            ret.append(ls_types.Diagnostic(new_item))

        return ret

    def retrieve_full_file_content(self, file_path: str) -> str:
        """
        주어진 파일의 전체 내용을 검색합니다.
        """
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path, self.repository_root_path)
        with self.open_file(file_path) as file_data:
            return file_data.contents

    def retrieve_content_around_line(
        self, relative_file_path: str, line: int, context_lines_before: int = 0, context_lines_after: int = 0
    ) -> MatchedConsecutiveLines:
        """
        주어진 줄 주위의 주어진 파일 내용을 검색합니다.

        :param relative_file_path: 내용을 검색할 파일의 상대 경로
        :param line: 내용을 검색할 줄 번호
        :param context_lines_before: 주어진 줄 앞에 검색할 줄 수
        :param context_lines_after: 주어진 줄 뒤에 검색할 줄 수

        :return MatchedConsecutiveLines: 원하는 줄이 포함된 컨테이너.
        """
        with self.open_file(relative_file_path) as file_data:
            file_contents = file_data.contents
        return MatchedConsecutiveLines.from_file_contents(
            file_contents,
            line=line,
            context_lines_before=context_lines_before,
            context_lines_after=context_lines_after,
            source_file_path=relative_file_path,
        )

    def request_completions(
        self, relative_file_path: str, line: int, column: int, allow_incomplete: bool = False
    ) -> list[ls_types.CompletionItem]:
        """
        주어진 파일의 주어진 줄과 열에서 완성을 찾기 위해 언어 서버에 [textDocument/completion](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_completion) 요청을 보냅니다.
        응답을 기다린 후 결과를 반환합니다.

        :param relative_file_path: 완성을 조회할 심볼이 있는 파일의 상대 경로
        :param line: 심볼의 줄 번호
        :param column: 심볼의 열 번호

        :return List[multilspy_types.CompletionItem]: 완성 목록
        """
        with self.open_file(relative_file_path):
            open_file_buffer = self.open_file_buffers[pathlib.Path(os.path.join(self.repository_root_path, relative_file_path)).as_uri()]
            completion_params: LSPTypes.CompletionParams = {
                "position": {"line": line, "character": column},
                "textDocument": {"uri": open_file_buffer.uri},
                "context": {"triggerKind": LSPTypes.CompletionTriggerKind.Invoked},
            }
            response: list[LSPTypes.CompletionItem] | LSPTypes.CompletionList | None = None

            num_retries = 0
            while response is None or (response["isIncomplete"] and num_retries < 30):
                self.completions_available.wait()
                response: list[LSPTypes.CompletionItem] | LSPTypes.CompletionList | None = self.server.send.completion(completion_params)
                if isinstance(response, list):
                    response = {"items": response, "isIncomplete": False}
                num_retries += 1

            # TODO: `isIncomplete`를 적절하게 처리하는 방법을 이해해야 합니다.
            if response is None or (response["isIncomplete"] and not (allow_incomplete)):
                return []

            if "items" in response:
                response = response["items"]

            response = cast(list[LSPTypes.CompletionItem], response)

            # TODO: 완성이 키워드인 경우 처리
            items = [item for item in response if item["kind"] != LSPTypes.CompletionItemKind.Keyword]

            completions_list: list[ls_types.CompletionItem] = []

            for item in items:
                assert "insertText" in item or "textEdit" in item
                assert "kind" in item
                completion_item = {}
                if "detail" in item:
                    completion_item["detail"] = item["detail"]

                if "label" in item:
                    completion_item["completionText"] = item["label"]
                    completion_item["kind"] = item["kind"]
                elif "insertText" in item:
                    completion_item["completionText"] = item["insertText"]
                    completion_item["kind"] = item["kind"]
                elif "textEdit" in item and "newText" in item["textEdit"]:
                    completion_item["completionText"] = item["textEdit"]["newText"]
                    completion_item["kind"] = item["kind"]
                elif "textEdit" in item and "range" in item["textEdit"]:
                    new_dot_lineno, new_dot_colno = (
                        completion_params["position"]["line"],
                        completion_params["position"]["character"],
                    )
                    assert all(
                        (
                            item["textEdit"]["range"]["start"]["line"] == new_dot_lineno,
                            item["textEdit"]["range"]["start"]["character"] == new_dot_colno,
                            item["textEdit"]["range"]["start"]["line"] == item["textEdit"]["range"]["end"]["line"],
                            item["textEdit"]["range"]["start"]["character"] == item["textEdit"]["range"]["end"]["character"],
                        )
                    )

                    completion_item["completionText"] = item["textEdit"]["newText"]
                    completion_item["kind"] = item["kind"]
                elif "textEdit" in item and "insert" in item["textEdit"]:
                    assert False
                else:
                    assert False

                completion_item = ls_types.CompletionItem(**completion_item)
                completions_list.append(completion_item)

            return [json.loads(json_repr) for json_repr in set(json.dumps(item, sort_keys=True) for item in completions_list)]

    def request_document_symbols(
        self, relative_file_path: str, include_body: bool = False
    ) -> tuple[list[ls_types.UnifiedSymbolInformation], list[ls_types.UnifiedSymbolInformation]]:
        """
        주어진 파일에서 심볼을 찾기 위해 언어 서버에 [textDocument/documentSymbol](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_documentSymbol) 요청을 보냅니다.
        응답을 기다린 후 결과를 반환합니다.

        :param relative_file_path: 심볼이 있는 파일의 상대 경로
        :param include_body: 결과에 심볼의 본문을 포함할지 여부.
        :return: 파일의 심볼 목록과 심볼의 트리 구조를 나타내는 루트 심볼 목록.
            모든 심볼에는 위치, 자식, 부모 속성이 있으며, 루트 심볼의 부모 속성은 None입니다.
            이는 부모 속성이 파일 심볼이고, 파일 심볼이 패키지 심볼을 부모로 가질 수 있는 request_full_symbol_tree 호출과 약간 다릅니다.
            파일 심볼도 포함하는 심볼 트리가 필요한 경우 `request_full_symbol_tree`를 대신 사용해야 합니다.
        """
        # TODO: include_body가 한 번 True인 후 include_body가 False인 경우 캐시를 사용하지 않는 것은 어리석습니다.
        #   향후 수정해야 하며, 작은 성능 최적화입니다.
        cache_key = f"{relative_file_path}-{include_body}"
        with self.open_file(relative_file_path) as file_data:
            with self._cache_lock:
                file_hash_and_result = self._document_symbols_cache.get(cache_key)
                if file_hash_and_result is not None:
                    file_hash, result = file_hash_and_result
                    if file_hash == file_data.content_hash:
                        self.logger.log(f"{relative_file_path}에 대한 캐시된 문서 심볼 반환 중", logging.DEBUG)
                        return result
                    else:
                        self.logger.log(f"{relative_file_path}의 내용이 변경되었습니다. 메모리 내 캐시를 덮어씁니다.", logging.DEBUG)
                else:
                    self.logger.log(f"{relative_file_path}에서 {include_body=}로 심볼에 대한 캐시 히트 없음", logging.DEBUG)

            self.logger.log(f"언어 서버에서 {relative_file_path}에 대한 문서 심볼 요청 중", logging.DEBUG)
            response = self.server.send.document_symbol(
                {"textDocument": {"uri": pathlib.Path(os.path.join(self.repository_root_path, relative_file_path)).as_uri()}}
            )
            if response is None:
                self.logger.log(
                    f"{relative_file_path}의 문서 심볼에 대해 언어 서버로부터 None 응답을 받았습니다. "
                    f"이는 언어 서버가 이 파일을 이해할 수 없음을 의미합니다 (구문 오류 가능성). LS의 버그나 잘못된 구성으로 인해 발생할 수도 있습니다. "
                    f"빈 목록을 반환합니다.",
                    logging.WARNING,
                )
                return [], []
            assert isinstance(response, list), f"언어 서버로부터 예기치 않은 응답: {response}"
            self.logger.log(
                f"언어 서버로부터 {relative_file_path}에 대한 {len(response)}개의 문서 심볼을 받았습니다.",
                logging.DEBUG,
            )

        def turn_item_into_symbol_with_children(item: GenericDocumentSymbol):
            item = cast(ls_types.UnifiedSymbolInformation, item)
            absolute_path = os.path.join(self.repository_root_path, relative_file_path)

            # 위치에 누락된 항목 처리
            if "location" not in item:
                uri = pathlib.Path(absolute_path).as_uri()
                assert "range" in item
                tree_location = ls_types.Location(
                    uri=uri,
                    range=item["range"],
                    absolutePath=absolute_path,
                    relativePath=relative_file_path,
                )
                item["location"] = tree_location
            location = item["location"]
            if "absolutePath" not in location:
                location["absolutePath"] = absolute_path
            if "relativePath" not in location:
                location["relativePath"] = relative_file_path
            if include_body:
                item["body"] = self.retrieve_symbol_body(item)
            # 누락된 selectionRange 처리
            if "selectionRange" not in item:
                if "range" in item:
                    item["selectionRange"] = item["range"]
                else:
                    item["selectionRange"] = item["location"]["range"]
            children = item.get(LSPConstants.CHILDREN, [])
            for child in children:
                child["parent"] = item
            item[LSPConstants.CHILDREN] = children

        flat_all_symbol_list: list[ls_types.UnifiedSymbolInformation] = []
        root_nodes: list[ls_types.UnifiedSymbolInformation] = []
        for root_item in response:
            if "range" not in root_item and "location" not in root_item:
                if root_item["kind"] in [SymbolKind.File, SymbolKind.Module]:
                    ...

            # 돌연변이가 새 딕셔너리를 만드는 것보다 편리하므로,
            # 항목을 "심볼"로 바꾼 turn_item_into_symbol_with_children에 대한 돌연변이 호출 후
            # 변수를 캐스트하고 이름을 바꿉니다.
            turn_item_into_symbol_with_children(root_item)
            root_symbol = cast(ls_types.UnifiedSymbolInformation, root_item)
            root_symbol["parent"] = None

            root_nodes.append(root_symbol)
            assert isinstance(root_symbol, dict)
            assert LSPConstants.NAME in root_symbol
            assert LSPConstants.KIND in root_symbol

            if LSPConstants.CHILDREN in root_symbol:
                # TODO: l_tree는 TreeRepr 목록이어야 합니다. 다음 함수가 TreeRepr도 반환하도록 정의합니다.

                def visit_tree_nodes_and_build_tree_repr(node: GenericDocumentSymbol) -> list[ls_types.UnifiedSymbolInformation]:
                    node = cast(ls_types.UnifiedSymbolInformation, node)
                    l: list[ls_types.UnifiedSymbolInformation] = []
                    turn_item_into_symbol_with_children(node)
                    assert LSPConstants.CHILDREN in node
                    children = node[LSPConstants.CHILDREN]
                    l.append(node)
                    for child in children:
                        l.extend(visit_tree_nodes_and_build_tree_repr(child))
                    return l

                flat_all_symbol_list.extend(visit_tree_nodes_and_build_tree_repr(root_symbol))
            else:
                flat_all_symbol_list.append(ls_types.UnifiedSymbolInformation(**root_symbol))

        result = flat_all_symbol_list, root_nodes
        self.logger.log(f"{relative_file_path}에 대한 문서 심볼 캐싱 중", logging.DEBUG)
        with self._cache_lock:
            self._document_symbols_cache[cache_key] = (file_data.content_hash, result)
            self._cache_has_changed = True
        return result

    def request_full_symbol_tree(
        self,
        within_relative_path: str | None = None,
        include_body: bool = False,
    ) -> list[ls_types.UnifiedSymbolInformation]:
        """
        프로젝트 또는 상대 경로 내의 모든 파일을 탐색하고 심볼 트리를 구축합니다.
        참고: 이 작업은 특히 `within_relative_path`를 사용하여 검색을 제한하지 않는 경우 처음 호출할 때 느릴 수 있습니다.

        각 파일에 대해 File(2) 종류의 심볼이 생성됩니다. 디렉토리에 대해서는 Package(4) 종류의 심볼이 생성됩니다.
        모든 심볼에는 children 속성이 있어 리포지토리 내에 있는 프로젝트의 모든 심볼의 트리 구조를 나타냅니다.
        루트 패키지를 제외한 모든 심볼에는 parent 속성이 있습니다.
        '.'으로 시작하는 디렉토리, 언어별 기본값 및 사용자 구성 디렉토리(예: .gitignore)는 무시합니다.

        :param within_relative_path: 이 경로 내의 심볼만 고려하도록 상대 경로를 전달합니다.
            파일이 전달되면 이 파일 내의 심볼만 고려됩니다.
            디렉토리가 전달되면 이 디렉토리 내의 모든 파일이 고려됩니다.
        :param include_body: 결과에 심볼의 본문을 포함할지 여부.

        :return: 프로젝트의 최상위 패키지/모듈을 나타내는 루트 심볼 목록.
        """
        if within_relative_path is not None:
            within_abs_path = os.path.join(self.repository_root_path, within_relative_path)
            if not os.path.exists(within_abs_path):
                raise FileNotFoundError(f"파일 또는 디렉토리를 찾을 수 없습니다: {within_abs_path}")
            if os.path.isfile(within_abs_path):
                if self.is_ignored_path(within_relative_path):
                    self.logger.log(
                        f"파일을 명시적으로 전달했지만 무시됩니다. 이것은 아마도 오류일 것입니다. 파일: {within_relative_path}",
                        logging.ERROR,
                    )
                    return []
                else:
                    _, root_nodes = self.request_document_symbols(within_relative_path, include_body=include_body)
                    return root_nodes

        # 디렉토리를 재귀적으로 처리하는 헬퍼 함수
        def process_directory(rel_dir_path: str) -> list[ls_types.UnifiedSymbolInformation]:
            abs_dir_path = self.repository_root_path if rel_dir_path == "." else os.path.join(self.repository_root_path, rel_dir_path)
            abs_dir_path = os.path.realpath(abs_dir_path)

            if self.is_ignored_path(str(Path(abs_dir_path).relative_to(self.repository_root_path))):
                self.logger.log(f"디렉토리 건너뛰기: {rel_dir_path}\n(무시해야 하므로)", logging.DEBUG)
                return []

            result = []
            try:
                contained_dir_or_file_names = os.listdir(abs_dir_path)
            except OSError:
                return []

            # 디렉토리에 대한 패키지 심볼 생성
            package_symbol = ls_types.UnifiedSymbolInformation(  # type: ignore
                name=os.path.basename(abs_dir_path),
                kind=ls_types.SymbolKind.Package,
                location=ls_types.Location(
                    uri=str(pathlib.Path(abs_dir_path).as_uri()),
                    range={"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
                    absolutePath=str(abs_dir_path),
                    relativePath=str(Path(abs_dir_path).resolve().relative_to(self.repository_root_path)),
                ),
                children=[],
            )
            result.append(package_symbol)

            for contained_dir_or_file_name in contained_dir_or_file_names:
                contained_dir_or_file_abs_path = os.path.join(abs_dir_path, contained_dir_or_file_name)
                contained_dir_or_file_rel_path = str(Path(contained_dir_or_file_abs_path).resolve().relative_to(self.repository_root_path))
                if self.is_ignored_path(contained_dir_or_file_rel_path):
                    self.logger.log(f"항목 건너뛰기: {contained_dir_or_file_rel_path}\n(무시해야 하므로)", logging.DEBUG)
                    continue

                if os.path.isdir(contained_dir_or_file_abs_path):
                    child_symbols = process_directory(contained_dir_or_file_rel_path)
                    package_symbol["children"].extend(child_symbols)
                    for child in child_symbols:
                        child["parent"] = package_symbol

                elif os.path.isfile(contained_dir_or_file_abs_path):
                    _, file_root_nodes = self.request_document_symbols(contained_dir_or_file_rel_path, include_body=include_body)

                    # 파일 심볼 생성, 자식과 연결
                    file_rel_path = str(Path(contained_dir_or_file_abs_path).resolve().relative_to(self.repository_root_path))
                    with self.open_file(file_rel_path) as file_data:
                        fileRange = self._get_range_from_file_content(file_data.contents)
                    file_symbol = ls_types.UnifiedSymbolInformation(  # type: ignore
                        name=os.path.splitext(contained_dir_or_file_name)[0],
                        kind=ls_types.SymbolKind.File,
                        range=fileRange,
                        selectionRange=fileRange,
                        location=ls_types.Location(
                            uri=str(pathlib.Path(contained_dir_or_file_abs_path).as_uri()),
                            range=fileRange,
                            absolutePath=str(contained_dir_or_file_abs_path),
                            relativePath=str(Path(contained_dir_or_file_abs_path).resolve().relative_to(self.repository_root_path)),
                        ),
                        children=file_root_nodes,
                        parent=package_symbol,
                    )
                    for child in file_root_nodes:
                        child["parent"] = file_symbol

                    # 파일 심볼을 패키지와 연결
                    package_symbol["children"].append(file_symbol)

                    # TODO: 상대 경로 처리에 대한 최근 변경 사항을 고려할 때 이것이 실제로 여전히 필요한지 확실하지 않습니다.
                    def fix_relative_path(nodes: list[ls_types.UnifiedSymbolInformation]):
                        for node in nodes:
                            if "location" in node and "relativePath" in node["location"]:
                                path = Path(node["location"]["relativePath"])
                                if path.is_absolute():
                                    try:
                                        path = path.relative_to(self.repository_root_path)
                                        node["location"]["relativePath"] = str(path)
                                    except Exception:
                                        pass
                            if "children" in node:
                                fix_relative_path(node["children"])

                    fix_relative_path(file_root_nodes)

            return result

        # 루트 또는 지정된 디렉토리에서 시작
        start_rel_path = within_relative_path or "."
        return process_directory(start_rel_path)

    @staticmethod
    def _get_range_from_file_content(file_content: str) -> ls_types.Range:
        """
        주어진 파일에 대한 범위를 가져옵니다.
        """
        lines = file_content.split("\n")
        end_line = len(lines)
        end_column = len(lines[-1])
        return ls_types.Range(start=ls_types.Position(line=0, character=0), end=ls_types.Position(line=end_line, character=end_column))

    def request_dir_overview(self, relative_dir_path: str) -> dict[str, list[UnifiedSymbolInformation]]:
        """
        :return: 분석된 모든 상대 경로를 해당 파일의 최상위 심볼 목록에 매핑합니다.
        """
        symbol_tree = self.request_full_symbol_tree(relative_dir_path)
        # 결과 딕셔너리 초기화
        result: dict[str, list[UnifiedSymbolInformation]] = defaultdict(list)

        # 심볼과 그 자식을 재귀적으로 처리하는 헬퍼 함수
        def process_symbol(symbol: ls_types.UnifiedSymbolInformation):
            if symbol["kind"] == ls_types.SymbolKind.File:
                # 파일 심볼의 경우 자식(최상위 심볼) 처리
                for child in symbol["children"]:
                    # 교차 플랫폼 경로 해결 (Docker/macOS 경로 문제 수정)
                    absolute_path = Path(child["location"]["absolutePath"]).resolve()
                    repository_root = Path(self.repository_root_path).resolve()

                    # 먼저 pathlib을 시도하고, 경로가 호환되지 않으면 다른 접근 방식으로 대체
                    try:
                        path = absolute_path.relative_to(repository_root)
                    except ValueError:
                        # 경로가 다른 루트에서 온 경우 (예: /workspaces vs /Users),
                        # location의 relativePath를 사용하거나 absolutePath에서 추출
                        if "relativePath" in child["location"] and child["location"]["relativePath"]:
                            path = Path(child["location"]["relativePath"])
                        else:
                            # 공통 구조를 찾아 상대 경로 추출
                            # 예: /workspaces/.../test_repo/file.py -> test_repo/file.py
                            path_parts = absolute_path.parts

                            # 마지막 공통 부분을 찾거나 대체 사용
                            if "test_repo" in path_parts:
                                test_repo_idx = path_parts.index("test_repo")
                                path = Path(*path_parts[test_repo_idx:])
                            else:
                                # 마지막 수단: 파일 이름만 사용
                                path = Path(absolute_path.name)
                    result[str(path)].append(child)
            # 패키지/디렉토리 심볼의 경우 자식 처리
            for child in symbol["children"]:
                process_symbol(child)

        # 각 루트 심볼 처리
        for root in symbol_tree:
            process_symbol(root)
        return result

    def request_document_overview(self, relative_file_path: str) -> list[UnifiedSymbolInformation]:
        """
        :return: 주어진 파일의 최상위 심볼.
        """
        _, document_roots = self.request_document_symbols(relative_file_path)
        return document_roots

    def request_overview(self, within_relative_path: str) -> dict[str, list[UnifiedSymbolInformation]]:
        """
        주어진 파일 또는 디렉토리의 모든 심볼에 대한 개요입니다.

        :param within_relative_path: 개요를 가져올 파일 또는 디렉토리의 상대 경로.
        :return: 분석된 모든 상대 경로를 해당 파일의 최상위 심볼 목록에 매핑합니다.
        """
        abs_path = (Path(self.repository_root_path) / within_relative_path).resolve()
        if not abs_path.exists():
            raise FileNotFoundError(f"파일 또는 디렉토리를 찾을 수 없습니다: {abs_path}")

        if abs_path.is_file():
            symbols_overview = self.request_document_overview(within_relative_path)
            return {within_relative_path: symbols_overview}
        else:
            return self.request_dir_overview(within_relative_path)

    def request_hover(self, relative_file_path: str, line: int, column: int) -> ls_types.Hover | None:
        """
        주어진 파일의 주어진 줄과 열에서 호버 정보를 찾기 위해 언어 서버에 [textDocument/hover](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_hover) 요청을 보냅니다.
        응답을 기다린 후 결과를 반환합니다.

        :param relative_file_path: 호버 정보가 있는 파일의 상대 경로
        :param line: 심볼의 줄 번호
        :param column: 심볼의 열 번호

        :return None
        """
        with self.open_file(relative_file_path):
            response = self.server.send.hover(
                {
                    "textDocument": {"uri": pathlib.Path(os.path.join(self.repository_root_path, relative_file_path)).as_uri()},
                    "position": {
                        "line": line,
                        "character": column,
                    },
                }
            )

        if response is None:
            return None

        assert isinstance(response, dict)

        return ls_types.Hover(**response)

    def retrieve_symbol_body(self, symbol: ls_types.UnifiedSymbolInformation | LSPTypes.DocumentSymbol | LSPTypes.SymbolInformation) -> str:
        """
        주어진 심볼의 본문을 로드합니다. 본문이 이미 심볼에 포함되어 있으면 그냥 반환합니다.
        """
        existing_body = symbol.get("body", None)
        if existing_body:
            return existing_body

        assert "location" in symbol
        symbol_start_line = symbol["location"]["range"]["start"]["line"]
        symbol_end_line = symbol["location"]["range"]["end"]["line"]
        assert "relativePath" in symbol["location"]
        symbol_file = self.retrieve_full_file_content(symbol["location"]["relativePath"])
        symbol_lines = symbol_file.split("\n")
        symbol_body = "\n".join(symbol_lines[symbol_start_line : symbol_end_line + 1])

        # 선행 들여쓰기 제거
        symbol_start_column = symbol["location"]["range"]["start"]["character"]
        symbol_body = symbol_body[symbol_start_column:]
        return symbol_body

    def request_referencing_symbols(
        self,
        relative_file_path: str,
        line: int,
        column: int,
        include_imports: bool = True,
        include_self: bool = False,
        include_body: bool = False,
        include_file_symbols: bool = False,
    ) -> list[ReferenceInSymbol]:
        """
        주어진 위치의 심볼을 참조하는 모든 심볼을 찾습니다.
        이는 request_references와 유사하지만 대상 심볼을 참조하는 심볼(함수, 메서드, 클래스 등)만 포함하도록 필터링합니다.

        :param relative_file_path: 파일의 상대 경로.
        :param line: 0부터 시작하는 줄 번호.
        :param column: 0부터 시작하는 열 번호.
        :param include_imports: 가져오기도 참조로 포함할지 여부.
            불행히도 LSP에는 가져오기 유형이 없으므로 가져오기에 해당하는 참조는
            정의와 쉽게 구별할 수 없습니다.
        :param include_self: "입력 심볼" 자체인 참조를 포함할지 여부.
            relative_file_path, line, column이 심볼(예: 정의)을 가리키는 경우에만 효과가 있습니다.
        :param include_body: 결과에 심볼의 본문을 포함할지 여부.
        :param include_file_symbols: 파일 심볼인 참조를 포함할지 여부. 이는
            참조를 심볼로 확인할 수 없을 때의 대체 메커니즘입니다.
        :return: 심볼과 참조 위치를 포함하는 객체 목록.
        """
        if not self.server_started:
            self.logger.log(
                "언어 서버가 시작되기 전에 request_referencing_symbols가 호출되었습니다.",
                logging.ERROR,
            )
            raise SolidLSPException("언어 서버가 시작되지 않았습니다.")

        # 먼저 심볼에 대한 모든 참조를 가져옵니다.
        references = self.request_references(relative_file_path, line, column)
        if not references:
            return []

        # 각 참조에 대해 포함하는 심볼을 찾습니다.
        result = []
        incoming_symbol = None
        for ref in references:
            ref_path = ref["relativePath"]
            ref_line = ref["range"]["start"]["line"]
            ref_col = ref["range"]["start"]["character"]

            with self.open_file(ref_path) as file_data:
                # 이 참조를 포함하는 심볼 가져오기
                containing_symbol = self.request_containing_symbol(ref_path, ref_line, ref_col, include_body=include_body)
                if containing_symbol is None:
                    # TODO: 끔찍한 핵! 지금은 더 나은 방법을 모르겠습니다...
                    # 이것은 많은 경우에 깨질 수 있습니다! 또한 파이썬에만 해당됩니다!
                    # 배경:
                    # 변수가 무언가를 변경하는 데 사용될 때, 예를 들어
                    # 
                    # instance = MyClass()
                    # instance.status = "new status"
                    # 
                    # 참조 라인에 컨테이너가 없기 때문에 `status`에 대한 참조를 포함하는 심볼을 찾을 수 없습니다.
                    # 핵은 참조의 텍스트를 사용하여 변수 이름을 찾는 것(매우 휴리스틱한 방식으로)
                    # 그리고 그 이름과 종류가 Variable인 심볼을 찾는 것입니다.
                    ref_text = file_data.contents.split("\n")[ref_line]
                    if "." in ref_text:
                        containing_symbol_name = ref_text.split(".")[0]
                        all_symbols, _ = self.request_document_symbols(ref_path)
                        for symbol in all_symbols:
                            if symbol["name"] == containing_symbol_name and symbol["kind"] == ls_types.SymbolKind.Variable:
                                containing_symbol = copy(symbol)
                                containing_symbol["location"] = ref
                                containing_symbol["range"] = ref["range"]
                                break

                # 심볼을 검색하지 못하여 파일 심볼 생성으로 대체
                if containing_symbol is None and include_file_symbols:
                    self.logger.log(
                        f"{ref_path}:{ref_line}:{ref_col}에 대한 포함 심볼을 찾을 수 없습니다. 대신 파일 심볼을 반환합니다.",
                        logging.WARNING,
                    )
                    fileRange = self._get_range_from_file_content(file_data.contents)
                    location = ls_types.Location(
                        uri=str(pathlib.Path(os.path.join(self.repository_root_path, ref_path)).as_uri()),
                        range=fileRange,
                        absolutePath=str(os.path.join(self.repository_root_path, ref_path)),
                        relativePath=ref_path,
                    )
                    name = os.path.splitext(os.path.basename(ref_path))[0]

                    if include_body:
                        body = self.retrieve_full_file_content(ref_path)
                    else:
                        body = ""

                    containing_symbol = ls_types.UnifiedSymbolInformation(
                        kind=ls_types.SymbolKind.File,
                        range=fileRange,
                        selectionRange=fileRange,
                        location=location,
                        name=name,
                        children=[],
                        body=body,
                    )
                if containing_symbol is None or (not include_file_symbols and containing_symbol["kind"] == ls_types.SymbolKind.File):
                    continue

                assert "location" in containing_symbol
                assert "selectionRange" in containing_symbol

                # 자기 참조 확인
                if (
                    containing_symbol["location"]["relativePath"] == relative_file_path
                    and containing_symbol["selectionRange"]["start"]["line"] == ref_line
                    and containing_symbol["selectionRange"]["start"]["character"] == ref_col
                ):
                    incoming_symbol = containing_symbol
                    if include_self:
                        result.append(ReferenceInSymbol(symbol=containing_symbol, line=ref_line, character=ref_col))
                        continue
                    self.logger.log(f"{incoming_symbol['name']}에 대한 자기 참조를 찾았으므로 {include_self=}로 건너뜁니다.", logging.DEBUG)
                    continue

                # 참조가 가져오기인지 확인
                # 이것은 정말 안전하거나 우아하지는 않지만, 이렇게 하지 않으면
                # 가져오기가 심볼 유형이 아니기 때문에 정의와 가져오기를 구별할 방법이 없습니다.
                # 그리고 가져오기에서 발생하는 유형 참조 심볼을 얻습니다...
                if (
                    not include_imports
                    and incoming_symbol is not None
                    and containing_symbol["name"] == incoming_symbol["name"]
                    and containing_symbol["kind"] == incoming_symbol["kind"]
                ):
                    self.logger.log(
                        f"{containing_symbol['location']['relativePath']}에서 참조된 심볼 {incoming_symbol['name']}의 가져오기를 찾았으므로 건너뜁니다.",
                        logging.DEBUG,
                    )
                    continue

                result.append(ReferenceInSymbol(symbol=containing_symbol, line=ref_line, character=ref_col))

        return result

    def request_containing_symbol(
        self,
        relative_file_path: str,
        line: int,
        column: int | None = None,
        strict: bool = False,
        include_body: bool = False,
    ) -> ls_types.UnifiedSymbolInformation | None:
        """
        주어진 파일의 위치를 포함하는 첫 번째 심볼을 찾습니다.
        Python의 경우 컨테이너 심볼은 함수, 메서드 또는 클래스에 해당하는 종류를 가진 것으로 간주됩니다
        (일반적으로: Function (12), Method (6), Class (5)).

        메서드는 다음과 같이 작동합니다:
          - 파일에 대한 문서 심볼을 요청합니다.
          - 주어진 줄 이전에 시작하는 심볼로 필터링합니다.
          - 이 중에서 먼저 (줄, 열)을 포함하는 범위의 심볼을 찾습니다.
          - 하나 이상의 심볼이 위치를 포함하는 경우 가장 큰 시작 위치를 가진 심볼을 반환합니다
            (즉, 가장 안쪽 컨테이너).
          - 위치를 (엄격하게) 포함하는 심볼이 없는 경우 주어진 줄 위의 심볼 중에서 가장 큰 시작 위치를 가진 심볼을 반환합니다.
          - 컨테이너 후보를 찾지 못하면 None을 반환합니다.

        :param relative_file_path: Python 파일의 상대 경로.
        :param line: 0부터 시작하는 줄 번호.
        :param column: 0부터 시작하는 열 번호 (문자라고도 함). 전달되지 않으면 줄만 기반으로 조회합니다.
        :param strict: True이면 위치가 심볼의 범위 내에 엄격하게 있어야 합니다.
            True로 설정하는 것은 예를 들어 심볼의 부모를 찾는 데 유용합니다. strict=False이고
            줄이 심볼 자체를 가리키는 경우 포함하는 심볼은 심볼 자체가 됩니다
            (부모가 아님).
        :param include_body: 결과에 심볼의 본문을 포함할지 여부.
        :return: 컨테이너 심볼 (찾은 경우) 또는 None.
        """
        # 줄이 비어 있는지 확인, 불행히도 코드가 중복되고 보기 흉하지만 리팩토링하고 싶지 않습니다.
        with self.open_file(relative_file_path):
            absolute_file_path = str(PurePath(self.repository_root_path, relative_file_path))
            content = FileUtils.read_file(self.logger, absolute_file_path)
            if content.split("\n")[line].strip() == "":
                self.logger.log(
                    f"request_container_symbol에 빈 줄을 전달하는 것은 현재 지원되지 않습니다, {relative_file_path=}, {line=}",
                    logging.ERROR,
                )
                return None

        symbols, _ = self.request_document_symbols(relative_file_path)

        # jedi와 pyright api 호환되도록 만들기
        # 전자는 위치가 없고 후자는 범위가 없습니다.
        # 모든 심볼에 원하는 형식의 위치를 항상 추가합니다.
        for symbol in symbols:
            if "location" not in symbol:
                range = symbol["range"]
                location = ls_types.Location(
                    uri=f"file:/{absolute_file_path}",
                    range=range,
                    absolutePath=absolute_file_path,
                    relativePath=relative_file_path,
                )
                symbol["location"] = location
            else:
                location = symbol["location"]
                assert "range" in location
                location["absolutePath"] = absolute_file_path
                location["relativePath"] = relative_file_path
                location["uri"] = Path(absolute_file_path).as_uri()

        # 허용되는 컨테이너 종류, 현재는 Python에만 해당
        container_symbol_kinds = {ls_types.SymbolKind.Method, ls_types.SymbolKind.Function, ls_types.SymbolKind.Class}

        def is_position_in_range(line: int, range_d: ls_types.Range) -> bool:
            start = range_d["start"]
            end = range_d["end"]

            column_condition = True
            if strict:
                line_condition = end["line"] >= line > start["line"]
                if column is not None and line == start["line"]:
                    column_condition = column > start["character"]
            else:
                line_condition = end["line"] >= line >= start["line"]
                if column is not None and line == start["line"]:
                    column_condition = column >= start["character"]
            return line_condition and column_condition

        # 한 줄짜리가 아닌 컨테이너만 고려 (그렇지 않으면 가져오기를 얻을 수 있음)
        candidate_containers = [
            s
            for s in symbols
            if s["kind"] in container_symbol_kinds and s["location"]["range"]["start"]["line"] != s["location"]["range"]["end"]["line"]
        ]
        var_containers = [s for s in symbols if s["kind"] == ls_types.SymbolKind.Variable]
        candidate_containers.extend(var_containers)

        if not candidate_containers:
            return None

        # 후보 중에서 주어진 위치를 포함하는 범위를 가진 것을 찾습니다.
        containing_symbols = []
        for symbol in candidate_containers:
            s_range = symbol["location"]["range"]
            if not is_position_in_range(line, s_range):
                continue
            containing_symbols.append(symbol)

        if containing_symbols:
            # 가장 큰 시작 위치를 가진 것을 반환합니다 (즉, 가장 안쪽 컨테이너).
            containing_symbol = max(containing_symbols, key=lambda s: s["location"]["range"]["start"]["line"])
            if include_body:
                containing_symbol["body"] = self.retrieve_symbol_body(containing_symbol)
            return containing_symbol
        else:
            return None

    def request_container_of_symbol(
        self, symbol: ls_types.UnifiedSymbolInformation, include_body: bool = False
    ) -> ls_types.UnifiedSymbolInformation | None:
        """
        주어진 심볼의 컨테이너가 있는 경우 찾습니다. 부모 속성이 있는 경우 추가 검색 없이 부모를 반환합니다.

        :param symbol: 컨테이너를 찾을 심볼.
        :param include_body: 결과에 심볼의 본문을 포함할지 여부.
        :return: 주어진 심볼의 컨테이너 또는 컨테이너를 찾지 못한 경우 None.
        """
        if "parent" in symbol:
            return symbol["parent"]
        assert "location" in symbol, f"심볼 {symbol}에 위치 및 부모 속성이 없습니다."
        return self.request_containing_symbol(
            symbol["location"]["relativePath"],
            symbol["location"]["range"]["start"]["line"],
            symbol["location"]["range"]["start"]["character"],
            strict=True,
            include_body=include_body,
        )

    def request_defining_symbol(
        self,
        relative_file_path: str,
        line: int,
        column: int,
        include_body: bool = False,
    ) -> ls_types.UnifiedSymbolInformation | None:
        """
        주어진 위치의 심볼을 정의하는 심볼을 찾습니다.

        이 메서드는 먼저 주어진 위치의 심볼 정의를 찾은 다음,
        해당 정의에 대한 전체 심볼 정보를 검색합니다.

        :param relative_file_path: 파일의 상대 경로.
        :param line: 0부터 시작하는 줄 번호.
        :param column: 0부터 시작하는 열 번호.
        :param include_body: 결과에 심볼의 본문을 포함할지 여부.
        :return: 정의에 대한 심볼 정보 또는 찾지 못한 경우 None.
        """
        if not self.server_started:
            self.logger.log(
                "언어 서버가 시작되기 전에 request_defining_symbol이 호출되었습니다.",
                logging.ERROR,
            )
            raise SolidLSPException("언어 서버가 시작되지 않았습니다.")

        # 정의 위치 가져오기
        definitions = self.request_definition(relative_file_path, line, column)
        if not definitions:
            return None

        # 첫 번째 정의 위치 사용
        definition = definitions[0]
        def_path = definition["relativePath"]
        def_line = definition["range"]["start"]["line"]
        def_col = definition["range"]["start"]["character"]

        # 이 위치를 포함하거나 이 위치에 있는 심볼 찾기
        defining_symbol = self.request_containing_symbol(def_path, def_line, def_col, strict=False, include_body=include_body)

        return defining_symbol

    @property
    def cache_path(self) -> Path:
        """
        문서 심볼에 대한 캐시 파일 경로입니다.
        """
        return (
            Path(self.repository_root_path)
            / self._solidlsp_settings.project_data_relative_path
            / self.CACHE_FOLDER_NAME
            / self.language_id
            / "document_symbols_cache_v23-06-25.pkl"
        )

    def save_cache(self):
        with self._cache_lock:
            if not self._cache_has_changed:
                self.logger.log("문서 심볼 캐시에 변경 사항이 없어 저장을 건너뜁니다.", logging.DEBUG)
                return

            self.logger.log(f"업데이트된 문서 심볼 캐시를 {self.cache_path}에 저장 중", logging.INFO)
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(self.cache_path, "wb") as f:
                    pickle.dump(self._document_symbols_cache, f)
                self._cache_has_changed = False
            except Exception as e:
                self.logger.log(
                    f"문서 심볼 캐시를 {self.cache_path}에 저장하지 못했습니다: {e}. "
                    "참고: 이로 인해 캐시 파일이 손상되었을 수 있습니다.",
                    logging.ERROR,
                )

    def load_cache(self):
        if not self.cache_path.exists():
            return

        with self._cache_lock:
            self.logger.log(f"{self.cache_path}에서 문서 심볼 캐시 로드 중", logging.INFO)
            try:
                with open(self.cache_path, "rb") as f:
                    self._document_symbols_cache = pickle.load(f)
                self.logger.log(f"캐시에서 {len(self._document_symbols_cache)}개의 문서 심볼을 로드했습니다.", logging.INFO)
            except Exception as e:
                # 캐시가 종종 손상되므로 로드를 건너뜁니다.
                self.logger.log(
                    f"{self.cache_path}에서 문서 심볼 캐시를 로드하지 못했습니다: {e}. 가능한 원인: 캐시 파일이 손상되었습니다. "
                    "로그에서 캐시 저장과 관련된 오류를 확인하세요.",
                    logging.ERROR,
                )

    def request_workspace_symbol(self, query: str) -> list[ls_types.UnifiedSymbolInformation] | None:
        """
        전체 작업 공간에서 심볼을 찾기 위해 언어 서버에 [workspace/symbol](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#workspace_symbol) 요청을 보냅니다.
        응답을 기다린 후 결과를 반환합니다.

        :param query: 심볼을 필터링할 쿼리 문자열

        :return: 일치하는 심볼 목록
        """
        response = self.server.send.workspace_symbol({"query": query})
        if response is None:
            return None

        assert isinstance(response, list)

        ret: list[ls_types.UnifiedSymbolInformation] = []
        for item in response:
            assert isinstance(item, dict)

            assert LSPConstants.NAME in item
            assert LSPConstants.KIND in item
            assert LSPConstants.LOCATION in item

            ret.append(ls_types.UnifiedSymbolInformation(**item))

        return ret

    def start(self) -> "SolidLanguageServer":
        """
        언어 서버 프로세스를 시작하고 연결합니다. 준비가 되면 shutdown을 호출하세요.

        :return: 메서드 체이닝을 위한 self
        """
        self.logger.log(
            f"{self.language_server.repository_root_path}에 대해 언어 {self.language_server.language}로 언어 서버 시작 중",
            logging.INFO,
        )
        self._server_context = self._start_server_process()
        return self

    def stop(self, shutdown_timeout: float = 2.0) -> None:
        self._shutdown(timeout=shutdown_timeout)

    @property
    def language_server(self) -> Self:
        return self

    def is_running(self) -> bool:
        return self.server.is_running()