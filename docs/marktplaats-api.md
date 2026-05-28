# Marktplaats search API — field reference

> Research notes from a one-time live exploration (Playwright + direct API
> capture) on 2026-05-17. This documents the *observed* behaviour of the
> private `lrp/api/search` endpoint so the client in `marktplaats_monitor/`
> stays grounded. It is **not** an official or stable contract — code must
> degrade gracefully if fields change.

## How the site works

`marktplaats.nl` is a server-side-rendered Next.js app. Search results are
rendered into the HTML on the server; the browser does **not** fire a client
XHR to the search API on initial page load (that's why a naive Playwright
network capture saw zero `lrp/api/search` calls). The JSON endpoint below is
the canonical backend and is directly callable with `requests` + realistic
headers — this is the path the client in `marktplaats_monitor/` uses.

## Endpoint

```
GET https://www.marktplaats.nl/lrp/api/search
```

Headers that work (HTTP 200, no bot wall on the API itself):

```
User-Agent: <realistic desktop Chrome UA>
Accept: application/json, text/plain, */*
Accept-Language: nl-NL,nl;q=0.9,en;q=0.8
Sec-Fetch-Mode: cors
Sec-Fetch-Site: same-origin
Referer: https://www.marktplaats.nl/
```

### Query parameters (all confirmed working — HTTP 200)

| Param | Type | Notes |
|---|---|---|
| `query` | str | Free-text search. |
| `postcode` | str | e.g. `"1011 AB"`. Only filters when combined with `distanceMeters`. |
| `distanceMeters` | int | Radius in **meters**. With a postcode set, results narrow to that radius. |
| `limit` | int | Page size (≤ 100). |
| `offset` | int | Pagination offset (`page * limit`). |
| `sortBy` | str | `OPTIMIZED`, `SORT_INDEX`, `PRICE` (see `sortOptions` in the response). |
| `sortOrder` | str | `INCREASING` / `DECREASING`. |
| `attributeRanges[]` | str | Price filter: `PriceCents:LOWER:UPPER` (use `null` for an open bound). Confirmed with `PriceCents:10000:30000`. |
| `attributesById[]` | int | Condition codes: NEW=30, AS_GOOD_AS_NEW=31, USED=32, REFURBISHED=14050, NOT_WORKING=13940. |
| `attributesByKey[]` | str | Recency: `offeredSince:<unix_millis>`. |
| `l1CategoryId` / `l2CategoryId` | int | Category filter. Confirmed `l1CategoryId` returns category-scoped results. |

The response echoes the parsed request under
`searchRequest.originalRequest` (categories, searchQuery, attributesById,
attributeRanges, sortOptions, pagination) — useful for debugging param
construction.

## Response shape

Top-level keys: `listings`, `topBlock` (sponsored, also shown on the page),
`totalResultCount`, `maxAllowedPageNumber`, `sortOptions`, `searchRequest`,
`categoriesById`, `facets`, `correlationId`, `metaTags`, …

`sortOptions` advertised: `OPTIMIZED/DECREASING`, `SORT_INDEX/DECREASING`,
`SORT_INDEX/INCREASING`, `PRICE/INCREASING`, `PRICE/DECREASING`. Empirically
verified behaviour:

- `SORT_INDEX/DECREASING` — Marktplaats UI's "Nieuwste eerst": **strict
  chronological order** (newest first). A few DAGTOPPER paid promos may
  float to the top of page 1; filter them via `exclude_promoted`. **This is
  the monitor's default**, combined with `exclude_promoted: true`.
- `SORT_INDEX/INCREASING` — genuinely organic but **oldest-first**, static.
- `OPTIMIZED/DECREASING` — Marktplaats' *relevance* sort (the bare
  marktplaats.nl default with no sort param). Mixes recency with
  relevance — produces hundreds of date-inversions on page 1, so newer
  listings can sit below older ones. **Wrong for a new-listing monitor.**
- `PRICE/*` — price-ordered, not relevant to recency.

**Known limitation of `SORT_INDEX/DECREASING` + `exclude_promoted`**: for
ultra-broad queries (single common words with 100k+ results, e.g. `tv` by
itself), the DAGTOPPER pool is large enough that 100% of page 1 is paid
promos. Filtering them out empties the page. Narrow the query (category,
price, postcode) or accept some promo noise with `exclude_promoted: false`.

### A listing object

Keys: `itemId`, `title`, `description`, `categorySpecificDescription`,
`categoryId`, `date`, `priceInfo`, `location`, `sellerInformation`,
`pictures`, `imageUrls`, `attributes`, `extendedAttributes`, `vipUrl`,
`reserved`, `priorityProduct`, `traits`, `verticals`, …

- **`itemId`** — stable string id, e.g. `"m2400641485"`. **Use this for dedup.**
- **`priceInfo`** — `{"priceCents": 9000, "priceType": "FIXED"}`. Other
  `priceType` values: `FAST_BID`, `MIN_BID`, `RESERVED`, `FREE`, `EXCHANGE`,
  `NOTK`, `ON_REQUEST`, `SEE_DESCRIPTION`.
- **`location`** — `{cityName, countryName, countryAbbreviation,
  distanceMeters (-1000 = unknown), latitude, longitude, isBuyerLocation,
  onCountryLevel, abroad}`.
- **`date`** — Dutch relative/abbreviated string: `"Vandaag"`, `"Gisteren"`,
  `"Eergisteren"`, or `"10 mrt 24"`. Needs the vendored Dutch date parser.
- **`sellerInformation`** — `{sellerId, sellerName, isVerified, showSoiUrl,
  showWebsiteUrl}`.
- **Images — both keys exist:**
  - `pictures[]`: rich objects `{id, mediaId, url, extraSmallUrl, mediumUrl,
    largeUrl, extraExtraLargeUrl, aspectRatio}`. `url` is a template
    containing a `#` size placeholder; the `*Url` fields are concrete.
  - `imageUrls[]`: protocol-relative single URL, e.g.
    `//images.marktplaats.com/...?rule=ecg_mp_eps$_82.jpg` (needs `https:`).
  - **Decision:** prefer `pictures[0].largeUrl` → `mediumUrl`, fall back to
    `imageUrls[0]` (prefixing `https:` if it starts with `//`) for resilience.
- **`attributes`** — `[{key, value, values[]}]`. The `condition` attribute's
  value comes back **localized in Dutch** (`"Nieuw"`, `"Gebruikt"`, …), so
  filtering by condition must use the numeric `attributesById[]` request
  codes, not the response text.
- **`vipUrl`** — relative path (`/v/...`); prefix with
  `https://www.marktplaats.nl`.

## Test fixture

`tests/fixtures/search_response.json` is a trimmed (3 listings + 2 topBlock),
seller-anonymised capture preserving the full key structure above. Used for
offline client/model unit tests (no network).
