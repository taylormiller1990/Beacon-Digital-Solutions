# Going live — Beacon Budget payments (step by step)

This is the checklist to take Beacon Budget Premium from "test sandbox" to real,
working $8/mo subscriptions. Do it in order. The whole thing can be validated for
**free** in Stripe test mode before you ever charge a real card.

## The big picture (read this first)

There are **two** separate things:

1. **The website** (`index.html`, `beaconbudget.html`, …) — static files served by
   **GitHub Pages** at `beacondigitalsolutionsllc.com`. GitHub Pages can only serve
   files; **it cannot run `app.py`.**
2. **The backend** (`app.py`) — must run on a real Python host (we'll use **Render**).
   This is what talks to Stripe, generates license keys, and emails them.

So the website stays where it is; we deploy `app.py` to Render and point the website
+ the Mac app at Render's URL.

```
Customer → beaconbudget.html (GitHub Pages) → [BB_BACKEND] → app.py on Render → Stripe
                                                                   │
                                              emails license key ──┘ (via Resend)
Customer → Mac app → Settings → Premium → [licensingBaseURL] → app.py /activate
```

`BB_BACKEND` (website) and `licensingBaseURL` (app) must point at the SAME Render URL.
Both are currently set to `https://api.beacondigitalsolutionsllc.com` — either point
that subdomain at Render (Step 5) or change both to Render's default URL.

---

## Step 1 — Deploy the backend to Render (still in TEST mode)

1. Push this repo to GitHub (it already is) and make sure these files are committed:
   `app.py`, `requirements.txt`, `Procfile`, `runtime.txt`, `render.yaml`.
   (Do **not** commit `.env` or `licenses.db` — they're git-ignored now.)
2. Go to <https://render.com>, sign up (free), and click **New → Blueprint**.
3. Connect your `Beacon-Digital-Solutions` GitHub repo. Render reads `render.yaml`
   and proposes a web service called **beacon-backend** with a 1 GB persistent disk.
   Click **Apply**.
4. It will build and start. When it's live you'll get a URL like
   `https://beacon-backend.onrender.com`. Visit `…/health` — you should see
   `{"status":"ok"}`. (It may say env vars are missing — that's Step 3.)

> Render's free tier sleeps after inactivity, so the first request after idle takes
> ~30s. Fine for beta; upgrade to the $7/mo "Starter" plan when you want it always-on.

---

## Step 2 — Stripe TEST setup

Make sure the Stripe dashboard toggle (top-left) says **Test mode**.

1. **Product/price:** Products → **+ Add product** → name "Beacon Budget Premium",
   price **$8.00**, **Recurring / Monthly**. Save. Click the price and copy its ID
   (`price_…`). This is `PREMIUM_PRICE_ID`.
2. **API key:** Developers → API keys → copy the **Secret key** (`sk_test_…`).
   This is `STRIPE_SECRET_KEY`.
3. **Webhook:** Developers → Webhooks → **+ Add endpoint**.
   - Endpoint URL: `https://<your-render-url>/webhook`
   - Events: select **`checkout.session.completed`** (and optionally
     `customer.subscription.deleted`).
   - Add endpoint, then copy the **Signing secret** (`whsec_…`).
     This is `STRIPE_WEBHOOK_SECRET`.

---

## Step 3 — Email delivery (Resend) — REQUIRED

Without this, the license key only prints to the server log and your customer never
gets it.

1. Sign up at <https://resend.com> (free tier is plenty for beta).
2. Add + verify your domain `beacondigitalsolutionsllc.com` (they give you DNS
   records to add at your domain registrar). Until the domain is verified you can
   only send to your own address — fine for your first test.
3. Create an API key → copy it (`re_…`). This is `RESEND_API_KEY`.
4. The "from" address in `app.py` is `licenses@beacondigitalsolutionsllc.com` — once
   the domain is verified in Resend, that address works.

---

## Step 4 — Put the secrets into Render

In Render → your service → **Environment** → add each (the blueprint already created
`DB_PATH` and `BACKEND_BASE_URL` for you):

| Key | Value |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_…` from Step 2 |
| `PREMIUM_PRICE_ID` | `price_…` from Step 2 |
| `STRIPE_WEBHOOK_SECRET` | `whsec_…` from Step 2 |
| `RESEND_API_KEY` | `re_…` from Step 3 |
| `LICENSE_SIGNING_SECRET` | run `python3 -c "import secrets; print(secrets.token_hex(32))"` and paste the output |
| `ADMIN_PASSWORD` | a strong password (guards `/admin/contacts` + `/admin/feedback`) |

Click **Save** — Render redeploys automatically.

---

## Step 5 — Point the website + app at the backend

You have two options:

**A. Use a clean subdomain (recommended).** In your domain DNS, add a `CNAME`
record `api` → your Render URL (`beacon-backend.onrender.com`), and in Render →
Settings → Custom Domains add `api.beacondigitalsolutionsllc.com`. Then the existing
values already in the code (`https://api.beacondigitalsolutionsllc.com`) just work —
nothing to change.

**B. Use Render's URL directly.** Edit two places to your `…onrender.com` URL:
- Website: `window.BB_BACKEND` near the top of `beaconbudget.html`.
- Mac app: `AppConstants.licensingBaseURL`, then rebuild the app.

---

## Step 6 — Test the whole loop for FREE (test card)

1. Open `beaconbudget.html` on your live site, enter an email, click **Subscribe**.
2. On Stripe's page use test card **`4242 4242 4242 4242`**, any future expiry, any CVC, any ZIP.
3. You should land on the "you're all set" page and **receive the license email**.
4. Open Beacon Budget → **Settings → Premium** → enter that same email + the key →
   premium unlocks.
5. Check `https://<backend>/admin/contacts` (log in `admin` / your `ADMIN_PASSWORD`)
   to see your records.

If the email doesn't arrive: check Resend's dashboard logs and that the domain is
verified. If activation fails: confirm the app's `licensingBaseURL` matches the
backend and that you used the same email as checkout.

---

## Step 7 — Flip to LIVE (when beta looks good)

1. In Stripe, switch the toggle to **Live mode**.
2. Recreate the **$8/mo** product in live → copy the new live `price_…`.
3. Developers → API keys → copy the live secret `sk_live_…`.
4. Developers → Webhooks → add the **same** `/webhook` endpoint in live → copy the
   new live `whsec_…`.
5. In Render → Environment, replace these three with the live values:
   `STRIPE_SECRET_KEY`, `PREMIUM_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`. Save (redeploys).
6. Do one real $8 purchase yourself end-to-end, confirm the email + activation, then
   refund it in Stripe if you like.

You're live. 🎉

---

## Quick reference — which value goes where

| Thing | Lives in | Notes |
|---|---|---|
| `STRIPE_SECRET_KEY` | Render env | test → live when you flip |
| `PREMIUM_PRICE_ID` | Render env | the $8/mo price; **recreate in live mode** |
| `STRIPE_WEBHOOK_SECRET` | Render env | per-endpoint; **separate test vs live** |
| `RESEND_API_KEY` | Render env | required for the license email |
| `LICENSE_SIGNING_SECRET` | Render env | any long random string |
| `ADMIN_PASSWORD` | Render env | guards /admin |
| `DB_PATH` | Render env | `/var/data/licenses.db` (persistent disk) |
| `BB_BACKEND` | `beaconbudget.html` | backend URL |
| `licensingBaseURL` | app `AppConstants.swift` | backend URL (rebuild app after change) |

## Security notes
- `licenses.db` is now git-ignored — **never** commit it (the repo is public).
- Secret keys live only in Render's Environment, never in the repo or the HTML.
- The website only ever calls public endpoints; no secret key is exposed to the browser.
