"""
serena/util/logging.py - 메모리 기반 로깅 유틸리티

이 파일은 로그 메시지를 메모리에 저장하고 관리하기 위한 커스텀 로깅 핸들러를 제공합니다.
GUI 로그 뷰어나 웹 대시보드에서 실시간으로 로그를 표시하는 데 사용됩니다.

주요 클래스:
- MemoryLogHandler: `logging.Handler`를 상속받아, 로그 레코드를 포맷하여
  내부 큐(Queue)에 저장하는 커스텀 핸들러입니다. 백그라운드 스레드를 사용하여
  로그 메시지를 비동기적으로 처리합니다.
- LogBuffer: 로그 메시지를 저장하는 스레드 안전(thread-safe) 버퍼입니다.
  `MemoryLogHandler`가 내부적으로 사용하여 로그 목록을 관리합니다.

아키텍처 노트:
- `MemoryLogHandler`는 생산자-소비자 패턴을 사용합니다. `emit` 메서드가 로그 레코드를
  생산하여 큐에 넣으면, 백그라운드 `worker_thread`가 이를 소비하여 `LogBuffer`에 저장하고
  등록된 콜백 함수들을 호출합니다.
- 이 비동기 처리 방식 덕분에, 로깅 작업(특히 콜백 호출)이 메인 애플리케이션의
  실행 흐름을 막지 않습니다.
- `threading.Lock`을 사용하여 `LogBuffer`에 대한 동시 접근을 제어함으로써,
  여러 스레드에서 안전하게 로그를 읽고 쓸 수 있습니다.
"""

import queue
import threading
from collections.abc import Callable

from sensai.util import logging

from serena.constants import SERENA_LOG_FORMAT


class MemoryLogHandler(logging.Handler):
    """
    로그 메시지를 메모리에 저장하고, 선택적으로 콜백을 통해 다른 곳으로 전파하는 로깅 핸들러.
    """

    def __init__(self, level: int = logging.NOTSET) -> None:
        """
        MemoryLogHandler를 초기화합니다.

        Args:
            level (int): 이 핸들러가 처리할 최소 로그 레벨.
        """
        super().__init__(level=level)
        self.setFormatter(logging.Formatter(SERENA_LOG_FORMAT))
        self._log_buffer = LogBuffer()
        self._log_queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._emit_callbacks: list[Callable[[str], None]] = []

        # 로그 처리를 위한 백그라운드 스레드 시작
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def add_emit_callback(self, callback: Callable[[str], None]) -> None:
        """
        로그 메시지가 발생할 때마다 호출될 콜백을 추가합니다.

        콜백은 단일 문자열 인자(로그 메시지)를 받아야 합니다.

        Args:
            callback (Callable[[str], None]): 추가할 콜백 함수.
        """
        self._emit_callbacks.append(callback)

    def emit(self, record: logging.LogRecord) -> None:
        """
        로그 레코드를 포맷하여 내부 큐에 넣습니다.

        Args:
            record (logging.LogRecord): 처리할 로그 레코드.
        """
        msg = self.format(record)
        self._log_queue.put_nowait(msg)

    def _process_queue(self) -> None:
        """백그라운드에서 실행되며 큐의 로그 메시지를 처리하는 작업자 함수."""
        while not self._stop_event.is_set():
            try:
                msg = self._log_queue.get(timeout=1)
                self._log_buffer.append(msg)
                for callback in self._emit_callbacks:
                    try:
                        callback(msg)
                    except Exception:
                        pass  # 콜백 함수의 예외가 로깅 시스템 전체를 중단시키지 않도록 합니다.
                self._log_queue.task_done()
            except queue.Empty:
                continue

    def get_log_messages(self) -> list[str]:
        """
        지금까지 버퍼에 저장된 모든 로그 메시지의 복사본을 반환합니다.

        Returns:
            list[str]: 로그 메시지 목록.
        """
        return self._log_buffer.get_log_messages()


class LogBuffer:
    """
    로그 메시지를 저장하기 위한 스레드 안전(thread-safe) 버퍼.
    """

    def __init__(self) -> None:
        """LogBuffer를 초기화합니다."""
        self._log_messages: list[str] = []
        self._lock = threading.Lock()

    def append(self, msg: str) -> None:
        """
        버퍼에 로그 메시지를 추가합니다.

        Args:
            msg (str): 추가할 로그 메시지.
        """
        with self._lock:
            self._log_messages.append(msg)

    def get_log_messages(self) -> list[str]:
        """
        버퍼에 있는 모든 로그 메시지의 복사본을 반환합니다.

        Returns:
            list[str]: 현재까지 기록된 모든 로그 메시지의 목록.
        """
        with self._lock:
            return self._log_messages.copy()