"""
solidlsp/ls_handler.py - SolidLSP 언어 서버 핸들러

이 파일은 언어 서버 프로세스를 시작하고, JSON-RPC 2.0 프로토콜을 통해
통신하는 `SolidLanguageServerHandler` 클래스를 구현합니다.
LSP 클라이언트의 핵심 로직을 담당합니다.

주요 클래스:
- LanguageServerTerminatedException: 언어 서버 프로세스가 예기치 않게 종료되었을 때 발생하는 예외.
- Request: 비동기 LSP 요청의 상태와 결과를 관리하는 클래스.
- SolidLanguageServerHandler: 언어 서버 프로세스의 생명주기를 관리하고,
  요청/응답/알림을 보내고 받는 핵심 핸들러 클래스.

주요 기능:
- 언어 서버 프로세스 시작 및 종료.
- 표준 입출력(stdio)을 통한 메시지 읽기/쓰기 스레드 관리.
- LSP 메시지 직렬화/역직렬화.
- 요청 ID를 기반으로 비동기 요청과 응답을 매칭.
- 서버로부터의 요청 및 알림에 대한 콜백 핸들러 등록.
- 스레드 안전성을 위한 잠금(lock) 메커니즘.
"""

import asyncio
import json
import logging
import os
import platform
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any

import psutil
from sensai.util.string import ToStringMixin

from solidlsp.ls_exceptions import SolidLSPException
from solidlsp.ls_request import LanguageServerRequest
from solidlsp.lsp_protocol_handler.lsp_requests import LspNotification
from solidlsp.lsp_protocol_handler.lsp_types import ErrorCodes
from solidlsp.lsp_protocol_handler.server import (
    ENCODING,
    LSPError,
    MessageType,
    PayloadLike,
    ProcessLaunchInfo,
    StringDict,
    content_length,
    create_message,
    make_error_response,
    make_notification,
    make_request,
    make_response,
)
from solidlsp.util.subprocess_util import subprocess_kwargs

log = logging.getLogger(__name__)


class LanguageServerTerminatedException(Exception):
    """
    언어 서버 프로세스가 예기치 않게 종료되었을 때 발생하는 예외입니다.
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause

    def __str__(self) -> str:
        return f"LanguageServerTerminatedException: {self.message}" + (f"; 원인: {self.cause}" if self.cause else "")


class Request(ToStringMixin):
    @dataclass
    class Result:
        payload: PayloadLike | None = None
        error: Exception | None = None

        def is_error(self) -> bool:
            return self.error is not None

    def __init__(self, request_id: int, method: str) -> None:
        self._request_id = request_id
        self._method = method
        self._status = "pending"
        self._result_queue = Queue()

    def _tostring_includes(self) -> list[str]:
        return ["_request_id", "_status", "_method"]

    def on_result(self, params: PayloadLike) -> None:
        self._status = "completed"
        self._result_queue.put(Request.Result(payload=params))

    def on_error(self, err: Exception) -> None:
        """
        :param err: 요청 처리 중 발생한 오류 (일반적으로 LS가 반환한 오류에 대한 LSPError
            또는 언어 서버 프로세스가 예기치 않게 종료되어 발생한 오류인 경우 LanguageServerTerminatedException).
        """
        self._status = "error"
        self._result_queue.put(Request.Result(error=err))

    def get_result(self, timeout: float | None = None) -> Result:
        try:
            return self._result_queue.get(timeout=timeout)
        except Empty as e:
            if timeout is not None:
                raise TimeoutError(f"요청 시간 초과 ({timeout=})") from e
            raise e


class SolidLanguageServerHandler:
    """
    이 클래스는 언어 서버 프로토콜(LSP)을 위한 파이썬 클라이언트 구현을 제공합니다.
    언어 서버를 시작하고 LSP를 사용하여 통신하는 클래스입니다.

    서버에 요청, 응답, 알림을 보내고 서버로부터의 요청 및 알림에 대한 핸들러를
    등록하는 메서드를 제공합니다.

    stdin/stdout을 통해 서버와 통신하기 위해 JSON-RPC 2.0을 사용합니다.

    Attributes:
        send: 서버에 요청을 보내고 응답을 기다리는 데 사용할 수 있는 LspRequest 객체.
        notify: 서버에 알림을 보내는 데 사용할 수 있는 LspNotification 객체.
        cmd: 언어 서버 프로세스를 시작하는 명령을 나타내는 문자열.
        process: 언어 서버 프로세스를 나타내는 subprocess.Popen 객체.
        request_id: 클라이언트의 다음 사용 가능한 요청 ID를 나타내는 정수.
        _pending_requests: 요청 ID를 요청의 결과나 오류를 저장하는 Request 객체에 매핑하는 딕셔너리.
        on_request_handlers: 메서드 이름을 서버로부터의 요청을 처리하는 콜백 함수에 매핑하는 딕셔너리.
        on_notification_handlers: 메서드 이름을 서버로부터의 알림을 처리하는 콜백 함수에 매핑하는 딕셔너리.
        logger: 두 개의 문자열(소스 및 대상)과 페이로드 딕셔너리를 받아 클라이언트와 서버 간의 통신을 기록하는 선택적 함수.
        tasks: 태스크 ID를 핸들러가 생성한 비동기 태스크를 나타내는 asyncio.Task 객체에 매핑하는 딕셔너리.
        task_counter: 핸들러의 다음 사용 가능한 태스크 ID를 나타내는 정수.
        loop: 핸들러가 사용하는 이벤트 루프를 나타내는 asyncio.AbstractEventLoop 객체.
        start_independent_lsp_process: 언어 서버 프로세스를 독립적인 프로세스 그룹에서 시작할지 여부를 나타내는 선택적 부울 플래그. 기본값은 `True`입니다.
        `False`로 설정하면 언어 서버 프로세스가 현재 프로세스와 동일한 프로세스 그룹에 있게 되며, 모든 SIGINT 및 SIGTERM 신호가 두 프로세스 모두에 전송됩니다.

    """

    def __init__(
        self,
        process_launch_info: ProcessLaunchInfo,
        logger: Callable[[str, str, StringDict | str], None] | None = None,
        start_independent_lsp_process=True,
        request_timeout: float | None = None,
    ) -> None:
        self.send = LanguageServerRequest(self)
        self.notify = LspNotification(self.send_notification)

        self.process_launch_info = process_launch_info
        self.process: subprocess.Popen | None = None
        self._is_shutting_down = False

        self.request_id = 1
        self._pending_requests: dict[Any, Request] = {}
        self.on_request_handlers = {}
        self.on_notification_handlers = {}
        self.logger = logger
        self.tasks = {}
        self.task_counter = 0
        self.loop = None
        self.start_independent_lsp_process = start_independent_lsp_process
        self._request_timeout = request_timeout

        # 경쟁 조건을 방지하기 위해 공유 리소스에 대한 스레드 잠금 추가
        self._stdin_lock = threading.Lock()
        self._request_id_lock = threading.Lock()
        self._response_handlers_lock = threading.Lock()
        self._tasks_lock = threading.Lock()

    def set_request_timeout(self, timeout: float | None) -> None:
        """
        :param timeout: 언어 서버로 보내는 모든 요청에 대한 시간 초과(초).
        """
        self._request_timeout = timeout

    def is_running(self) -> bool:
        """
        언어 서버 프로세스가 현재 실행 중인지 확인합니다.
        """
        return self.process is not None and self.process.returncode is None

    def start(self) -> None:
        """
        언어 서버 프로세스를 시작하고 stdout에서 지속적으로 읽어
        서버에서 클라이언트로의 통신을 처리하는 작업을 생성합니다.
        """
        child_proc_env = os.environ.copy()
        child_proc_env.update(self.process_launch_info.env)

        cmd = self.process_launch_info.cmd
        is_windows = platform.system() == "Windows"
        if not isinstance(cmd, str) and not is_windows:
            # 셸을 사용하므로 Linux/macOS에서는 명령어 목록을 단일 문자열로 변환해야 합니다.
            cmd = " ".join(cmd)
        log.info("명령어를 통해 언어 서버 프로세스 시작: %s", self.process_launch_info.cmd)
        kwargs = subprocess_kwargs()
        kwargs["start_new_session"] = self.start_independent_lsp_process
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=child_proc_env,
            cwd=self.process_launch_info.cwd,
            shell=True,
            **kwargs,
        )

        # 프로세스가 즉시 종료되었는지 확인
        if self.process.returncode is not None:
            log.error("언어 서버가 이미 종료되었거나 시작할 수 없습니다.")
            # 프로세스가 이미 종료됨
            stderr_data = self.process.stderr.read()
            error_message = stderr_data.decode("utf-8", errors="replace")
            raise RuntimeError(f"프로세스가 코드 {self.process.returncode}로 즉시 종료되었습니다. 오류: {error_message}")

        # 프로세스의 stdout 및 stderr를 읽는 스레드 시작
        threading.Thread(
            target=self._read_ls_process_stdout,
            name="LSP-stdout-reader",
            daemon=True,
        ).start()
        threading.Thread(
            target=self._read_ls_process_stderr,
            name="LSP-stderr-reader",
            daemon=True,
        ).start()

    def stop(self) -> None:
        """
        언어 서버 프로세스에 종료 신호를 보내고 시간 초과와 함께 종료될 때까지 기다린 후, 필요한 경우 강제 종료합니다.
        """
        process = self.process
        self.process = None
        if process:
            self._cleanup_process(process)

    def _cleanup_process(self, process):
        """프로세스 정리: stdin 닫기, 프로세스 종료/강제 종료, stdout/stderr 닫기."""
        # 교착 상태를 방지하기 위해 먼저 stdin을 닫습니다.
        # 참조: https://bugs.python.org/issue35539
        self._safely_close_pipe(process.stdin)

        # 프로세스가 여전히 실행 중인 경우 종료/강제 종료
        if process.returncode is None:
            self._terminate_or_kill_process(process)

        # 프로세스가 종료된 후 stdout 및 stderr 파이프 닫기
        # 이는 "닫힌 파이프에 대한 I/O 작업" 오류 및
        # 가비지 수집 중 "이벤트 루프가 닫혔습니다" 오류를 방지하는 데 필수적입니다.
        # 참조: https://bugs.python.org/issue41320 및 https://github.com/python/cpython/issues/88050
        self._safely_close_pipe(process.stdout)
        self._safely_close_pipe(process.stderr)

    def _safely_close_pipe(self, pipe):
        """파이프를 안전하게 닫고 모든 예외를 무시합니다."""
        if pipe:
            try:
                pipe.close()
            except Exception:
                pass

    def _terminate_or_kill_process(self, process):
        """프로세스를 정상적으로 종료한 다음, 필요한 경우 강제로 종료합니다."""
        # 먼저 프로세스 트리를 정상적으로 종료하려고 시도합니다.
        self._signal_process_tree(process, terminate=True)

    def _signal_process_tree(self, process, terminate=True):
        """프로세스와 모든 자식 프로세스에 신호(종료 또는 강제 종료)를 보냅니다."""
        signal_method = "terminate" if terminate else "kill"

        # 부모 프로세스를 가져오려고 시도합니다.
        parent = None
        try:
            parent = psutil.Process(process.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            pass

        # 부모 프로세스가 있고 실행 중인 경우 전체 트리에 신호를 보냅니다.
        if parent and parent.is_running():
            # 먼저 자식에게 신호를 보냅니다.
            for child in parent.children(recursive=True):
                try:
                    getattr(child, signal_method)()
                except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                    pass

            # 그런 다음 부모에게 신호를 보냅니다.
            try:
                getattr(parent, signal_method)()
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
        else:
            # 직접 프로세스 신호로 대체합니다.
            try:
                getattr(process, signal_method)()
            except Exception:
                pass

    def shutdown(self) -> None:
        """
        서버에 종료 요청을 보내고 종료를 알리는 것을 포함하여 클라이언트에 대한 종료 시퀀스를 수행합니다.
        """
        self._is_shutting_down = True
        self._log("서버에 종료 요청 보내는 중")
        self.send.shutdown()
        self._log("서버로부터 종료 응답 받음")
        self._log("서버에 종료 알림 보내는 중")
        self.notify.exit()
        self._log("서버에 종료 알림 보냄")

    def _log(self, message: str | StringDict) -> None:
        """
        로그 메시지를 생성합니다.
        """
        if self.logger is not None:
            self.logger("client", "logger", message)

    @staticmethod
    def _read_bytes_from_process(process, stream, num_bytes):
        """프로세스 stdout에서 정확히 num_bytes를 읽습니다."""
        data = b""
        while len(data) < num_bytes:
            chunk = stream.read(num_bytes - len(data))
            if not chunk:
                if process.poll() is not None:
                    raise LanguageServerTerminatedException(
                        f"응답을 읽는 동안 프로세스가 종료되었습니다 (종료 전 {len(data)}/{num_bytes} 바이트 읽음)"
                    )
                # 프로세스는 여전히 실행 중이지만 아직 사용 가능한 데이터가 없으므로 잠시 후 다시 시도합니다.
                time.sleep(0.01)
                continue
            data += chunk
        return data

    def _read_ls_process_stdout(self) -> None:
        """
        언어 서버 프로세스 stdout에서 지속적으로 읽고 등록된 응답 및 알림 핸들러를 호출하여 메시지를 처리합니다.
        """
        exception: Exception | None = None
        try:
            while self.process and self.process.stdout:
                if self.process.poll() is not None:  # 프로세스가 종료됨
                    break
                line = self.process.stdout.readline()
                if not line:
                    continue
                try:
                    num_bytes = content_length(line)
                except ValueError:
                    continue
                if num_bytes is None:
                    continue
                while line and line.strip():
                    line = self.process.stdout.readline()
                if not line:
                    continue
                body = self._read_bytes_from_process(self.process, self.process.stdout, num_bytes)

                self._handle_body(body)
        except LanguageServerTerminatedException as e:
            exception = e
        except (BrokenPipeError, ConnectionResetError) as e:
            exception = LanguageServerTerminatedException("stdout을 읽는 동안 언어 서버 프로세스가 종료되었습니다.", cause=e)
        except Exception as e:
            exception = LanguageServerTerminatedException("언어 서버 프로세스에서 stdout을 읽는 동안 예기치 않은 오류가 발생했습니다.", cause=e)
        log.info("언어 서버 stdout 리더 스레드가 종료되었습니다.")
        if not self._is_shutting_down:
            if exception is None:
                exception = LanguageServerTerminatedException("언어 서버 stdout 읽기 프로세스가 예기치 않게 종료되었습니다.")
            log.error(str(exception))
            self._cancel_pending_requests(exception)

    def _read_ls_process_stderr(self) -> None:
        """
        언어 서버 프로세스 stderr에서 지속적으로 읽고 메시지를 기록합니다.
        """
        try:
            while self.process and self.process.stderr:
                if self.process.poll() is not None:
                    # 프로세스가 종료됨
                    break
                line = self.process.stderr.readline()
                if not line:
                    continue
                line = line.decode(ENCODING, errors="replace")
                line_lower = line.lower()
                if "error" in line_lower or "exception" in line_lower or line.startswith("E["):
                    level = logging.ERROR
                else:
                    level = logging.INFO
                log.log(level, line)
        except Exception as e:
            log.error("언어 서버 프로세스에서 stderr를 읽는 동안 오류 발생: %s", e, exc_info=e)
        if not self._is_shutting_down:
            log.error("언어 서버 stderr 리더 스레드가 예기치 않게 종료되었습니다.")
        else:
            log.info("언어 서버 stderr 리더 스레드가 종료되었습니다.")

    def _handle_body(self, body: bytes) -> None:
        """
        언어 서버 프로세스에서 받은 본문 텍스트를 구문 분석하고 적절한 핸들러를 호출합니다.
        """
        try:
            self._receive_payload(json.loads(body))
        except OSError as ex:
            self._log(f"잘못된 형식의 {ENCODING}: {ex}")
        except UnicodeDecodeError as ex:
            self._log(f"잘못된 형식의 {ENCODING}: {ex}")
        except json.JSONDecodeError as ex:
            self._log(f"잘못된 형식의 JSON: {ex}")

    def _receive_payload(self, payload: StringDict) -> None:
        """
        서버에서 받은 페이로드가 요청, 응답 또는 알림용인지 확인하고 적절한 핸들러를 호출합니다.
        """
        if self.logger:
            self.logger("server", "client", payload)
        try:
            if "method" in payload:
                if "id" in payload:
                    self._request_handler(payload)
                else:
                    self._notification_handler(payload)
            elif "id" in payload:
                self._response_handler(payload)
            else:
                self._log(f"알 수 없는 페이로드 유형: {payload}")
        except Exception as err:
            self._log(f"서버 페이로드 처리 중 오류: {err}")

    def send_notification(self, method: str, params: dict | None = None) -> None:
        """
        주어진 메서드에 대한 알림을 주어진 매개변수와 함께 서버에 보냅니다.
        """
        self._send_payload(make_notification(method, params))

    def send_response(self, request_id: Any, params: PayloadLike) -> None:
        """
        주어진 요청 ID에 대한 응답을 주어진 매개변수와 함께 서버에 보냅니다.
        """
        self._send_payload(make_response(request_id, params))

    def send_error_response(self, request_id: Any, err: LSPError) -> None:
        """
        주어진 요청 ID에 대한 오류 응답을 주어진 오류와 함께 서버에 보냅니다.
        """
        # 태스크 및 task_counter에 대한 경쟁 조건을 방지하기 위해 잠금 사용
        self._send_payload(make_error_response(request_id, err))

    def _cancel_pending_requests(self, exception: Exception) -> None:
        """
        결과를 오류로 설정하여 모든 보류 중인 요청을 취소합니다.
        """
        with self._response_handlers_lock:
            log.info("%d개의 보류 중인 언어 서버 요청을 취소합니다.", len(self._pending_requests))
            for request in self._pending_requests.values():
                log.info("%s를 취소합니다.", request)
                request.on_error(exception)
            self._pending_requests.clear()

    def send_request(self, method: str, params: dict | None = None) -> PayloadLike:
        """
        서버에 요청을 보내고 요청 ID를 등록한 다음 응답을 기다립니다.
        """
        with self._request_id_lock:
            request_id = self.request_id
            self.request_id += 1

        request = Request(request_id=request_id, method=method)
        log.debug("시작: %s", request)

        with self._response_handlers_lock:
            self._pending_requests[request_id] = request

        self._send_payload(make_request(method, request_id, params))

        self._log(f"매개변수와 함께 요청 {method}에 대한 응답 대기 중:\n{params}")
        result = request.get_result(timeout=self._request_timeout)
        log.debug("완료: %s", request)

        self._log("결과 처리 중")
        if result.is_error():
            raise SolidLSPException(f"매개변수와 함께 요청 {method} 처리 중 오류:\n{params}", cause=result.error) from result.error

        self._log(f"오류가 아닌 결과 반환 중:\n{result.payload}")
        return result.payload

    def _send_payload(self, payload: StringDict) -> None:
        """
        stdin에 비동기적으로 기록하여 서버에 페이로드를 보냅니다.
        """
        if not self.process or not self.process.stdin:
            return
        self._log(payload)
        msg = create_message(payload)

        # 버퍼 손상을 유발하는 stdin에 대한 동시 쓰기를 방지하기 위해 잠금 사용
        with self._stdin_lock:
            try:
                self.process.stdin.writelines(msg)
                self.process.stdin.flush()
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                # 오류를 기록하지만 연쇄적인 실패를 방지하기 위해 발생시키지 않음
                if self.logger:
                    self.logger("client", "logger", f"stdin에 쓰기 실패: {e}")
                return

    def on_request(self, method: str, cb) -> None:
        """
        주어진 메서드에 대해 서버에서 클라이언트로의 요청을 처리할 콜백 함수를 등록합니다.
        """
        self.on_request_handlers[method] = cb

    def on_notification(self, method: str, cb) -> None:
        """
        주어진 메서드에 대해 서버에서 클라이언트로의 알림을 처리할 콜백 함수를 등록합니다.
        """
        self.on_notification_handlers[method] = cb

    def _response_handler(self, response: StringDict) -> None:
        """
        ID를 사용하여 요청을 결정하고 서버에서 받은 요청에 대한 응답을 처리합니다.
        """
        with self._response_handlers_lock:
            request = self._pending_requests.pop(response["id"])

        if "result" in response and "error" not in response:
            request.on_result(response["result"])
        elif "result" not in response and "error" in response:
            request.on_error(LSPError.from_lsp(response["error"]))
        else:
            request.on_error(LSPError(ErrorCodes.InvalidRequest, ""))

    def _request_handler(self, response: StringDict) -> None:
        """
        서버에서 받은 요청을 처리합니다: 적절한 콜백 함수를 호출하고 결과를 반환합니다.
        """
        method = response.get("method", "")
        params = response.get("params")
        request_id = response.get("id")
        handler = self.on_request_handlers.get(method)
        if not handler:
            self.send_error_response(
                request_id,
                LSPError(
                    ErrorCodes.MethodNotFound,
                    f"메서드 '{method}'가 클라이언트에서 처리되지 않았습니다.",
                ),
            )
            return
        try:
            self.send_response(request_id, handler(params))
        except LSPError as ex:
            self.send_error_response(request_id, ex)
        except Exception as ex:
            self.send_error_response(request_id, LSPError(ErrorCodes.InternalError, str(ex)))

    def _notification_handler(self, response: StringDict) -> None:
        """
        서버에서 받은 알림을 처리합니다: 적절한 콜백 함수를 호출합니다.
        """
        method = response.get("method", "")
        params = response.get("params")
        handler = self.on_notification_handlers.get(method)
        if not handler:
            self._log(f"처리되지 않은 {method}")
            return
        try:
            handler(params)
        except asyncio.CancelledError:
            return
        except Exception as ex:
            if (not self._is_shutting_down) and self.logger:
                self.logger(
                    "client",
                    "logger",
                    str(
                        {
                            "type": MessageType.error,
                            "message": str(ex),
                            "method": method,
                            "params": params,
                        }
                    ),
                )