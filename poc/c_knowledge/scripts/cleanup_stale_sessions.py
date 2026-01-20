"""
24시간 이상 미사용 세션 정리 배치

실행: python scripts/cleanup_stale_sessions.py
크론: 0 3 * * * cd /path/to/project && python scripts/cleanup_stale_sessions.py
"""

import asyncio
import logging
import os
import sys

import redis.asyncio as redis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import REDIS_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def cleanup_stale_sessions(redis_client: redis.Redis) -> dict:
    """
    24시간 이상 미사용 세션 삭제.

    TTL이 만료되었거나 0 이하인 세션의 모든 관련 키를 삭제.

    Returns:
        dict: 삭제 통계 {"sessions": 삭제된 세션 수, "keys": 삭제된 키 수}
    """
    cursor = 0
    deleted_sessions = 0
    deleted_keys = 0
    scanned_keys = 0

    logger.info("세션 정리 시작...")

    while True:
        # chat:*:short 패턴으로 스캔
        cursor, keys = await redis_client.scan(
            cursor=cursor,
            match="chat:*:short",
            count=100,
        )
        scanned_keys += len(keys)

        for key in keys:
            ttl = await redis_client.ttl(key)

            # TTL이 만료됨 (-2) 또는 TTL 없음 (-1) 또는 곧 만료 (0)
            if ttl <= 0:
                # chat:{session}:short → chat:{session}
                prefix = key.rsplit(":short", 1)[0]

                keys_to_delete = [
                    f"{prefix}:short",
                    f"{prefix}:memory",
                    f"{prefix}:entities",
                ]

                # 실제 존재하는 키만 삭제
                deleted = await redis_client.delete(*keys_to_delete)
                deleted_keys += deleted
                deleted_sessions += 1

                logger.debug(f"삭제됨: {prefix} ({deleted}개 키)")

        if cursor == 0:
            break

    return {
        "sessions": deleted_sessions,
        "keys": deleted_keys,
        "scanned": scanned_keys,
    }


async def get_session_stats(redis_client: redis.Redis) -> dict:
    """현재 세션 통계 조회."""
    cursor = 0
    total_sessions = 0
    expiring_soon = 0  # 1시간 이내 만료
    healthy = 0

    while True:
        cursor, keys = await redis_client.scan(
            cursor=cursor,
            match="chat:*:short",
            count=100,
        )

        for key in keys:
            total_sessions += 1
            ttl = await redis_client.ttl(key)

            if ttl <= 0:
                pass  # 이미 만료됨
            elif ttl <= 3600:  # 1시간 이내
                expiring_soon += 1
            else:
                healthy += 1

        if cursor == 0:
            break

    return {
        "total": total_sessions,
        "healthy": healthy,
        "expiring_soon": expiring_soon,
    }


async def main():
    """메인 실행 함수."""
    logger.info("=" * 50)
    logger.info("세션 정리 배치 시작")
    logger.info("=" * 50)

    redis_client = None

    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info(f"Redis 연결 완료: {REDIS_URL}")

        # 정리 전 통계
        before_stats = await get_session_stats(redis_client)
        logger.info(f"정리 전 세션: {before_stats['total']}개")
        logger.info(f"  - 정상: {before_stats['healthy']}개")
        logger.info(f"  - 1시간 내 만료 예정: {before_stats['expiring_soon']}개")

        # 정리 실행
        result = await cleanup_stale_sessions(redis_client)

        # 정리 후 통계
        after_stats = await get_session_stats(redis_client)

        logger.info("-" * 50)
        logger.info(f"스캔된 세션: {result['scanned']}개")
        logger.info(f"삭제된 세션: {result['sessions']}개")
        logger.info(f"삭제된 키: {result['keys']}개")
        logger.info(f"남은 세션: {after_stats['total']}개")
        logger.info("=" * 50)
        logger.info("세션 정리 완료")
        logger.info("=" * 50)

    except redis.ConnectionError as e:
        logger.error(f"Redis 연결 실패: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"배치 실행 오류: {e}")
        sys.exit(1)
    finally:
        if redis_client:
            await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
