# SportsVisio Public API docs

The hand-written public API documentation served at **https://api.sportsvisio.com/**.

```
docs/
  index.html   the whole site (one page: guides + endpoint reference)
  styles.css
  scripts.js   search, collapsible endpoint cards, copy buttons
```

No build step, no dependencies, no framework. Open `docs/index.html` in a browser to
preview exactly what production serves.

## Deployment

Render static site **`api-docs`**, declared in [`svisio/sv`'s `render.yaml`](https://github.com/svisio/sv)
(`publishPath: ./docs`, `autoDeploy: true`). Push to `main` and Render publishes it —
there is intentionally no `render.yaml` in this repo, so two blueprints never fight over
the same service.

History: this started as an S3 + CloudFront deployment driven by a `terraform/` directory
here (`docs.sportsvisio-api.com`). That bucket and distribution were deleted, the site moved
to a hand-deployed Vercel project, and it now runs on Render. The terraform was removed in
the same commit series that imported the live site — see git history if you ever need it.

## Editing

Edit `docs/index.html` directly. Two sections with different rules:

- **Guides** (Getting Started, Scheduling Games, Accessing Game Data) — written by hand.
  Anything you claim here must be checked against the API, not remembered. This is where a
  wrong `offset` parameter sat long enough for a consumer to build a workaround around it.
- **API Reference** (the collapsible endpoint cards) — transcribed from the OpenAPI spec that
  `svisio/api` serves at `/api-docs/public`. When the spec changes, update the matching card.
  It is currently behind the spec in places (e.g. `limit` is documented there as
  "clamped to 50").

The API host in examples is `https://api.sportsvisio-api.com` (prod). This repo's own
domain, `api.sportsvisio.com`, serves only these docs.

Copyright 2026 Sports Visio Inc. All rights reserved.
