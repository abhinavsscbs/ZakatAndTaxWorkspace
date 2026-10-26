# Full-stack Render deployment (private single-workspace)

This deploys **one Docker web service** serving React from Flask at `/` and API routes under `/api`. Do **not** use GitHub Pages for the full-stack app. The existing GitHub Pages configuration, if enabled, must be replaced or disabled to avoid displaying an unrelated README/static site.

## Security boundary

This is **single-workspace access only**. The Docker image sets `REQUIRE_AUTH=1` and refuses access unless both `APP_BASIC_AUTH_USER` and `APP_BASIC_AUTH_PASSWORD` are configured. Browser Basic authentication protects frontend and APIs over HTTPS; it is **not** a multi-tenant identity system. All authenticated visitors share the same uploaded contracts, database, replacement dictionary, and API billing. Use unique strong credentials and share them only with trusted people. Do not advertise this as a public SaaS.

For broader user access, implement per-user identity, authorization and tenant-isolated storage, rate limiting, data retention, encryption policy, and security review before enabling open access.

## Render deployment

1. Review and merge the full-stack Render pull request into `main`.
2. Sign in to [Render](https://dashboard.render.com) and select **New → Blueprint**. Connect the GitHub repository `abhinavsscbs/ZakatAndTaxWorkspace` and deploy the `render.yaml` blueprint from `main`.
3. Enter strong `APP_BASIC_AUTH_USER` and `APP_BASIC_AUTH_PASSWORD`. Set `OPENAI_API_KEY` and/or `COHERE_API_KEY` as **secret environment variables**, never in Git. Configure the chosen provider/model identifiers with your account's enabled models as needed.
4. Verify Render's build and deploy logs. Open the generated `https://<service>.onrender.com` URL. Authenticate using the browser prompt. Verify `/api/health` and `/api/providers`, then test a non-sensitive workflow end to end.
5. The blueprint uses a **paid starter service** with a persistent disk mounted at `/app/storage`. Check the quoted costs in Render before activating. The disk holds knowledge.sqlite, original uploads, exported files, logs, and the shared JSON dictionary.

## Important operational details

- The frontend is built with Vite inside Docker and served by Flask; `/api` uses the same origin. GitHub Pages and a separate React hosting plan are not needed.
- Only `/api/health` is anonymous, for Render health checks.
- Gunicorn uses one worker to avoid multi-process shared-state complications with SQLite; more concurrency and background work require architecture changes.
- Flask and model requests may take considerable time; the deployment timeout is a starting point, not a guarantee for large jobs.
- Tesseract and its English/Arabic packs are installed in the image.
- Render disks persist only under their configured mount path; backups and retention policies are still your responsibility.
- The GitHub Pages site will **not** automatically redirect to Render. Disable Pages under **Settings → Pages**, or configure a redirect separately.
- To run locally without authentication, set `REQUIRE_AUTH=0` only on your own trusted machine. Never set it to 0 on a public Render deployment.
