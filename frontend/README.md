# BillBro — React Frontend

React replacement for the Streamlit `app.py` skeleton. Same 6 tabs (Checkout,
Inventory, Alerts, Admin, Add Item, Models), same sidebar layout, same
Week-by-Week TODOs — just running as a real SPA so you have full control over
UI/UX instead of Streamlit's widget set.

## What moved where

| Streamlit file | React equivalent |
|---|---|
| `app.py` (page config, sidebar, routing) | `src/App.jsx` + `src/components/Sidebar.jsx` |
| `config.py` | `src/config.js` (reads `VITE_*` env vars) |
| `pages/*.py` | `src/pages/*.jsx` |
| `utils.py` (cart/pricing/receipt logic) | `src/utils.js` |
| `predict.py` (model inference) | **stays in Python, backend-side.** The browser can't run model inference regardless of framework — call it via `api.js` once Person A exposes a `/checkout/detect` endpoint. The frontend doesn't care which model is behind that endpoint (YOLO or otherwise), so a model swap shouldn't require any frontend changes. |

`utils.py`'s image preprocessing functions (`preprocess_image`,
`resize_for_display`, `load_image_from_path`) also stay backend-side for the
same reason — they depend on OpenCV/PIL.

## Local development

```bash
cd frontend
npm install
cp .env.example .env      # adjust VITE_API_BASE_URL if your backend isn't on :5000
npm run dev                # http://localhost:5173
```

The dev server proxies `/api/*` to `VITE_API_BASE_URL` (see `vite.config.js`),
so you can call the backend from the browser with relative paths and avoid
CORS during development.

## Production build

```bash
npm run build       # outputs static files to dist/
npm run preview     # sanity-check the build locally before deploying
```

## Deploying with nginx

1. Build: `npm run build`.
2. Copy `dist/` to the server, e.g. `/var/www/billbro/dist`.
3. Copy `nginx.conf` to `/etc/nginx/sites-available/billbro`, edit the two
   placeholders (`root` path and `BACKEND_HOST:BACKEND_PORT`), then:
   ```bash
   sudo ln -s /etc/nginx/sites-available/billbro /etc/nginx/sites-enabled/
   sudo nginx -t          # validate config
   sudo systemctl reload nginx
   ```
4. `nginx.conf` handles two things: serving the SPA with a `try_files`
   fallback (so client-side routes like `/inventory` don't 404 on refresh),
   and reverse-proxying `/api/` to the backend so the browser never needs
   direct network access to it.

If you don't know your deploy target yet (local box vs. a VM vs. containers),
the config as written is generic — the only things you must fill in are the
`root` path and the backend host/port.

## Design

- **Dark mode** — toggle lives in the sidebar footer. Preference is saved to
  `localStorage` and respected on load (falls back to the OS preference for
  first-time visitors); a tiny inline script in `index.html` applies it
  before React mounts so there's no light-mode flash.
- **Nav is grouped, not flat** — "Store Operations" (Checkout, Inventory,
  Alerts) for day-to-day work vs. "Catalog & Management" (Add Item, Admin,
  Models) for setup/config. Same split shows up on each page as an eyebrow
  label above the title.
- **Pages separate "what this is" from "what state it's in" from "what's
  next"** — header, status card, and roadmap card are distinct blocks
  (`src/components/PageShell.jsx`) rather than one undifferentiated wall of
  text, so related info stays together and unrelated info doesn't.

## What's still a placeholder

Every page currently shows the same "not wired up yet" banner the Streamlit
version had — that's intentional, this is a 1:1 skeleton port, not new
functionality. `src/api.js` has the client + endpoint stubs ready for Weeks
3-8; wire each page up to its corresponding function as the backend
endpoints come online.
