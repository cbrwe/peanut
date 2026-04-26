# Peanut

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/cbrwe/peanut/blob/main/LICENSE)

Content-aware duplicate finder. Scans actual file content using perceptual hashing for images, video keyframes for video, audio fingerprints for audio, and SimHash for text — to catch renamed, re-encoded, and resized copies. Review everything before you delete anything.

## Install

### Easy mode — download a release

Grab a build for your platform from [Releases](https://github.com/cbrwe/peanut/releases):

- **macOS** — open the `.dmg`, drag Peanut to Applications
- **Windows** — run the installer `.exe`
- **Linux** — `chmod +x Peanut-*.AppImage && ./Peanut-*.AppImage`

That's it. Open Peanut from your Applications / Start Menu / app launcher.

### Run from source

```bash
git clone https://github.com/cbrwe/peanut.git
cd peanut
python3 -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate            # Windows
pip install -r requirements.txt

# Optional — install ffmpeg for full video + audio support
brew install ffmpeg               # macOS
# sudo apt install ffmpeg         # Ubuntu
# choco install ffmpeg            # Windows

python app.py
```

Opens at `http://localhost:8787`.

## Features

- **Perceptual hashing** catches visually identical files regardless of filename, format, or compression
- **All file types** — images, video, audio, documents, code, archives, and binary files
- **Plain-text content matching** for YAML, TOML, INI, SQL, subtitles, and dozens of other formats
- **Progressive results** stream in real-time as files are analyzed
- **Quality scoring** ranks each file by sharpness, resolution, and compression
- **HEIC support** for iPhone photos (via `pillow-heif`)
- **Lossless/lossy tags** highlight format differences between duplicates
- **EXIF metadata** displays camera, lens, GPS, and capture settings
- **Smart source detection** identifies origins (iPhone, WhatsApp, Screenshot, Google Photos, etc.)
- **Similarity percentage** shows how closely matched similar files are
- **Side-by-side comparison** with draggable slider for visual diff
- **Folder-aware recommendations** prefers organized library folders over Downloads/Desktop
- **Incremental caching** — re-scans take seconds instead of minutes
- **Keyboard shortcuts** J/K navigate, D mark, Space toggle, E open details
- **Drag and drop** folders onto the landing page

## Usage

```bash
python app.py ~/Pictures /Volumes/External/Photos    # Multiple folders
python app.py ~/Photos --no-recursive                 # Skip subfolders
python app.py ~/Photos --threshold-image 6            # Stricter matching
python app.py ~/Photos --port 9090                    # Custom port
```

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `J` / `↓` | Next group |
| `K` / `↑` | Previous group |
| `D` | Mark group duplicates for deletion |
| `Space` | Toggle group selection |
| `E` | Open detail panel |
| `Esc` | Close panels |

## How it works

**Phase 1** groups files by size and compares MD5 hashes for exact byte-for-byte matches.

**Phase 2** computes perceptual hashes for images and clusters visually similar ones using hamming distance.

**Phase 3** extracts video keyframes (via ffmpeg) and runs the same perceptual comparison across frames.

**Phase 4** fingerprints audio (via ffmpeg) and clusters by acoustic similarity.

**Phase 5** extracts text from documents (`.docx`, `.pdf`, `.odt`, `.epub`, plain-text formats, etc.) and matches via SimHash for near-duplicate detection.

Hashes cache in your platform's app-data directory so re-scans skip already-analyzed files:

- macOS: `~/Library/Application Support/Peanut/`
- Windows: `%APPDATA%/Peanut/`
- Linux: `~/.local/share/peanut/` (or `~/.peanut/` when running from source)

## Building from source

See [BUILD.md](BUILD.md) for cross-platform packaging instructions (macOS `.app`, Windows installer, Linux AppImage).

## Tech stack

| Library | Purpose |
|---------|---------|
| imagehash | Perceptual hashing |
| Pillow + pillow-heif | Image processing, EXIF, thumbnails, HEIC |
| numpy | Sharpness scoring + vectorized hamming distance |
| ffmpeg | Video keyframes + audio fingerprints |
| python-docx, PyPDF2, openpyxl, python-pptx | Document text extraction |
| Flask | Web server + Server-Sent Events streaming |
| send2trash | Cross-platform trash |
| SQLite | Hash caching |

## Disclaimer

**Peanut is provided as-is, without warranty of any kind.** You are solely responsible for verifying which files to delete. Always carefully review every duplicate group before clicking Delete.

By default, Peanut moves files to your system Trash, where they remain recoverable. The **"Permanently delete"** option bypasses Trash and is **irreversible** — use it only when you're certain.

The author assumes no responsibility for data loss, accidental deletions, corrupted files, or any other damages that result from use of this software. If your files matter to you, back them up before running any duplicate finder, including this one.

By using Peanut, you accept that all decisions about which files to keep or remove are yours.

See [LICENSE](LICENSE) for full terms.

## License

Peanut is released under the MIT License. You can use, modify, and distribute
it freely, including for commercial purposes. See [LICENSE](LICENSE) for the
full text.

## Author

Built by [Cody Browne](https://github.com/cbrwe) · [cbrwe@proton.me](mailto:cbrwe@proton.me)
