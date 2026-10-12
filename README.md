# Global Power Atlas

An interactive, self-contained map and analytical dossier of geopolitical, economic, military, energy, resource and financial entities derived from the four-volume series *Geopolitics, Political Economy & Global Strategy* by Rani Miari.

The app is a static site. It has no backend, no build step at runtime, no environment variables, and no runtime fetch of data.

## Repository contents

| File | Purpose |
| --- | --- |
| `atlas.html` | The complete application: HTML, CSS and JavaScript in one file. The dataset is embedded in a `window.ATLAS_DATA` script block. |
| `index.html` | Root entry point. Redirects to `atlas.html` with relative paths, keeping any query string and `#entity` hash. |
| `data.json` | Normalised dataset (the extraction artifact). Embedded verbatim into `atlas.html`. |
| `scripts/build_atlas.py` | Merges per-volume extractions into `data.json`, validates it, and embeds it into `atlas.html`. Standard library only. |
| `.gitignore` | Excludes EPUB files, extraction scratch output, secrets and editor noise. |
| `README.md` | This document. |

## Running locally

Open `atlas.html` directly in a browser, or open `index.html`. Nothing needs to be installed.

The page loads three external resources, all over HTTPS:

- Tailwind CSS from `cdn.tailwindcss.com`
- Leaflet 1.9.4 from `cdnjs.cloudflare.com`
- Basemap tiles from keyless providers: Esri World Dark Gray Canvas (default) from `server.arcgisonline.com`, and OpenStreetMap standard tiles from `tile.openstreetmap.org` (selectable with the layer control, top right)

No API key is needed for any of these. If the map library cannot load, the page shows a notice and the dossier and search still work. If the tiles fail to load, a notice explains this, markers still render, and the layer control lets you switch basemap.

## Deploying to Vercel

1. In Vercel, choose **Add New → Project** and import the GitHub repository.
2. Framework preset: **Other**.
3. Build command: **none** (leave empty). Output directory: **none** (repository root).
4. Install command: **none**. No environment variables are required.
5. Deploy. The root URL serves `index.html`, which redirects to `atlas.html`.

The same files work unchanged on GitHub Pages.

## Using the app

- **Map:** pan and zoom with the mouse, touch or the zoom control (top left). Hover a marker for its name, or click it to open the dossier.
- **Filters:** All, Trade, Energy, Resources, Military, Finance, Geopolitics. Changing a filter updates the markers immediately. Each filter shows its entity count.
- **Search:** matches titles, types, categories, geography and connected-entity names, with partial matches (for example `hormu`). Use the arrow keys and Enter to select a result, or Escape to clear.
- **Quick select:** a dropdown of every entity in the dataset, including those that are not on the map.
- **Dossier:** a right-side panel on desktop and a bottom sheet on mobile. It shows type, categories, coordinate status, geography, economic and resource significance, strategic dynamics, vulnerabilities, connected entities, and sources with chapter, section and confidence. Connected entities are buttons that focus the map and open their own dossier. Entities without reliable coordinates explain that they are in the dataset but cannot be placed on the map.
- **Keyboard:** `Escape` closes the dossier. Focus rings are visible throughout. Deep links such as `atlas.html#strait-of-hormuz` open that entity.

## Data model

`data.json` has two top-level keys: `meta` and `entities`.

### `meta`

| Field | Meaning |
| --- | --- |
| `volumes` | The four source volumes, by number and book title. |
| `entityCount` | Number of entities in the dataset. |
| `mappedCount` | Entities with a latitude and longitude. |
| `approximateCount` | Mapped entities whose location is approximate. |
| `needsReviewCount` | Entities flagged `needsReview`. |
| `categoryCounts` | Number of entities tagged with each category. |

### Entity fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Lowercase kebab-case, unique. |
| `title` | string | Display name. |
| `type` | string | One of `country`, `region`, `city`, `port`, `chokepoint`, `trade-route`, `pipeline`, `energy-infrastructure`, `resource`, `military-site`, `financial-center`, `alliance`, `institution`, `event`, `other`. |
| `categories` | string[] | Any of `Trade`, `Energy`, `Resources`, `Military`, `Finance`, `Geopolitics`. An entity may have several. The first listed sets the marker colour and shape. |
| `latitude`, `longitude` | number or null | `null` when there is no single meaningful point, or when the location is not reliable. Such entities are not mapped. |
| `coordinateSource` | `"book"`, `"reference"` or null | `"reference"` means the point is a well-known real-world location supplied during extraction. It is not stated in the books. No entity currently has `"book"`. |
| `coordinatesApproximate` | boolean | `true` for country, region, route, pipeline and representative points. Shown as a dashed ring. |
| `geography` | string or null | Location and setting. `null` means not stated. |
| `economicResourceSignificance` | string or null | Economic, financial, energy or resource significance as the books describe it. |
| `strategicDynamics` | string or null | Strategic, geopolitical or information dynamics as the books describe them. |
| `vulnerabilities` | string or null | Risks and exposures the books identify. |
| `connectedEntities` | string[] | Ids of other entities in the dataset. Every reference resolves to a record. |
| `sources` | object[] | At least one per entity. Each has `volume`, `book`, `chapter`, `locator` (nearest section heading), `note` (a short paraphrase) and `contentKind`: `"historical"`, `"analytical"` or `"scenario"`. `"scenario"` marks hypothetical material, which the dossier labels "Hypothetical scenario". |
| `confidence` | `"low"`, `"medium"` or `"high"` | Overall confidence in the entity's extracted facts. |
| `needsReview` | boolean | `true` when a coordinate is a reference point, a figure is flagged in the source, a field is missing, or the entity appears only in scenario material. |
| `reviewNotes` | string or null | Why the entity needs review, and which fields are uncertain or missing. |

A field with no source support is `null`. The dossier shows it as "Not stated in the source volumes." It is never filled in.

## Extraction method and notes

**Source.** Four EPUB files, one per volume. Each contains eight content chapters. The text was extracted from the XHTML chapter files and read in full.

**Process.** One extraction pass per volume produced a JSON file of entity records. Each record followed the schema above, with paraphrased dossier text, provenance for every source, and explicit `null` values where the books gave no information. These per-volume files were then merged by `scripts/build_atlas.py`. The merge:

- de-duplicates entities that appear in more than one volume and unions their categories, sources and connections;
- applies a small alias table for ids that differed across volumes (`russian-invasion-ukraine-2022`, `russian-reserves-immobilization-2022`, `us-fifth-fleet-bahrain`);
- drops any connection that does not resolve to a record;
- takes the lowest confidence across merged records, and flags any entity with conflicting coordinates.

Of 258 raw records across the four volumes, 207 entities remain after merging.

**Coordinates are not from the books.** None of the four volumes gives coordinates. Every mapped position is a reference point chosen for a well-known real-world place: a city, a named strait or canal, a base, or a country's capital or representative point. These are marked `coordinateSource: "reference"`, and 93 of the 124 mapped entities are also marked approximate. Verify any position before relying on it for analysis.

**Mapped entities.** 124 of 207 entities have a reference position. The remaining 83 are shown in search and the quick-select list with a note that they have no reliable coordinates. Examples include alliances, treaties, currencies, financial systems, and events without a single location.

**Needs review.** 144 entities are flagged. Most flags come from the reference-point rule above, not from missing information. Other flags come from:

- figures the books mark as provisional or that should be checked (for example the 2026 Hormuz disruption figures, US Treasury and sovereign debt totals, the 40% EU gas share, LNG storage estimates, and chip-capacity estimates);
- attributions the books state without independent verification (for example some quotations and some disputed claims, which are carried as the books' framing and not as established fact);
- entities whose facts come only from hypothetical scenarios.

**Scenarios.** Several chapters are hypothetical. They include a Taiwan Strait quarantine, a 30-day Hormuz closure, and a capstone crisis. Facts from these are tagged `contentKind: "scenario"`, carry low confidence, and are labelled in the dossier. They are not presented as history.

**Omissions.** Passing mentions were not extracted as entities. Examples include minor names in lists, and events mentioned only in passing. The aim was entities the books treat substantively, so the dataset is a curated selection, not a complete index of every name in the books.

**Paraphrase.** Dossier text is written in the extraction's own words. Long quotations from the books are not reproduced.

## Rebuilding the dataset

The per-volume extraction files are intermediate output. They are not committed, to keep the repository to the normalised artifact. To rebuild from them:

```bash
python3 scripts/build_atlas.py --extract path/to/extract-dir --report merge_report.txt
```

`path/to/extract-dir` must contain `vol1.json` through `vol4.json` in the schema above. The script validates `data.json`, writes it, and embeds it into `atlas.html`.

To re-embed `data.json` into `atlas.html` without re-merging:

```bash
python3 scripts/build_atlas.py
```

The script exits non-zero if validation fails, for example on a dangling connection, a missing source, an unknown category, or coordinates out of range.

## Limitations

- Coordinates are reference points, not survey-grade positions. Country and region markers are representative points, not territorial centres.
- The dataset reflects what the four volumes discuss. It is not an independent check of their claims.
- Connections are those the books state or clearly imply. Many real relationships are not captured.
- Map tiles and the Tailwind and Leaflet libraries come from third-party CDNs. The app needs network access to render the basemap. The basemaps are keyless public services, which can change their terms or availability without notice.
- The app has been tested in headless Chromium against a local copy of Leaflet, with the CDN tile requests stubbed. It has not been tested against live CDN responses or on real mobile devices.
