"""
solidlsp/lsp_protocol_handler/server.py - JSON-RPC 클라이언트 구현

이 파일은 언어 서버와 통신하는 JSON-RPC 클라이언트의 구현을 제공합니다.
언어 서버 프로세스를 시작하고, 표준 입출력(stdio)을 통해 LSP 메시지를
주고받는 저수준(low-level) 로직을 담당합니다.

주요 기능:
- LSP 메시지 생성: `create_message` 함수는 페이로드를 `Content-Length` 헤더가 포함된
  JSON-RPC 메시지 형식으로 인코딩합니다.
- 요청/응답/알림 생성: `make_request`, `make_response`, `make_notification` 등의 헬퍼 함수를 제공합니다.
- 오류 처리: `LSPError` 클래스를 통해 LSP 사양에 맞는 오류 응답을 생성합니다.
- 프로세스 실행 정보: `ProcessLaunchInfo` 데이터 클래스를 통해 언어 서버 프로세스 실행에
  필요한 정보를 관리합니다.

참고:
- 이 파일의 초기 구현은 https://github.com/predragnikolic/OLSP 프로젝트에서 가져왔습니다.

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

import dataclasses
import json
import logging
import os
from typing import Any, Union

from .lsp_types import ErrorCodes

StringDict = dict[str, Any]
PayloadLike = Union[list[StringDict], StringDict, None]
CONTENT_LENGTH = "Content-Length: "
ENCODING = "utf-8"
log = logging.getLogger(__name__)


@dataclasses.dataclass
class ProcessLaunchInfo:
    """
    프로세스를 시작하는 데 필요한 정보를 저장하는 데 사용되는 클래스입니다.
    """

    # 프로세스를 시작하는 명령어
    cmd: str | list[str]

    # 프로세스에 설정할 환경 변수
    env: dict[str, str] = dataclasses.field(default_factory=dict)

    # 프로세스의 작업 디렉토리
    cwd: str = os.getcwd()


class LSPError(Exception):
    def __init__(self, code: ErrorCodes, message: str) -> None:
        super().__init__(message)
        self.code = code

    def to_lsp(self) -> StringDict:
        return {"code": self.code, "message": super().__str__()}

    @classmethod
    def from_lsp(cls, d: StringDict) -> "LSPError":
        return LSPError(d["code"], d["message"])

    def __str__(self) -> str:
        return f"{super().__str__()} ({self.code})"


def make_response(request_id: Any, params: PayloadLike) -> StringDict:
    """성공적인 요청에 대한 LSP 응답 메시지를 생성합니다."""
    return {"jsonrpc": "2.0", "id": request_id, "result": params}


def make_error_response(request_id: Any, err: LSPError) -> StringDict:
    """오류가 발생한 요청에 대한 LSP 오류 응답 메시지를 생성합니다."""
    return {"jsonrpc": "2.0", "id": request_id, "error": err.to_lsp()}


def make_notification(method: str, params: PayloadLike) -> StringDict:
    """LSP 알림 메시지를 생성합니다."""
    return {"jsonrpc": "2.0", "method": method, "params": params}


def make_request(method: str, request_id: Any, params: PayloadLike) -> StringDict:
    """LSP 요청 메시지를 생성합니다."""
    return {"jsonrpc": "2.0", "method": method, "id": request_id, "params": params}


class StopLoopException(Exception):
    """메시지 처리 루프를 중지시키기 위해 발생하는 예외입니다."""
    pass


def create_message(payload: PayloadLike):
    """
    주어진 페이로드로부터 LSP 메시지를 생성합니다.

    LSP는 `Content-Length` 헤더와 함께 JSON-RPC 페이로드를 전송하는 것을 요구합니다.
    이 함수는 페이로드를 JSON 문자열로 직렬화하고, 필요한 헤더를 추가하여
    전송 가능한 바이트 시퀀스로 만듭니다.

    Args:
        payload (PayloadLike): JSON으로 직렬화할 페이로드 객체.

    Returns:
        tuple[bytes, bytes, bytes]: Content-Length 헤더, Content-Type 헤더, 그리고
                                   UTF-8로 인코딩된 JSON 본문.
    """
    body = json.dumps(payload, check_circular=False, ensure_ascii=False, separators=((",", ":"))).encode(ENCODING)
    return (
        f"Content-Length: {len(body)}\r\n".encode(ENCODING),
        "Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(ENCODING),
        body,
    )


class MessageType:
    error = 1
    warning = 2
    info = 3
    log = 4


def content_length(line: bytes) -> int | None:
    """
    LSP 메시지의 `Content-Length` 헤더 라인에서 길이를 추출합니다.

    Args:
        line (bytes): 확인할 헤더 라인.

    Returns:
        int | None: 추출된 콘텐츠 길이. `Content-Length` 헤더가 아니면 None.

    Raises:
        ValueError: 헤더 값의 형식이 잘못된 경우.
    """
    if line.startswith(b"Content-Length: "):
        _, value = line.split(b"Content-Length: ")
        value = value.strip()
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"잘못된 Content-Length 헤더: {value}")
    return None