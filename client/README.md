# Trading Signals — Cloudflare Client

Standalone single-page application (SPA) client for the Trading Signals Framework.
Designed to be deployed on **Cloudflare Pages** while the Flask API backend runs on your server.

## Deployment to Cloudflare Pages

1. **Go to Cloudflare Dashboard → Pages → Create a project**
2. **Connect your GitHub repo** or upload the `client/` directory manually
3. **Build settings:**
   - Framework preset: **None**
   - Build command: *(leave empty — this is a static SPA)*
   - Build output directory: **`client`**

4. **Set the API_BASE** (optional):
   - If your backend is at `https://api.yourdomain.com`, open `client/index.html`
   - Change `const API_BASE = window.location.origin` to `const API_BASE = 'https://api.yourdomain.com'`
   - Or use Cloudflare Pages `functions/proxy.js` to proxy `/api/*` to your backend

5. **Deploy!** Your trading dashboard will be live at `https://your-project.pages.dev`

## Running Locally

```bash
# Serve the client with any HTTP server
python3 -m http.server 8080 --directory client
```

Or open `client/index.html` directly (API calls may be blocked by CORS — use the Flask backend on port 5000 instead).

## Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | Home | Market overview, active setups, news |
| Signals | All pairs | Unified signal breakdown with 5 components |
| Trading Bot | Deriv account | Active trades, account info, summary |
| News | Economic calendar | Upcoming events with impact levels |
| Cross-Asset | Analysis | DXY, VIX, yields, regime detection |
| Account Log | History | Trade history & activity log |
