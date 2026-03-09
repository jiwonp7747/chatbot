"""백엔드 팩토리

create_deep_agent의 backend 파라미터로 전달하여,
서브에이전트에 파일 읽기/쓰기 도구를 자동 제공합니다.
LargeDataMiddleware와 함께 사용하여 대용량 도구 결과를 파일로 저장합니다.
"""
from deepagents.backends import FilesystemBackend

from ai.backend.database_backend import DatabaseBackend

# 모듈 싱글턴 (모든 에이전트가 동일한 가상 FS 공유)
_backend: FilesystemBackend | None = None
_db_backend: DatabaseBackend | None = None


def get_filesystem_backend(root_dir: str = "./data") -> FilesystemBackend:
    """FilesystemBackend 싱글턴 반환

    Args:
        root_dir: 가상 파일시스템 루트 디렉토리
    """
    global _backend
    if _backend is None:
        _backend = FilesystemBackend(root_dir=root_dir, virtual_mode=True)
    return _backend


def get_database_backend() -> DatabaseBackend:
    """DatabaseBackend 싱글턴 반환

    PostgreSQL large_data 테이블을 사용하는 백엔드입니다.
    """
    global _db_backend
    if _db_backend is None:
        _db_backend = DatabaseBackend()
    return _db_backend
