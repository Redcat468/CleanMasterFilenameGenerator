<img src="logo.png" alt="App Logo" width="100">

# Clean Masters Filename Generator

**Purpose**
A tiny Python / Streamlit app to **simplify filename nomenclature** for deliveries of **masters** and other **post-production exports** (PAD, broadcast, platforms, QC, archive). It enforces consistent, readable names and avoids human error.

**Live app:** [https://cmf.cairnstudios.fr](https://cmf.cairnstudios.fr)

---

## Main features

* **Clean filename builder**

  * Sanitizes program/version (no special chars, spaces → `_`).
  * Date as **YYMMDD**.
  * Video aspect `1.85` / `1,85` → `185`.
  * Subtitles with **`ST<LANG>`** (e.g., `STFR`), except **`NOSUB`** (no `ST`).
  * Skips optional empty fields (no double underscores).

* **Batch entries**

  * Add multiple filenames to a list.
  * **Inline description** (placeholder, max 50 chars).
  * **Copy** button right next to each filename.
  * **Delete** row; IDs auto-**renumber** (`01`, `02`, …) to match the current list.

* **Type-colored segments**

  * Each part of the name is color-coded **by meaning** (stable colors, e.g., DATE always light-blue).

* **PDF export**

  * Neat “card” layout with subtle shadow.
  * Per-row file icon (`file-icon.png`) with the **ID under the icon**.

* **Quick file-size calculator**

  * Duration (hh\:mm\:ss) + bitrate (Mbps) → estimated **MB/GB** (+\~1% container overhead).

* **Configurable lists (`config.ini`)**

  * `FILE FORMAT` and `VIDEO FORMAT` are editable; reloaded on app restart.

---

That’s it—fast, consistent names for all your master/export deliveries.
