# Release (Notes · Flow · Demo Assets)

Read this when cutting or refreshing a release, or when regenerating tracked demo
screenshots. Everyday template, script, and site work does not need it.

## Part 1 · Release notes

- Read the previous published release first for the structure, not the prose:
  `gh release view $(gh release list -R tw93/Kami --limit 1 --json tagName --jq '.[0].tagName') -R tw93/Kami`.
  Mirror its exact shape (centered logo block, `### Changelog`, `### 更新日志`,
  `### Thanks`, closing tagline blockquote). Do not rebuild the shape from memory. The
  wording of the items comes from the voice reference below; releases before V1.16.0
  carry the compressed one-line form that this section replaced.
- Title shape: `V<x.y.z> <Two-Word Codename>`, for example `V1.7.2 Cleaner Resumes`.
- Body: centered logo block + `### Changelog` (English numbered list) + `### 更新日志`
  (Chinese numbered list) + the closing tagline line.
- Bilingual and one-to-one: English item N maps to Chinese item N, with the count
  determined by distinct user-visible changes. At most five items. Fewer, denser items
  beat padding the list: group the commits by the capability a user gains, and drop
  anything that shipped to the site rather than into the package, since a site change
  is already live and needs no upgrade. Merging means folding the smaller outcomes into
  a larger one, never deleting them to hit the count.
- Shape of one item: the bold label is itself a sentence saying what changed for the
  user ("Long-doc contents pages no longer print every number as 0"), not a noun
  category ("Long-doc contents"). The text after the colon carries the specifics: what
  used to happen, what happens now, and where the new behavior stops. Name the real
  nouns, the template, the flag, the command.
- One item is one sentence, in both languages. Every Chinese item carries exactly one
  `。` at the end and chains its clauses with `，` and `、`; do not close each clause
  with its own full stop. Measured across the last three `tw93/Mole` releases, 19 of 19
  Chinese items have a single full stop and two to four commas. Length, from the same
  sample: Chinese 60 to 100 characters, median 83; English 150 to 290, median 213. A
  one-line item is the failure mode, and so is a three-sentence one.
- Measure, do not estimate. Both times these numbers were eyeballed the result was
  wrong by 30 percent, and V1.16.0 went out three times before it matched:

  ```bash
  gh release view V1.55.0 -R tw93/Mole --json body --jq .body | \
    grep -E '^[0-9]+\. ' | awk '{print length": "$0}'
  ```
- Register is plain technical writing, in both languages. The first V1.16.0 rewrite
  overcorrected from generated prose into spoken Chinese: 照单全收, 顶上, 开工,
  不好看, 不再动你已有的. Mole uses none of that. No idioms, no spoken verbs, no
  second-person instruction voice; write 解析失败 over 没成功, 端点未正确附着 over
  端点接错, 前置提问 over 开工前问. Precise technical nouns are what keeps an item
  from reading as either a press release or a chat message.
- The voice reference is `gh release view <tag> -R tw93/Mole`, not Kami's own older
  releases. A label that is an abstract category, an item with no before-and-after, and
  a subtitle that lists this release's themes are the three tells of a generated note.
  The subtitle stays the product's fixed line, the way Mole keeps one across releases.
- Close with `### Thanks` naming the issue reporters and PR contributors of this cycle
  when there are any: `gh issue list --state closed` and `gh pr list --state merged`
  filtered to the previous tag's date.
- Generate the scaffold, then rewrite it:
  `python3 scripts/draft-release-notes.py V<prev>..HEAD --version V<new> --title "<Codename>"`.
  Regroup the raw commit list into product-themed bullets; never paste commit subjects.

## Part 2 · Release flow

- `bash scripts/package-skill.sh dist/kami.zip` packages `skills/kami` as a top-level
  `kami/` skill folder; its audit gate rejects large fonts, rendered examples, tests,
  and cache files. `dist/` is ignored: the archive is never tracked, `release.yml`
  builds it from the tagged commit and uploads it.
- Any change under `skills/kami` that users should receive on Claude Desktop needs a
  new version tag; do not replace a published version with different payloads.
- Verify the published asset by content, not by page text: download the uploaded
  `kami.zip` and compare ZIP entry names plus per-entry SHA-256 digests against a
  fresh local `bash scripts/package-skill.sh` build of the same commit. File size or
  container SHA alone proves nothing.
- README and public site download links point at
  `https://github.com/tw93/kami/releases/latest/download/kami.zip`. Even small package
  changes require a new patch version so update checks and downloaded contents agree.
- Confirm remote CI is green on the exact commit about to be tagged, and read the
  `headSha` back rather than trusting the newest row:

  ```bash
  gh run list --workflow=check.yml --limit 20 \
    --json headSha,headBranch,event,status,conclusion
  ```

  A full local pass is not the verdict. V1.11.0 shipped while CI had been red for
  seven consecutive runs, because a test read `assets/examples/one-pager.pdf`, which
  is gitignored build output: it passed on any machine that had run a build and
  failed on every fresh checkout. Local green means "my working copy is fine", CI
  green means "a clean checkout is fine", and only a successful `push` run on `main`
  proves the tag candidate entered the release branch. Poll the structured status;
  piping `gh run watch` into `tail` swallows
  the exit code and reports an unfinished or failed run as passing.
- The release workflow enforces the same contract before it can create an asset:
  `TAG == V$(cat skills/kami/VERSION)`, the tag resolves to the checked-out commit, the commit is
  reachable from `origin/main`, an exact-SHA `check.yml` run from a `main` push is
  complete and successful, and, when a same-version asset already exists, the rebuilt
  archive has the same entry names and per-entry SHA-256 payloads as the published one.
  Immediately before upload, it also confirms the remote tag still resolves to the
  reviewed SHA. Keep these as hard gates; a manual dispatch is not an override.
- Create a version tag only when the maintainer explicitly asks for a versioned
  release, and tag the commit whose `skills/kami` is the final content.
- On tag push, `.github/workflows/release.yml` builds the archive from that commit and attaches it,
  creates the release if missing, refuses to replace a different same-version asset,
  and adds and verifies the house-style reactions. An idempotent rerun may keep an
  existing asset only when its entry names and payloads are identical. Do not
  `gh release create` by hand: let CI create the placeholder, then set the real title
  and notes with
  `gh release edit V<x> --title "V<x> <Codename>" --notes-file <file>`.
- If reactions are missing (older release, CI skipped), add them manually:
  `rid=$(gh api repos/tw93/Kami/releases/tags/V<x> --jq .id); for r in +1 eyes heart hooray laugh rocket; do gh api -X POST repos/tw93/Kami/releases/$rid/reactions -f content="$r"; done`.
- Reactions are part of publish completion. After the release is live, read them back
  with `gh api repos/tw93/Kami/releases/$rid/reactions --jq '.[].content'` and confirm
  all six positive reactions are present. Never add `-1` or `confused`; a negative
  reaction on our own release reads as self-deprecation.

## Part 3 · Demo screenshots

Every demo PNG under `site/assets/demos/` is 1241x1754px, the first A4 portrait page at
150dpi. Regenerate them whenever the demo's PDF changes.

Portrait documents (one-pager / letter / resume / portfolio / long-doc /
equity-report), capture page 1:

```bash
pdftoppm -r 150 -f 1 -l 1 -png <pdf> /tmp/p && cp /tmp/p-1.png <target>.png
```

Landscape slides: capture the first 2 pages, resize each to 867px high, add a 20px
parchment gap, then extend to the portrait frame:

```bash
pdftoppm -r 150 -f 1 -l 2 -png <pdf> /tmp/sl
magick /tmp/sl-1.png -resize x867 /tmp/sl1.png
magick /tmp/sl-2.png -resize x867 /tmp/sl2.png
magick -size $(identify -format '%w' /tmp/sl1.png)x20 xc:'#f5f4ed' /tmp/gap.png
magick /tmp/sl1.png /tmp/gap.png /tmp/sl2.png -append /tmp/stacked.png
magick /tmp/stacked.png -gravity Center -background '#f5f4ed' -extent 1241x1754 <target>.png
```

Before replacing a tracked PNG, confirm the source PDF used an intended primary or
listed fallback font (not DejaVu or Bitstream Vera) and that the captured page has
representative content with no placeholders or missing assets.
