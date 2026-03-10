# My Lottery User Manual

Last updated: 2026-03-10  
Applies to: `my-lottery` (Next.js + FastAPI + Supabase + Google Vision)

## 1. Overview

My Lottery is a web and mobile-friendly Progressive Web App (PWA) for:

- Uploading 4D/TOTO ticket images and extracting ticket data via OCR.
- Checking draw results (latest and historical).
- Auto-evaluating ticket outcomes (won/lost, prize tier, prize amount).
- Viewing purchase history and ticket details.
- Receiving push notifications when results are available.
- Generating 4D and TOTO prediction suggestions from historical results.

Core app areas:

- Home Upload: `/`
- Purchase History: `/purchase-history`
- Past Result: `/past-result`
- Predictive Analysis: `/prediction`

## 2. System Requirements

## 2.1 Required Applications

Install these before setup:

- Node.js 20 LTS or newer
- npm 10+ (bundled with Node.js)
- Python 3.10+ (recommended 3.11)
- pip (bundled with Python)
- Git
- `web-push` CLI (generate VAPID keys)
- ngrok (remote/mobile testing without LAN setup)

Create these:

- Supabase project (database + storage)
- Google Cloud account with Vision API enabled
- Vercel account (deployment and cron)

## 2.2 Supported Browsers

- Chrome (desktop/mobile)
- Safari (with platform-specific push support limits)

Push notifications require browser support + granted permission + valid VAPID setup.

## 3. Dependencies Installed by the Project

Frontend dependencies are installed from `package.json`:

- `next`, `react`, `react-dom`
- `browser-image-compression`
- `web-push`

Backend dependencies are installed from `requirements.txt`:

- `fastapi`, `uvicorn`
- `google-cloud-vision`, `google-auth`
- `pillow`, `numpy`
- `python-dotenv`, `python-multipart`
- `supabase`
- `pywebpush`, `py-vapid`
- `beautifulsoup4`, `requests`, `urllib3`

## 4. Installation and Setup

## 4.1 Frontend Boilerplate (From Scratch)

Run this command to set up the frontend boilerplate:

```bash
npx create-next-app@latest my-app --yes
```

## 4.2 Backend Boilerplate (From Scratch)

Set up the backend boilerplate as follows:

1. Create an `api` folder.
2. Inside `api`, create three folders: `routers`, `schemas`, and `services`.
3. Create `index.py` in the root of the `api` folder.

Example commands:

Windows Command Prompt:

```cmd
mkdir api api\routers api\schemas api\services
type nul > api\index.py
```

macOS/Linux:

```bash
mkdir -p api/routers api/schemas api/services
touch api/index.py
```

## 4.3 Clone and Enter the Project

```bash
git clone <your-repository-url>
cd my-lottery
```

## 4.4 Frontend Setup (Node)

Run this command to install all necessary packages

```bash
npm install
```

## 4.5 Backend Setup (Python venv)

Windows Command Prompt:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4.6 Configure Environment Variables

Create `.env.local` in the project root (`my-lottery/.env.local`).

Use this template:

```env
# =========================
# Core API / App Routing
# =========================
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
API_BASE_URL=http://localhost:8000

# =========================
# User identity (current implementation)
# =========================
NEXT_PUBLIC_USER_ID=a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d

# =========================
# Supabase
# =========================
NEXT_PUBLIC_SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your-supabase-service-role-key>

# =========================
# Google Vision (OCR)
# =========================
GOOGLE_CLOUD_CREDENTIALS_B64=<base64-encoded-service-account-json>

# =========================
# Push Notifications (VAPID)
# =========================
NEXT_PUBLIC_VAPID_PUBLIC_KEY=<your-vapid-public-key>
VAPID_PRIVATE_KEY=<your-vapid-private-key>

# =========================
# Cron endpoint security
# =========================
CRON_SECRET=<your-random-secret>
```

Notes:

- Backend loads `.env.local` from project root in `api/index.py`.
- `SUPABASE_SERVICE_ROLE_KEY` is required for backend writes and bypasses Row Level Security (RLS).

## 4.7 Database Setup (Supabase SQL)

Copy file content from `initial_schema.sql` in supabase sql editor

![DB setup](/docs/screenshots/db-setup.png)

## 4.8 Storage Setup (Supabase)

Create storage bucket:

- Name: `ticket-images`
- Public bucket: enabled
- Suggested size limit: 5 MB
- Allowed MIME types: Any

![DB storage](/docs/screenshots/db-storage.png)

## 4.9 VAPID Key Generation (Notifications)

```bash
npm install -g web-push
web-push generate-vapid-keys
```

Copy generated keys into `.env.local`:

- `NEXT_PUBLIC_VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`

## 4.10 Setup Google Project with Cloud Vision API

1. Go to https://console.cloud.google.com/
2. Click the button beside Google Cloud (top left hand corner)
3. Click "New project" (top right hand corner)
4. Give the project a name and press Create
5. Click the menu button (top left hand corner)
6. Click "APIs and services"
7. Click "Enable APIs and services" (top left hand corner)
8. Search or look for "Cloud Vision API", then click it
9. Click "Enable"
10. Click the menu button (top left hand corner)
11. Click "IAM and admin"
12. Look for "Service accounts" on the left hand side, then click it
13. Click "Create service account"
14. Auto-generate service account ID
15. Give Editor Role
16. Skip last step

![Google project](/docs/screenshots/gcv-0.png)

![Google project](/docs/screenshots/gcv-1.png)

![Google project](/docs/screenshots/gcv-2.png)

![Google project](/docs/screenshots/gcv-3.png)

![Google project](/docs/screenshots/gcv-4.png)

![Google project](/docs/screenshots/gcv-5.png)

![Google project](/docs/screenshots/gcv-6.png)

![Google project](/docs/screenshots/gcv-7.png)

![Google project](/docs/screenshots/gcv-8.png)

![Google project](/docs/screenshots/gcv-9.png)

## 5. Running the Web App and Mobile App

## 5.1 Run Backend (FastAPI)

From project root with venv activated:

```bash
python -m uvicorn api.index:app --host 0.0.0.0 --port 8000
```

Backend base URL: `http://localhost:8000`

## 5.2 Run Frontend (Next.js)

In another terminal:

```bash
npm run dev
```

Frontend URL: `http://localhost:3000`

Local rewrite is configured in `next.config.ts` to forward `/api/*` to `http://localhost:8000/api/*`.

## 5.2.1 Expose Frontend with ngrok (Optional)

If you are also tunneling the frontend for remote/mobile access, run this in another terminal:

```bash
ngrok http 3000
```

Use the HTTPS forwarding URL from ngrok (for example: `https://abc123.ngrok-free.app`) to open the app externally.

For consistent API behavior on all pages while using ngrok, set this in `.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=https://<your-ngrok-domain>
```

Then restart the frontend dev server:

```bash
npm run dev
```

## 5.3 Run Mobile App (Current Implementation)

There is no separate native iOS/Android codebase in this repository. Mobile usage is provided via:

- Mobile browser access to the web app
- PWA installation

## 5.3.1 Mobile on Same Wi-Fi (LAN)

1. Find your computer LAN IP (example: `192.168.1.20`).
2. Start backend on port `8000` and frontend on `3000`.
3. Ensure firewall allows inbound connections for these ports.
4. On phone browser, open `http://<LAN-IP>:3000`.
5. If needed, set:

```env
NEXT_PUBLIC_API_BASE_URL=http://<LAN-IP>:8000
API_BASE_URL=http://<LAN-IP>:8000
```

## 5.3.2 Install as PWA

Android Chrome:

1. Open app URL in Chrome.
2. Get prompted to install from notification

   ![PWA download on mobile](/docs/screenshots/PWA-mobile-install-1.jpg)

3. Tap install

   ![PWA download on mobile](/docs/screenshots/PWA-mobile-install-2.jpg)

4. Launch the app.

   ![PWA download on mobile](/docs/screenshots/PWA-mobile-install-3.jpg)

iOS Safari:

1. Open app URL in Safari.
2. Tap Share > Add to Home Screen.
3. Launch from home screen.

## 6. Step-by-Step User Flows

## 6.1 Flow A: Upload Ticket and Get Processing Status

1. Open Home page (`/`).
2. Tap `Take Photo / Upload`.
3. Select a ticket image.
4. Wait for OCR and processing.
5. See result

## 6.2 Flow B: Check Past Results

1. Navigate to `/past-result`.
2. Select `4D` or `TOTO`.
3. Pick `Draw Date`.
4. Click `Find Past Result`.
5. Optionally click `Load Latest` for selected game.

## 6.3 Flow C: View Purchase History Dashboard

1. Navigate to `/purchase-history`.
2. Verify summary cards:

- Total Spent
- Total Won
- Active Tickets

3. Use filters:

- Game Type
- Status
- Sort By

4. Expand TOTO ticket details to inspect combinations and matches.

## 6.4 Flow D: Generate Predictions

1. Navigate to `/prediction`.
2. Read the educational-use disclaimer.
3. Click `I understand — continue`.
4. Click `Generate Predictions`.
5. Review the three model cards:

- Frequency Analysis
- Markov Chain
- Gap / Due-Number Analysis

6. Review each model's:

- 4D predicted number
- TOTO System 12 numbers
- confidence meter
- reasoning summary

## 7. Feature Testing Guide

## 7.1 Quick Health Checks

- Backend health test:

```bash
curl http://localhost:8000/api/python
```

Expected: JSON with greeting message.

- Frontend page open test: `http://localhost:3000`

## 7.2 Test Ticket OCR Extraction (Upload)

Action:

- Upload clear 4D and TOTO sample images.

Expected:

- API `POST /api/extract` returns `status: success`.
- Return success message to frontend
- Ticket record inserted in Supabase.

![upload](/docs/screenshots/upload-0.png)

![upload](/docs/screenshots/upload-1.png)

## 7.3 Test Notifications

1. Ensure VAPID keys are set.
2. For draw date that has passed, notification will be returned after the upload action

![notification](/docs/screenshots/notif.png)

## 7.4 Test Past Results API

```bash
curl "http://localhost:8000/api/results/past/TOTO?draw_date=2026-03-01"
curl "http://localhost:8000/api/results/latest/TOTO"
```

Expected:

- Valid JSON result payload for available draws.
- Friendly message if result not yet released.

![past result](/docs/screenshots/past-result-pass.png)

![past result](/docs/screenshots/past-result-fail.png)

## 7.5 Test Purchase History API

```bash
curl "http://localhost:8000/api/tickets/<USER_ID>"
```

Expected:

- Summary and ticket list returned.
- Pending tickets for past draws may be evaluated on demand by this route.

![past result](/docs/screenshots/purchase-history.png)

## 7.6 Test Prediction Endpoints

Generate predictions using stored historical results:

```bash
curl -X POST http://localhost:8000/api/predictions/generate \
   -H "Content-Type: application/json" \
   -d '{"limit":50}'
```

Get model metadata:

```bash
curl http://localhost:8000/api/predictions/models-info
```

Expected:

- `POST /api/predictions/generate` returns `disclaimer`, `models`, and `data_points_used`.
- Each model includes `model_name`, `model_key`, `description`, `four_d`, `toto`, `methodology`, `assumptions`, `validation`, and `confidence_note`.
- `GET /api/predictions/models-info` returns static metadata for the three implemented models.

![prediction](/docs/screenshots/prediction-0.png)

![prediction](/docs/screenshots/prediction-1.png)

## 7.7 Test Cron-Protected Endpoints

```bash
curl -X POST http://localhost:8000/api/cron/check-results \
  -H "Authorization: Bearer <CRON_SECRET>"
```

Expected:

- `status: completed`
- summary payload for fetched/polled results

## 8. Troubleshooting

## 8.1 Backend Fails to Start

Symptoms:

- `RuntimeError` about missing env vars.

Checks:

- Confirm `.env.local` exists at project root.
- Confirm:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - Google credentials (`GOOGLE_CLOUD_CREDENTIALS` or `GOOGLE_CLOUD_CREDENTIALS_B64`)

## 8.2 Frontend Cannot Reach API

Symptoms:

- Upload fails or history/results pages error.

Checks:

- Backend running on port `8000`.
- Frontend running on port `3000`.
- `NEXT_PUBLIC_API_BASE_URL` matches reachable backend URL.
- CORS origin is allowed (localhost/LAN/ngrok patterns are supported in `api/index.py`).

## 8.3 Push Notifications Not Sent

Symptoms:

- `notification_sent: false`
- no browser popup

Checks:

- Browser permission is granted.
- `NEXT_PUBLIC_VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` are both set.
- User subscription exists in `user_subscriptions` table.
- Service worker `public/sw.js` is registered.

## 8.4 OCR Fails or Returns Warning

Symptoms:

- `status: warning` with no numbers detected.

Checks:

- Image clarity, glare, angle, and shadows.
- Correct file type (`jpeg`, `png`, `webp`).
- Google Vision credentials valid.

## 8.5 Database Write Errors

Symptoms:

- Ticket insert/update fails.

Checks:

- Required migrations completed.
- `ticket-images` bucket exists.
- Service role key is correct.
- Schema contains expected optional columns (`ticket_serial_number`, `draw_id`, `evaluation_result`, etc.).

## 8.6 Cron Endpoint 401/403

Symptoms:

- Unauthorized or forbidden from `/api/cron/*`.

Checks:

- Add header: `Authorization: Bearer <CRON_SECRET>`
- Ensure env `CRON_SECRET` matches request token.

## 8.7 Scraper Returns "Result not yet released"

This is normal before official draw result publication time. Retry later.

## 9. Known Issues and Limitations

- Prediction confidence values are heuristic indicators, not probabilities of winning.
- Prediction endpoints depend on historical draw data in Supabase unless a `results` payload is supplied directly.
- No native mobile app repository exists; mobile is delivered as web/PWA.
- Notification click payload uses `/tickets/{ticket_id}` but this route is not present in current frontend pages.
- Current default user strategy uses a fixed fallback `NEXT_PUBLIC_USER_ID`, which is not multi-user safe for production.
- current cron expression is a random timing between 7PM to 7:59PM due to limitations of free plan
- External scraping depends on Singapore Pools page structure; selector changes may break parsing until updated.

## 10. Prediction API Reference

Prediction is implemented in the backend under `/api/predictions`.

## 10.1 POST `/api/predictions/generate`

Use this endpoint to generate predictions from historical draw data.

Request body:

- `limit`: optional integer from `1` to `500`. Default is `50`. This controls how many draw-history rows are loaded per game type when using Supabase-backed history.
- `results`: optional array of result rows. If provided, the endpoint uses this payload directly instead of querying Supabase.

Example request using Supabase history:

```bash
curl -X POST http://localhost:8000/api/predictions/generate \
   -H "Content-Type: application/json" \
   -d '{"limit":50}'
```

Example request using an explicit results payload:

```bash
curl -X POST http://localhost:8000/api/predictions/generate \
   -H "Content-Type: application/json" \
   -d '{"results":[{"game_type":"4D","results":{"first_prize":"1234","second_prize":"5678","third_prize":"9012","starter":["1111"],"consolation":["2222"]}},{"game_type":"TOTO","results":{"winning_numbers":[1,2,3,4,5,6]}}]}'
```

Response fields:

- `disclaimer`: responsible-use notice returned by the API.
- `models`: array containing one response block per model.
- `data_points_used`: total number of historical result rows used to generate the predictions.

Each `models[]` entry contains:

- `model_name`, `model_key`, `description`
- `four_d.number`, `four_d.confidence`, `four_d.reasoning`
- `toto.numbers`, `toto.primary`, `toto.supplementary`, `toto.confidence`, `toto.reasoning`
- `methodology`, `assumptions`, `validation`, `confidence_note`

Common error cases:

- `400`: no past results were provided in a custom `results` payload.
- `404`: no usable draw history is available in Supabase or no valid 4D/TOTO rows were found.
- `500`: unexpected draw-history response format.

## 10.2 GET `/api/predictions/models-info`

Use this endpoint to retrieve static metadata about the implemented prediction models.

Example request:

```bash
curl http://localhost:8000/api/predictions/models-info
```

Response returns a `models` array with:

- `key`
- `name`
- `tagline`
- `icon`

## 10.3 Implemented Prediction Models

Frequency Analysis:
Uses hot-number frequency patterns from historical results. For 4D, it evaluates digit frequency by position. For TOTO, it ranks numbers by historical occurrence and builds a System 12 suggestion from the most frequent values.

Markov Chain:
Uses first-order transitions between consecutive draws. For 4D, each digit position is modeled separately. For TOTO, sorted ball positions are used to estimate the most likely next values from the previous draw.

Gap / Due-Number Analysis:
Tracks how long digits or numbers have been absent. For 4D, it looks for overdue digits by position. For TOTO, it ranks all 49 numbers by gap length and selects a weighted System 12 suggestion from the most overdue values.

## 10.4 Interpreting Prediction Output

- `four_d.number` is a 4-digit string.
- `toto.numbers` contains 12 numbers intended as a System 12 entry.
- `toto.primary` is the primary set of 6 numbers.
- `toto.supplementary` is the secondary set of 6 numbers.
- `confidence` is a relative model score from `0.0` to `1.0`. It is not a probability of winning.

## 10.5 Responsible Use

Prediction output is provided for educational and entertainment purposes only. Lottery draws are random events, and no model in this project should be treated as financial or gambling advice.

## 11. Data Privacy and Security Considerations

## 11.1 Vercel Platform Security Features

When deployed on Vercel, the application benefits from several built-in security protections:

**DDoS and Flooding Protection:**

- Automatic traffic filtering and rate limiting at the edge
- Built-in protection against large-scale distributed denial-of-service attacks
- Smart routing that absorbs traffic spikes across global CDN infrastructure

**Infrastructure Security:**

- Automatic HTTPS/TLS encryption for all deployments
- SSL certificates provisioned and auto-renewed via Let's Encrypt
- Edge network distributed across 100+ data centers prevents single point of failure

**Request Security:**

- Automatic protection against common web vulnerabilities (XSS, injection attacks)
- Request size limits prevent payload-based attacks
- Headers sanitization and validation at the platform level

**Serverless Function Protections:**

- Isolated execution environment per function invocation
- Automatic resource limits (memory, CPU, execution time)
- Cold start protections prevent resource exhaustion

**Deployment Security:**

- Immutable deployments - each build is isolated and versioned
- Preview deployments isolated from production environment
- Environment variables encrypted at rest and in transit

**Monitoring and Observability:**

- Built-in logging for all requests and function executions
- Real-time performance metrics and error tracking
- Automatic alerting for deployment and runtime failures

**Notes:**

- Free tier has baseline protections; Pro/Enterprise tiers offer advanced DDoS mitigation
- Vercel Firewall (Enterprise) provides custom WAF rules and geo-blocking
- See [Vercel Security](https://vercel.com/security) for detailed platform documentation
