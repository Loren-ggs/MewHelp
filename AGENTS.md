# Deployment verification

- After changing domain or proxy routing, verify the public URL in the user's browser and confirm the page is MewHelp with a valid HTTPS certificate. A server-side HTTP 200 alone is insufficient because local DNS or proxy rules can still reach another site.

# Preset question verification

- Before publishing preset questions, run each through the live `/api/chat` path and check the final answer. When changing `data/kb/*.md`, add or update its indexed chunks and vectorize them; copying the Markdown file alone does not update retrieval. Preserve existing knowledge and reviewed flywheel entries.

# Long evaluation jobs

- For `eval-rag` failures, replay the affected retrieval inputs before changing error handling. Retry only verified transient upstream errors with a fixed limit; keep other input errors visible. After deployment, start the registered `eval-rag` job and confirm it exits successfully, writes a new complete report, and `/api/rag-eval/overview` serves that report.

# Public source releases

- Build public releases from an explicit allowlist. Exclude `.env`, runtime databases, logs, caches, model and evaluation artifacts; compare staged text against local credential values before pushing. Verify the remote file tree and README after publication.
