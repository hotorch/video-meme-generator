# Global character assets

Each folder here is one character. Everything except this README is gitignored, so faces and likenesses never get committed.

```
<slug>/
  character.json   # name, type (me|fixed|public_figure|generated), species, bible, views[], provenance[]
  source/          # original sheets, photos, and downloaded candidates (never sent to Genjutsu)
  views/           # single-subject crops; only these are sent to Genjutsu
```

Registering a new character sheet:
```bash
memegen asset new mycat --name "Nabi" --type fixed --species cat --bible "gray tabby, yellow eyes"
memegen asset add mycat ~/Downloads/nabi-sheet.png
memegen asset crop mycat "assets/characters/mycat/source/nabi-sheet.png" \
  --box 900,40,1500,780 --name hero --shot close-up --description "close-up of the face"
memegen asset show mycat        # check the crops on views_sheet.jpg
```
Rules: docs/references/sourcing-policy.md
