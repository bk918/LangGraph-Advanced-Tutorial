"""
solidlsp/ls_config.py - 언어 서버 설정

이 파일은 `solidlsp` 라이브러리에서 지원하는 프로그래밍 언어와
각 언어별 언어 서버(Language Server) 설정을 정의합니다.

주요 컴포넌트:
- FilenameMatcher: 파일 이름이 특정 패턴과 일치하는지 확인하는 유틸리티 클래스.
- Language: 지원되는 모든 프로그래밍 언어를 정의하는 열거형(Enum) 클래스.
  각 언어 멤버는 해당 언어의 소스 파일 패턴과, 사용할 언어 서버 클래스를 반환하는
  메서드를 포함합니다.
- LanguageServerConfig: 특정 언어 서버 세션을 위한 설정 값들을 담는 데이터 클래스.

아키텍처 노트:
- `Language` 열거형은 `solidlsp`의 다중 언어 지원의 핵심입니다. 새로운 언어를 추가하려면
  이 열거형에 새로운 멤버를 추가하고, `get_source_fn_matcher`와 `get_ls_class` 메서드에
  해당 언어에 대한 로직을 구현해야 합니다.
- `get_ls_class` 메서드는 동적 임포트(dynamic import)를 사용하여, 특정 언어 서버 클래스가
  필요할 때만 해당 모듈을 로드합니다. 이는 불필요한 모듈 로딩을 방지하고 시작 시간을 단축합니다.
- 팩토리 메서드 패턴(`get_ls_class`)을 사용하여, `Language` 열거형 값에 따라
  적절한 `SolidLanguageServer` 서브클래스의 인스턴스를 생성할 수 있는 유연한 구조를 제공합니다.
"""

import fnmatch
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from solidlsp import SolidLanguageServer


class FilenameMatcher:
    """
    주어진 패턴 목록을 기반으로 파일 이름이 일치하는지 확인하는 클래스.
    """

    def __init__(self, *patterns: str) -> None:
        """
        FilenameMatcher를 초기화합니다.

        Args:
            *patterns (str): `fnmatch`와 호환되는 파일 이름 패턴들.
        """
        self.patterns = patterns

    def is_relevant_filename(self, fn: str) -> bool:
        """
        주어진 파일 이름이 패턴 중 하나와 일치하는지 확인합니다.

        Args:
            fn (str): 확인할 파일 이름.

        Returns:
            bool: 일치하면 True, 그렇지 않으면 False.
        """
        for pattern in self.patterns:
            if fnmatch.fnmatch(fn, pattern):
                return True
        return False


class Language(str, Enum):
    """
    `solidlsp`에서 지원하는 프로그래밍 언어들을 정의하는 열거형.
    """

    CSHARP = "csharp"
    PYTHON = "python"
    RUST = "rust"
    JAVA = "java"
    KOTLIN = "kotlin"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUBY = "ruby"
    DART = "dart"
    CPP = "cpp"
    PHP = "php"
    R = "r"
    CLOJURE = "clojure"
    ELIXIR = "elixir"
    TERRAFORM = "terraform"
    SWIFT = "swift"
    BASH = "bash"
    ZIG = "zig"
    LUA = "lua"
    NIX = "nix"
    ERLANG = "erlang"
    AL = "al"
    # 실험적이거나 폐기된 언어 서버들
    TYPESCRIPT_VTS = "typescript_vts"
    PYTHON_JEDI = "python_jedi"
    CSHARP_OMNISHARP = "csharp_omnisharp"
    RUBY_SOLARGRAPH = "ruby_solargraph"

    @classmethod
    def iter_all(cls, include_experimental: bool = False) -> Iterable[Self]:
        """모든 언어 멤버를 반복합니다."""
        for lang in cls:
            if include_experimental or not lang.is_experimental():
                yield lang

    def is_experimental(self) -> bool:
        """언어 서버가 실험적이거나 폐기되었는지 확인합니다."""
        return self in {self.TYPESCRIPT_VTS, self.PYTHON_JEDI, self.CSHARP_OMNISHARP, self.RUBY_SOLARGRAPH}

    def __str__(self) -> str:
        return self.value

    def get_source_fn_matcher(self) -> FilenameMatcher:
        """해당 언어의 소스 파일 이름과 일치하는 `FilenameMatcher`를 반환합니다."""
        match self:
            case self.PYTHON | self.PYTHON_JEDI:
                return FilenameMatcher("*.py", "*.pyi")
            case self.JAVA:
                return FilenameMatcher("*.java")
            case self.TYPESCRIPT | self.TYPESCRIPT_VTS:
                path_patterns = [f"*.{p}{b}{s}" for p in ["c", "m", ""] for s in ["x", ""] for b in ["ts", "js"]]
                return FilenameMatcher(*path_patterns)
            case self.CSHARP | self.CSHARP_OMNISHARP:
                return FilenameMatcher("*.cs")
            case self.RUST:
                return FilenameMatcher("*.rs")
            case self.GO:
                return FilenameMatcher("*.go")
            case self.RUBY | self.RUBY_SOLARGRAPH:
                return FilenameMatcher("*.rb", "*.erb")
            case self.CPP:
                return FilenameMatcher("*.cpp", "*.h", "*.hpp", "*.c", "*.hxx", "*.cc", "*.cxx")
            case self.KOTLIN:
                return FilenameMatcher("*.kt", "*.kts")
            case self.DART:
                return FilenameMatcher("*.dart")
            case self.PHP:
                return FilenameMatcher("*.php")
            case self.R:
                return FilenameMatcher("*.R", "*.r", "*.Rmd", "*.Rnw")
            case self.CLOJURE:
                return FilenameMatcher("*.clj", "*.cljs", "*.cljc", "*.edn")
            case self.ELIXIR:
                return FilenameMatcher("*.ex", "*.exs")
            case self.TERRAFORM:
                return FilenameMatcher("*.tf", "*.tfvars", "*.tfstate")
            case self.SWIFT:
                return FilenameMatcher("*.swift")
            case self.BASH:
                return FilenameMatcher("*.sh", "*.bash")
            case self.ZIG:
                return FilenameMatcher("*.zig", "*.zon")
            case self.LUA:
                return FilenameMatcher("*.lua")
            case self.NIX:
                return FilenameMatcher("*.nix")
            case self.ERLANG:
                return FilenameMatcher("*.erl", "*.hrl", "*.escript", "*.config", "*.app", "*.app.src")
            case self.AL:
                return FilenameMatcher("*.al", "*.dal")
            case _:
                raise ValueError(f"처리되지 않은 언어: {self}")

    def get_ls_class(self) -> type["SolidLanguageServer"]:
        """해당 언어에 대한 `SolidLanguageServer` 서브클래스를 반환합니다."""
        match self:
            case self.PYTHON:
                from solidlsp.language_servers.pyright_server import PyrightServer
                return PyrightServer
            case self.PYTHON_JEDI:
                from solidlsp.language_servers.jedi_server import JediServer
                return JediServer
            case self.JAVA:
                from solidlsp.language_servers.eclipse_jdtls import EclipseJDTLS
                return EclipseJDTLS
            case self.KOTLIN:
                from solidlsp.language_servers.kotlin_language_server import KotlinLanguageServer
                return KotlinLanguageServer
            case self.RUST:
                from solidlsp.language_servers.rust_analyzer import RustAnalyzer
                return RustAnalyzer
            case self.CSHARP:
                from solidlsp.language_servers.csharp_language_server import CSharpLanguageServer
                return CSharpLanguageServer
            case self.CSHARP_OMNISHARP:
                from solidlsp.language_servers.omnisharp import OmniSharp
                return OmniSharp
            case self.TYPESCRIPT:
                from solidlsp.language_servers.typescript_language_server import TypeScriptLanguageServer
                return TypeScriptLanguageServer
            case self.TYPESCRIPT_VTS:
                from solidlsp.language_servers.vts_language_server import VtsLanguageServer
                return VtsLanguageServer
            case self.GO:
                from solidlsp.language_servers.gopls import Gopls
                return Gopls
            case self.RUBY:
                from solidlsp.language_servers.ruby_lsp import RubyLsp
                return RubyLsp
            case self.RUBY_SOLARGRAPH:
                from solidlsp.language_servers.solargraph import Solargraph
                return Solargraph
            case self.DART:
                from solidlsp.language_servers.dart_language_server import DartLanguageServer
                return DartLanguageServer
            case self.CPP:
                from solidlsp.language_servers.clangd_language_server import ClangdLanguageServer
                return ClangdLanguageServer
            case self.PHP:
                from solidlsp.language_servers.intelephense import Intelephense
                return Intelephense
            case self.CLOJURE:
                from solidlsp.language_servers.clojure_lsp import ClojureLSP
                return ClojureLSP
            case self.ELIXIR:
                from solidlsp.language_servers.elixir_tools.elixir_tools import ElixirTools
                return ElixirTools
            case self.TERRAFORM:
                from solidlsp.language_servers.terraform_ls import TerraformLS
                return TerraformLS
            case self.SWIFT:
                from solidlsp.language_servers.sourcekit_lsp import SourceKitLSP
                return SourceKitLSP
            case self.BASH:
                from solidlsp.language_servers.bash_language_server import BashLanguageServer
                return BashLanguageServer
            case self.ZIG:
                from solidlsp.language_servers.zls import ZigLanguageServer
                return ZigLanguageServer
            case self.NIX:
                from solidlsp.language_servers.nixd_ls import NixLanguageServer
                return NixLanguageServer
            case self.LUA:
                from solidlsp.language_servers.lua_ls import LuaLanguageServer
                return LuaLanguageServer
            case self.ERLANG:
                from solidlsp.language_servers.erlang_language_server import ErlangLanguageServer
                return ErlangLanguageServer
            case self.AL:
                from solidlsp.language_servers.al_language_server import ALLanguageServer
                return ALLanguageServer
            case self.R:
                from solidlsp.language_servers.r_language_server import RLanguageServer
                return RLanguageServer
            case _:
                raise ValueError(f"처리되지 않은 언어: {self}")

    @classmethod
    def from_ls_class(cls, ls_class: type["SolidLanguageServer"]) -> Self:
        """
        `SolidLanguageServer` 클래스로부터 해당하는 `Language` 열거형 값을 가져옵니다.

        Args:
            ls_class (type["SolidLanguageServer"]): 해당하는 `Language`를 찾을 클래스.

        Returns:
            Self: `Language` 열거형 값.

        Raises:
            ValueError: 지원되지 않는 언어 서버 클래스인 경우.
        """
        for enum_instance in cls:
            if enum_instance.get_ls_class() == ls_class:
                return enum_instance
        raise ValueError(f"처리되지 않은 언어 서버 클래스: {ls_class}")


@dataclass
class LanguageServerConfig:
    """
    언어 서버의 설정 파라미터를 담는 데이터 클래스.
    """

    code_language: Language
    trace_lsp_communication: bool = False
    start_independent_lsp_process: bool = True
    ignored_paths: list[str] = field(default_factory=list)
    """경로, 디렉토리 또는 glob과 유사한 패턴. .gitignore 항목과 동일한 로직으로 매칭됩니다."""

    @classmethod
    def from_dict(cls, env: dict):
        """
        딕셔너리로부터 `LanguageServerConfig` 인스턴스를 생성합니다.
        """
        import inspect

        return cls(**{k: v for k, v in env.items() if k in inspect.signature(cls).parameters})
