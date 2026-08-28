import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://katitas.jp/"
IFRAME_PATTERN = re.compile(r"home\.katitas\.jp/properties_number")
COUNT_PATTERN = re.compile(r"(?:現在の公開物件数\s*[:：]?\s*)?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\s*件?")


def extract_count(text: str) -> str | None:
    candidates = COUNT_PATTERN.findall(text.replace("\u00a0", " "))
    if not candidates:
        return None

    # 公開物件数として現実的な4〜6桁を優先
    for value in candidates:
        n = int(value.replace(",", ""))
        if 1000 <= n <= 999999:
            return f"{n:,}"
    return None


def main() -> int:
    out = Path("artifacts")
    out.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ja-JP",
            viewport={"width": 1440, "height": 1200},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            },
        )
        page = context.new_page()

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(8_000)
            page.screenshot(path=str(out / "katitas.png"), full_page=True)

            # 1) iframe の DOM を最優先
            for frame in page.frames:
                if IFRAME_PATTERN.search(frame.url):
                    try:
                        text = frame.locator("body").inner_text(timeout=10_000)
                        (out / "iframe.txt").write_text(text, encoding="utf-8")
                        count = extract_count(text)
                        if count:
                            print(f"公開物件数: {count}件")
                            return 0
                    except Exception as e:
                        print(f"iframe DOM read failed: {e}", file=sys.stderr)

            # 2) iframe URL をブラウザの同一コンテキストで直接開く
            iframe_page = context.new_page()
            try:
                iframe_page.goto(
                    "https://home.katitas.jp/properties_number",
                    wait_until="domcontentloaded",
                    timeout=45_000,
                    referer=URL,
                )
                iframe_page.wait_for_timeout(3_000)
                iframe_page.screenshot(path=str(out / "properties_number.png"), full_page=True)
                text = iframe_page.locator("body").inner_text(timeout=10_000)
                (out / "properties_number.txt").write_text(text, encoding="utf-8")
                count = extract_count(text)
                if count:
                    print(f"公開物件数: {count}件")
                    return 0
            except Exception as e:
                print(f"direct iframe page failed: {e}", file=sys.stderr)
            finally:
                iframe_page.close()

            # 3) トップページ本文も最後に確認
            body_text = page.locator("body").inner_text(timeout=10_000)
            (out / "body.txt").write_text(body_text, encoding="utf-8")
            count = extract_count(body_text)
            if count:
                print(f"公開物件数: {count}件")
                return 0

            print("公開物件数を取得できませんでした。スクリーンショットを artifacts に保存しました。", file=sys.stderr)
            return 1
        finally:
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
