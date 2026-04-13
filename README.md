# Calibre Library Web Server

A full‑featured, self‑hosted web server for your Calibre ebook collection.  
Browse, search, filter, read, and download your books from any device with a modern browser.

## ✨ Features

- **Multi‑select filters** – Authors, Series, Tags, Formats (AND logic)
- **Powerful search** – across title, author, series, tags
- **In‑browser reading** of EPUB, PDF, TXT, CBZ/CBR, MOBI (with theme support)
- **Reading progress** – resumes where you left off (localStorage)
- **Dark / Light / Sepia / Nord / Cyberpunk …** – 8 themes + custom colours
- **Adjustable filter panel height** – drag to resize
- **Download individual books** or **ZIP collections** of filtered results
- **Responsive grid** – works on desktop, tablet, and phone
- **Settings persist** – your colour choices and panel size are saved
- **Continue reading** button on book modal if progress exists

## 📦 Dependencies

### Python packages (required)

| Package   | Purpose                          |
|-----------|----------------------------------|
| `Flask`   | Web framework                    |
| `waitress`| Production WSGI server           |
| `rarfile` | In‑browser reading of CBR files  |
| `mobi`    | In‑browser reading of MOBI files |

### Frontend libraries (loaded from CDN)

- [JSZip](https://stuk.github.io/jszip/) – for CBR/CBZ image extraction
- [Epub.js](https://github.com/futurepress/epub.js/) – EPUB reader engine

## 🚀 Installation

1. **Clone or download** this script (save as `calibre-server.py`).

2. **Install Python dependencies** (preferably in a virtual environment):

   ```bash
   pip install flask waitress
   # optional:
   pip install rarfile mobi
   ```

3. **Run the server** – point it to your Calibre library folder:

   ```bash
   python calibre-server.py --library /path/to/calibre/library
   ```

4. **Open your browser** at `http://localhost:5000`

## 🖥️ Usage

### Command‑line arguments

| Argument        | Default       | Description                                      |
|-----------------|---------------|--------------------------------------------------|
| `--library`     | `./`          | Path to your Calibre library (contains `metadata.db`) |
| `--port`        | `5000`        | Port to listen on                                |
| `--host`        | `0.0.0.0`     | Host IP (use `127.0.0.1` for local only)        |
| `--browser`     | `False`       | Automatically open a browser tab on start       |

**Examples:**

```bash
# Serve library at /media/books on port 8080, open browser
python calibre-server.py --library /media/books --port 8080 --browser

# Local only, no automatic browser
python calibre-server.py --library ~/Calibre\ Library --host 127.0.0.1
```

### Keyboard shortcuts

| Key          | Action                            |
|--------------|-----------------------------------|
| `Escape`     | Close modal or reader overlay     |

## 🧰 How it works

- Reads the Calibre `metadata.db` SQLite database.
- Serves book covers, downloads, and reading streams via Flask routes.
- The frontend is a single HTML/CSS/JS template with all filtering and reading logic.
- EPUB reading uses `epub.js` with a scrolled‑document layout (falls back to paginated if needed).
- CBZ and CBR files are unpacked client‑side (CBR is converted to ZIP on the server).
- MOBI files are converted to HTML on the server (images inlined, theme injected by client).
- TXT files are displayed as plain text with adjustable font size and saved scroll position.

## 🗂️ Supported formats

| Format | Download | Read in browser | Notes                                |
|--------|----------|----------------|--------------------------------------|
| EPUB   | ✅       | ✅             | Full reader with TOC & progress      |
| PDF    | ✅       | ✅             | Embedded PDF viewer                  |
| TXT    | ✅       | ✅             | Adjustable font, remembers scroll    |
| CBZ    | ✅       | ✅             | Lazy‑loaded images, remembers scroll |
| CBR    | ✅       | ✅             | Requires `rarfile` (auto‑converted)  |
| MOBI   | ✅       | ✅             | Requires `mobi` (converted to HTML)  |
| AZW    | ✅       | ❌             | Download only                        |
| AZW3   | ✅       | ❌             | Download only                        |
| LIT    | ✅       | ❌             | Download only                        |
| DJVU   | ✅       | ❌             | Download only                        |

## ⚙️ Customisation

- **Themes & colours** – click the ⚙️ icon in the header.  
  Presets: Dark, Light, Sepia, Nord, Solarized, Cyberpunk, Xterm, Rainbow.  
  You can also pick custom background, card, accent, and text colours.

- **Filter panel height** – drag the `⋮⋮⋮` bar at the bottom of the filter section.

- **Auto‑save settings** – enabled by default; all preferences are stored in `localStorage`.

## 📝 Notes

- The server does **not** require a separate database – it reads your existing Calibre library directly.
- All reading progress is stored in your browser’s `localStorage` (no server‑side tracking).
- Large libraries are cached on the client after the first `/api/books` call – filtering is instant.
- For CBR support, `unrar` must be installed on the system (the `rarfile` Python package calls it).
- MOBI conversion is experimental – some complex MOBI files may not render perfectly.

## 🛡️ License

This project is provided under the **MIT License**. Feel free to use, modify, and distribute it.

## 🙏 Acknowledgements

- [Calibre](https://calibre-ebook.com/) – the amazing ebook management tool.
- [Epub.js](https://github.com/futurepress/epub.js/) – HTML5 EPUB reader.
- [JSZip](https://stuk.github.io/jszip/) – client‑side ZIP handling.
- [Flask](https://flask.palletsprojects.com/) – micro web framework.

---

**Enjoy your personal Calibre cloud!**  
If you encounter any issues, please check that your library path is correct and that `metadata.db` exists.