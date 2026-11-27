# Reliable daily on-chain refresh: external scheduler

GitHub's native `schedule` event is best-effort. The repository retains three off-hour cron slots as a backup, but an independent scheduler can dispatch the refresh at the desired time.

## Recommended setup (cron-job.org)

1. Create a free account at [cron-job.org](https://cron-job.org/).
2. Create one job scheduled **daily at 09:00 Brisbane time** (`Australia/Brisbane`; Brisbane does not observe daylight saving).
3. Request URL:
   `https://api.github.com/repos/aussiekarl-gif/BTC_Composite/actions/workflows/cowen_onchain_daily_refresh.yml/dispatches`
4. Method: `POST`.
5. Headers:
   - `Accept: application/vnd.github+json`
   - `Authorization: Bearer <your fine-grained token>`
   - `X-GitHub-Api-Version: 2022-11-28`
   - `Content-Type: application/json`
6. Body: `{"ref":"main"}`
7. Save, run a test, and confirm a run with event `workflow_dispatch` appears in GitHub Actions.

## Create a least-privilege GitHub token

In GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.

- Resource owner: your account.
- Repository access: only `BTC_Composite`.
- Repository permission: **Actions: Read and write**.
- Set an expiry (recommend 90 days initially) and store it only in cron-job.org's credential/header configuration. Never paste it into chat, commit it, or place it in a public URL.

The token can dispatch this workflow but should not have Contents write permission. The workflow itself has its own `contents: write` permission to publish validated data snapshots.

## Keep the native cron backup

Do not remove the existing schedule. It remains a fallback if the external scheduler fails. The refresh workflow has a concurrency lock and snapshot integrity checks, so concurrent attempts should not overwrite each other; the native and external triggers may nevertheless cause redundant source requests.

## Timing and verification

- External target: 09:00 Brisbane.
- Native backup slots: 09:17, 10:17 and 11:17 Brisbane.
- Confirm the Actions run's event type and actual start time after testing.
- Review the workflow summary for each provider's result. A run may publish successful sources but still fail overall if one provider fails.
- Recheck token expiry periodically and rotate it before expiry.

**Security note:** cron-job.org holds the token used in the Authorization header. Use a repo-only token with the minimum permission and expiry. If you prefer not to place a long-lived token in a third-party scheduler, use a GitHub App with short-lived installation tokens through a Cloudflare Worker, but that is more setup.
