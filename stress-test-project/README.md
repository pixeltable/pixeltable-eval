# Pixeltable Stress Test Project

A suite of Pixeltable applications exercising the platform across media types,
documents, structured data, embeddings, and event-style rows. Validated on
Pixeltable 0.7.8 installed via `brew install pixeltable/tap/pxt`.

## Project Structure

```
stress-test-project/
├── apps/
│   ├── audio/          # Audio transcription + AI analysis (OpenAI, chat)
│   ├── video/          # Video -> audio extract -> transcription -> summary
│   ├── image/          # Vision analysis via chat_completions image_url parts
│   ├── doc/            # pxt.Document + document_splitter chunk views
│   ├── data/           # Arithmetic computed columns + classification UDFs
│   ├── search/         # EmbeddingIndex + similarity query routes
│   └── realtime/       # Event rows + derived metrics + chat analysis
├── pixeltable.toml
└── README.md
```

## What each app exercises

| App | Tables / views | Key features |
|-----|----------------|--------------|
| audio | audio_files, podcasts | `openai.transcriptions` on `pxt.Audio`, `chat_completions` |
| video | video_files, lectures | `video.extract_audio`, `video.get_duration`, `openai.transcriptions`, chat |
| image | images, product_images, screenshots | `image.width/height/get_metadata`, vision messages |
| doc | documents + document_chunks, reports + report_sections, contracts + contract_clauses | `document_splitter` views (`separators='paragraph'`) |
| data | sales_data, customers, inventory | arithmetic operators, `@pxt.udf` classifiers + guards, chat |
| search | knowledge_base + kb_chunks, faq, products | `pxt.EmbeddingIndex` with `embeddings.using(...)`, `.similarity()` query routes |
| realtime | sensor_data, network_events, user_activity | arithmetic, `string.len`, UDFs, chat |

## Verified API notes (0.7.8)

Works:
- `pxtf.openai.transcriptions(audio_col, model='whisper-1')` - OpenAI transcription
  API, requires an Audio column and `OPENAI_API_KEY`. Extract the text with
  `.text`. (`pxtf.whisper.transcribe` is a different function: it runs the local
  `openai-whisper` package, needs `torch`, and takes local model names like
  `base.en` - `whisper-1` is not valid there.)
  For video: `audio = pxtf.video.extract_audio(video)` first (uses PyAV, bundled).
- Vision: pass content parts in messages -
  `{'image_url': image_col, 'type': 'image_url'}` plus `{'text': ..., 'type': 'text'}`.
- `pxtf.openai.embeddings(input, model='text-embedding-3-small')` and
  `pxt.EmbeddingIndex(column=<colref>, string_embed=embeddings.using(model=...))`.
  Index column must be a column ref, not a string name.
- Views in model syntax:
  `class Chunks(TableModel, name='x', base=Docs, iterator=document_splitter(Docs.doc, separators='paragraph'))`.
  Iterator outputs (e.g. `text`) are referenceable in the class body.
- `pxtf.image.width/height/get_metadata`, `pxtf.video.get_duration`,
  `pxtf.string.len`, plain `* / + -` arithmetic on columns, `@pxt.udf`.

Does not exist / needs extra deps:
- `pxtf.math.multiply/divide/add`, `pxtf.string.if_else` - use operators and UDFs.
- `pxtf.image.get_width/get_height` - it is `width`/`height`.
- `document_splitter(..., separators='sentence')` and `string_splitter` need `spacy`.
  `'paragraph'`/`'page'`/`'heading'`/`'token_limit'`/`'char_limit'` need no spacy
  (`token_limit` needs `tiktoken`).
- `video.scene_detect_*` needs `pip install scenedetect`.
- `pxt.Parameter` does not exist. Query endpoints are instead `@pxt.query`
  functions exposed with `router.add_query_route(path=..., query=..., method=...)`
  - see the search app.

Gotcha: dict literals inside computed-column expressions are stored with keys
normalized alphabetically. Write keys alphabetically (e.g.
`{'text': ..., 'type': 'text'}`, `{'image_url': ..., 'type': 'image_url'}`)
or `pxt service update` reports a FATAL schema diff it cannot reconcile.
The apps write content-part dicts in alphabetical key order for that reason.

## Setup

```bash
brew install pixeltable/tap/pxt

# AI columns need openai in the Homebrew virtualenv
/opt/homebrew/Cellar/pxt/0.7.8/libexec/bin/python -m pip install openai

# Credentials for chat/transcription/embeddings columns (required at insert time)
export OPENAI_API_KEY='your-api-key'
```

## Validate and deploy each app locally

```bash
cd stress-test-project

pxt schema check apps/<app>/app.py
pxt schema update apps/<app>/app.py stress_<app> -f
pxt service update apps/<app>/app.py stress_<app> -f

pxt service list   # shows every running route and port
```

Suggested service names (check `pxt service list` for ports - they are assigned
dynamically):
- `stress_audio`: POST /audio, /podcasts
- `stress_video`: POST /video, /lectures
- `stress_image`: POST /images, /products, /screenshots
- `stress_doc`: POST /documents, /reports, /contracts
- `stress_data`: POST /sales, /customers, /inventory
- `stress_search`: POST /knowledge, /faq, /products (insert);
  POST /knowledge/search, /faq/search, /products/search (query)
- `stress_realtime`: POST /sensors, /network, /activity

## Inserting data

Routes take JSON; media fields are file paths on disk:

```bash
curl -X POST http://127.0.0.1:PORT/sales \
  -H 'Content-Type: application/json' \
  -d '{"product_id": "P1", "sale_date": "2025-01-15", "quantity": 5,
       "price": 250.0, "region": "West"}'
# -> {"id": "...", "revenue": 1250.0, "size": "LARGE"}
```

The search app also serves similarity queries over its embedding indexes:

```bash
curl -X POST http://127.0.0.1:PORT/products/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "wireless noise cancelling headphones", "limit": 5}'
# -> {"rows": [{"name": "...", "similarity": 0.83, ...}, ...]}
```

Verified end-to-end without credentials: `/sales` (arithmetic + UDF) and
`/sensors` (arithmetic + UDF) insert and compute correctly. Any route whose
table has chat/transcription/embedding columns (including the search routes,
which embed the query string) needs `OPENAI_API_KEY` or it returns
403 MISSING_CREDENTIALS on insert/query.

## Cloud deployment

Target: `pxt://pixeltable:new-db` (registered in `pixeltable.toml`).

```bash
export PIXELTABLE_API_KEY='your-cloud-api-key'

# AI secrets: org scope failed with a server 500; db scope works
pxt secret set pxt://pixeltable:new-db OPENAI_API_KEY='sk-...'

pxt db update pxt://pixeltable:new-db -f     # uploads project + builds image from requirements.txt
pxt schema update apps/<app>/app.py pxt://pixeltable:new-db -f
pxt service update apps/<app>/app.py pxt://pixeltable:new-db -f
```

Deployed and verified:
- `data` app: POST `/sales/sales`, `/customers/customers`, `/inventory/inventory`
- `realtime` app: POST `/sensors/sensors`, `/network/network`, `/activity/activity`
- Base URL `https://pixeltable-new-db.svc.pxt.run`, auth via
  `Authorization: Bearer <PIXELTABLE_API_KEY>`. Route path is
  `/<service-name>/<route>`: the `sales` service's `/sales` route is `/sales/sales`.
- Verified end-to-end: computed columns and `chat_completions` run on cloud
  workers; `string.format` prompts deliver real row values to the model.

Blocked (cloud-side, not client):
- `audio`, `video`, `image`, `doc`, `search` schemas fail with
  `502 get_bucket_credentials` on the `home` bucket. Only tables with media
  columns (Audio/Video/Image/Document) hit it; non-media tables deploy fine.
  Retried over ~30 min including a db restart; persistent. Platform issue.

## Round 2: 10 more apps, deeper paths

| App | Tables / views | New paths exercised |
|-----|----------------|---------------------|
| frames | videos + frames view | `frame_iterator(num_frames=4)`, view-level vision cols |
| clipper | podcasts + segments view | `audio_splitter(duration,overlap)`, `openai.transcriptions` |
| crud | products | `add_update_route`, `add_delete_route`, `add_compute_route`, `BtreeIndex`, `pxt get/revert` |
| query | articles | `@pxt.query` + `add_query_route` (POST + GET), `similarity()` |
| uploads | photos | `uploadfile_inputs=` multipart, `return_fileresponse` image out |
| jsonlab | orders | `json.keys/len/get/contains/dumps`, `map`/`sort` over Json arrays |
| timeseries | metrics | `timestamp.date/hour/weekday/month`, `group_by` + `count/sum/max` + custom `@pxt.uda` |
| pipeline | docs + paras + sentences | `string_splitter('sentence')`, nested iterator views (view over view) |
| toolchat | kb + questions | `@pxt.query` similarity route; tools tested separately (see wedge) |
| tiles | maps + tiles view | `tile_iterator(tile_size)`, per-tile vision |

Verified live: 4 frames from `num_frames=4`; 3 segments from `duration=30,overlap=5` on 75s audio; 12 tiles from a 1600x1200 image; update/delete/compute/query routes; multipart upload + JPEG `FileResponse`; `group_by` + `p90` uda in a GET route; `pxt.tools`/`invoke_tools`/`tool_choice` executed a real tool call (`{'count_words': [5]}`); nested iterator views (doc->paras->sentences); `pxt errors`, `recompute --errors-only`, `history`, `idxs`, `get`, `rename`, `mv`, `revert`, `config`, `status`, `health`, `shell`, `localproxy` lifecycle, `service diff/restart/check/example/run`.

## New findings

- **`tools=` in an app-file computed column permanently wedges the table** (PXT-1429 variant). `pxt.tools()` serializes tool-spec dicts as literals -> JSONB reorders their keys -> every future `schema/service update` is FATAL. Unlike user-authored dicts, there is no client-side workaround; and the FATAL diff blocks the app's *other* services too ("2 blocked"). Via the Python API (`create_table` + `add_computed_column`) the identical tools pipeline runs fine.
- **`pxt.tools(ModelQuery)` fails at file load**: "A query over model `KB` cannot be serialized". The same `@pxt.query` used directly in `add_query_route` serializes and executes correctly. Eager vs deferred evaluation differs by route type.
- **`add_compute_route` is unusable with partial `inputs`** (PXT-1402): the route only accepts fields listed in `inputs` but row validation still demands every required non-computed column, so it can never accept what it requires. Workaround: list all required columns in `inputs`.
- **`pxt service run` prints a success banner regardless of port bind**: with another service on :8000 it still printed "Pixeltable is running on http://127.0.0.1:8000".
- **`pxt service logs` on local services 400s**: "not supported; the log is at ~/.pixeltable/logs/services/<name>.log". The file exists and has content; the CLI just won't tail it.
- **`pxt mv` moves a table *into* an existing directory**, it does not rename across dirs: `mv a/t b/` -> `b/t`; `mv a/t b/u` fails asking for `create_dir('b/u')`.
- **`pxtf.whisper.transcribe` needs local `openai-whisper` (torch)**; `pxtf.openai.transcriptions` uses the API and needs only `openai` + key. Easy to confuse.
- **`document_splitter` needs `spacy` even for `separators='paragraph'` on `.txt`; `.md` needs `mistune`.** Fixed via `/opt/homebrew/Cellar/pxt/0.7.8/libexec/bin/python -m pip install spacy mistune` + `spacy download en_core_web_sm`.
- **`@pxt.udf` cannot be defined in `__main__`** (script or `-c`): must live in an importable module. The error message says so clearly.
- **Services don't pick up env changes after start**: set `OPENAI_API_KEY`, restart daemon, then `pxt service restart` is still required. Persisted fix: `[openai] api_key` in `~/.pixeltable/config.toml`.
- **`recompute --errors-only` prints "N rows, 0 computed values"** while actually clearing the error cells; the count phrasing is confusing.
- **`txt` -> `document_splitter('paragraph')` produced 1 chunk for a 3-paragraph file** (txt has no structure); the downstream `string_splitter('sentence')` still emitted 3 rows. Nested iterator views did not deadlock (PXT-1373 not reproduced).
- **Insert routes drop request fields not listed in `inputs`** (insert-route twin of PXT-1402): a required column omitted from `inputs` is dropped from the parsed body, so the route can never succeed - `MISSING_REQUIRED` on every call. `doc` app's `/reports` (missing `report_date`) and `/contracts` (missing `contract_type`) were dead this way; fixed by listing all required columns. Rule: `inputs` must cover every required non-computed column.
- **`document_splitter(separators='paragraph')` does not support PDF** - insert fails atomically with `UNSUPPORTED_OPERATION` (no base row, no error cells, whole insert rolls back). For PDF use `'page'`, `'token_limit'`, or `'char_limit'` (the latter two need `limit=`). `.md`/`.txt` paragraph splitting works.
- **Changing a route's `inputs` is destructive**: `pxt service update` reports "route will be replaced: inputs changed [destructive]" and requires `--allow-destructive`.

## Round 3 (2026-09-18): full live pass, all 17 apps

All 17 apps deployed into one catalog and every route exercised over HTTP with
generated media (TTS audio via `say`, ffmpeg video, PIL images, .md/.txt/PDF docs).
Zero error cells across all 38 tables/views afterward.

- `openai.transcriptions` on TTS `.m4a` and on `extract_audio` of an `.mp4`: accurate transcripts; downstream `chat_completions` sentiment/summary/topics/chapters all returned.
- Vision columns read generated images correctly (identified drawn headphones, read a fake settings UI incl. toggle states, described map tiles).
- Iterators: `frame_iterator(num_frames=4)` -> 4 rows+captions; `audio_splitter(30,5)` on 71s audio -> 3 segments+transcripts+gists; `tile_iterator(512)` on 1600x1200 -> 12 tiles+notes; `document_splitter('paragraph')` -> 5 chunks (.md) / 1 chunk (.txt); nested `string_splitter('sentence')` -> 6 rows.
- `EmbeddingIndex` + `.similarity()` routes ranked correctly (headphones 0.48 > boots 0.23; billing 0.68 > shipping 0.21); `where(sim > 0.4)` filtered weak matches out of `/articles/search`.
- `@pxt.uda` p90 + `group_by` GET route; JSON `keys/len/get/contains/map/sort`; `BtreeIndex` + insert/update/delete/compute routes; multipart `uploadfile_inputs` + 256px JPEG `FileResponse`.
- `batch_update` quirk: updating only *some* of a computed column's dependencies nullifies it (computed cols evaluate against the update row, not merged with stored values). Routes that list all dependency columns in `inputs` (as crud does) are unaffected.

## Cloud round 2 (2026-09-18)

- `PIXELTABLE_API_KEY` works persisted as `api_key` under `[pixeltable]` in `~/.pixeltable/config.toml`; the CLI reads it without the env var. Note: exporting `PIXELTABLE_API_KEY` inline for one command triggers a daemon restart on the next un-exported command (env-diff respawn, PXT-1394 behavior).
- The `home`-bucket `get_bucket_credentials` 502 is resolved: `pxt schema update apps/audio/app.py pxt://pixeltable:new-db` created `audio_files` and `podcasts` with media columns.
- Cloud schema updates require the app file to already be in the db's uploaded project archive: new files get BLOCKED with "run pxt db update first". `pxt db diff` shows the pending upload, `pxt db update -f` applies it.
- `pxt db update` needs `-f` non-interactively (same as `revert`); without it the command prints the plan and exits 3.
- **Platform incident (PXT-1440)**: mid-session, all db-scoped Management API calls began returning `502 ... 500` (`get_db`, `update_db`, `start_db`, `stop_db`, `restart_db`, `get_logs`, `list_services`, `build-image`, `set_secret`, eventually `list_orgs`), and both pods' PXT/1.0 tunnels returned `503 Service Unavailable` (`pxt ls`, `service update`, anything touching the catalog). Edges still enforce auth (401 on `/healthz`). `db list` reports AVAILABLE throughout; `md_version` reads 0. No client-side recovery; first `db update -f` correlates with the onset but both dbs died simultaneously, so likely a fleet-side wedge.
- Daemon port isolation: `PXT_PORT=<port>` runs an independent daemon with its own pidfile. Useful when another project's pxt daemon (e.g. pixelbot's venv) holds the default 22089.

Cloud gotchas hit:
- `requirements.txt` must include `pixeltable==<version>` itself: the image
  build treats it as the full dep set; without it pods crash with
  `ModuleNotFoundError: No module named 'pixeltable'`.
- f-strings in computed columns bake column *names*, not values. Use
  `pxtf.string.format('... {} ...', col)` for prompts (verified via a cloud
  response echoing real row values).
- Changing a computed column's expression is irreconcilable; `pxt drop` the
  table and re-run `schema update` (no migration path for expression edits).
- After `pxt secret set`, `pxt db restart` picks up secrets for tables and
  `pxt service update` restarts service pods onto the new image.
- Local `~/.pixeltable/pgdata` metadata was stamped v35 while actually at v56
  schema, crashing every command on a duplicate `lock_dummy` migration.
  Fixed by setting `systeminfo.md->>'schema_version'` to the real version via
  the unix socket at `~/.pixeltable/pgdata/.s.PGSQL.5432`.
