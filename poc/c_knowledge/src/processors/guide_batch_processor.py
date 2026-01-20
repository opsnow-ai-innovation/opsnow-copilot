"""FAQ, Guide 문서 임베딩 및 FAISS 인덱스 생성 배치 프로세서"""

import csv
import hashlib
import json
import os
import pickle
import re
import time
from enum import Enum

import faiss
import numpy as np
import tiktoken
from openai import OpenAI
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from src.config import EMBEDDING_MODEL, OPENAI_MODEL
from src.constants import (
    BASE_PATH,
    CHUNK_MAX_CHAR_SIZE,
    CHUNK_OVERLAP_SIZE,
    CHUNK_WORD_OVERLAP,
    CHUNK_WORD_SIZE,
    EMBEDDED_VECTOR_PATH,
    EMBEDDING_DIMENSION,
    FAQ_DATA_PATH,
    MAX_EMBEDDING_TOKEN_LIMIT,
    MENU_DATA_PATH,
    RETRY_COUNT,
    USER_AGENT,
)
from src.utils.logger import Logger
from src.utils.secrets import get_open_ai_key

os.environ["USER_AGENT"] = USER_AGENT

logger = Logger().get()

client = OpenAI(api_key=get_open_ai_key())


class GuideType(str, Enum):
    """가이드 문서 타입"""

    USER_GUIDE = "user_guide"
    DEVELOPER_GUIDE = "developer_guide"
    TECH_BLOG = "tech_blog"


# 크롤링 대상 URL
OPSNOW_USER_GUIDE_URLS = [
    'https://docs.opsnow.io/opsnow-user-guide-v0.2',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/introduction/what-is-finops',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/what-is-opsnow',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/create-your-accounts',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/create-your-company',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/create-your-organization',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/connect-your-cloud-accounts',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/connect-your-cloud-accounts/how-to-connect-cloud-accounts',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/connect-your-cloud-accounts/connect-aws-accounts',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/connect-your-cloud-accounts/connect-azure-subscriptions',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/connect-your-cloud-accounts/connect-gcp-projects',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/check-connected-accounts',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/invite-members',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/modifying-your-company-and-organization',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/introduction/getting-started/add-your-cloud-accounts',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/overview',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/analytics',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/anomalies',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/anomalies/overview-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/anomalies/alerts-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/anomalies/history-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/budgets',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/budgets/budgets-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/budgets/history-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/resources',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/resources/usage',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/resources/optimization',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/resources/optimization/exclusion-from-recommendation-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/resources/optimization/right-sizing-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/resources/optimization/unused-resources-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/my-commitments',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/my-commitments/recommendations-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/my-commitments/utilization-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/my-commitments/coverage-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/my-commitments/inventory-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/autosavings',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/autosavings/registering-as-a-seller',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/policy-management',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/policy-management/report-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/policy-management/history-tab',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/menu/policy-management/settings',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/profile',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/members',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/organizations',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/cloud-accounts',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/cloud-accounts/cloud-account-type',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/cloud-accounts/cloud-account-status',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/cloud-accounts/cloud-account-data-ingest',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/cloud-accounts/aws-cloud-account',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/cloud-accounts/aws-cloud-account/aws-cloud-account-status-error',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/billing',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/security',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/authentication',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/api-key',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/terminology',
    'https://docs.opsnow.io/opsnow-user-guide-v0.2/setting/terminology/aws-create-stack',
]

OPSNOW_DEVELOPER_GUIDE_URLS = [
    "https://docs.opsnow.io/opsnow-developer-guide",
    "https://docs.opsnow.io/opsnow-developer-guide/end-point",
    "https://docs.opsnow.io/opsnow-developer-guide/end-point/platform",
    "https://docs.opsnow.io/opsnow-developer-guide/end-point/resources",
    "https://docs.opsnow.io/opsnow-developer-guide/authentication",
    "https://docs.opsnow.io/opsnow-developer-guide/errors",
    "https://docs.opsnow.io/opsnow-developer-guide/rate-limiting",
    "https://docs.opsnow.io/opsnow-developer-guide/api-reference",
    "https://docs.opsnow.io/opsnow-developer-guide/api-reference/platform",
    "https://docs.opsnow.io/opsnow-developer-guide/api-reference/cost",
    "https://docs.opsnow.io/opsnow-developer-guide/api-reference/resources",
    "https://docs.opsnow.io/opsnow-developer-guide/api-reference/auto-savings",
    "https://docs.opsnow.io/opsnow-developer-guide/api-reference/commitment",
]

OPSNOW_TECH_BLOG_URLS = [
    "https://www.opsnow.io/us-en/resources/blog",
]

GUIDE_URLS = {
    GuideType.USER_GUIDE: OPSNOW_USER_GUIDE_URLS,
    GuideType.DEVELOPER_GUIDE: OPSNOW_DEVELOPER_GUIDE_URLS,
    GuideType.TECH_BLOG: OPSNOW_TECH_BLOG_URLS,
}


class GuideBatchProcessor:
    """FAQ, Guide 문서 배치 프로세서"""

    menu_data = None

    @staticmethod
    def sanitize_text(text: str) -> str:
        """UTF-8 인코딩이 불가능한 문자 제거"""
        if not isinstance(text, str):
            return ""
        try:
            text.encode('utf-8')
            return text
        except UnicodeEncodeError:
            return text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')

    @staticmethod
    def strip_html_tags(text: str) -> str:
        """HTML 태그 제거"""
        if not isinstance(text, str):
            return ""
        no_tags = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", no_tags).strip()

    @staticmethod
    def question_answer_parser(title: str, content: str) -> str:
        """FAQ 문서의 Question과 Answer를 구분 및 명시"""
        return f"Title: {title}\nContent: {content}"

    @staticmethod
    def chrome_driver():
        """Headless Chrome 드라이버 생성"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("start-maximized")
        chrome_options.add_argument("disable-infobars")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation"]
        )
        chrome_options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        return driver

    @staticmethod
    def fetch_text_from_url(url_list: list[str], url_type: GuideType) -> list[dict]:
        """URL 리스트에서 텍스트 크롤링"""
        if not url_list:
            logger.warning(f"{url_type.value} URL 리스트가 비어있습니다.")
            return []

        driver = GuideBatchProcessor.chrome_driver()

        # User Guide용 JavaScript (breadcrumb 추출 포함)
        script = """
        var result = {content: "", breadcrumb: ""};
        var mainElement = document.querySelector('main');
        if (mainElement) {
            // Breadcrumb 추출 (nav > ol > li > a)
            var nav = mainElement.querySelector('nav[aria-label="Breadcrumb"]');
            if (nav) {
                var links = nav.querySelectorAll('a');
                var breadcrumbParts = [];
                links.forEach(function(link) {
                    breadcrumbParts.push(link.innerText.trim().toUpperCase());
                });
                result.breadcrumb = breadcrumbParts.join(' > ');
            }

            var header = mainElement.querySelector('h1');
            var headerText = header ? 'Title: ' + header.innerText.trim() + '\\n' : "";
            var firstDiv = mainElement.querySelector(':scope > div');
            if (firstDiv) {
                result.content = headerText + 'Content: ' + firstDiv.innerText.trim();
            } else {
                result.content = headerText + 'Content: ';
            }
        }
        return JSON.stringify(result);
        """

        def fetch_blog_links():
            faq_link_list = driver.find_element(By.XPATH, "//div[@role='list']")
            accordion_items = faq_link_list.find_elements(
                By.XPATH, "//div[@role='listitem']"
            )
            links = [
                item.find_element(By.TAG_NAME, "a").get_attribute("href").strip()
                for item in accordion_items
            ][2:]
            links = list(
                dict.fromkeys(
                    [
                        link
                        for link in links
                        if "us-en" in link and "/resources/blog" not in link
                    ]
                )
            )
            return links

        def parse_blog_content():
            main = driver.find_element(By.CLASS_NAME, "div-w-small")
            title = main.find_element(By.TAG_NAME, "h1").text
            content = main.find_element(By.CLASS_NAME, "w-richtext").text
            content = GuideBatchProcessor.question_answer_parser(title, content)
            content = re.sub(r"[\u200d\n]", " ", content)
            return title, content

        def remove_emojis(text):
            emoji_pattern = re.compile(
                "["
                "\U0001F300-\U0001F6FF"
                "\U0001F900-\U0001F9FF"
                "\U0001FA70-\U0001FAFF"
                "\u2600-\u26FF"
                "\u2700-\u27BF"
                "]",
                flags=re.UNICODE,
            )
            return emoji_pattern.sub("", text)

        def filtered_text(text):
            pattern = r"Last updated .*? ago"
            return re.sub(pattern, "", text).strip()

        documents = []

        try:
            for url in url_list:
                driver.get(url)
                time.sleep(10)

                retries = RETRY_COUNT
                while retries > 0:
                    try:
                        if url_type == GuideType.TECH_BLOG:
                            time.sleep(10)
                            blog_links = fetch_blog_links()
                            for link in blog_links:
                                driver.get(link)
                                WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located(
                                        (By.CLASS_NAME, "div-w-small")
                                    )
                                )
                                try:
                                    title, new_content = parse_blog_content()
                                    new_content = remove_emojis(new_content)
                                    breadcrumb = title.strip() or url_type.value
                                    documents.append(
                                        {
                                            "content": new_content,
                                            "source": link,
                                            "breadcrumb": breadcrumb,
                                            "guide_type": url_type.value,
                                        }
                                    )
                                except NoSuchElementException:
                                    logger.error(f"요소를 찾을 수 없음: {link}")
                                    continue
                        else:
                            breadcrumb = ""
                            if url_type == GuideType.USER_GUIDE:
                                raw_result = driver.execute_script(script)
                                try:
                                    parsed = json.loads(raw_result)
                                    content = parsed.get("content", "")
                                    breadcrumb = parsed.get("breadcrumb", "")
                                except (json.JSONDecodeError, TypeError):
                                    content = raw_result if isinstance(raw_result, str) else ""
                            elif url_type == GuideType.DEVELOPER_GUIDE:
                                content = driver.find_element(By.TAG_NAME, "main").text

                            if content:
                                content = filtered_text(content)
                                if not breadcrumb:
                                    breadcrumb = url_type.value
                                documents.append({
                                    "content": content,
                                    "source": url,
                                    "breadcrumb": breadcrumb,
                                    "guide_type": url_type.value,
                                })

                        retries = 0

                    except StaleElementReferenceException:
                        retries -= 1
                        logger.warning(f"Stale element: {url}, 재시도: {retries}")
                        time.sleep(3)
                    except NoSuchElementException:
                        logger.error(f"요소를 찾을 수 없음: {url}")
                        break
                    except Exception as e:
                        logger.error(f"URL 처리 중 오류 {url}: {e}")
                        break

        except Exception as e:
            logger.error(f"URL 리스트 처리 오류: {e}")
        finally:
            if driver.session_id:
                try:
                    driver.quit()
                except Exception as e:
                    logger.error(f"드라이버 종료 오류: {e}")

        return documents

    @staticmethod
    def load_menu_description_json():
        """메뉴 설명 JSON 로드"""
        menu_file = os.path.join(MENU_DATA_PATH, "1.json")
        try:
            with open(menu_file, "r", encoding="utf-8") as f:
                GuideBatchProcessor.menu_data = json.load(f)
        except FileNotFoundError:
            logger.warning(f"메뉴 파일을 찾을 수 없음: {menu_file}")
            GuideBatchProcessor.menu_data = None

    @staticmethod
    def parsing_menu_document() -> list[dict]:
        """메뉴 문서 파싱"""
        GuideBatchProcessor.load_menu_description_json()
        data = GuideBatchProcessor.menu_data

        if not data:
            return []

        try:
            name_list = list(set(menu["name"] for menu in data["menuItems"]))
            new_document = f"""Here's an explanation of the menu descriptions for OpsNow.
OpsNow menu list : {', '.join(name_list)}
"""
            menu_dict = {}
            for menu in data["menuItems"]:
                if menu["name"] not in menu_dict:
                    menu_dict[menu["name"]] = []

                details = []
                for key, value in menu.items():
                    if key != "name":
                        details.append(f"{menu['name']}_{key}: '{value}'")

                menu_dict[menu["name"]].append("\n".join(details))

            for name, details_list in menu_dict.items():
                new_document += f"\nmenu name: {name}\n"
                new_document += "\n".join(details_list) + "\n"

            return [
                {
                    "content": new_document,
                    "source": MENU_DATA_PATH,
                    "breadcrumb": "MENU",
                    "guide_type": "menu",
                }
            ]

        except Exception as e:
            logger.error(f"메뉴 문서 파싱 오류: {e}")
            return []

    @staticmethod
    def split_by_sentence_with_overlap(
        texts: list[dict],
        max_char_size: int = CHUNK_MAX_CHAR_SIZE,
        overlap_size: int = CHUNK_OVERLAP_SIZE,
        max_token: int = MAX_EMBEDDING_TOKEN_LIMIT,
    ) -> list[dict]:
        """문장 단위로 청킹 (오버랩 지원, metadata 유지)"""
        encoder = tiktoken.encoding_for_model("gpt-4")
        chunks = []

        for content in texts:
            text = content["content"]
            url = content["source"]
            breadcrumb = content.get("breadcrumb", "")
            guide_type = content.get("guide_type", "")
            sentences = [s.strip() for s in text.split(".") if s.strip()]
            start = 0

            while start < len(sentences):
                current_chunk = sentences[start : start + max_char_size]
                chunk_text = ". ".join(current_chunk) + "."

                token_count = len(encoder.encode(chunk_text))
                while token_count > max_token and len(current_chunk) > 1:
                    current_chunk.pop()
                    chunk_text = ". ".join(current_chunk) + "."
                    chunk_text = chunk_text.replace("\n", " ")
                    token_count = len(encoder.encode(chunk_text))

                chunks.append({
                    "content": chunk_text,
                    "source": url,
                    "breadcrumb": breadcrumb,
                    "guide_type": guide_type,
                })
                start += max_char_size - overlap_size

        return chunks

    @staticmethod
    def split_by_word_with_overlap(
        texts: list[dict],
        chunk_size: int = CHUNK_WORD_SIZE,
        overlap_size: int = CHUNK_WORD_OVERLAP,
    ) -> list[dict]:
        """단어 단위로 청킹 (오버랩 지원, metadata 유지)"""
        chunks = []

        for content in texts:
            text = content["content"]
            url = content["source"]
            breadcrumb = content.get("breadcrumb", "")
            guide_type = content.get("guide_type", "")
            words = text.split()
            start = 0

            while start < len(words):
                current_chunk = words[start : start + chunk_size]
                chunks.append({
                    "content": " ".join(current_chunk),
                    "source": url,
                    "breadcrumb": breadcrumb,
                    "guide_type": guide_type,
                })
                start += chunk_size - overlap_size

        return chunks

    @staticmethod
    def generate_doc_id(source: str, chunk_index: int = 0) -> str:
        """문서 ID 생성 (source + chunk_index 해시)"""
        unique_str = f"{source}:{chunk_index}"
        return hashlib.sha256(unique_str.encode()).hexdigest()[:16]

    @staticmethod
    def detect_has_steps(content: str) -> bool:
        """
        단계별 설명 포함 여부 탐지 (LLM 기반)

        Args:
            content: 분석할 텍스트

        Returns:
            True if content contains step-by-step instructions
        """
        try:
            # UTF-8 문제 방지
            clean_content = GuideBatchProcessor.sanitize_text(content[:1000])

            response = client.responses.create(
                model=OPENAI_MODEL,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a document classifier. "
                            "Determine if the given text contains step-by-step instructions or a sequential procedure. "
                            "Respond with only 'true' or 'false'."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Does this text contain step-by-step instructions?\n\n{clean_content}",
                    },
                ],
                max_output_tokens=5,
            )
            result = _extract_response_text(response).strip().lower()
            return result == "true"
        except Exception as e:
            logger.warning(f"has_steps 탐지 실패, fallback to False: {e}")
            return False


def _extract_response_text(response) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text
    text_outputs: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) == "message" and hasattr(item, "content"):
            for content_item in item.content:
                if getattr(content_item, "type", None) == "output_text":
                    text_outputs.append(content_item.text)
    return "\n".join(text_outputs) if text_outputs else ""

    @staticmethod
    def get_embedded_documents(
        documents: list[dict],
        doc_type: str = "guide",
    ) -> list[dict]:
        """
        문서 임베딩 생성 (metadata 포함)

        Args:
            documents: 문서 리스트 (content, source, breadcrumb, guide_type 포함)
            doc_type: 문서 타입 (faq | guide)

        Returns:
            임베딩된 문서 리스트 (vector, content, source, metadata 포함)
        """
        if not documents:
            return []

        embedded_documents = []
        batches = []
        current_batch = []
        current_tokens = 0

        encoder = tiktoken.encoding_for_model("gpt-4")

        # chunk_index 추가를 위한 전처리
        indexed_docs = []
        for idx, doc in enumerate(documents):
            doc_copy = doc.copy()
            doc_copy["_chunk_index"] = idx
            indexed_docs.append(doc_copy)

        for doc in indexed_docs:
            doc_token = len(encoder.encode(doc["content"]))

            if doc_token > MAX_EMBEDDING_TOKEN_LIMIT:
                logger.warning(f"토큰 제한 초과, 스킵: {doc_token} tokens")
                continue

            if current_tokens + doc_token > MAX_EMBEDDING_TOKEN_LIMIT:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(doc)
            current_tokens += doc_token

        if current_batch:
            batches.append(current_batch)

        for i, batch in enumerate(batches):
            try:
                embeddings = client.embeddings.create(
                    input=[doc["content"] for doc in batch],
                    model=EMBEDDING_MODEL,
                )
                embedded_result = [
                    {
                        "vector": embedded_doc.embedding,
                        "content": doc["content"],
                        "source": doc["source"],
                        "metadata": {
                            "doc_id": GuideBatchProcessor.generate_doc_id(
                                doc["source"], doc["_chunk_index"]
                            ),
                            "doc_type": doc_type,
                            "guide_type": doc.get("guide_type", ""),
                            "section_path": doc.get("breadcrumb", ""),
                            "has_steps": GuideBatchProcessor.detect_has_steps(
                                doc["content"]
                            ),
                        },
                    }
                    for doc, embedded_doc in zip(batch, embeddings.data)
                ]
                embedded_documents.extend(embedded_result)
                logger.info(f"배치 {i + 1}/{len(batches)} 임베딩 완료")

            except Exception as e:
                logger.error(f"배치 임베딩 오류: {e}")
                continue

        return embedded_documents

    @staticmethod
    def get_faiss_index(documents: list[dict]) -> bytes:
        """FAISS 인덱스 생성"""
        embeddings_list = [doc["vector"] for doc in documents]

        if not embeddings_list:
            raise ValueError("임베딩 리스트가 비어있습니다.")

        if not all(len(vec) == EMBEDDING_DIMENSION for vec in embeddings_list):
            raise ValueError("모든 임베딩의 차원이 동일해야 합니다.")

        embeddings = np.array(embeddings_list, dtype="float32")
        faiss.normalize_L2(embeddings)

        index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
        index.add(embeddings)

        return faiss.serialize_index(index)

    @staticmethod
    def guide_process() -> dict | None:
        """Guide 문서 처리"""
        try:
            user_guide = GuideBatchProcessor.fetch_text_from_url(
                GUIDE_URLS.get(GuideType.USER_GUIDE, []),
                GuideType.USER_GUIDE,
            )
            develop_guide = GuideBatchProcessor.fetch_text_from_url(
                GUIDE_URLS.get(GuideType.DEVELOPER_GUIDE, []),
                GuideType.DEVELOPER_GUIDE,
            )
            blog = GuideBatchProcessor.fetch_text_from_url(
                GUIDE_URLS.get(GuideType.TECH_BLOG, []),
                GuideType.TECH_BLOG,
            )
            menu_description = GuideBatchProcessor.parsing_menu_document()

            # 청킹
            chunked_documents = GuideBatchProcessor.split_by_sentence_with_overlap(
                user_guide + blog + menu_description
            )
            chunked_develop_guide = GuideBatchProcessor.split_by_word_with_overlap(
                develop_guide
            )
            all_chunks = chunked_documents + chunked_develop_guide

            if not all_chunks:
                logger.warning("Guide 문서가 없습니다.")
                return None

            # 임베딩 (doc_type="guide")
            embedded_documents = GuideBatchProcessor.get_embedded_documents(
                all_chunks, doc_type="guide"
            )
            faiss_index = GuideBatchProcessor.get_faiss_index(embedded_documents)

            return {"faiss_index": faiss_index, "data": embedded_documents}

        except Exception as e:
            logger.error(f"Guide 처리 오류: {e}")
            return None

    @staticmethod
    def faq_process() -> dict:
        """
        io_faq CSV 파일을 읽어 Title/Content 형식으로 변환하고 HTML 태그를 제거한 뒤 임베딩을 생성.
        """
        faq_documents = []

        if not os.path.isdir(FAQ_DATA_PATH):
            raise Exception(f"FAQ 디렉토리를 찾을 수 없음: {FAQ_DATA_PATH}")

        csv_files = [f for f in os.listdir(FAQ_DATA_PATH) if f.lower().endswith(".csv")]
        if not csv_files:
            raise Exception(f"CSV 파일이 없음: {FAQ_DATA_PATH}")

        for csv_file in csv_files:
            file_path = os.path.join(FAQ_DATA_PATH, csv_file)
            try:
                with open(file_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        title = row.get("name") or row.get("Name") or ""
                        raw_answer = row.get("Answer") or row.get("answer") or ""
                        answer = GuideBatchProcessor.strip_html_tags(raw_answer)

                        if not title and not answer:
                            continue

                        content = GuideBatchProcessor.question_answer_parser(
                            title, answer
                        )
                        breadcrumb = title.strip() or "FAQ"
                        faq_documents.append(
                            {
                                "content": content,
                                "source": file_path,
                                "breadcrumb": breadcrumb,
                                "guide_type": "faq",
                            }
                        )

            except Exception as e:
                logger.error(f"FAQ CSV 읽기 오류 {file_path}: {e}")
                continue

        if not faq_documents:
            raise Exception("FAQ CSV 파일에서 항목을 로드하지 못했습니다.")

        try:
            # 중복 제거
            faq_documents = [
                dict(t) for t in {frozenset(item.items()) for item in faq_documents}
            ]
            # 임베딩 (doc_type="faq")
            embedded_faq = GuideBatchProcessor.get_embedded_documents(
                faq_documents, doc_type="faq"
            )
            faiss_index = GuideBatchProcessor.get_faiss_index(embedded_faq)

            return {"faiss_index": faiss_index, "data": embedded_faq}

        except Exception as e:
            raise Exception(f"FAQ 처리 중 오류: {e}")

    @staticmethod
    def process():
        """메인 배치 프로세스"""
        logger.info("=" * 50)
        logger.info("문서 임베딩 배치 시작")
        logger.info("=" * 50)

        try:
            embedded_documents = GuideBatchProcessor.guide_process()
            embedded_faq = GuideBatchProcessor.faq_process()

            result = {}

            if embedded_documents:
                result["guide"] = embedded_documents
                logger.info(f"Guide: {len(embedded_documents['data'])}개 문서")

            if embedded_faq:
                result["faq"] = embedded_faq
                logger.info(f"FAQ: {len(embedded_faq['data'])}개 문서")

            if result:
                # 출력 디렉토리 생성
                output_dir = os.path.dirname(EMBEDDED_VECTOR_PATH)
                os.makedirs(output_dir, exist_ok=True)

                with open(EMBEDDED_VECTOR_PATH, "wb") as f:
                    pickle.dump(result, f)

                logger.info("=" * 50)
                logger.info(f"완료! 저장 위치: {EMBEDDED_VECTOR_PATH}")
                logger.info("=" * 50)
            else:
                logger.error("처리된 문서가 없습니다.")

        except Exception as e:
            logger.error(f"배치 처리 오류: {e}")


if __name__ == "__main__":
    GuideBatchProcessor.process()
