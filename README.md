# Beacon Digital Solutions Website

Privacy-first, on-device tools for families.

This site promotes Beacon Budget (our first local-first zero-based budgeting app) and the community of people who want technology that protects their time, data, and dignity instead of extracting it.

## Key pages
- index.html — Home with privacy promise and community focus
- products.html — New top-level Products hub (Beacon Budget lives underneath as the detail page)
- thrive.html — Beacon Budget detail page (Free + $8/mo Premium, direct web subscribe with automated license)
- about.html — Personal story + values (God-image bearers, protect our neighbor)
- videos.html — Training VLOG hub (primary content destination)
- privacy.html — Expanded manifesto-style policy

Blog has been removed from navigation (Videos are now the main content vehicle).

Legacy consulting pages (services.html and subpages) are de-emphasized following the pivot from AI consulting/prompts to building tools and community.

## Notes
- Uses static HTML + Tailwind CDN for simplicity
- Update App Store links in thrive.html once live
- Web subscription flow will be added; forms currently capture interest
- All CTAs and navigation now point to tools + community direction (no more "Book Consult" primary)

## Local development
Open index.html in a browser or use a simple local server:
`python3 -m http.server 8000` (or similar)

## Community records + Feedback / Backlog (owned by you — no Formspree)

All "Join the Community" buttons and the feedback form on support.html now post to the Flask backend and are stored in `licenses.db` (contacts + feedback tables).

This gives you:
- A single owned list of every email from the website/community buttons.
- Structured bug reports + feature requests that you can triage into a real backlog.
- CSV export for the contacts list.
- Simple web UI to change status/priority/notes on feedback items.

### How to use it locally (takes 30 seconds)

1. In a terminal (cd to the project folder first):
   ```
   cd "/Users/taylor/Documents/Business Website/Beacon-Digital-Solutions"
   PORT=5001 python3 app.py
   ```
   (First run creates the contacts + feedback tables automatically.)

2. In another terminal (or tab), serve the static site:
   ```
   python3 -m http.server 8000
   ```

3. Browse the site at http://localhost:8000 and use any "Join the Community" form or go to Support and submit feedback.

4. View / manage your records:
   - Community emails: http://localhost:5001/admin/contacts
     - Login: username `admin`, password = value of ADMIN_PASSWORD env var (default in code is `change-this-password-now`)
     - Use the search box and the "Export CSV" link.
   - Feedback & backlog: http://localhost:5001/admin/feedback
     - Same login.
     - Update status (new → triaged → in_progress → done / wontfix), set priority, add notes. This becomes your living backlog.

5. (Optional but recommended) Set a real admin password before using:
   ```
   export ADMIN_PASSWORD=your-strong-password-here
   PORT=5001 python3 app.py
   ```

When you later deploy the Flask app (Railway, Render, Fly.io, etc.), update the three `COMMUNITY_ENDPOINT` / `FEEDBACK_ENDPOINT` constants in index.html, thrive.html, blog.html, and support.html to point at your live backend URL (e.g. `https://beacon-backend.onrender.com/community/signup`).

The same backend binary also handles the (currently paused) Stripe + license issuance flow.

## Testing web payments + automatic licensing (local, no deploy needed) — PAUSED

(The payments/licensing automation work is paused per your request. The code is still here and was one environment variable away from working end-to-end in local testing. We can resume it in a single focused session whenever you want to ship direct web subscriptions.)

**CRITICAL:** You must run these commands from inside the folder that contains `app.py` (and `thrive.html`). The folder has a space in the name, so use quotes.

Exact sequence:

1. Open Terminal and cd into the folder:
   ```
   cd "/Users/taylor/Documents/Business Website/Beacon-Digital-Solutions"
   ```

2. Set your Stripe test secret key (replace with the full sk_test_... key you have):
   ```
   export STRIPE_SECRET_KEY=sk_test_paste_your_full_key_here
   ```

   (Optional for now — only if you have a Resend key for real emails):
   ```
   export RESEND_API_KEY=re_your_resend_key_here
   ```

3. In the **same Terminal window**, start the backend on a free port (5000 is often taken by AirPlay on macOS):
   ```
   PORT=5001 python3 app.py
   ```
   (You should see the Flask server start on port 5001. Leave this running. If it says "No module named 'flask'" or 'stripe', first run: `pip3 install flask stripe`)

4. Open a **second Terminal** window, cd to the same folder, and start the webhook forwarder (requires Stripe CLI installed once from https://stripe.com/docs/stripe-cli ):
   ```
   cd "/Users/taylor/Documents/Business Website/Beacon-Digital-Solutions"
   stripe login
   stripe listen --forward-to localhost:5001/webhook
   ```
   (Leave this running. It will print when payments/webhooks happen.)

5. To test the website form safely (recommended):
   Open a **third Terminal** (or new tab), cd, and serve the static files:
   ```
   cd "/Users/taylor/Documents/Business Website/Beacon-Digital-Solutions"
   python3 -m http.server 8000
   ```
   Then in your browser go to: http://localhost:8000/thrive.html

6. On the page, enter a test email in the "Subscribe for $8/mo" box and click the button.

7. Complete the Stripe test checkout with this card:
   - 4242 4242 4242 4242
   - Any future date (e.g. 12/34)
   - Any 3-digit CVC (e.g. 123)

8. After success:
   - Watch the `stripe listen` terminal — it should show the event.
   - Watch the `python app.py` terminal — it should print the generated license key (or send an email if you set RESEND_API_KEY).

9. For your Mac app (handle separately): add a small UI to enter the buyer's email + the license key you saw printed, then POST to:
   http://localhost:5001/activate
   with JSON body: `{"email": "the-email-you-used", "license_key": "the-key-from-logs"}`
   On success, unlock the premium features in the app.
   (You can later call /validate the same way to check if the subscription is still active.)

**If something fails:**
- Make sure every `cd` and every `python` / `export` is done after cd'ing into the exact folder above.
- Environment variables (the `export` lines) only apply to the terminal where you typed them. If you open a brand new terminal, re-do the `cd` + `export`.
- The JS on the page is already configured to call localhost:5001 for this local test (with PORT=5001).

Once this local test works, the next real step is deploying the backend to a public URL (e.g. Railway), setting the same env vars there, updating the one fetch URL in thrive.html, and adding the webhook in your Stripe Dashboard.

Full troubleshooting and production notes are in the big comment at the top of `app.py`. Paste any error messages you see and I'll help fix them immediately.
