# Reset Auth

This repo uses a manually generated Playwright `auth.json` file for the
Google OAuth-protected Nurture announcements page.

GitHub Actions restores that file from the `AUTH_JSON` repository secret before
running the scraper. Resetting auth means regenerating `auth.json` locally,
letting the helper write `auth_json_base64.txt`, and replacing the `AUTH_JSON`
secret with that base64 text.

## 1. Install Dependencies

Run from the repo root:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## 2. Generate a Fresh `auth.json`

```powershell
python src/login_once.py
```

A browser window opens. Complete Google login manually.

Before returning to the terminal, confirm the browser can view:

```text
https://nurture.diveanalytics.com/announcements
```

Then return to the terminal and press Enter.

The script writes a fresh local `auth.json`.

It also writes a base64-encoded copy to:

```text
auth_json_base64.txt
```

## 3. Update the GitHub Secret

Replace the `AUTH_JSON` repository secret with the generated base64 text:

```powershell
$auth = Get-Content "auth_json_base64.txt" -Raw
$auth | gh secret set AUTH_JSON --repo horse-3903/nurture-newsfeed
```

## 4. Test Locally

```powershell
python src/generate_feed.py
```

This should generate or update:

- `feed.xml`
- `cache.json`

## 5. Test GitHub Actions

```powershell
gh workflow run rss.yml --repo horse-3903/nurture-newsfeed
```

Then check the `Generate RSS Feed` workflow run in GitHub Actions.

## Notes

- `auth.json` and `auth_json_base64.txt` are gitignored and must never be committed.
- If GitHub Actions reports an expired session, rerun this reset process.
- If `gh secret set` fails, run `gh auth login` and try again.
