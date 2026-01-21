"""
ConnectionManager - 다중 사용자 연결 관리

기능:
- 사용자별 다중 연결 관리
- 단일 세션 정책 옵션
- 연결 현황 추적
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from fastapi import WebSocket


@dataclass
class ConnectionInfo:
    """연결 정보"""
    websocket: WebSocket
    username: str
    connection_id: str
    connected_at: datetime
    user_info: dict


class ConnectionManager:
    """다중 사용자 연결 관리"""

    def __init__(self, single_session_per_user: bool = False):
        """
        Args:
            single_session_per_user: True면 사용자당 단일 연결만 허용
        """
        self._single_session_per_user = single_session_per_user
        self._connections: dict[str, list[ConnectionInfo]] = defaultdict(list)
        self._connection_by_id: dict[str, ConnectionInfo] = {}

    @property
    def single_session_per_user(self) -> bool:
        return self._single_session_per_user

    def get_user_connections(self, username: str) -> list[ConnectionInfo]:
        """사용자의 모든 연결 조회"""
        return self._connections.get(username, [])

    def get_connection_count(self, username: str) -> int:
        """사용자의 연결 수"""
        return len(self._connections.get(username, []))

    def get_connection_by_id(self, connection_id: str) -> Optional[ConnectionInfo]:
        """연결 ID로 연결 정보 조회"""
        return self._connection_by_id.get(connection_id)

    def add(self, conn_info: ConnectionInfo) -> Optional[ConnectionInfo]:
        """
        연결 추가

        Returns:
            기존 연결 (single_session_per_user=True일 때 끊을 연결)
        """
        username = conn_info.username
        old_connection = None

        if self._single_session_per_user:
            existing = self._connections.get(username, [])
            if existing:
                old_connection = existing[0]
                self._connections[username] = []
                del self._connection_by_id[old_connection.connection_id]

        self._connections[username].append(conn_info)
        self._connection_by_id[conn_info.connection_id] = conn_info

        return old_connection

    def remove(self, connection_id: str) -> bool:
        """연결 제거"""
        if connection_id not in self._connection_by_id:
            return False

        conn_info = self._connection_by_id.pop(connection_id)
        username = conn_info.username

        self._connections[username] = [
            c for c in self._connections[username]
            if c.connection_id != connection_id
        ]

        if not self._connections[username]:
            del self._connections[username]

        return True

    def get_all_connections(self) -> list[dict]:
        """모든 연결 현황"""
        result = []
        for username, connections in self._connections.items():
            for conn in connections:
                result.append({
                    "username": username,
                    "connectionId": conn.connection_id,
                    "connectedAt": conn.connected_at.isoformat(),
                    "name": conn.user_info.get("name", "")
                })
        return result

    def get_stats(self) -> dict:
        """연결 통계"""
        total_connections = sum(len(conns) for conns in self._connections.values())
        return {
            "totalUsers": len(self._connections),
            "totalConnections": total_connections,
            "users": {
                username: len(conns)
                for username, conns in self._connections.items()
            }
        }

    def get_all_usernames(self) -> list[str]:
        """모든 연결된 사용자 이름 목록"""
        return list(self._connections.keys())

    async def broadcast(self, message: dict, exclude_connection_id: str = None):
        """모든 연결에 메시지 브로드캐스트"""
        for conn_info in self._connection_by_id.values():
            if exclude_connection_id and conn_info.connection_id == exclude_connection_id:
                continue
            try:
                await conn_info.websocket.send_json(message)
            except Exception:
                pass

    async def send_to_user(self, username: str, message: dict):
        """특정 사용자의 모든 연결에 메시지 전송"""
        connections = self._connections.get(username, [])
        for conn_info in connections:
            try:
                await conn_info.websocket.send_json(message)
            except Exception:
                pass