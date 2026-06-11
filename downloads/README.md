# Thrive — beta downloads

The website's free-download button points here. Drop the **notarized** beta build
in this folder so the link works:

```
downloads/Thrive-beta.zip
```

The filename must match `window.BB_DOWNLOAD` in `beaconbudget.html` (currently
`downloads/Thrive-beta.zip`). If you publish via GitHub Releases or a CDN
instead, just set `window.BB_DOWNLOAD` to that URL and you can ignore this folder.

## How to produce the beta build (Mac, direct distribution — NOT App Store)

1. In Xcode: **Product → Archive**.
2. **Distribute App → Direct Distribution** (Developer ID, notarized). Wait for
   Apple notarization to finish and for the ticket to staple.
3. Export the `.app`, then zip it preserving symlinks:
   ```
   ditto -c -k --keepParent "Thrive.app" Thrive-beta.zip
   ```
4. Copy `Thrive-beta.zip` into this folder and commit, **or** upload it to a
   GitHub Release and point `BB_DOWNLOAD` at that URL.

> Notarization matters: an un-notarized direct build triggers Gatekeeper warnings
> ("cannot be opened because the developer cannot be verified") for your beta users.

## Premium flow (how the $8/mo connects to this download)

There is **one** app binary. "Free" and "Premium" are the same download — Premium
unlocks via a license key:

1. User downloads this free build and opens it (core budgeting works immediately).
2. User subscribes for $8/mo on the site → Stripe Checkout (`app.py /create-checkout`).
3. Stripe webhook (`app.py /webhook`) generates a `BB-XXXX-…` key and emails it.
4. User enters their email + key in the app: **Settings → Premium → Activate**,
   which calls `<BACKEND>/activate`. The planning modules unlock.
