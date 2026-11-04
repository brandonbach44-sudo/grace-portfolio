# Automatic site updates

Every hour, GitHub reads Grace's **Student Teaching** Google Drive folder (view-only robot account),
converts anything new or changed, rebuilds the pages in `site/`, and publishes them.

- **Run it now:** repo → Actions → "Update site from Google Drive" → Run workflow.
- **What goes on the site:** edit `pipeline/settings.yml` (sections, skipped folders, held files and decks).
- **Hide a folder or file without editing settings:** add `(private)` to the end of its name in Drive.
- Hand-written titles and lesson details live in `pipeline/curation.json`; new files use their file name.
