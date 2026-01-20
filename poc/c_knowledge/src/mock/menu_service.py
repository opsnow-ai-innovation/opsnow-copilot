"""
Mock 메뉴 API 서비스

TODO: 합칠 때 제거 - 실제 서비스에서는 메뉴 API로 대체
"""

from dataclasses import dataclass

from src.mock.menus import MOCK_MENU_DATA


@dataclass
class MenuInfo:
    """메뉴 정보"""

    menu_id: str
    menu_url: str
    menu_nm: str
    menu_desc: str
    parent_menu_nm: str | None = None


class MenuService:
    """
    TODO: 합칠 때 제거 - Mock 메뉴 API 서비스

    실제 서비스에서는 메뉴 API 호출로 대체
    """

    def __init__(self, lang: str = "ko"):
        self.lang = lang
        self._menus: list[MenuInfo] = []
        self._load_menus()

    def _load_menus(self):
        """Mock 메뉴 데이터 로드 (flat 구조로 변환)"""
        menu_list = MOCK_MENU_DATA.get("data", {}).get("list", [])

        for menu in menu_list:
            self._add_menu(menu)

            # 서브메뉴도 추가
            sub_menus = menu.get("subMenuList") or []
            parent_nm = menu.get("menuNm", {}).get(self.lang, "")

            for sub in sub_menus:
                self._add_menu(sub, parent_nm)

    def _add_menu(self, menu: dict, parent_nm: str | None = None):
        """메뉴 정보 추가"""
        self._menus.append(
            MenuInfo(
                menu_id=menu.get("menuId", ""),
                menu_url=menu.get("menuUrl", ""),
                menu_nm=menu.get("menuNm", {}).get(self.lang, ""),
                menu_desc=menu.get("menuDesc", {}).get(self.lang, ""),
                parent_menu_nm=parent_nm,
            )
        )

    async def get_user_menus(self, user_id: str) -> list[MenuInfo]:
        """
        TODO: 합칠 때 제거 - 유저별 접근 가능 메뉴 조회

        실제 서비스:
            response = await http_client.get(f"/api/menus?userId={user_id}")
            return parse_menu_response(response)

        Mock:
            모든 유저가 동일한 메뉴 접근 가능
        """
        # Mock: 모든 유저가 전체 메뉴 접근 가능
        return self._menus

    async def search_menus(
        self,
        query: str,
        user_id: str,
        top_k: int = 3,
    ) -> list[MenuInfo]:
        """
        쿼리와 관련된 메뉴 검색 (Fallback용)

        Args:
            query: 사용자 질문
            user_id: 유저 ID (권한 체크용)
            top_k: 반환할 메뉴 수

        Returns:
            관련 메뉴 리스트
        """
        user_menus = await self.get_user_menus(user_id)
        query_lower = query.lower()

        scored_menus: list[tuple[float, MenuInfo]] = []

        for menu in user_menus:
            score = 0.0

            # 메뉴명 매칭
            menu_nm_lower = menu.menu_nm.lower()
            if query_lower in menu_nm_lower or menu_nm_lower in query_lower:
                score += 1.0

            # menuDesc 매칭 (나중에 채워지면 사용)
            if menu.menu_desc:
                menu_desc_lower = menu.menu_desc.lower()
                if query_lower in menu_desc_lower:
                    score += 0.8

                # 키워드 부분 매칭
                query_words = query_lower.split()
                for word in query_words:
                    if len(word) > 1 and word in menu_desc_lower:
                        score += 0.3

            # 키워드 기반 매칭 (메뉴명)
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 1 and word in menu_nm_lower:
                    score += 0.5

            if score > 0:
                scored_menus.append((score, menu))

        # 점수순 정렬
        scored_menus.sort(key=lambda x: x[0], reverse=True)

        return [menu for _, menu in scored_menus[:top_k]]

    def format_menu_links(self, menus: list[MenuInfo]) -> str:
        """메뉴 링크 포맷팅"""
        if not menus:
            return ""

        lines = ["관련 메뉴를 확인해보세요:"]
        for menu in menus:
            if menu.parent_menu_nm:
                lines.append(f"  - {menu.parent_menu_nm} > {menu.menu_nm}: {menu.menu_url}")
            else:
                lines.append(f"  - {menu.menu_nm}: {menu.menu_url}")

        return "\n".join(lines)
