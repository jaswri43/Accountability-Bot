# Dashboard frontend

React + Vite + Tailwind v4 + Recharts dashboard for the LoL Accountability Bot.
Setup, the dev proxy, and production deployment are covered in the
[root README](../README.md).

```bash
npm install
npm run dev     # http://localhost:5173, proxies /api/* to the API on :8001
npm run lint    # oxlint
npm run build   # type-check + build to dist/ (served by nginx in production)
```
