Daily Norway News Digest

This folder stores daily HTML newsletters and a deduplication index.

Files:
- index.json: JSON array of canonical article IDs (used to avoid repeats ever)
- archive/YYYY-MM-DD.html: saved newsletter files

Notes:
- Cron job will run daily at 10:00 Europe/Berlin and save an HTML file here.
- Summaries are Chinese (Simplified), fluent tone, with original headline and link.
- Paywalled articles will be linked and summarized from available preview only.
