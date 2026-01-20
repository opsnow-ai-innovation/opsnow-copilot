"""비밀 정보 관리"""

from src import config


def get_secret(secret_name: str) -> str:
    """
    비밀 정보 조회 (배포 환경용)

    Args:
        secret_name: 비밀 정보 이름

    Returns:
        비밀 정보 값

    Note:
        배포 환경에서는 AWS Secrets Manager, Vault 등에서 조회
        현재는 환경변수에서 조회하는 기본 구현
    """
    # TODO: 배포 환경에서는 실제 Secret Manager 구현으로 교체
    import os
    return os.environ.get(secret_name.upper(), "")


def get_open_ai_key() -> str:
    """
    OpenAI API 키 조회

    Returns:
        OpenAI API 키
    """
    if config.IS_LOCAL_DEV:
        open_ai_key = config.OPENAI_API_KEY
    else:
        open_ai_key = get_secret("apikey")

    return open_ai_key