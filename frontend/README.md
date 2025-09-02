Live Ops Dashboard (Next.js)

Setup
- Copy .env.local.example to .env.local and adjust values
- Install deps: npm install
- Run dev server: npm run dev

Environment
- NEXT_PUBLIC_BACKEND_HTTP: http base to Python service (e.g., http://localhost:5001)
- NEXT_PUBLIC_BACKEND_WS: ws/wss URL to ops stream (e.g., ws://localhost:5001/ops)
- NEXTAUTH_SECRET: random string
- AUTH_USERNAME / AUTH_PASSWORD: credentials for login

Build & Run
- Production build: npm run build && npm start
- Docker: docker build -t live-ops-dashboard . && docker run -p 3000:3000 live-ops-dashboard # Heroku deployment
