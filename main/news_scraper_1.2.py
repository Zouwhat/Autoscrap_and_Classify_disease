import os
import asyncio
import pandas as pd
from typing import Optional
from tqdm.auto import tqdm
from playwright.async_api import async_playwright
import trafilatura
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

def extract_article_text(html: str) -> str:
    if not html:
        return ""
    try:
        txt = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True)
        if txt and txt.strip():
            return txt.strip()
    except Exception:
        pass
    try:
        soup = BeautifulSoup(html, "lxml")
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return "\n".join([t for t in paras if t])
    except Exception:
        return ""

async def fetch_html_async(page, url: str, timeout_ms: int = 30000, wait_until: str = "domcontentloaded") -> Optional[str]:
    try:
        await page.goto(url, timeout=timeout_ms, wait_until=wait_until)
        await page.wait_for_timeout(500)
        return await page.content()
    except Exception as e:
        print(f"[fetch_html] Failed for {url}: {e}")
        return None

async def scrape_all_async(df: pd.DataFrame) -> pd.DataFrame:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        try:
            for idx, row in tqdm(df.iterrows(), total=len(df)):
                url = str(row['url'])
                if row.get('skip', False):
                    df.at[idx, 'scrape_status'] = 'skipped: platform'
                    continue
                html = await fetch_html_async(page, url)
                if not html:
                    df.at[idx, 'scrape_status'] = 'error: fetch'
                    continue
                text = extract_article_text(html)
                if text:
                    df.at[idx, 'content'] = text
                    df.at[idx, 'scrape_status'] = 'ok'
                else:
                    df.at[idx, 'scrape_status'] = 'error: extract'
        finally:
            await page.close()
            await context.close()
            await browser.close()
    return df

def main(input_csv: str = "/SS5ฝึกงาน/google_alert_new/input_df.csv", out_csv: str = "prepare_data.csv"):
    if not os.path.exists(input_csv):
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv)

    # Normalize URL column
    if "url" not in df.columns:
        for cand in ["URL","Url","link","Link","href","Href"]:
            if cand in df.columns:
                df = df.rename(columns={cand: "url"})
                break
    if "url" not in df.columns:
        raise KeyError("No URL-like column found (expected one of url/link/href)")

    # Domain filtering
    df = df[~df['url'].astype(str).str.contains('ebs-ddce\\.ddc\\.moph\\.go\\.th', case=False, na=False)].copy()
    df['skip'] = df['url'].astype(str).str.contains('youtube|facebook|docs\\.google', case=False, na=False)

    # Ensure columns
    if 'scrape_status' not in df.columns:
        df['scrape_status'] = ''
    if 'content' not in df.columns:
        df['content'] = ''

    # Run scraping
    asyncio.run(scrape_all_async(df))

    # Save
    df.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"Saved to {out_csv}. Rows: {len(df)} | OK: {(df['scrape_status']=='ok').sum()} | Skipped: {(df['scrape_status']=='skipped: platform').sum()}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv", default="input_df.csv")
    parser.add_argument("--out_csv", default="prepare_data.csv")
    args = parser.parse_args()
    main(args.input_csv, args.out_csv)