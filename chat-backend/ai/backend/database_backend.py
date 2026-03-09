"""PostgreSQL 기반 대용량 데이터 백엔드

BackendProtocol을 구현하여 large_data 테이블에 파일을 저장합니다.
서버사이드 라인 분할, 정규식 검색 등 PostgreSQL 기능을 활용합니다.
"""
import asyncio
import concurrent.futures
import fnmatch
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import text

from db.database import AsyncSessionLocal
from deepagents.backends.protocol import (
    BackendProtocol,
    EditResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult,
)

logger = logging.getLogger("chat-server")


class DatabaseBackend(BackendProtocol):
    """PostgreSQL large_data 테이블 기반 BackendProtocol 구현

    모든 파일 데이터를 DB에 저장하며, 서버사이드 라인 분할과
    정규식 검색을 지원합니다.
    """

    # ── sync → async 브릿지 ──────────────────────────────────

    def _run_async(self, coro):
        """Run async coroutine from sync context."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # 이벤트 루프 없음 — 직접 실행
            return asyncio.run(coro)
        # 이미 async 컨텍스트 — 별도 스레드에서 실행
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()

    # ── read ─────────────────────────────────────────────────

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        return self._run_async(self.aread(file_path, offset, limit))

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """서버사이드 라인 분할로 파일 내용 읽기 (cat -n 형식)"""
        async with AsyncSessionLocal() as session:
            # 서버사이드 라인 분할 + OFFSET/LIMIT
            result = await session.execute(
                text("""
                    SELECT line_number, line_text FROM (
                        SELECT unnest(string_to_array(content, E'\\n'))
                            WITH ORDINALITY AS t(line_text, line_number)
                        FROM large_data WHERE path = :path
                    ) sub
                    WHERE line_number > :offset
                      AND line_number <= :offset_plus_limit
                """),
                {
                    "path": file_path,
                    "offset": offset,
                    "offset_plus_limit": offset + limit,
                },
            )
            rows = result.fetchall()

        if not rows:
            # 파일이 존재하는지 확인
            async with AsyncSessionLocal() as session:
                exists = await session.execute(
                    text("SELECT 1 FROM large_data WHERE path = :path"),
                    {"path": file_path},
                )
                if exists.fetchone() is None:
                    return f"Error: file not found: {file_path}"
            # 파일은 있지만 해당 범위에 행이 없음
            return ""

        # cat -n 형식: "  {line_number}\t{line_text}"
        lines = []
        for line_number, line_text in rows:
            # 2000자 초과 시 잘라냄
            truncated = line_text[:2000] if line_text and len(line_text) > 2000 else (line_text or "")
            lines.append(f"  {int(line_number)}\t{truncated}")
        return "\n".join(lines)

    # ── write ────────────────────────────────────────────────

    def write(self, file_path: str, content: str) -> WriteResult:
        return self._run_async(self.awrite(file_path, content))

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        """파일 내용을 DB에 upsert (INSERT or UPDATE)"""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("""
                        INSERT INTO large_data (path, content)
                        VALUES (:path, :content)
                        ON CONFLICT (path) DO UPDATE
                            SET content = EXCLUDED.content
                    """),
                    {"path": file_path, "content": content},
                )
                await session.commit()
            return WriteResult(path=file_path)
        except Exception as e:
            logger.error(f"DatabaseBackend.awrite 에러: {e}")
            return WriteResult(error=str(e))

    # ── edit ─────────────────────────────────────────────────

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        return self._run_async(self.aedit(file_path, old_string, new_string, replace_all))

    async def aedit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        """파일 내용에서 문자열 치환 (Python에서 수행 후 UPDATE)"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT content FROM large_data WHERE path = :path"),
                {"path": file_path},
            )
            row = result.fetchone()
            if row is None:
                return EditResult(error=f"File not found: {file_path}")

            content = row[0]
            if old_string == new_string:
                return EditResult(error="old_string and new_string are identical")

            count = content.count(old_string)
            if count == 0:
                return EditResult(error=f"old_string not found in {file_path}")

            if not replace_all and count > 1:
                return EditResult(
                    error=f"old_string found {count} times in {file_path}. "
                          "Use replace_all=True to replace all occurrences."
                )

            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            await session.execute(
                text("UPDATE large_data SET content = :content WHERE path = :path"),
                {"path": file_path, "content": new_content},
            )
            await session.commit()

        return EditResult(path=file_path, occurrences=count)

    # ── grep_raw ─────────────────────────────────────────────

    def grep_raw(self, pattern: str, path: str | None = None, glob: str | None = None) -> list[GrepMatch] | str:
        return self._run_async(self.agrep_raw(pattern, path, glob))

    async def agrep_raw(self, pattern: str, path: str | None = None, glob: str | None = None) -> list[GrepMatch] | str:
        """PostgreSQL ~ 정규식 연산자로 서버사이드 검색"""
        try:
            # 기본 쿼리: 라인 분할 후 패턴 매칭
            sql = """
                SELECT sub.path, sub.line_number::int, sub.line_text
                FROM (
                    SELECT ld.path,
                           unnest(string_to_array(ld.content, E'\\n'))
                               WITH ORDINALITY AS t(line_text, line_number)
                    FROM large_data ld
                    WHERE 1=1
                      {path_filter}
                      {glob_filter}
                ) sub
                WHERE sub.line_text ~ :pattern
                ORDER BY sub.path, sub.line_number
                LIMIT 1000
            """

            params: dict = {"pattern": pattern}

            # path 필터: 해당 디렉토리 하위
            path_filter = ""
            if path:
                path_filter = "AND ld.path LIKE :path_prefix"
                prefix = path.rstrip("/") + "/%"
                params["path_prefix"] = prefix

            # glob 필터: fnmatch 패턴을 SQL LIKE로 변환
            glob_filter = ""
            if glob:
                like_pattern = self._glob_to_like(glob)
                glob_filter = "AND ld.path LIKE :glob_pattern"
                params["glob_pattern"] = like_pattern

            sql = sql.format(path_filter=path_filter, glob_filter=glob_filter)

            async with AsyncSessionLocal() as session:
                result = await session.execute(text(sql), params)
                rows = result.fetchall()

            matches: list[GrepMatch] = []
            for row_path, line_num, line_text in rows:
                matches.append(GrepMatch(
                    path=row_path,
                    line=line_num,
                    text=line_text or "",
                ))
            return matches

        except Exception as e:
            return f"Grep error: {e}"

    # ── ls_info ──────────────────────────────────────────────

    def ls_info(self, path: str) -> list[FileInfo]:
        return self._run_async(self.als_info(path))

    async def als_info(self, path: str) -> list[FileInfo]:
        """경로 접두사 기반 파일/디렉토리 목록"""
        prefix = path.rstrip("/")
        async with AsyncSessionLocal() as session:
            # 해당 경로 바로 아래의 파일과 디렉토리를 추출
            result = await session.execute(
                text("""
                    SELECT DISTINCT
                        CASE
                            WHEN position('/' in substring(path from :prefix_len)) > 0
                            THEN :prefix || '/' || split_part(substring(path from :prefix_len), '/', 1)
                            ELSE path
                        END AS entry_path,
                        CASE
                            WHEN position('/' in substring(path from :prefix_len)) > 0
                            THEN TRUE
                            ELSE FALSE
                        END AS is_directory,
                        MAX(length(content)) AS size,
                        MAX(created_at) AS modified_at
                    FROM large_data
                    WHERE path LIKE :like_prefix
                    GROUP BY entry_path, is_directory
                    ORDER BY is_directory DESC, entry_path
                """),
                {
                    "prefix": prefix,
                    "prefix_len": len(prefix) + 2,  # skip prefix + "/"
                    "like_prefix": prefix + "/%",
                },
            )
            rows = result.fetchall()

        entries: list[FileInfo] = []
        for entry_path, is_directory, size, modified_at in rows:
            info: FileInfo = {"path": entry_path, "is_dir": is_directory}
            if size is not None:
                info["size"] = size
            if modified_at is not None:
                info["modified_at"] = modified_at.isoformat() if isinstance(modified_at, datetime) else str(modified_at)
            entries.append(info)
        return entries

    # ── glob_info ────────────────────────────────────────────

    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        return self._run_async(self.aglob_info(pattern, path))

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        """glob 패턴을 SQL LIKE로 변환하여 파일 목록 조회"""
        # 패턴에 path 접두사 추가
        if not pattern.startswith("/"):
            full_pattern = path.rstrip("/") + "/" + pattern
        else:
            full_pattern = pattern

        like_pattern = self._glob_to_like(full_pattern)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT path, length(content) AS size, created_at
                    FROM large_data
                    WHERE path LIKE :pattern
                    ORDER BY path
                """),
                {"pattern": like_pattern},
            )
            rows = result.fetchall()

        entries: list[FileInfo] = []
        for row_path, size, created_at in rows:
            # fnmatch로 2차 검증 (LIKE는 ** 등 복잡한 패턴 미지원)
            if fnmatch.fnmatch(row_path, full_pattern):
                info: FileInfo = {"path": row_path, "is_dir": False}
                if size is not None:
                    info["size"] = size
                if created_at is not None:
                    info["modified_at"] = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
                entries.append(info)
        return entries

    # ── upload_files / download_files ────────────────────────

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        return self._run_async(self.aupload_files(files))

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """바이트 데이터를 UTF-8 텍스트로 디코딩하여 DB에 저장"""
        responses: list[FileUploadResponse] = []
        for path, data in files:
            try:
                content = data.decode("utf-8")
                result = await self.awrite(path, content)
                if result.error:
                    responses.append(FileUploadResponse(path=path, error="invalid_path"))
                else:
                    responses.append(FileUploadResponse(path=path))
            except Exception:
                responses.append(FileUploadResponse(path=path, error="permission_denied"))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return self._run_async(self.adownload_files(paths))

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """DB에서 파일 내용을 바이트로 반환"""
        responses: list[FileDownloadResponse] = []
        for path in paths:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text("SELECT content FROM large_data WHERE path = :path"),
                    {"path": path},
                )
                row = result.fetchone()
            if row is None:
                responses.append(FileDownloadResponse(path=path, error="file_not_found"))
            else:
                responses.append(FileDownloadResponse(path=path, content=row[0].encode("utf-8")))
        return responses

    # ── 유틸리티 ─────────────────────────────────────────────

    @staticmethod
    def _glob_to_like(pattern: str) -> str:
        """glob 패턴을 SQL LIKE 패턴으로 변환

        * → %
        ? → _
        ** → % (재귀적 매칭)
        """
        # ** 를 먼저 처리
        result = pattern.replace("**", "\x00")
        # SQL LIKE 특수문자 이스케이프
        result = result.replace("%", "\\%").replace("_", "\\_")
        # glob 와일드카드 → LIKE
        result = result.replace("*", "%").replace("?", "_")
        # ** 복원
        result = result.replace("\x00", "%")
        return result
