"""
serena/constants.py - 전역 상수 모음

이 파일은 Serena 프로젝트 전반에서 사용되는 주요 상수들을 정의합니다.
경로, 기본 설정값, 로그 형식 등 하드코딩될 수 있는 값들을
한 곳에서 관리하여 유지보수성을 높입니다.

주요 상수:
- 경로 관련: REPO_ROOT, SERENA_MANAGED_DIR_NAME, PROMPT_TEMPLATES_DIR_INTERNAL 등
  프로젝트의 주요 디렉토리 및 파일 경로를 정의합니다.
- 기본 설정값: DEFAULT_ENCODING, DEFAULT_CONTEXT, DEFAULT_MODES 등
  사용자가 별도로 설정하지 않았을 때 사용될 기본값들을 정의합니다.
- 템플릿 파일 경로: PROJECT_TEMPLATE_FILE, SERENA_CONFIG_TEMPLATE_FILE 등
  새로운 설정 파일 생성 시 사용될 템플릿 파일의 위치를 지정합니다.
- 로그 형식: SERENA_LOG_FORMAT
  프로젝트 전체에서 일관된 로그 출력 형식을 유지하기 위해 사용됩니다.

참고:
- 경로 관련 상수들은 `pathlib`을 사용하여 운영 체제에 독립적으로 생성됩니다.
- 향후 경로 관련 상수들은 `SerenaPaths` 클래스로 이전하여 더 체계적으로 관리될 예정입니다.
"""

from pathlib import Path

_repo_root_path = Path(__file__).parent.parent.parent.resolve()
_serena_pkg_path = Path(__file__).parent.resolve()

SERENA_MANAGED_DIR_NAME = ".serena"
_serena_in_home_managed_dir = Path.home() / ".serena"

SERENA_MANAGED_DIR_IN_HOME = str(_serena_in_home_managed_dir)

# TODO: 경로 관련 상수들은 SerenaPaths로 옮겨야 합니다. 여기에 더 이상 상수를 추가하지 마세요.
REPO_ROOT = str(_repo_root_path)
PROMPT_TEMPLATES_DIR_INTERNAL = str(_serena_pkg_path / "resources" / "config" / "prompt_templates")
PROMPT_TEMPLATES_DIR_IN_USER_HOME = str(_serena_in_home_managed_dir / "prompt_templates")
SERENAS_OWN_CONTEXT_YAMLS_DIR = str(_serena_pkg_path / "resources" / "config" / "contexts")
"""Serena 패키지와 함께 제공되는 컨텍스트, 즉 기본 컨텍스트입니다."""
USER_CONTEXT_YAMLS_DIR = str(_serena_in_home_managed_dir / "contexts")
"""사용자가 정의한 컨텍스트입니다. 컨텍스트 이름이 SERENAS_OWN_CONTEXT_YAMLS_DIR의 컨텍스트 이름과 일치하면 사용자 컨텍스트가 기본 컨텍스트를 재정의합니다."""
SERENAS_OWN_MODE_YAMLS_DIR = str(_serena_pkg_path / "resources" / "config" / "modes")
"""Serena 패키지와 함께 제공되는 모드, 즉 기본 모드입니다."""
USER_MODE_YAMLS_DIR = str(_serena_in_home_managed_dir / "modes")
"""사용자가 정의한 모드입니다. 모드 이름이 SERENAS_OWN_MODE_YAMLS_DIR의 모드 이름과 일치하면 사용자 모드가 기본 모드를 재정의합니다."""
INTERNAL_MODE_YAMLS_DIR = str(_serena_pkg_path / "resources" / "config" / "internal_modes")
"""내부 모드, 사용자 모드에 의해 재정의되지 않습니다."""
SERENA_DASHBOARD_DIR = str(_serena_pkg_path / "resources" / "dashboard")
SERENA_ICON_DIR = str(_serena_pkg_path / "resources" / "icons")

DEFAULT_ENCODING = "utf-8"
DEFAULT_CONTEXT = "desktop-app"
DEFAULT_MODES = ("interactive", "editing")

PROJECT_TEMPLATE_FILE = str(_serena_pkg_path / "resources" / "project.template.yml")
SERENA_CONFIG_TEMPLATE_FILE = str(_serena_pkg_path / "resources" / "serena_config.template.yml")

SERENA_LOG_FORMAT = "%(levelname)-5s %(asctime)-15s [%(threadName)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s"