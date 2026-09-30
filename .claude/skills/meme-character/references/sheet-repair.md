# Repairing a character sheet without regenerating the whole thing

Regenerating a full sheet garbles text (Korean personality notes, labels) and palettes. Regenerate only the
panels that are wrong, then paste them back into the original, so everything else stays pixel-exact.

1. **Find the panel borders**: scan rows/columns for the thin grey border lines (values ~180–215).
   ```python
   rows = [y for y in range(H) if sum(150 < px[x, y] < 215 for x in range(x0, x1, 4)) > 0.8 * len(range(x0, x1, 4))]
   ```
2. **Find the cells inside a panel**: runs of columns that contain dark pixels in the image band; find the label
   row by profiling dark pixels per row (labels sit just below the images).
3. **Generate the replacement** (one Codex call per panel keeps views consistent): four-view turnaround
   (landscape), expressions as a 2×2 grid (landscape), close-up (square).
4. **Split + fit**: for a turnaround, find each figure's column run, crop with a small margin, scale to the
   panel's image height, paste centred on the original label x-centres. For expression cells, crop each grid
   quadrant to the cell's aspect ratio around the face centre and paste bottom-aligned.
5. **Clean seams**: fill the old image area with the panel background colour first; afterwards redraw any
   border line the fill touched (sample the original line colour). Zoom into seams before calling it done.
6. Save as a new file (`… fixed.png`), record provenance ("panels X regenerated with Codex, rest original").
