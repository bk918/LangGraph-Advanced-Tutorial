"""
solidlsp/ls_utils.py - SolidLSP 유틸리티 함수

이 파일은 텍스트 처리, 경로 변환, 파일 시스템 작업, 플랫폼 감지 등
`solidlsp` 라이브러리 전반에서 사용되는 다양한 유틸리티 함수와 클래스를 포함합니다.

주요 컴포넌트:
- TextUtils: 텍스트 인덱스 변환, 텍스트 삽입/삭제 등 문자열 조작 관련 유틸리티.
- PathUtils: `file://` URI와 로컬 파일 시스템 경로 간의 상호 변환 유틸리티.
- FileUtils: 파일 읽기, 다운로드, 압축 해제 등 파일 I/O 관련 유틸리티.
- PlatformId, DotnetVersion: 현재 실행 중인 운영 체제, 아키텍처, .NET 버전을 식별하기 위한 열거형.
- PlatformUtils: 플랫폼 정보를 감지하고 반환하는 유틸리티 클래스.
- SymbolUtils: 심볼 트리 관련 유틸리티.
"""

import gzip
import logging
import os
import platform
import shutil
import subprocess
import uuid
import zipfile
from enum import Enum
from pathlib import Path, PurePath

import requests

from solidlsp.ls_exceptions import SolidLSPException
from solidlsp.ls_logger import LanguageServerLogger
from solidlsp.ls_types import UnifiedSymbolInformation


class InvalidTextLocationError(Exception):
    pass


class TextUtils:
    """
    텍스트 작업을 위한 유틸리티입니다.
    """

    @staticmethod
    def get_line_col_from_index(text: str, index: int) -> tuple[int, int]:
        """
        주어진 텍스트에서 주어진 인덱스의 0부터 시작하는 줄과 열 번호를 반환합니다.
        """
        l = 0
        c = 0
        idx = 0
        while idx < index:
            if text[idx] == "\n":
                l += 1
                c = 0
            else:
                c += 1
            idx += 1

        return l, c

    @staticmethod
    def get_index_from_line_col(text: str, line: int, col: int) -> int:
        """
        주어진 텍스트에서 주어진 0부터 시작하는 줄과 열 번호의 인덱스를 반환합니다.
        """
        idx = 0
        while line > 0:
            if idx >= len(text):
                raise InvalidTextLocationError
            if text[idx] == "\n":
                line -= 1
            idx += 1
        idx += col
        return idx

    @staticmethod
    def _get_updated_position_from_line_and_column_and_edit(l: int, c: int, text_to_be_inserted: str) -> tuple[int, int]:
        """
        주어진 줄과 열에 텍스트를 삽입한 후 커서의 위치를 가져오는 유틸리티 함수입니다.
        """
        num_newlines_in_gen_text = text_to_be_inserted.count("\n")
        if num_newlines_in_gen_text > 0:
            l += num_newlines_in_gen_text
            c = len(text_to_be_inserted.split("\n")[-1])
        else:
            c += len(text_to_be_inserted)
        return (l, c)

    @staticmethod
    def delete_text_between_positions(text: str, start_line: int, start_col: int, end_line: int, end_col: int) -> tuple[str, str]:
        """
        주어진 시작 및 끝 위치 사이의 텍스트를 삭제합니다.
        수정된 텍스트와 삭제된 텍스트를 반환합니다.
        """
        del_start_idx = TextUtils.get_index_from_line_col(text, start_line, start_col)
        del_end_idx = TextUtils.get_index_from_line_col(text, end_line, end_col)

        deleted_text = text[del_start_idx:del_end_idx]
        new_text = text[:del_start_idx] + text[del_end_idx:]
        return new_text, deleted_text

    @staticmethod
    def insert_text_at_position(text: str, line: int, col: int, text_to_be_inserted: str) -> tuple[str, int, int]:
        """
        주어진 줄과 열에 주어진 텍스트를 삽입합니다.
        수정된 텍스트와 새 줄 및 열을 반환합니다.
        """
        try:
            change_index = TextUtils.get_index_from_line_col(text, line, col)
        except InvalidTextLocationError:
            num_lines_in_text = text.count("\n") + 1
            max_line = num_lines_in_text - 1
            if line == max_line + 1 and col == 0:  # 전체 텍스트 뒤에 새 줄에 삽입하려고 시도
                # 끝에 삽입, 누락된 개행 추가
                change_index = len(text)
                text_to_be_inserted = "\n" + text_to_be_inserted
            else:
                raise
        new_text = text[:change_index] + text_to_be_inserted + text[change_index:]
        new_l, new_c = TextUtils._get_updated_position_from_line_and_column_and_edit(line, col, text_to_be_inserted)
        return new_text, new_l, new_c


class PathUtils:
    """
    플랫폼에 구애받지 않는 경로 작업을 위한 유틸리티입니다.
    """

    @staticmethod
    def uri_to_path(uri: str) -> str:
        """
        URI를 파일 경로로 변환합니다. Linux와 Windows 모두에서 작동합니다.

        이 메서드는 https://stackoverflow.com/a/61922504 에서 가져왔습니다.
        """
        try:
            from urllib.parse import unquote, urlparse
            from urllib.request import url2pathname
        except ImportError:
            # 하위 호환성
            from urllib import unquote, url2pathname

            from urlparse import urlparse
        parsed = urlparse(uri)
        host = f"{os.path.sep}{os.path.sep}{parsed.netloc}{os.path.sep}"
        path = os.path.normpath(os.path.join(host, url2pathname(unquote(parsed.path))))
        return path

    @staticmethod
    def path_to_uri(path: str) -> str:
        """
        파일 경로를 파일 URI(file:///...)로 변환합니다.
        """
        return str(Path(path).absolute().as_uri())

    @staticmethod
    def is_glob_pattern(pattern: str) -> bool:
        """패턴에 glob 관련 문자가 포함되어 있는지 확인합니다."""
        return any(c in pattern for c in "*?[]!")

    @staticmethod
    def get_relative_path(path: str, base_path: str) -> str | None:
        """
        가능한 경우 상대 경로를 가져옵니다(경로는 동일한 드라이브에 있어야 함).
        그렇지 않으면 `None`을 반환합니다.
        """
        if PurePath(path).drive == PurePath(base_path).drive:
            rel_path = str(PurePath(os.path.relpath(path, base_path)))
            return rel_path
        return None


class FileUtils:
    """
    파일 작업을 위한 유틸리티 함수입니다.
    """

    @staticmethod
    def read_file(logger: LanguageServerLogger, file_path: str) -> str:
        """
        주어진 경로의 파일을 읽고 내용을 문자열로 반환합니다.
        """
        if not os.path.exists(file_path):
            logger.log(f"파일 읽기 '{file_path}' 실패: 파일이 존재하지 않습니다.", logging.ERROR)
            raise SolidLSPException(f"파일 읽기 '{file_path}' 실패: 파일이 존재하지 않습니다.")
        try:
            with open(file_path, encoding="utf-8") as inp_file:
                return inp_file.read()
        except Exception as exc:
            logger.log(f"파일 읽기 '{file_path}'가 인코딩 'utf-8'로 읽기 실패: {exc}", logging.ERROR)
            raise SolidLSPException("파일 읽기 실패.") from None

    @staticmethod
    def download_file(logger: LanguageServerLogger, url: str, target_path: str) -> None:
        """
        주어진 URL에서 주어진 {target_path}로 파일을 다운로드합니다.
        """
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        try:
            response = requests.get(url, stream=True, timeout=60)
            if response.status_code != 200:
                logger.log(f"파일 다운로드 오류 '{url}': {response.status_code} {response.text}", logging.ERROR)
                raise SolidLSPException("파일 다운로드 오류.")
            with open(target_path, "wb") as f:
                shutil.copyfileobj(response.raw, f)
        except Exception as exc:
            logger.log(f"파일 다운로드 오류 '{url}': {exc}", logging.ERROR)
            raise SolidLSPException("파일 다운로드 오류.") from None

    @staticmethod
    def download_and_extract_archive(logger: LanguageServerLogger, url: str, target_path: str, archive_type: str) -> None:
        """
        주어진 URL에서 {archive_type} 형식의 아카이브를 다운로드하고 주어진 {target_path}에 압축을 <0xED><0x81><0xx8D>니다.
        """
        try:
            tmp_files = []
            tmp_file_name = str(PurePath(os.path.expanduser("~"), "multilspy_tmp", uuid.uuid4().hex))
            tmp_files.append(tmp_file_name)
            os.makedirs(os.path.dirname(tmp_file_name), exist_ok=True)
            FileUtils.download_file(logger, url, tmp_file_name)
            if archive_type in ["tar", "gztar", "bztar", "xztar"]:
                os.makedirs(target_path, exist_ok=True)
                shutil.unpack_archive(tmp_file_name, target_path, archive_type)
            elif archive_type == "zip":
                os.makedirs(target_path, exist_ok=True)
                with zipfile.ZipFile(tmp_file_name, "r") as zip_ref:
                    for zip_info in zip_ref.infolist():
                        extracted_path = zip_ref.extract(zip_info, target_path)
                        ZIP_SYSTEM_UNIX = 3  # Unix 시스템에서 생성된 zip 파일
                        if zip_info.create_system != ZIP_SYSTEM_UNIX:
                            continue
                        # extractall()은 권한을 보존하지 않습니다.
                        # 참조: https://github.com/python/cpython/issues/59999
                        attrs = (zip_info.external_attr >> 16) & 0o777
                        if attrs:
                            os.chmod(extracted_path, attrs)
            elif archive_type == "zip.gz":
                os.makedirs(target_path, exist_ok=True)
                tmp_file_name_ungzipped = tmp_file_name + ".zip"
                tmp_files.append(tmp_file_name_ungzipped)
                with gzip.open(tmp_file_name, "rb") as f_in, open(tmp_file_name_ungzipped, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                shutil.unpack_archive(tmp_file_name_ungzipped, target_path, "zip")
            elif archive_type == "gz":
                with gzip.open(tmp_file_name, "rb") as f_in, open(target_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            else:
                logger.log(f"압축 해제를 위한 알 수 없는 아카이브 유형 '{archive_type}'", logging.ERROR)
                raise SolidLSPException(f"알 수 없는 아카이브 유형 '{archive_type}'")
        except Exception as exc:
            logger.log(f"'{url}'에서 가져온 아카이브 '{tmp_file_name}' 압축 해제 중 오류: {exc}", logging.ERROR)
            raise SolidLSPException("아카이브 압축 해제 중 오류.") from exc
        finally:
            for tmp_file_name in tmp_files:
                if os.path.exists(tmp_file_name):
                    Path.unlink(Path(tmp_file_name))


class PlatformId(str, Enum):
    """
    multilspy 지원 플랫폼
    """

    WIN_x86 = "win-x86"
    WIN_x64 = "win-x64"
    WIN_arm64 = "win-arm64"
    OSX = "osx"
    OSX_x64 = "osx-x64"
    OSX_arm64 = "osx-arm64"
    LINUX_x86 = "linux-x86"
    LINUX_x64 = "linux-x64"
    LINUX_arm64 = "linux-arm64"
    LINUX_MUSL_x64 = "linux-musl-x64"
    LINUX_MUSL_arm64 = "linux-musl-arm64"

    def is_windows(self):
        return self.value.startswith("win")


class DotnetVersion(str, Enum):
    """
    multilspy 지원 dotnet 버전
    """

    V4 = "4"
    V6 = "6"
    V7 = "7"
    V8 = "8"
    V9 = "9"
    VMONO = "mono"


class PlatformUtils:
    """
    이 클래스는 플랫폼 감지 및 식별을 위한 유틸리티를 제공합니다.
    """

    @classmethod
    def get_platform_id(cls) -> PlatformId:
        """
        현재 시스템의 플랫폼 ID를 반환합니다.
        """
        system = platform.system()
        machine = platform.machine()
        bitness = platform.architecture()[0]
        if system == "Windows" and machine == "":
            machine = cls._determine_windows_machine_type()
        system_map = {"Windows": "win", "Darwin": "osx", "Linux": "linux"}
        machine_map = {
            "AMD64": "x64",
            "x86_64": "x64",
            "i386": "x86",
            "i686": "x86",
            "aarch64": "arm64",
            "arm64": "arm64",
            "ARM64": "arm64",
        }
        if system in system_map and machine in machine_map:
            platform_id = system_map[system] + "-" + machine_map[machine]
            if system == "Linux" and bitness == "64bit":
                libc = platform.libc_ver()[0]
                if libc != "glibc":
                    platform_id += "-" + libc
            return PlatformId(platform_id)
        else:
            raise SolidLSPException(f"알 수 없는 플랫폼: {system=}, {machine=}, {bitness=}")

    @staticmethod
    def _determine_windows_machine_type():
        import ctypes
        from ctypes import wintypes

        class SYSTEM_INFO(ctypes.Structure):
            class _U(ctypes.Union):
                class _S(ctypes.Structure):
                    _fields_ = [("wProcessorArchitecture", wintypes.WORD), ("wReserved", wintypes.WORD)]

                _fields_ = [("dwOemId", wintypes.DWORD), ("s", _S)]
                _anonymous_ = ("s",)

            _fields_ = [
                ("u", _U),
                ("dwPageSize", wintypes.DWORD),
                ("lpMinimumApplicationAddress", wintypes.LPVOID),
                ("lpMaximumApplicationAddress", wintypes.LPVOID),
                ("dwActiveProcessorMask", wintypes.LPVOID),
                ("dwNumberOfProcessors", wintypes.DWORD),
                ("dwProcessorType", wintypes.DWORD),
                ("dwAllocationGranularity", wintypes.DWORD),
                ("wProcessorLevel", wintypes.WORD),
                ("wProcessorRevision", wintypes.WORD),
            ]
            _anonymous_ = ("u",)

        sys_info = SYSTEM_INFO()
        ctypes.windll.kernel32.GetNativeSystemInfo(ctypes.byref(sys_info))

        arch_map = {
            9: "AMD64",
            5: "ARM",
            12: "arm64",
            6: "Intel Itanium-based",
            0: "i386",
        }

        return arch_map.get(sys_info.wProcessorArchitecture, f"Unknown ({sys_info.wProcessorArchitecture})")

    @staticmethod
    def get_dotnet_version() -> DotnetVersion:
        """
        현재 시스템의 dotnet 버전을 반환합니다.
        """
        try:
            result = subprocess.run(["dotnet", "--list-runtimes"], capture_output=True, check=True)
            available_version_cmd_output = []
            for line in result.stdout.decode("utf-8").split("\n"):
                if line.startswith("Microsoft.NETCore.App"):
                    version_cmd_output = line.split(" ")[1]
                    available_version_cmd_output.append(version_cmd_output)

            if not available_version_cmd_output:
                raise SolidLSPException("시스템에서 dotnet을 찾을 수 없습니다.")

            # 지원되는 버전을 최신 버전 우선으로 확인
            for version_cmd_output in available_version_cmd_output:
                if version_cmd_output.startswith("9"):
                    return DotnetVersion.V9
                if version_cmd_output.startswith("8"):
                    return DotnetVersion.V8
                if version_cmd_output.startswith("7"):
                    return DotnetVersion.V7
                if version_cmd_output.startswith("6"):
                    return DotnetVersion.V6
                if version_cmd_output.startswith("4"):
                    return DotnetVersion.V4

            # 지원되는 버전이 없는 경우 사용 가능한 모든 버전과 함께 예외 발생
            raise SolidLSPException(
                f"지원되는 dotnet 버전을 찾을 수 없습니다. 사용 가능한 버전: {', '.join(available_version_cmd_output)}. 지원되는 버전: 4, 6, 7, 8"
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                result = subprocess.run(["mono", "--version"], capture_output=True, check=True)
                return DotnetVersion.VMONO
            except (FileNotFoundError, subprocess.CalledProcessError):
                raise SolidLSPException("시스템에서 dotnet 또는 mono를 찾을 수 없습니다.")


class SymbolUtils:
    @staticmethod
    def symbol_tree_contains_name(roots: list[UnifiedSymbolInformation], name: str) -> bool:
        for symbol in roots:
            if symbol["name"] == name:
                return True
            if SymbolUtils.symbol_tree_contains_name(symbol["children"], name):
                return True
        return False