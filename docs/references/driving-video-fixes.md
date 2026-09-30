# Fixing the driving video instead of the prompt

Motion-transfer follows the **shapes** in the driving video: head size, face width, who stands higher. Prompt
wording like "taller", "a head taller than him" or "slimmer face" barely moved the result on real runs, while
editing the driving video did. Object-swap keeps the source geometry too. So when height or face width is
part of the brief, change `01_input/prepared.mp4` itself, then send the edited copy.

Keep the edited file next to it (`01_input/prepared_hfix.mp4`, `prepared_slim.mp4`), keep the script that made
it in `01_input/` (it is per clip), pass it as the driving video (`take add --driving …` for MCP), and keep
its length identical to `prepared.mp4` (same frame count, audio copied) so `finalize` still lines up.

## Height between two people (two-shot)
Goal: the new person clearly taller than the other one.
- Per shot, find each person's column range and their head-top/shoulder line (a few keyframes, interpolated).
- Remap rows so the taller-to-be person's body is shifted up (≈ 5–8 % of frame height) and the other one's
  down, blending over a wide horizontal band between them so no seam shows.
- **Stretch below the shoulders only.** A warp that also scales the head made the head look too big in the
  output. Keep the head at its size (or even 90 % width) and lengthen the torso/legs.
- Check the band between them frame by frame: a warp seam once showed as a thin white curve on a coat for a few
  frames at the start of a shot.
- Shots with one person, or seated people, don't need it.

## Face width (a round/broad source face)
Goal: a slimmer face than the performer's.
- Keyframe the face box (centre x, half width, top, chin) every ~6 frames through the close-ups; interpolate.
- Squeeze horizontally toward the face centre by ~10–12 % inside the box, fading to zero over ~0.8 × the half
  width outside it and a little below the chin, so the collar, scarf and frame edges don't move.
- Measured result: cheek width in the output dropped 10–17 %. It does less on low-angle or dash-cam close-ups,
  where the driving video's perspective still wins.
- Only touch the shots where the face is big; wide shots don't need it.

## Tools
numpy + scipy `map_coordinates` over raw frames piped through ffmpeg (`-f rawvideo -pix_fmt rgb24`) is enough;
write the frames back with the original audio (`-map 1:a -c:a copy`). These packages are not memegen
dependencies — install them into the venv when needed (`uv pip install numpy scipy`).

## Other things that were tried and failed
- Mask-compositing the original background people back over a motion-transfer take (to undo the redraw):
  per-cut mask gaps, one-frame flashes, flickering inpaint blobs. If unswapped people must stay exact, use
  object-swap for that clip, or accept the redraw and say so.
