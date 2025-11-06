<p align="center">
  <img src="https://kick.com/img/kick-logo.svg" alt="Kick Drop Miner Logo" width="180" />
</p>

# Kick Drop Miner

Automates watching Kick.com streams to accumulate drop time. Comes with a compact CustomTkinter UI, drives Google Chrome via Selenium, persists state locally, and gracefully pauses/resumes when a stream goes offline/online.

## Features

- Multiple links: add several Kick live URLs with a target watch time (in minutes)
- Queue runner: processes items top-to-bottom, skips finished, retries offline items later
- Smart timer: counts only while the stream is LIVE; auto-resumes after cuts
- Cookie helper: open a browser window to sign in and save cookies per domain
- Faster option: if `browser_cookie3` is installed, the app automatically imports cookies from your browsers (Chrome/Edge/Firefox) for the domain and saves them under `./cookies/`.
- Playback controls: Mute, Hide Player, Mini Player overlay, Dark Mode (remembered)
- Local persistence: `config.json`, per-domain cookies under `./cookies/`, and Chrome profile under `./chrome_data/`
- Rate‑limit friendly: caches “is live?” API checks per item to reduce request frequency

## Screenshot

<p align="center">
  <img src="https://i.postimg.cc/RV7qshx2/image.png" alt="Main window" width="600" />
</p>

## Requirements

- Windows 10/11 (Linux and macOS likely work but are not the primary target)
- Python 3.10+ (tested with 3.10)
- Google Chrome installed
- Internet access (for `webdriver-manager` to fetch a matching ChromeDriver)

## Install

1) Create and activate a virtual environment (recommended)

   - `py -3.10 -m venv .venv`
   - `.\.venv\Scripts\activate`

2) Install dependencies

   - `pip install customtkinter pillow selenium webdriver-manager undetected-chromedriver`

3) Run

   - `python main.py`
   - Or double‑click `run.bat` on Windows

## Sign In and Cookies

- Reliable drop tracking typically requires being signed in to Kick.
- In the app, click “Sign in (cookies)”. If `browser_cookie3` is installed, cookies for the selected domain are imported automatically from your browser profile.
- Otherwise, confirm to open a Chrome window for the site (e.g., `kick.com`).
- Complete login in the opened window, then click “OK” in the app to save cookies.
- Cookies are saved per domain in `./cookies/` (e.g., `cookies/kick.com.json`).
  - Tip: install `browser_cookie3` to import cookies without logging in: `pip install browser_cookie3`

## Add Links

- Click “Add link”, paste a full live URL (e.g., `https://kick.com/username`), and enter the target minutes (`0` = infinite).
- The item is added to the table with its target.

## Start the Queue

- Click “Start queue” to process items in order:
  - If a channel is offline at start, it is tagged “Retry” and skipped for now.
  - If a stream goes offline mid‑watch, the timer pauses (PAUSED) and resumes once LIVE again.
  - When the target is reached, the row is tagged FINISHED, recorded in `config.json`, and skipped on future runs.

## Playback Options

- Mute: forces the video to be muted (reapplied periodically)
- Hide Player: hides the `<video>` element while it keeps playing
- Mini Player: shows a small always‑on‑top preview and shrinks the browser window
- Dark Mode: applies a dark theme to the UI (persisted)

### Mini Player notes

- “Hide Player” takes precedence; if enabled, Mini Player isn’t shown.
- The overlay is small and muted by default, to stay out of your way.
- The main Chrome window is reduced and repositioned while Mini Player is active.

### Window visibility rules

- Hide Player ON → Chrome runs headless (fully hidden)
- Hide Player OFF + Mini Player OFF → visible normal window
- Mini Player ON → visible mini window (overrides Hide Player)
- Chrome extension (.crx) loaded → always visible (Chrome disallows headless with .crx)

## Data & Persistence

- `config.json`: app state and preferences
  - `items`: list of `{ url, minutes, finished }`
  - `chromedriver_path` (optional)
  - `extension_path` (optional, `.crx` or unpacked extension folder)
  - `mute`, `hide_player`, `mini_player`, `dark_mode` (booleans)
- `cookies/`: per‑domain cookie JSON (e.g., `kick.com.json`)
- `chrome_data/`: persistent Chrome profile used by Selenium

## Optional: Chrome Extension

- Load a `.crx` or unpacked extension folder via the “Chrome extension...” button.
- Note: when an extension is loaded, Chrome disables headless mode; the app handles this.

## Troubleshooting

- Chrome doesn’t launch / driver mismatch
  - Ensure Google Chrome is installed and up to date. `webdriver-manager` will fetch a matching driver automatically.
  - If needed, use “Chromedriver...” to pick a specific driver binary.

- Timer doesn’t increment
  - Make sure you’re signed in (use “Sign in (cookies)” to save cookies).
  - The timer only increases while the stream is actually LIVE.

- Too Many Requests (429) during login
  - The site may rate‑limit login attempts if repeated in a short period.
  - Prefer importing cookies from your browser: `pip install browser_cookie3`, then click “Sign in (cookies)”. No login page hit, no 429.
  - If you must retry login, wait 10–20 minutes between attempts. Keep the persistent profile in `chrome_data/` to avoid logging in again.

- Noisy Chrome/DevTools logs in console
  - The app reduces Chrome logging (exclude switches, lower log level). Some third‑party warnings are harmless and can be ignored.

- UI too small in Mini Player
  - Mini Player reduces the window size and overlays a small preview. Disable “Mini player” for a normal window.

- Re‑run a finished link
  - Edit `config.json` and remove the `finished` flag for that entry, or add the link again with a new target.

## Tips

- Use “Remove” to delete a selected row; it also stops a running worker for that row.
- Language and theme options are available in the UI and are remembered.

## Uninstall

- Close the app and remove the folder. This deletes `config.json`, `cookies/`, and `chrome_data/`.
