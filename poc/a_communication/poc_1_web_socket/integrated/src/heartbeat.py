"""
HeartbeatManager - Ping/Pong 기반 연결 상태 관리

기능:
- 주기적 ping 전송
- pong 응답 타임아웃 감지
- 무응답 시 연결 종료
"""

import asyncio
from fastapi import WebSocket


class HeartbeatManager:
    """Ping/Pong 기반 연결 상태 관리"""

    def __init__(
        self,
        websocket: WebSocket,
        username: str,
        connection_id: str,
        interval: int = 30,
        pong_timeout: int = 10,
        max_missed_pongs: int = 3
    ):
        """
        Args:
            websocket: WebSocket 연결
            username: 사용자 이름
            connection_id: 연결 ID
            interval: ping 전송 간격 (초)
            pong_timeout: pong 응답 대기 시간 (초)
            max_missed_pongs: 최대 허용 무응답 횟수
        """
        self.websocket = websocket
        self.username = username
        self.connection_id = connection_id
        self.interval = interval
        self.pong_timeout = pong_timeout
        self.max_missed_pongs = max_missed_pongs

        self.pong_received = asyncio.Event()
        self.missed_pongs = 0
        self.should_disconnect = False
        self._task: asyncio.Task = None

    async def start(self):
        """Heartbeat 루프 시작"""
        self._task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        """Heartbeat 루프 중지"""
        self.should_disconnect = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self):
        """Heartbeat 루프"""
        try:
            while not self.should_disconnect:
                await asyncio.sleep(self.interval)

                if self.should_disconnect:
                    break

                # ping 전송
                self.pong_received.clear()
                await self.websocket.send_json({
                    "type": "ping",
                    "missedPongs": self.missed_pongs,
                    "maxMissedPongs": self.max_missed_pongs
                })

                # pong 대기
                try:
                    await asyncio.wait_for(
                        self.pong_received.wait(),
                        timeout=self.pong_timeout
                    )
                    self.missed_pongs = 0

                except asyncio.TimeoutError:
                    self.missed_pongs += 1

                    if self.missed_pongs >= self.max_missed_pongs:
                        self.should_disconnect = True
                        await self.websocket.close(
                            code=4003,
                            reason=f"Pong timeout ({self.max_missed_pongs} missed)"
                        )
                        break

        except Exception:
            pass

    def on_pong_received(self):
        """pong 메시지 수신 시 호출"""
        self.pong_received.set()
