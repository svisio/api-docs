# SportsVisio Public API docs

The hand-written public API documentation served at **https://api.sportsvisio.com/**.

```
docs/
  index.html            the whole site (one page: guides + endpoint reference)
  styles.css
  scripts.js            search, collapsible endpoint cards, copy buttons
  sportsvisio-logo.svg  sidebar logo (on-dark variant from the brand kit)
scripts/
  sync_reference.py     regenerates the endpoint cards from the OpenAPI spec
```

No build step, no dependencies, no framework. Open `docs/index.html` in a browser to
preview exactly what production serves (`python3 -m http.server -d docs` if you want
the hash links to behave).

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
- **API Reference** (the collapsible endpoint cards) — generated from the OpenAPI spec that
  `svisio/api` serves at `/api-docs/public-json`. Don't hand-edit the cards; run the sync:

  ```
  python3 scripts/sync_reference.py                      # dry run against prod
  python3 scripts/sync_reference.py --write              # apply
  python3 scripts/sync_reference.py --spec https://api.stage.sportsvisio-api.com/api-docs/public-json --write
  ```

  It rewrites every card's summary, description, parameters, request body, response codes
  and search index from the spec, adds cards (and tag groups) for new endpoints, and
  recounts the sidebar badges. Existing example response bodies are kept because they're
  real data; new cards get a schema-derived stub. Cards for endpoints that left the spec
  are reported, never deleted. Pointing it at stage documents endpoints before they reach
  prod, so do that deliberately.

The API host in examples is `https://api.sportsvisio-api.com` (prod). This repo's own
domain, `api.sportsvisio.com`, serves only these docs.

Copyright 2026 Sports Visio Inc. All rights reserved.
