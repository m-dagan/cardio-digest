# Cardiopulmonary literature digest

Every Friday a GitHub Actions job searches PubMed for articles entered in the previous week across 67 cardiology, respiratory and general medical journals, keeps those matching five topics — pulmonary hypertension, HFpEF, tricuspid regurgitation, invasive haemodynamics and advanced heart failure — and publishes a digest page on GitHub Pages. A small scheduler on the laptop opens that page as a popup window at 4 pm on Fridays.

Each article shows its topic flags, article type, title, authors, journal and date. Hovering expands it to show the structured-abstract conclusion (or a Claude-written summary, if enabled), the full abstract, and links to the full text (DOI), PubMed and any free PMC copy. Clicking keeps a card open; the topic chips filter the list (Alt/Option-click isolates one topic), and the drop-down selects earlier weeks.

## How the search works

PubMed is queried with the E-utilities API using the Entrez date, so ahead-of-print articles are caught when they are first indexed rather than when they reach an issue. Each topic is a PubMed query combining MeSH headings with title/abstract terms (MeSH indexing lags new records by weeks, so the free-text terms carry most of the weekly yield). Journals are matched by NLM title abbreviation. Errata, retraction notices and expressions of concern are excluded. Articles are ordered by the number of topics matched, then by article type (RCT, meta-analysis and guideline first; letters and case reports last), then by date. The search window is eight days so nothing falls between runs; anything already shown in an earlier digest is not repeated.

Every run also checks that each journal abbreviation still returns records; any that do not are listed under "Journal warnings" at the foot of the page. Topic queries, journals and settings are all in `config.yaml`.

## Setting up

1. **Create the repository.** On GitHub create a new **public** repository (for example `cardio-digest`) and upload the contents of this folder, keeping the folder structure (the `.github` folder must be included). GitHub Pages on a free account requires a public repository; the repository holds only bibliographic metadata.
2. **Turn on Pages.** Repository → Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
3. **Optional secrets** (Settings → Secrets and variables → Actions → New repository secret):
   - `NCBI_API_KEY` — a free key from your NCBI account (raises the rate limit; recommended).
   - `NCBI_EMAIL` — a contact address NCBI asks automated tools to supply.
   - `ANTHROPIC_API_KEY` — enables one- to two-sentence summaries (design, population, principal effect estimate) written by Claude from each abstract. Without it the page shows the abstract's own conclusion.
4. **First run.** Actions tab → *Weekly digest* → *Run workflow*. After a few minutes the digest is live at `https://<your-username>.github.io/cardio-digest/`. Check the journal warnings at the bottom of the page on this first run.
5. **Laptop popup.**
   - **macOS:** in Terminal, `bash local/macos/install.sh https://<your-username>.github.io/cardio-digest/`
   - **Windows:** in PowerShell, `powershell -ExecutionPolicy Bypass -File local\windows\install.ps1 -Url https://<your-username>.github.io/cardio-digest/`

   The popup opens in Chrome or Edge as a chromeless app window (falling back to the default browser). If the laptop is asleep at 4 pm it appears on wake. Each installer prints a command to test it immediately, and an `uninstall` script sits beside it.

## Timing

The search runs at 00:17 UTC on Fridays — 11:17 am in Melbourne during daylight saving, 10:17 am otherwise — leaving several hours of margin before the 4 pm popup even if GitHub delays the scheduled job. Editing `config.yaml`, the script or the page and committing to `main` triggers an immediate re-run. A manual re-run during the week reproduces the current digest rather than emptying it.

## Customising

- **Topics:** edit or add entries under `topics:` in `config.yaml` (any valid PubMed syntax; colours available: violet, teal, amber, blue, rose).
- **Journals:** add NLM abbreviations (searchable in the NLM Catalog) under any family, or set `enabled: false` on a family.
- **Popup time:** macOS — `DIGEST_HOUR=15 DIGEST_MINUTE=30 bash local/macos/install.sh <url>`; Windows — add `-Time 3:30PM`.
