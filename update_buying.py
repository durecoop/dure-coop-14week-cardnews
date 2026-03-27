"""
ecoop.or.kr 구매수량 자동 업데이트 스크립트
매시 50분에 실행 (Windows Task Scheduler)
이미지 파일명을 고유 키로 사용하여 상품 매칭
"""
import re
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
HTML_PATH = BASE_DIR / "weekly_deal.html"
LOG_PATH = BASE_DIR / "update_buying.log"
URL = "https://ecoop.or.kr/DureShop/recommend.do"

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)
log = logging.getLogger(__name__)


def fetch_buying_counts() -> dict[str, int]:
    """ecoop 페이지에서 {이미지stem: 구매수량} 딕셔너리 반환"""
    resp = requests.get(URL, timeout=20, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    counts: dict[str, int] = {}

    for img_tag in soup.find_all("img", src=re.compile(r"GoodsImage/")):
        src = img_tag.get("src", "")
        stem_match = re.search(r"/(\w+C)\.\w+$", src)
        if not stem_match:
            continue
        stem = stem_match.group(1)

        container = img_tag.find_parent("li") or img_tag.find_parent("div")
        if not container:
            counts[stem] = 0
            continue

        text = container.get_text()
        buy_match = re.search(r"(\d+)\s*개", text)
        counts[stem] = int(buy_match.group(1)) if buy_match else 0

    return counts


def update_html(counts: dict[str, int]) -> int:
    """weekly_deal.html의 buying:N 값을 업데이트. 변경 건수 반환"""
    content = HTML_PATH.read_text(encoding="utf-8")
    lines = content.split("\n")

    updated = 0
    current_stem = None

    for i, line in enumerate(lines):
        img_match = re.search(r"img:IMG\+'(\w+C)\.\w+'", line)
        if img_match:
            current_stem = img_match.group(1)

        if current_stem and current_stem in counts:
            buy_match = re.search(r"buying:(\d+)", line)
            if buy_match:
                old_val = int(buy_match.group(1))
                new_val = counts[current_stem]
                if old_val != new_val:
                    lines[i] = re.sub(
                        r"buying:\d+",
                        f"buying:{new_val}",
                        line,
                        count=1,
                    )
                    updated += 1
                current_stem = None

    if updated > 0:
        HTML_PATH.write_text("\n".join(lines), encoding="utf-8")

    return updated


def main():
    log.info("=== 업데이트 시작 ===")
    try:
        counts = fetch_buying_counts()
        if len(counts) < 10:
            log.warning(f"상품 수가 너무 적음: {len(counts)}개. 업데이트 중단.")
            return

        log.info(f"ecoop에서 {len(counts)}개 상품 구매수량 수집 완료")

        updated = update_html(counts)
        log.info(f"weekly_deal.html 업데이트 완료: {updated}건 변경")

    except requests.exceptions.RequestException as e:
        log.error(f"네트워크 오류: {e}")
    except FileNotFoundError:
        log.error(f"파일 없음: {HTML_PATH}")
    except Exception as e:
        log.error(f"예상치 못한 오류: {e}", exc_info=True)


if __name__ == "__main__":
    main()
