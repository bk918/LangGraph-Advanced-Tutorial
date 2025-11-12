# mypy: ignore-errors
"""
serena/gui_log_viewer.py - GUI 기반 로그 뷰어

이 파일은 Tkinter를 사용하여 Serena 에이전트의 로그 메시지를 표시하는 GUI 애플리케이션을 구현합니다.
별도의 스레드에서 실행되어 메인 애플리케이션의 동작을 방해하지 않습니다.

주요 컴포넌트:
- GuiLogViewer: 로그 뷰어 GUI의 생성 및 관리를 담당하는 핵심 클래스.
- GuiLogViewerHandler: Python의 `logging` 모듈과 연동하여 로그 레코드를 GUI로 전송하는 핸들러.
- LogLevel: 로그 레벨별 색상 구분을 위한 열거형.

주요 기능:
- 실시간 로그 표시: `queue`를 사용하여 다른 스레드로부터 로그 메시지를 받아 실시간으로 업데이트합니다.
- 로그 레벨별 색상 구분: DEBUG, INFO, WARNING, ERROR 레벨에 따라 다른 색상으로 로그를 표시합니다.
- 도구 이름 하이라이팅: 로그 메시지에 포함된 도구 이름을 강조하여 가독성을 높입니다.
- 원격 종료 기능: GUI 메뉴를 통해 에이전트 프로세스를 종료할 수 있습니다.

아키텍처 노트:
- Tkinter는 메인 스레드에서만 실행되어야 하는 제약이 있으므로, `GuiLogViewer`는 자체적인
  `threading.Thread` 내에서 Tkinter의 `mainloop()`를 실행합니다.
- `queue.Queue`를 사용하여 스레드 간 안전하게 로그 메시지를 전달합니다.
- `MemoryLogHandler`와 연동하여, 시작 시 기존 로그를 모두 표시하고 이후 발생하는 로그를 실시간으로 받습니다.
- Windows 플랫폼에서는 `ctypes`를 사용하여 고유한 애플리케이션 모델 ID(AppUserModelID)를 설정함으로써,
  작업 표시줄에서 다른 Python 앱과 구별되도록 합니다.
"""
import logging
import os
import queue
import sys
import threading
import tkinter as tk
import traceback
from enum import Enum, auto
from pathlib import Path
from typing import Literal

from serena import constants
from serena.util.logging import MemoryLogHandler

log = logging.getLogger(__name__)


class LogLevel(Enum):
    """로그 레벨을 정의하는 열거형 클래스."""

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    DEFAULT = auto()


class GuiLogViewer:
    """
    별도의 스레드에서 로그 메시지를 표시하기 위한 Tkinter GUI를 생성하는 클래스.

    로그 뷰어는 로그 레벨(DEBUG, INFO, WARNING, ERROR)에 따른 색상 구분을 지원합니다.
    또한 로그 메시지에 나타나는 도구 이름을 굵게 강조 표시할 수 있습니다.
    """

    def __init__(
        self,
        mode: Literal["dashboard", "error"],
        title="Log Viewer",
        memory_log_handler: MemoryLogHandler | None = None,
        width=800,
        height=600,
    ):
        """
        GuiLogViewer를 초기화합니다.

        Args:
            mode (Literal["dashboard", "error"]): "dashboard" 모드에서는 로그 및 제어 옵션이 있는 대시보드를 실행하고,
                "error" 모드에서는 치명적인 예외를 위한 간단한 오류 로그 뷰어를 실행합니다.
            title (str): 창 제목.
            memory_log_handler (MemoryLogHandler | None): 로그 메시지를 가져올 선택적 로그 핸들러.
                제공되지 않으면, 로그 메시지를 추가하기 위해 인스턴스를 `GuiLogViewerHandler`에 전달해야 합니다.
            width (int): 초기 창 너비.
            height (int): 초기 창 높이.
        """
        self.mode = mode
        self.title = title
        self.width = width
        self.height = height
        self.message_queue = queue.Queue()
        self.running = False
        self.log_thread = None
        self.tool_names = []  # 강조할 도구 이름을 저장하는 목록

        # 다른 로그 레벨에 대한 색상 정의
        self.log_colors = {
            LogLevel.DEBUG: "#808080",  # Gray
            LogLevel.INFO: "#000000",  # Black
            LogLevel.WARNING: "#FF8C00",  # Dark Orange
            LogLevel.ERROR: "#FF0000",  # Red
            LogLevel.DEFAULT: "#000000",  # Black
        }

        if memory_log_handler is not None:
            for msg in memory_log_handler.get_log_messages():
                self.message_queue.put(msg)
            memory_log_handler.add_emit_callback(lambda msg: self.message_queue.put(msg))

    def start(self):
        """별도의 스레드에서 로그 뷰어를 시작합니다."""
        if not self.running:
            self.log_thread = threading.Thread(target=self.run_gui)
            self.log_thread.daemon = True
            self.log_thread.start()
            return True
        return False

    def stop(self):
        """로그 뷰어를 중지합니다."""
        if self.running:
            # GUI 종료를 알리기 위해 큐에 센티널 값을 추가합니다.
            self.message_queue.put(None)
            return True
        return False

    def set_tool_names(self, tool_names):
        """
        로그 메시지에서 강조할 도구 이름 목록을 설정하거나 업데이트합니다.

        Args:
            tool_names (list): 강조할 도구 이름 문자열 목록.
        """
        self.tool_names = tool_names

    def add_log(self, message):
        """
        뷰어에 로그 메시지를 추가합니다.

        Args:
            message (str): 표시할 로그 메시지.
        """
        self.message_queue.put(message)

    def _determine_log_level(self, message):
        """
        메시지에서 로그 레벨을 결정합니다.

        Args:
            message (str): 로그 메시지.

        Returns:
            LogLevel: 결정된 로그 레벨.
        """
        message_upper = message.upper()
        if message_upper.startswith("DEBUG"):
            return LogLevel.DEBUG
        elif message_upper.startswith("INFO"):
            return LogLevel.INFO
        elif message_upper.startswith("WARNING"):
            return LogLevel.WARNING
        elif message_upper.startswith("ERROR"):
            return LogLevel.ERROR
        else:
            return LogLevel.DEFAULT

    def _process_queue(self):
        """큐에서 메시지를 처리하고 텍스트 위젯을 업데이트합니다."""
        try:
            while not self.message_queue.empty():
                message = self.message_queue.get_nowait()

                # 종료를 위한 센티널 값 확인
                if message is None:
                    self.root.quit()
                    return

                # 새 텍스트를 추가하기 전에 스크롤바가 맨 아래에 있는지 확인
                current_position = self.text_widget.yview()
                was_at_bottom = current_position[1] > 0.99

                log_level = self._determine_log_level(message)

                self.text_widget.configure(state=tk.NORMAL)

                if self.tool_names:
                    start_index = self.text_widget.index("end-1c")
                    self.text_widget.insert(tk.END, message + "\n", log_level.name)
                    line, char = map(int, start_index.split("."))

                    for tool_name in self.tool_names:
                        start_offset = 0
                        while True:
                            found_at = message.find(tool_name, start_offset)
                            if found_at == -1:
                                break

                            offset_line = line
                            offset_char = char
                            for c in message[:found_at]:
                                if c == "\n":
                                    offset_line += 1
                                    offset_char = 0
                                else:
                                    offset_char += 1

                            start_pos = f"{offset_line}.{offset_char}"
                            end_pos = f"{offset_line}.{offset_char + len(tool_name)}"
                            self.text_widget.tag_add("TOOL_NAME", start_pos, end_pos)
                            start_offset = found_at + len(tool_name)
                else:
                    self.text_widget.insert(tk.END, message + "\n", log_level.name)

                self.text_widget.configure(state=tk.DISABLED)

                if was_at_bottom:
                    self.text_widget.see(tk.END)

            if self.running:
                self.root.after(100, self._process_queue)

        except Exception as e:
            print(f"메시지 큐 처리 중 오류 발생: {e}", file=sys.stderr)
            if self.running:
                self.root.after(100, self._process_queue)

    def run_gui(self):
        """GUI를 실행합니다."""
        self.running = True
        try:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("oraios.serena")

            self.root = tk.Tk()
            self.root.title(self.title)
            self.root.geometry(f"{self.width}x{self.height}")

            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=0)
            self.root.rowconfigure(1, weight=1)

            dashboard_path = Path(constants.SERENA_DASHBOARD_DIR)

            try:
                image_path = dashboard_path / "serena-logs.png"
                self.logo_image = tk.PhotoImage(file=image_path)
                self.logo_label = tk.Label(self.root, image=self.logo_image)
                self.logo_label.grid(row=0, column=0, sticky="ew")
            except Exception as e:
                print(f"로고 이미지 로딩 오류: {e}", file=sys.stderr)

            frame = tk.Frame(self.root)
            frame.grid(row=1, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)

            h_scrollbar = tk.Scrollbar(frame, orient=tk.HORIZONTAL)
            h_scrollbar.grid(row=1, column=0, sticky="ew")

            v_scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
            v_scrollbar.grid(row=0, column=1, sticky="ns")

            self.text_widget = tk.Text(
                frame, wrap=tk.NONE, width=self.width, height=self.height, xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set
            )
            self.text_widget.grid(row=0, column=0, sticky="nsew")
            self.text_widget.configure(state=tk.DISABLED)

            h_scrollbar.config(command=self.text_widget.xview)
            v_scrollbar.config(command=self.text_widget.yview)

            for level, color in self.log_colors.items():
                self.text_widget.tag_configure(level.name, foreground=color)

            self.text_widget.tag_configure("TOOL_NAME", background="#ffff00")

            self.root.after(100, self._process_queue)

            if self.mode == "dashboard":
                self.root.protocol("WM_DELETE_WINDOW", lambda: self.root.iconify())
            else:
                self.root.protocol("WM_DELETE_WINDOW", self.stop)

            if self.mode == "dashboard":
                menubar = tk.Menu(self.root)
                server_menu = tk.Menu(menubar, tearoff=0)
                server_menu.add_command(label="Shutdown", command=self._shutdown_server)
                menubar.add_cascade(label="Server", menu=server_menu)
                self.root.config(menu=menubar)

            icon_16 = tk.PhotoImage(file=dashboard_path / "serena-icon-16.png")
            icon_32 = tk.PhotoImage(file=dashboard_path / "serena-icon-32.png")
            icon_48 = tk.PhotoImage(file=dashboard_path / "serena-icon-48.png")
            self.root.iconphoto(False, icon_48, icon_32, icon_16)

            self.root.mainloop()

        except Exception as e:
            print(f"GUI 스레드 오류: {e}", file=sys.stderr)
        finally:
            self.running = False

    def _shutdown_server(self) -> None:
        """서버 종료 명령을 실행합니다."""
        log.info("Serena를 종료합니다.")
        os._exit(0)


class GuiLogViewerHandler(logging.Handler):
    """
    로그 레코드를 `GuiLogViewer` 인스턴스로 보내는 로깅 핸들러.

    이 핸들러는 Python의 표준 로깅 모듈과 통합되어
    로그 항목을 GUI 로그 뷰어로 보낼 수 있습니다.
    """

    def __init__(
        self,
        log_viewer: GuiLogViewer,
        level=logging.NOTSET,
        format_string: str | None = "% (levelname) -5s % (asctime) -15s % (name)s:% (funcName)s:% (lineno)d - % (message)s",
    ):
        """
        `GuiLogViewer` 인스턴스로 핸들러를 초기화합니다.

        Args:
            log_viewer (GuiLogViewer): 로그를 표시할 `GuiLogViewer` 인스턴스.
            level: 로깅 레벨 (기본값: NOTSET, 모든 로그 캡처).
            format_string (str | None): 포맷 문자열.
        """
        super().__init__(level)
        self.log_viewer = log_viewer
        self.formatter = logging.Formatter(format_string)

        if not self.log_viewer.running:
            self.log_viewer.start()

    @classmethod
    def is_instance_registered(cls) -> bool:
        """이 핸들러의 인스턴스가 루트 로거에 등록되었는지 확인합니다."""
        for h in logging.Logger.root.handlers:
            if isinstance(h, cls):
                return True
        return False

    def emit(self, record):
        """
        로그 레코드를 `GuiLogViewer`로 보냅니다.

        Args:
            record: 보낼 로그 레코드.
        """
        try:
            msg = self.format(record)
            level_prefix = record.levelname

            if not msg.startswith(level_prefix):
                msg = f"{level_prefix}: {msg}"

            self.log_viewer.add_log(msg)

        except Exception:
            self.handleError(record)

    def close(self):
        """핸들러를 닫습니다."""
        super().close()

    def stop_viewer(self):
        """
        연결된 로그 뷰어를 명시적으로 중지합니다.
        """
        if self.log_viewer.running:
            self.log_viewer.stop()


def show_fatal_exception(e: Exception):
    """
    주어진 예외를 GUI 로그 뷰어에 표시하도록 합니다.

    기존 인스턴스 또는 새 인스턴스를 사용합니다.

    Args:
        e (Exception): 표시할 예외.
    """
    log_viewer = GuiLogViewer("error")
    exc_info = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    log_viewer.add_log(f"ERROR 치명적인 예외 발생: {e}\n{exc_info}")
    log_viewer.run_gui()