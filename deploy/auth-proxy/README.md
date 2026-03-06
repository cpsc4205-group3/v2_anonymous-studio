# Auth0 Proxy Starter (`oauth2-proxy` + `nginx`)

This starter protects both:

- Taipy GUI (`main.py`) on `localhost:5000`
- Taipy REST (`rest_main.py`) on `localhost:5001` via `/api/*`

## 1) Prepare env file

```bash
cp deploy/auth-proxy/.env.auth-proxy.example deploy/auth-proxy/.env.auth-proxy
make proxy-cookie-secret
```

Put the generated secret in `OAUTH2_PROXY_COOKIE_SECRET`.

Set Auth0 values in `deploy/auth-proxy/.env.auth-proxy`:

- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`
- `AUTH_PROXY_REDIRECT_URL`

Auth0 callback URL must match:

- `http://localhost:8080/oauth2/callback`

## 2) Run Taipy services locally

```bash
# Terminal A
taipy run main.py

# Terminal B
TAIPY_PORT=5001 taipy run rest_main.py
```

## 3) Start proxy stack

```bash
make auth-proxy-up
```

Open:

- `http://localhost:8080/` for GUI
- `http://localhost:8080/api/` for REST root

## 4) Stop stack

```bash
make auth-proxy-down
```
