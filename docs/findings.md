# What we learned running Genjutsu (2026-09-29 – 09-30)

Results from ~80 real takes on six reference clips (1–4 people, 10–30 s, vertical and horizontal), through the
REST API and the Higgsfield MCP. The official docs give no prompt guidance, so everything here was measured.
Rules that came out of it live in the skills (`.claude/skills/`) and references (`docs/references/`).

## API facts
| # | Question | Result | Applied |
|---|---|---|---|
| 1 | Inputs | `video_url` (MP4 4–30 s, longer is cut to 30 s), `image_urls` 1–8 in order, `prompt` optional ≤ 10k chars, `resolution` 480p / 720p (1080p priced by `/estimate`, never run) | `schemas.Analysis`, `prompt.lint` |
| 2 | Price | Per input second, **rounded up**, same for both modes. REST: 480p $0.318 · 720p $0.681 · 1080p $1.632. MCP: 480p 3 · 720p 7 credits per second **per variant** (`count: 2` quotes the per-variant price). Failed / `nsfw` / `ip_detected` are refunded | `endpoints.genjutsu_cost`, `memegen cost` |
| 3 | Output length | Comes back about whole seconds: 12.04 s in → ~12.0 s out; object-swap 4 s → 3.71 s, 15 → 14.71. Pad the input to the next whole second (costs nothing extra), trim back at the end | `prepare` pads, `finalize` trims |
| 4 | Pixels | Object-swap needs ≥ 409,600 px per frame (480p = 409,920) | `prepare` upscales |
| 5 | Tokens | The web app's @-mentions serialize to `<<<image_N>>>` / `<<<video_1>>>`; they bind in both modes | `prompt.lint` |
| 6 | Queue | REST and MCP jobs sometimes wait 30–40 min. A REST job once ended `canceled` on its own | `take wait`, never resubmit |
| 7 | Orphans | An MCP submit that timed out had still been created and billed | check `show_generations` before resubmitting |

## Identity: what decides the face
| # | Experiment | Result |
|---|---|---|
| 8 | Object-swap, same 4 s window: 1,400-char prompt, 227-char prompt, no prompt, the official "Ad Multiplier" contract, 480p vs 720p, one view vs three vs a whole sheet | All the same face: the **source actor's face geometry** (jaw, cheeks, head size) survives. Ad Multiplier is the same backend (same length, same look) |
| 9 | Motion-transfer, same window | The only mode where the face shape follows the reference. It redraws the scene (light, colours, other people) but keeps pose, camera and props |
| 10 | Six clips, same-window 4 s probes of both modes | Motion-transfer won on every clip with a visible face. Object-swap won once later: a high-quality single-person clip where a car was swapped too, after face-gap sentences were added |
| 11 | Identity images | One clean multi-view sheet of the person as the single image beat hero + selfies stacks; stacked selfies widened the face and one selfie's grey shirt leaked into the outfit |
| 12 | Face gap (source woman with long hair → man with short hair; braids, glasses, goatee → none) | A generic "identity from image_1" let those traits leak. One short contrast sentence per large gap removed them. Long contrast blocks caused side effects (red lips). A prop only the source has (sunglasses) needs its own "keep" sentence before the block |
| 13 | Prompt wording for height / face width in motion-transfer | "Taller", "slimmer face" barely moved anything. Editing the driving video did: a height warp fixed a two-shot; a 12 % horizontal face squeeze made cheeks 10–17 % narrower |
| 14 | Body sentence ("video_1 gives only pose/timing/camera, not body shape") + slim-build negatives | Helped on frontal/medium shots; not on low-angle or dash-cam close-ups |
| 15 | Probe vs full | A 4 s close-up probe swapped fine, the 18.5 s full run drifted back to the original face where the person gets small |

## Moderation and refusals
| # | Case | Result |
|---|---|---|
| 16 | Real broadcast footage of celebrities (REST) | `nsfw` even with only the user swapped; the same clip passed through MCP |
| 17 | Public figure image in object-swap | Twice "completed" and billed with the original face untouched (silently ignored); worked in motion-transfer |
| 18 | MCP object-swap on some clips | `ip_detected` (refunded); motion-transfer on the same clip passed |
| 19 | Crops of the source's own people sent as images (to "keep" them) | `ip_detected` |
| 20 | Prompt / look wording | Skin, neck, chest words and a tight generated close-up look tripped `nsfw`; "complexion" is safe |

## Scene side effects
| # | Case | Fix |
|---|---|---|
| 21 | Music clip | Lyric-like subtitles appeared → "no subtitles, no captions, no on-screen lyrics" |
| 22 | Motion-transfer crowd | The crowd was redrawn (different faces and ethnicity) → a crowd lock block (count, positions, look as in video_1) |
| 23 | Four people in one request | Only the one or two largest faces swap; small back-seat faces never did |
| 24 | Black-and-white segments | Came back in colour → re-grade in post |
| 25 | Compositing the original background people back over a take | Mask gaps at cuts, flicker, inpaint blobs; abandoned |

## Images (Codex)
| # | Case | Result |
|---|---|---|
| 26 | Higgsfield image models vs Codex image_gen with the character's views as references | Codex keeps face, hair and accessories; ~70–100 s per image. Higgsfield image models and Soul are not used |
| 27 | Parallel `look gen` | Used to pick up another thread's newest image from `~/.codex/generated_images`; fixed (thread folder first) |
| 28 | A generated look with a rounder face | Made the swap worse; identity on the face crop decides, not the thumbnail |
