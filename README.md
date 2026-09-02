<div align="center">

# nurture-newsfeed

Serverless RSS feed generator for the Google OAuth-protected Nurture announcements page

[![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![License](https://img.shields.io/github/license/horse-3903/nurture-newsfeed?style=flat-square)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/horse-3903/nurture-newsfeed?style=flat-square)](../../commits)

</div>

---

## Overview

**nurture-newsfeed** automates monitoring of the Google OAuth-protected Nurture announcements page by scraping it with Playwright, generating an RSS feed, and sending email notifications for new announcements. A GitHub Actions workflow runs every hour to keep the feed up to date, with the resulting `feed.xml` hosted via GitHub Pages.

This project does **not** bypass Google OAuth — you log in manually once, persist the authenticated browser state as a secret, and the automation uses that session going forward.

## Features

- Hourly GitHub Actions workflow that scrapes the authenticated Nurture announcements page
- RSS feed (`feed.xml`) published via GitHub Pages
- Change detection via `cache.json` — only new announcements trigger emails
- Email notifications via Gmail SMTP (optional)
- Flexible recipient management via GitHub Secret, local file, or both
- Optional post-commit hook to sync recipients to GitHub Secrets automatically
- Clean session expiry detection with actionable error messages

## Tech Stack

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-4-orange?style=for-the-badge)](https://www.crummy.com/software/BeautifulSoup/)
[![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-222222?style=for-the-badge&logo=github&logoColor=white)](https://pages.github.com/)

## Getting Started

### Prerequisites

- Python 3.10+
- A GitHub account with Actions enabled
- A Gmail account (for email notifications — optional)

### Step 1 — One-Time Local Login

This step saves your authenticated browser session so the workflow can use it without storing credentials.

```bash
pip install -r requirements.txt
python -m playwright install chromium

python src/login_once.py
```

A browser window will open. Complete Google login and navigate to the Nurture announcements page, then return to the terminal and press **Enter**. This saves `auth.json` (gitignored).

### Step 2 — Encode `auth.json` as a GitHub Secret

**Windows (PowerShell):**
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("auth.json")) | Set-Clipboard
```

**macOS / Linux:**
```bash
base64 < auth.json | tr -d '\n'
```

### Step 3 — Configure GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and create:

| Secret | Value |
|--------|-------|
| `AUTH_JSON` | Base64-encoded contents of `auth.json` |
| `EMAIL_SENDER` | Gmail address to send from (optional) |
| `EMAIL_PASSWORD` | Gmail App Password — not your regular password (optional) |
| `EMAIL_RECIPIENTS` | Comma- or newline-separated list of recipient emails (optional) |

If email secrets are omitted, feed generation still runs and email is silently skipped.

### Step 4 — Deploy

1. Push the repository to GitHub.
2. Go to **Actions → Generate RSS Feed → Run workflow** to test manually.
3. Confirm `feed.xml` and `cache.json` are created/updated.

### Step 5 — Enable GitHub Pages (to host `feed.xml`)

1. Go to **Settings → Pages**
2. Set source to **Deploy from a branch**
3. Choose branch `gh-pages` and `/ (root)`
4. Save

Your RSS feed URL:
```
https://<your-github-username>.github.io/<repo-name>/feed.xml
```

## Project Structure

```
nurture-newsfeed/
├── .github/
│   └── workflows/
│       ├── rss.yml                       # Main scheduled workflow (hourly)
│       ├── test-email.yml                # Test email workflow
│       └── update-recipients.yml         # Update EMAIL_RECIPIENTS from the Actions tab
├── src/
│   ├── generate_feed.py                  # Scraper + RSS generation + email
│   ├── login_once.py                     # One-time manual login helper
│   ├── install_email_secret_hook.py      # Install post-commit hook
│   ├── sync_email_recipients_secret.py   # Sync recipients to GitHub Secret
│   ├── test_email.py                     # Test email sending
│   └── test_extraction.py               # Test scraping without writing files
├── cache.json                            # Previously seen announcements
├── feed.xml                              # Generated RSS feed
└── requirements.txt
```

## Usage

**Test scraping locally (no email, no feed write):**
```bash
python src/test_extraction.py --limit 5
```

**Test with full detail-page content:**
```bash
python src/test_extraction.py --limit 3 --enrich-details
```

**Run the full feed generation locally:**
```bash
python src/generate_feed.py
```

**Adjust the schedule** — edit `.github/workflows/rss.yml`:
```yaml
on:
  schedule:
    - cron: '0 * * * *'  # every hour — change as needed
```

## Recipient Management

Recipients can be configured via:

1. `EMAIL_RECIPIENTS` GitHub Secret (preferred) — supports commas, semicolons, or newlines; comments (`#`) are ignored
2. `EMAIL_RECIPIENTS_FILE` environment variable pointing to a file path
3. `email_recipients.txt` in the repo root (gitignored, local only)

### Fastest way: update recipients from the Actions tab

Instead of editing the secret by hand, use the **Update Email Recipients** workflow — paste an email list into a form in the GitHub UI and it updates the `EMAIL_RECIPIENTS` secret for you.

**One-time setup:**
1. Create a personal access token with permission to manage this repo's Actions secrets (a fine-grained token scoped to this repo with "Secrets" write access, or a classic token with `repo` scope).
2. Add it as a repository secret named `SECRETS_ADMIN_TOKEN` (**Settings → Secrets and variables → Actions → New repository secret**).

**Every time you want to change recipients:**
1. Go to **Actions → Update Email Recipients → Run workflow**.
2. Paste the email addresses (comma, semicolon, or newline separated).
3. Click **Run workflow**.

Bookmark this direct link for one-click access:
```
https://github.com/<owner>/<repo>/actions/workflows/update-recipients.yml
```

**Alternative: auto-sync recipients on commit**
```bash
python src/install_email_secret_hook.py
```
After installation, a post-commit hook will push `email_recipients.txt` to the GitHub Secret automatically.

## Customizing Selectors

If the Nurture page structure changes, update `get_selector_config()` in `src/generate_feed.py`:

```python
def get_selector_config() -> dict[str, list[str]]:
    return {
        "item_nodes": [".announcements-list .announcement-row"],
        "title_nodes": [".announcement-title a"],
        "description_nodes": [".announcement-summary"],
        "date_nodes": ["time"],
    }
```

Place the most specific selector first; keep 1–2 fallbacks.

## License

MIT License — see [LICENSE](LICENSE) for details.
