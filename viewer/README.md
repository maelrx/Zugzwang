# Viewer local

Viewer estático e somente leitura dos runs persistidos no workspace.

Atualize o recorte depois de uma nova rodada:

```bash
uv run python scripts/build_readonly_viewer.py
```

Sirva a pasta localmente:

```bash
python3 -m http.server 4173 --bind 127.0.0.1 --directory viewer
```

Abra <http://127.0.0.1:4173/>. O navegador lê apenas `data.js` e `pieces.js`.
O script não copia requests/responses brutos e redige chaves sensíveis.
