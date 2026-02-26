# Nurture Announcements RSS + Email Notifier

Serverless RSS feed generator for the Google OAuth-protected Nurture announcements page.

Architecture:

- GitHub Actions runs every hour
- Restores `auth.json` from `AUTH_JSON` GitHub Secret
- Uses Playwright with persisted `storage_state`
- Scrapes announcements
- Updates `feed.xml` and `cache.json`
- Optionally emails new announcements via Gmail SMTP
- Commits changes back to the repo
- `feed.xml` can be hosted with GitHub Pages

## Files

- `src/login_once.py`: one-time manual login helper (saves Playwright `auth.json`)
- `src/generate_feed.py`: scraper + change detection + RSS generation + email notifications
- `.github/workflows/rss.yml`: scheduled GitHub Actions workflow
- `cache.json`: previously seen announcements cache
- `requirements.txt`: Python dependencies

## 1) Local One-Time Login (manual, no credential automation)

This project does not bypass Google OAuth. You log in manually once, then persist the authenticated browser state.

1. Install dependencies locally:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

2. Run the login helper:

```bash
python src/login_once.py
```

3. A browser window opens. Complete Google login manually and ensure you can see:

`https://nurture.diveanalytics.com/announcements`

4. Return to the terminal and press Enter.

5. The script saves `auth.json` (gitignored).

## 2) Base64 Encode `auth.json` for GitHub Secret

Windows PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("auth.json")) | Set-Clipboard
```

macOS / Linux:

```bash
base64 < auth.json | tr -d '\n'
```

Copy the full output value.

## 3) GitHub Secrets Setup

In GitHub: `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

Create these secrets:

1. `AUTH_JSON`
   - Base64-encoded contents of `auth.json`

2. `EMAIL_SENDER`
   - Gmail address used to send notifications (optional if email not needed)

3. `EMAIL_PASSWORD`
   - Gmail App Password (not your normal Gmail password)

4. `EMAIL_RECIPIENTS`
   - Comma-separated email list, e.g. `you@example.com,team@example.com`

If email secrets are omitted, feed generation still runs and email is skipped.

### Easier recipient management (private, recommended)

Keep recipients in the `EMAIL_RECIPIENTS` GitHub Secret, but use a multiline value
instead of a comma-separated one.

Example secret value:

```txt
you@example.com
team@example.com
# comments are allowed
```

The app now accepts recipients separated by commas, semicolons, or newlines, and
it ignores duplicate entries.

Optional local-only workflow (not committed):

- Create `email_recipients.txt` in the repo root (one email per line)
- It is gitignored and used only if `EMAIL_RECIPIENTS` is not set

Recipient load order:

1. `EMAIL_RECIPIENTS` secret (preferred)
2. `EMAIL_RECIPIENTS_FILE` path (optional override)
3. `email_recipients.txt` in the repo root (local/private file)

### Local file -> GitHub Secret sync on commit (optional)

If you want to edit recipients locally and automatically push them into the
GitHub Actions secret after each commit, use the included local hook setup.

Prerequisites:

- GitHub CLI installed (`gh`)
- `gh auth login` completed
- Permission to update repository Actions secrets

1. Create a local `email_recipients.txt` (this file is gitignored):

```txt
you@example.com
team@example.com
```

2. Install the local post-commit hook:

```bash
python src/install_email_secret_hook.py
```

3. Make a commit. After each commit, the hook runs:

- `python src/sync_email_recipients_secret.py --skip-if-unchanged --quiet`
- It updates the `EMAIL_RECIPIENTS` GitHub secret only when the file content changed
- If sync fails (e.g. `gh` not logged in), your commit still succeeds

Manual sync (any time):

```bash
python src/sync_email_recipients_secret.py
```

## 4) GitHub Actions Deployment

1. Push this repository to GitHub.
2. Add the secrets listed above.
3. Enable GitHub Actions for the repo (if prompted).
4. Go to `Actions` -> `Generate RSS Feed` -> `Run workflow` to test manually.
5. Confirm the workflow creates/updates `feed.xml` and `cache.json`.

If you want GitHub Actions to use file-based recipients, point `EMAIL_RECIPIENTS_FILE`
to a file you provision at runtime. Otherwise, use the `EMAIL_RECIPIENTS` secret.

The workflow also runs automatically every hour via GitHub Actions schedule.

## 5) Enable GitHub Pages (to host `feed.xml`)

1. In GitHub, open `Settings` -> `Pages`
2. Set source to `Deploy from a branch`
3. Choose branch `gh-pages` and `/ (root)`
4. Save

Your RSS feed URL will be:

`https://<your-github-username>.github.io/<repo-name>/feed.xml`

## 6) Running Locally (optional)

After creating `auth.json`, you can test locally:

```bash
python src/generate_feed.py
```

Outputs:

- `feed.xml`
- updated `cache.json`

To test just the extraction logic (without writing feed/cache or sending email):

```bash
python src/test_extraction.py --limit 5
```

To also pull full detail-page content for the sample items:

```bash
python src/test_extraction.py --limit 3 --enrich-details
```

## Notes / Operations

- If the session expires, the workflow logs a clear error and exits.
- Refresh `AUTH_JSON` by rerunning `src/login_once.py` and updating the secret.
- `auth.json` must never be committed.
- Email failures do not fail the workflow; they are logged and skipped.

## How Scraping Works (selectors)

`src/generate_feed.py`:

- Uses Playwright to load the authenticated page HTML (with `auth.json`)
- Parses HTML with BeautifulSoup
- Extracts announcements using CSS selectors from one function:
  - `get_selector_config()`

This is the place to customize once you manually inspect the page.

Selector groups used:

- `item_nodes`: each announcement container (article/card/list item)
- `title_nodes`: title/link inside each item
- `description_nodes`: optional summary/body text
- `date_nodes`: optional publish date/time

Recommended approach after you inspect the page:

1. Replace the generic selectors in `get_selector_config()` with the exact site selectors you found.
2. Put the most specific selector first in each list.
3. Keep 1-2 fallback selectors only if needed.

Example (illustrative only):

```python
def get_selector_config() -> dict[str, list[str]]:
    return {
        "item_nodes": [".announcements-list .announcement-row"],
        "title_nodes": [".announcement-title a"],
        "description_nodes": [".announcement-summary"],
        "date_nodes": ["time"],
    }
```

## Adjusting Schedule

Edit `.github/workflows/rss.yml`:

- Current schedule: `0 * * * *` (every hour)

You can change the cron expression under `on.schedule` to another GitHub Actions schedule interval.
