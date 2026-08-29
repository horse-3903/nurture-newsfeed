# Reset Auth

This repo uses a manually generated Playwright `auth.json` file for the
Google OAuth-protected Nurture announcements page.

GitHub Actions restores that file from the `AUTH_JSON` repository secret before
running the scraper. Resetting auth means regenerating `auth.json` locally,
letting the helper write `auth_json_base64.txt`, and replacing the `AUTH_JSON`
secret with that base64 text. `src/login_once.py` now does the secret push for
you via the `gh` CLI, so step 3 below is automatic unless you pass
`--skip-secret-push`.

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

An Opera GX window opens (default browser for this; pass `--browser chrome`
or `--browser chromium` to use something else, or `--opera-path` if Opera GX
isn't auto-detected). Complete Google login manually in that window.

The script polls the page URL and detects on its own once you're off the
Google/login pages and onto the announcements page — no need to switch back
to the terminal. It gives up and warns after `--login-timeout-ms` (default
5 minutes) if login never completes.

The script writes a fresh local `auth.json`.

It also writes a base64-encoded copy to:

```text
auth_json_base64.txt
```

## 3. GitHub Secret Update (automatic)

By default the script then runs `gh secret set AUTH_JSON --repo horse-3903/nurture-newsfeed`
for you, using the freshly written `auth_json_base64.txt`. Requires `gh auth login`
to already be done. Override the target with `--repo` / `--secret-name`, or pass
`--skip-secret-push` to update the secret manually:

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
