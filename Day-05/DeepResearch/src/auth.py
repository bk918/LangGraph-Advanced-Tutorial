import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from langgraph_sdk import Auth
from langgraph_sdk.auth.types import StudioUser


# 사용자 데이터 모델
@dataclass
class User:
    """사용자 정보 데이터 클래스."""

    id: str
    email: str
    name: str
    role: str = "user"
    created_at: datetime = None
    is_active: bool = True

    def __post_init__(self):
        """사용자 정보 초기화."""
        if self.created_at is None:
            self.created_at = datetime.now(UTC)


# 간단한 인메모리 사용자 저장소 (실제로는 데이터베이스 사용)
class UserStore:
    """사용자 정보를 관리하는 간단한 저장소."""

    def __init__(self):
        self.users: dict[str, User] = {}
        self._load_users()

    def _load_users(self):
        """환경 변수나 파일에서 사용자 정보 로드"""
        # 환경 변수에서 사용자 정보 로드
        users_data = os.environ.get("DEFAULT_USERS", "[]")
        try:
            users_list = json.loads(users_data)
            for user_data in users_list:
                user = User(**user_data)
                self.users[user.id] = user
        except (json.JSONDecodeError, TypeError):
            pass

        # 기본 관리자 사용자 생성 (환경 변수가 없을 경우)
        if not self.users:
            admin_user = User(
                id="admin", email="admin@example.com", name="Administrator", role="admin"
            )
            self.users[admin_user.id] = admin_user

    def get_user(self, user_id: str) -> User | None:
        """사용자 ID로 사용자 정보 조회."""
        return self.users.get(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        """이메일로 사용자 정보 조회."""
        return next((user for user in self.users.values() if user.email == email), None)

    def authenticate(self, email: str, password: str) -> User | None:
        """이메일과 비밀번호로 사용자 인증."""
        user = self.get_user_by_email(email)
        if user and user.is_active and self._verify_password(password, user.id):
            return user
        return None

    def _verify_password(self, password: str, user_id: str) -> bool:
        """비밀번호 검증 (간단한 해시 비교)."""
        # TODO: 실제 구현에서는 bcrypt나 argon2 같은 보안 해시 사용
        hashed = hashlib.sha256(f"{password}:{user_id}".encode()).hexdigest()
        expected = os.environ.get(f"PASSWORD_HASH_{user_id.upper()}", "")
        return hashed == expected

    def create_token(self, user: User) -> str:
        """사용자를 위한 JWT 토큰 생성."""
        secret = os.environ.get("JWT_SECRET", "your-secret-key-change-in-production")
        expiration = datetime.now(UTC) + timedelta(hours=24)

        payload = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "exp": expiration,
            "iat": datetime.now(UTC),
        }

        return jwt.encode(payload, secret, algorithm="HS256")

    def verify_token(self, token: str) -> User | None:
        """JWT 토큰 검증."""
        try:
            secret = os.environ.get("JWT_SECRET", "your-secret-key-change-in-production")
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            user_id = payload.get("user_id")

            if user_id:
                return self.get_user(user_id)
        except jwt.ExpiredSignatureError:
            pass  # 토큰 만료
        except jwt.InvalidTokenError:
            pass  # 유효하지 않은 토큰

        return None


# 전역 사용자 저장소 인스턴스
user_store = UserStore()

# "Auth" 객체는 LangGraph가 인증 기능을 표시하는 데 사용할 컨테이너입니다
auth = Auth()


# =============================================================================
# SUPABASE 없이 AUTH 구현 가이드
# =============================================================================
"""
이 파일은 Supabase 없이 LangGraph에서 Auth를 구현하는 방법을 보여줍니다.

## 지원하는 인증 방식:

### 1. JWT 토큰 기반 인증 (기본)
- 사용자명/비밀번호로 로그인하여 JWT 토큰 획득
- Authorization: Bearer <token> 헤더로 요청
- 토큰 만료 시간: 24시간 (환경 변수로 조정 가능)

### 2. API 키 기반 인증 (선택적)
- API_KEY 환경 변수로 설정
- Authorization: Bearer <api_key> 헤더로 요청
- 시스템 간 통신에 유용

## 환경 변수 설정:

### 필수 설정:
JWT_SECRET=your-secret-key-change-in-production

### 사용자 설정:
DEFAULT_USERS=[{"id": "user1", "email": "user@example.com", "name": "User", "role": "user"}]

### 비밀번호 해시 설정:
PASSWORD_HASH_USER1=해시된비밀번호
PASSWORD_HASH_ADMIN=해시된비밀번호

## 보안 고려사항:

1. JWT_SECRET는 강력한 랜덤 문자열로 설정하세요
2. 프로덕션에서는 bcrypt나 argon2 같은 보안 해시 함수를 사용하세요
3. UserStore는 실제로는 데이터베이스로 교체하세요
4. HTTPS를 사용하고 민감한 정보를 환경 변수로 관리하세요

## LangGraph Auth 타입:

### 지원하는 리소스 타입:
- threads: 스레드 생성/읽기/수정/삭제/검색
- assistants: 어시스턴트 생성/읽기/수정/삭제/검색
- store: 키-값 저장소 접근
- runs: 실행 관련 작업
- crons: 예약 작업

### 권한 부여 전략:
- 소유자 기반: 사용자가 소유한 리소스만 접근
- 역할 기반: admin, user, api 역할별 권한
- 태그 기반: 특정 태그가 있는 리소스만 접근

## 확장 가능성:

1. OAuth2/OpenID Connect 연동
2. LDAP/Active Directory 연동
3. SAML 인증
4. 다중 요소 인증 (MFA)
5. 세션 기반 인증
6. 데이터베이스 연동
"""


# `authenticate` 데코레이터는 LangGraph가 모든 요청에 대해 미들웨어로 이 함수를 호출하도록 지시합니다
# 이 함수는 요청이 허용되는지 여부를 결정합니다
@auth.authenticate
async def authenticate_user(authorization: str | None) -> Auth.types.MinimalUserDict:
    """JWT 토큰을 검증하고 사용자 정보를 반환합니다."""
    # 인가 헤더가 있는지 확인합니다
    if not authorization:
        raise Auth.exceptions.HTTPException(status_code=401, detail="인가 헤더가 없습니다")

    # 인가 헤더를 파싱합니다
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise Auth.exceptions.HTTPException(
                status_code=401, detail="유효하지 않은 인가 헤더 형식입니다"
            )
    except (ValueError, AssertionError):
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="유효하지 않은 인가 헤더 형식입니다"
        )

    # 1. 먼저 API 키 인증을 시도합니다
    if check_api_key(authorization):
        return {
            "identity": "api-user",
            "email": "api@example.com",
            "name": "API User",
            "role": "api",
            "is_active": True,
        }

    # 2. API 키가 아닌 경우 JWT 토큰으로 인증을 시도합니다
    user = user_store.verify_token(token)
    if not user:
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="유효하지 않은 토큰이거나 토큰이 만료되었습니다"
        )

    # 유효한 사용자 정보를 반환합니다
    return {
        "identity": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active,
    }


# API 키 기반 인증 (선택적) - JWT 인증과 통합
# 하나의 Auth 핸들러에서 JWT와 API 키를 모두 처리합니다
async def check_api_key(authorization: str | None) -> bool:
    """API 키로 인증을 시도합니다."""
    if not authorization:
        return False

    api_key = authorization.replace("Bearer ", "")
    expected_api_key = os.environ.get("API_KEY")

    return expected_api_key and api_key == expected_api_key


# 기본 로그인 엔드포인트 (실제 구현에서는 별도 API로 분리)
async def login_user(email: str, password: str) -> str | None:
    """사용자 로그인 함수."""
    user = user_store.authenticate(email, password)
    if user:
        return user_store.create_token(user)
    return None


@auth.on.threads.create
@auth.on.threads.create_run
async def on_thread_create(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.create.value,
):
    """스레드 생성 시 소유자 정보를 추가하고 권한을 확인합니다.

    이 핸들러는 새 스레드 생성 시 실행되며 다음과 같은 작업을 수행합니다:
    1. 소유권 추적을 위해 생성 중인 스레드에 메타데이터를 설정합니다
    2. 생성자만 접근할 수 있도록 하는 필터를 반환합니다
    3. 역할 기반 권한 확인을 수행합니다
    """
    if isinstance(ctx.user, StudioUser):
        return

    # 역할 기반 권한 확인
    user_role = getattr(ctx.user, "role", "user")
    if user_role not in ["admin", "user"]:
        raise Auth.exceptions.HTTPException(status_code=403, detail="스레드 생성 권한이 없습니다")

    # 생성 중인 스레드에 소유자 메타데이터를 추가합니다
    # 이 메타데이터는 스레드와 함께 저장되어 지속됩니다
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity
    metadata["created_by"] = ctx.user.identity
    metadata["created_at"] = datetime.now(UTC).isoformat()

    # 생성자만 접근할 수 있도록 필터 반환
    return {"owner": ctx.user.identity}


@auth.on.threads.read
@auth.on.threads.delete
@auth.on.threads.update
@auth.on.threads.search
async def on_thread_access(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.read.value,
):
    """사용자가 자신의 스레드만 접근할 수 있도록 합니다.

    이 핸들러는 읽기/삭제/수정/검색 작업 시 실행됩니다.
    역할 기반 권한 확인을 수행하고, 관리자는 모든 스레드에 접근할 수 있습니다.
    """

    if isinstance(ctx.user, StudioUser):
        return

    user_role = getattr(ctx.user, "role", "user")

    # 관리자는 모든 스레드에 접근 가능
    if user_role == "admin":
        return

    # 일반 사용자는 자신의 스레드만 접근 가능
    if user_role == "user":
        return {"owner": ctx.user.identity}

    # API 사용자는 특정 태그가 있는 스레드만 접근 가능
    if user_role == "api":
        return {"tags": "api-accessible"}

    # 알 수 없는 역할은 접근 거부
    raise Auth.exceptions.HTTPException(status_code=403, detail="스레드 접근 권한이 없습니다")


@auth.on.assistants.create
async def on_assistants_create(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.assistants.create.value,
):
    """어시스턴트 생성 시 소유자 정보를 추가하고 권한을 확인합니다."""

    if isinstance(ctx.user, StudioUser):
        return

    # 역할 기반 권한 확인
    user_role = getattr(ctx.user, "role", "user")
    if user_role not in ["admin", "user"]:
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="어시스턴트 생성 권한이 없습니다"
        )

    # 생성 중인 어시스턴트에 소유자 메타데이터를 추가합니다
    # 이 메타데이터는 어시스턴트와 함께 저장되어 지속됩니다
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity
    metadata["created_by"] = ctx.user.identity
    metadata["created_at"] = datetime.now(UTC).isoformat()

    # 생성자만 접근할 수 있도록 필터 반환
    return {"owner": ctx.user.identity}


@auth.on.assistants.read
@auth.on.assistants.delete
@auth.on.assistants.update
@auth.on.assistants.search
async def on_assistants_access(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.assistants.read.value,
):
    """사용자가 자신의 어시스턴트만 접근할 수 있도록 합니다.

    이 핸들러는 읽기/삭제/수정/검색 작업 시 실행됩니다.
    역할 기반 권한 확인을 수행하고, 관리자는 모든 어시스턴트에 접근할 수 있습니다.
    """

    if isinstance(ctx.user, StudioUser):
        return

    user_role = getattr(ctx.user, "role", "user")

    # 관리자는 모든 어시스턴트에 접근 가능
    if user_role == "admin":
        return

    # 일반 사용자는 자신의 어시스턴트만 접근 가능
    if user_role == "user":
        return {"owner": ctx.user.identity}

    # API 사용자는 특정 태그가 있는 어시스턴트만 접근 가능
    if user_role == "api":
        return {"tags": "api-accessible"}

    # 알 수 없는 역할은 접근 거부
    raise Auth.exceptions.HTTPException(status_code=403, detail="어시스턴트 접근 권한이 없습니다")


@auth.on.store()
async def authorize_store(ctx: Auth.types.AuthContext, value: dict):
    """저장소 접근 권한을 확인합니다."""

    if isinstance(ctx.user, StudioUser):
        return

    # 각 저장소 항목의 "namespace" 필드는 항목의 디렉토리라고 생각할 수 있는 튜플입니다.
    namespace: tuple = value["namespace"]

    # 역할 기반 권한 확인
    user_role = getattr(ctx.user, "role", "user")

    # 관리자는 모든 저장소에 접근 가능
    if user_role == "admin":
        return

    # 일반 사용자는 자신의 네임스페이스만 접근 가능
    if user_role == "user":
        assert namespace[0] == ctx.user.identity, "저장소 접근 권한이 없습니다"

    # API 사용자는 특정 네임스페이스만 접근 가능
    elif user_role == "api":
        assert namespace[0] == "api", "API 저장소 접근 권한이 없습니다"

    else:
        # 알 수 없는 역할은 접근 거부
        raise Auth.exceptions.HTTPException(status_code=403, detail="저장소 접근 권한이 없습니다")
