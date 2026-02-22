# Zugzwang UI

Frontend for the Zugzwang engine migration track.

Current status:
- M3 scaffold complete (Vite + React + TypeScript)
- TanStack Router shell with core pages
- TanStack Query provider configured
- Vite proxy enabled: `/api` -> `http://127.0.0.1:8000`

## Local development

From `zugzwang-ui/`:

```bash
npm install
npm run dev
```

Run backend API in parallel from repo root:

```bash
python -m zugzwang.cli api --reload
```

## Scripts

- `npm run dev`: start Vite dev server
- `npm run build`: typecheck + production build
- `npm run lint`: lint frontend sources
- `npm run preview`: preview production build
