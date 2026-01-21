"""connection_manager.py 단위 테스트"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime
from connection_manager import ConnectionManager, ConnectionInfo


def create_mock_connection(username: str, connection_id: str, name: str = "") -> ConnectionInfo:
    """테스트용 ConnectionInfo 생성"""
    mock_ws = MagicMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()

    return ConnectionInfo(
        websocket=mock_ws,
        username=username,
        connection_id=connection_id,
        connected_at=datetime.now(),
        user_info={"name": name or username, "username": username}
    )


class TestConnectionManagerBasic:
    """ConnectionManager 기본 테스트"""

    def test_add_connection(self):
        """연결 추가"""
        manager = ConnectionManager()
        conn = create_mock_connection("user@test.com", "conn-1")

        old = manager.add(conn)
        assert old is None
        assert manager.get_connection_count("user@test.com") == 1

    def test_add_multiple_connections_same_user(self):
        """동일 사용자 다중 연결 (다중 허용 모드)"""
        manager = ConnectionManager(single_session_per_user=False)

        conn1 = create_mock_connection("user@test.com", "conn-1")
        conn2 = create_mock_connection("user@test.com", "conn-2")

        manager.add(conn1)
        manager.add(conn2)

        assert manager.get_connection_count("user@test.com") == 2

    def test_remove_connection(self):
        """연결 제거"""
        manager = ConnectionManager()
        conn = create_mock_connection("user@test.com", "conn-1")

        manager.add(conn)
        result = manager.remove("conn-1")

        assert result is True
        assert manager.get_connection_count("user@test.com") == 0

    def test_remove_nonexistent(self):
        """존재하지 않는 연결 제거"""
        manager = ConnectionManager()
        result = manager.remove("nonexistent")
        assert result is False

    def test_get_connection_by_id(self):
        """ID로 연결 조회"""
        manager = ConnectionManager()
        conn = create_mock_connection("user@test.com", "conn-1")
        manager.add(conn)

        found = manager.get_connection_by_id("conn-1")
        assert found is not None
        assert found.username == "user@test.com"

    def test_get_connection_by_id_nonexistent(self):
        """존재하지 않는 ID 조회"""
        manager = ConnectionManager()
        found = manager.get_connection_by_id("nonexistent")
        assert found is None


class TestSingleSessionMode:
    """단일 세션 모드 테스트"""

    def test_single_session_kicks_old_connection(self):
        """단일 세션 모드에서 기존 연결 반환"""
        manager = ConnectionManager(single_session_per_user=True)

        conn1 = create_mock_connection("user@test.com", "conn-1")
        conn2 = create_mock_connection("user@test.com", "conn-2")

        manager.add(conn1)
        old = manager.add(conn2)

        assert old is not None
        assert old.connection_id == "conn-1"
        assert manager.get_connection_count("user@test.com") == 1

    def test_single_session_property(self):
        """single_session_per_user 속성"""
        manager1 = ConnectionManager(single_session_per_user=True)
        manager2 = ConnectionManager(single_session_per_user=False)

        assert manager1.single_session_per_user is True
        assert manager2.single_session_per_user is False


class TestMultipleUsers:
    """다중 사용자 테스트"""

    def test_multiple_users(self, sample_users):
        """여러 사용자 연결"""
        manager = ConnectionManager()

        for i, user in enumerate(sample_users):
            conn = create_mock_connection(user["username"], f"conn-{i}")
            manager.add(conn)

        stats = manager.get_stats()
        assert stats["totalUsers"] == len(sample_users)
        assert stats["totalConnections"] == len(sample_users)

    def test_get_all_usernames(self, sample_users):
        """모든 사용자 이름 조회"""
        manager = ConnectionManager()

        for i, user in enumerate(sample_users):
            conn = create_mock_connection(user["username"], f"conn-{i}")
            manager.add(conn)

        usernames = manager.get_all_usernames()
        for user in sample_users:
            assert user["username"] in usernames


class TestStats:
    """통계 테스트"""

    def test_get_stats(self):
        """연결 통계"""
        manager = ConnectionManager()

        # user_a: 2개 연결
        manager.add(create_mock_connection("user_a@test.com", "conn-a1"))
        manager.add(create_mock_connection("user_a@test.com", "conn-a2"))

        # user_b: 1개 연결
        manager.add(create_mock_connection("user_b@test.com", "conn-b1"))

        stats = manager.get_stats()
        assert stats["totalUsers"] == 2
        assert stats["totalConnections"] == 3
        assert stats["users"]["user_a@test.com"] == 2
        assert stats["users"]["user_b@test.com"] == 1

    def test_get_all_connections(self):
        """모든 연결 현황"""
        manager = ConnectionManager()

        manager.add(create_mock_connection("user@test.com", "conn-1", "사용자"))

        connections = manager.get_all_connections()
        assert len(connections) == 1
        assert connections[0]["username"] == "user@test.com"
        assert connections[0]["connectionId"] == "conn-1"
        assert "connectedAt" in connections[0]


class TestBroadcast:
    """브로드캐스트 테스트"""

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """모든 연결에 브로드캐스트"""
        manager = ConnectionManager()

        conn1 = create_mock_connection("user1@test.com", "conn-1")
        conn2 = create_mock_connection("user2@test.com", "conn-2")
        manager.add(conn1)
        manager.add(conn2)

        await manager.broadcast({"type": "notification", "message": "test"})

        conn1.websocket.send_json.assert_called_once()
        conn2.websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_exclude(self):
        """특정 연결 제외 브로드캐스트"""
        manager = ConnectionManager()

        conn1 = create_mock_connection("user1@test.com", "conn-1")
        conn2 = create_mock_connection("user2@test.com", "conn-2")
        manager.add(conn1)
        manager.add(conn2)

        await manager.broadcast(
            {"type": "notification"},
            exclude_connection_id="conn-1"
        )

        conn1.websocket.send_json.assert_not_called()
        conn2.websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_user(self):
        """특정 사용자에게 전송"""
        manager = ConnectionManager()

        conn1 = create_mock_connection("user1@test.com", "conn-1")
        conn2 = create_mock_connection("user1@test.com", "conn-2")
        conn3 = create_mock_connection("user2@test.com", "conn-3")
        manager.add(conn1)
        manager.add(conn2)
        manager.add(conn3)

        await manager.send_to_user("user1@test.com", {"type": "message"})

        conn1.websocket.send_json.assert_called_once()
        conn2.websocket.send_json.assert_called_once()
        conn3.websocket.send_json.assert_not_called()
