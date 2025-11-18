# Cell 1: config + helpers
import os, json, imaplib, email
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode, unquote
from datetime import datetime, timedelta
from pathlib import Path

# ---- CONFIG ----
IMAP_HOST = "imap.gmail.com"
LOOKBACK_DAYS = 60   # how far back to fetch
MAILBOX = "INBOX"    # or '[Gmail]/All Mail'
CREDS_FILE = "google_pass.gitignore"
SINCE_STR = (datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")

ALERT_FROM = 'googlealerts-noreply@google.com'  # typical sender

EXCLUDE_DOMAINS = {
    "accounts.google.com", "support.google.com", "www.google.com/alerts"
}

def load_or_create_creds(file_path: str = CREDS_FILE):
    """
    Load Gmail credentials from a local JSON file.
    If the file doesn't exist or is incomplete, prompt once and write it.
    """
    email_addr = ""
    app_pass = ""

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            email_addr = (data.get("email") or "").strip()
            app_pass   = (data.get("app_password") or "").strip()
        except Exception:
            # If file is malformed, fall through to prompt-and-rewrite
            pass

    if not email_addr or not app_pass:
        from getpass import getpass
        email_addr = input("Gmail address: ").strip()
        app_pass = getpass("App password (or Gmail password if no 2FA): ").strip()

        payload = {"email": email_addr, "app_password": app_pass}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # Best-effort to lock down permissions (works on Unix; harmless on Windows)
        try:
            os.chmod(file_path, 0o600)
        except Exception:
            pass

    return email_addr, app_pass

EMAIL_ADDR, EMAIL_PASS = load_or_create_creds()

def add_links_first_rows(links, csv_path="raw_data.csv", **meta) -> pd.DataFrame:
    now = datetime.utcnow().isoformat(timespec="seconds")
    df_new = pd.DataFrame([{"link": link, "added_at_utc": now, **meta} for link in links])

    if Path(csv_path).exists():
        df_old = pd.read_csv(csv_path)
        for col in ["link", "added_at_utc"]:
            if col not in df_old.columns:
                df_old.insert(0 if col == "link" else 1, col, pd.NA)
        out = pd.concat([df_new, df_old], ignore_index=True)
        out = out.drop_duplicates(subset=["link"], keep="first").reset_index(drop=True)
        first_cols = ["link", "added_at_utc"]
        other_cols = [c for c in out.columns if c not in first_cols]
        out = out[first_cols + other_cols]
    else:
        out = df_new

    out.to_csv(csv_path, index=False, encoding="utf-8")
    return out

# Cell 2
def unwrap_google_redirect(href: str) -> str:
    """
    Google Alerts often wrap links like https://www.google.com/url?url=<real>&...
    This returns the underlying real URL when present.
    """
    try:
        p = urlparse(href)
        if p.netloc == "www.google.com" and p.path == "/url":
            q = parse_qs(p.query)
            target = q.get("url") or q.get("q")
            if target:
                return unquote(target[0])
        return href
    except Exception:
        return href

def strip_tracking_params(href: str) -> str:
    """Remove common UTMs, keep stable URL."""
    p = urlparse(href)
    q = parse_qs(p.query)
    for k in list(q.keys()):
        if k.lower().startswith("utm_") or k.lower() in {"ved", "usg", "ei"}:
            q.pop(k, None)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode({k:v[0] for k,v in q.items()}), p.fragment))

def extract_urls_from_html(html: str):
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            continue
        href = unwrap_google_redirect(href)
        href = strip_tracking_params(href)
        netloc_path = urlparse(href).netloc + urlparse(href).path
        if any(netloc_path.startswith(d) for d in EXCLUDE_DOMAINS):
            continue
        # de-dup while preserving order
        if href not in urls:
            urls.append(href)
    return urls

# Cell 4: fetch emails, build input_df, save CSV
def fetch_alert_links():
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(EMAIL_ADDR, EMAIL_PASS)
    imap.select(MAILBOX)

    # Search: from Google Alerts since a date
    typ, data = imap.search(None, f'(FROM "{ALERT_FROM}" SINCE "{SINCE_STR}")')
    ids = data[0].split()
    all_urls = []

    for msg_id in ids:
        typ, msg_data = imap.fetch(msg_id, "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        # Prefer HTML parts
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/html":
                    html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                    all_urls.extend(extract_urls_from_html(html))
        else:
            if msg.get_content_type() == "text/html":
                html = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
                all_urls.extend(extract_urls_from_html(html))

    imap.close()
    imap.logout()

    # De-duplicate
    seen = set()
    unique_urls = []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    return unique_urls

urls = fetch_alert_links()

# Build DataFrame with required columns
csv_path = "input_df.csv"
cols = ["url", "context", "is_news"]

# Load existing (or start empty)
if Path(csv_path).exists():
    old = pd.read_csv(csv_path)
else:
    old = pd.DataFrame(columns=cols)

# Compute only-new URLs vs what you already have
existing = set(old["url"].astype(str)) if "url" in old.columns else set()
new_urls = [u for u in urls if u not in existing]

# Prepend new rows to the TOP, keep the rest as-is
if new_urls:
    df_new = pd.DataFrame({
        "url": new_urls,
        "context": pd.NA,
        "is_news": pd.NA,
    })
    out = pd.concat([df_new, old], ignore_index=True)
    out.to_csv(csv_path, index=False, encoding="utf-8")
else:
    out = old

out.head(10)
