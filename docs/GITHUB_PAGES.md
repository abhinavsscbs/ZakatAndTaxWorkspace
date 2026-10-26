# GitHub Pages deployment (frontend only)

This repository's React/Vite frontend can be built as a static website at:

https://abhinavsscbs.github.io/ZakatAndTaxWorkspace/

## Enable publishing

1. Review and merge the GitHub Pages pull request into `main`.
2. In repository **Settings → Pages → Build and deployment**, select **GitHub Actions**.
3. Open **Actions → Deploy frontend to GitHub Pages** to check the first run. If it does not run automatically, use **Run workflow** on `main`.

The workflow runs `npm ci --prefix frontend` and `npm run build --prefix frontend`, then deploys `frontend/dist`. Vite uses `/ZakatAndTaxWorkspace/` as its production asset base. To preview locally, run `npm ci --prefix frontend && npm run build --prefix frontend && npm run preview --prefix frontend`.

## Important limitation

**This does not deploy the Flask/Python backend.** The UI makes API calls through relative `/api` URLs, which the local Vite development server proxies to Flask. GitHub Pages does not provide this proxy, so API-driven tools, document analysis, uploads, AI requests and exports will not work at the Pages URL.

Do not enter sensitive documents or API credentials into a public preview. Production deployment requires a separately hosted backend, deliberate API URL and CORS configuration, and authentication/authorization, tenant isolation, access control, retention and privacy/security review. Do not expose the existing single-workspace backend to the public internet as-is.
