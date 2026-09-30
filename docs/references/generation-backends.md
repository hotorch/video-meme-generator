# Running Genjutsu: REST API or Higgsfield MCP

Genjutsu can be called two ways. The prompt, images and driving video are the same; only who pays and who
uploads differ. Everything before the paid step (`new → ingest → prepare → cast → route/look → prompt check →
render --dry-run`) is local and identical for both.

| | REST API (`memegen render`) | Higgsfield MCP connector |
|---|---|---|
| Needs | `HF_KEY=KEY_ID:KEY_SECRET` in `.env` (https://console.higgsfield.ai) | The Higgsfield connector added to Claude (`https://mcp.higgsfield.ai/mcp`), signed in |
| Pays with | API balance, pay as you go | The higgsfield.ai subscription's credits |
| Price (per input second, rounded up) | 480p $0.318 · 720p $0.681 · 1080p $1.632 | 480p 3 cr · 720p 7 cr (per variant) |
| 4 s probe | $1.27 | 12 credits |
| Who uploads / waits | the CLI (cached uploads, safe polling, `take wait`) | Claude, with the MCP tools (below) |
| Take bookkeeping | automatic (manifest) | `memegen take add` after each job |

`memegen doctor` says which one is ready. With no `HF_KEY`, use the MCP. Both bill whole seconds, which is why
`prepare` pads the clip to the next whole second (the padding is free and `finalize` cuts it off again).
Failed, `nsfw` and `ip_detected` runs are refunded; a finished take you don't like is not.

## REST
```bash
memegen render <unit> --dry-run                  # request + cost, nothing sent
memegen render <unit> --probe --probe-start 6.0  # 4 s at 480p
memegen render <unit> [--resolution 480p]        # full run, 720p by default
memegen take wait <unit>                         # after a timeout: resumes, never resubmits
```
A timeout never resubmits (that bills twice). Default `--budget` is $25, enough for 30 s at 720p.

## MCP (verified on real runs)
1. **Build the request locally**: `memegen render <unit> --dry-run [--probe --probe-start <s>]`. It writes
   `02_analysis/genjutsu_request.json` with `mcp_model`, the driving `video` (`01_input/prepared.mp4`, or
   `01_input/probe.mp4` for a probe), the ordered `images` and the checked `prompt`.
2. **Upload** each file: `media_upload` (filename; several at once with `files[]`) → PUT the bytes locally:
   `uv run memegen upload-put <file> "<upload_url>"` (same on Windows, macOS, Linux; it sends the
   `If-None-Match: *` header, which is part of the signature — without it the PUT fails) → `"ok": true` →
   `media_confirm` (type image / video). `media_import_url` has timed out; prefer uploads.
3. **Submit** with `generate_video` (several jobs: `generate_video_batch`):
   `{model: <mcp_model>, resolution: "480p" | "720p", prompt, medias: [{value: <video id>, role: "video"},
   {value: <image 1 id>, role: "image"}, …]}`. The order of the image medias **is** `<<<image_N>>>`.
   - Ask for the price first with `get_cost: true`. With `count: 2` the quoted price is **per variant**.
   - Pass `use_unlim: false`; the web plan's unlimited perk does not apply to MCP.
   - If the server answers with a preset suggestion (e.g. "IN THE DARK"), resend the same call with
     `declined_preset_id: <that id>`.
4. **Wait** with `jobs_wait` (long-polls ~15 s) every minute or two. Queues can take 30+ minutes.
5. **Never resubmit a job whose outcome you don't know.** A submit that timed out or returned 503 may still have
   been created and billed (one orphan job cost 140 credits). Check `show_generations` / `transactions` first.
6. **Record every job**, finished or not:
   `memegen take add <unit> <result_url> --model <mcp_model> --resolution 720p --job-id <id> [--probe] [--credits N]`
   `memegen take add <unit> --model … --resolution … --job-id <id> --status ip_detected` (refunded, but remembered)
   It downloads to `04_renders/take_N.mp4`, logs prompt + cost in the manifest and builds the compare sheet, so
   Gate 3 and `memegen finalize <unit> --take N` work exactly as with REST.
7. Check the balance before and after a batch (`balance`) and reconcile with `transactions`; report credits spent.

## Moderation and refusals (both backends)
- `nsfw`: real TV/broadcast footage of celebrities can be refused even when only the user is swapped (seen on
  REST; the same clip passed through MCP). Body/skin/exposure words in the prompt and close-up generated looks
  have also tripped it. Say "complexion", never skin/neck/chest words.
- `ip_detected` (MCP object-swap): some source clips are refused outright in object-swap; motion-transfer on the
  same clip passed. Crops of the **source's own people** sent as images also trigger it — never send them.
- **Silently ignored**: a public figure's image in object-swap can come back "completed" and billed with the
  original face untouched. One ignored probe → drop that swap (keep the original person) or try motion-transfer.
