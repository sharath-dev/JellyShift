# JellyShift

Automatically move qBittorrent downloads into your Jellyfin library with the correct folder structure and filenames.

## What it does

When a torrent finishes downloading, qBittorrent calls JellyShift with the content path. JellyShift:

1. Classifies the download as a movie or TV show (using qBittorrent categories, or by detecting episode codes like `S01E01` in the name).
2. Looks up the canonical title and year on TMDB.
3. Moves video files (and subtitles / NFO files) into your Jellyfin library under the correct naming scheme.
4. Sends anything it cannot confidently match to a review folder with a JSON manifest.

### Output paths

```
D:/Media/Movies/
  The Dark Knight (2008)/
    The Dark Knight (2008).mkv

D:/Media/Shows/
  Breaking Bad (2008)/
    Season 01/
      Breaking Bad - S01E03 - ...And the Bag's in the River.mkv
```

## Requirements

- Python 3.10 or newer
- A free [TMDB API key](https://www.themoviedb.org/settings/api)
- qBittorrent (any platform)

## Installation

```bash
cd JellyShift
python3 -m venv .venv

# Windows (Command Prompt / PowerShell)
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install .
```

For the Web UI, install the optional web dependencies:

```bash
pip install ".[web]"
```

The `jellyshift` command is now available inside the venv.

## Configuration

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your paths and TMDB API key:

| Field | Description |
|---|---|
| `tmdb_api_key` | Your TMDB v3 API key (or set `TMDB_API_KEY` env var) |
| `movies_root` | Jellyfin Movies library root |
| `tv_root` | Jellyfin TV Shows library root |
| `review_dir` | Where unmatched items are parked |
| `category_map` | Maps qBittorrent category names to `movie` / `tv` |
| `tmdb_similarity_threshold` | 0.0–1.0 match confidence (default 0.6) |

Use paths that Jellyfin and JellyShift can both access on the machine where JellyShift runs:

| Where JellyShift runs | Example paths in `config.yaml` |
|---|---|
| Windows (native) | `D:/Media/Movies`, `D:/Media/Shows` |
| WSL | `/mnt/d/Media/Movies`, `/mnt/d/Media/Shows` |
| Linux / macOS | `/srv/media/Movies`, `/Volumes/Media/Shows` |

**Recommended:** Create two qBittorrent categories — `movies` and `tv` — and assign them when you add a torrent.

---

## qBittorrent hook setup

All setups use the same qBittorrent UI:

1. Open qBittorrent → **Options → Downloads**.
2. Enable **"Run external program on torrent completion"**.
3. Paste the command for your platform (see below).
4. Assign a category (`movies` or `tv`) when adding torrents.

### qBittorrent tokens

| Token | Meaning |
|---|---|
| `%F` | Full path to the content (file or folder) |
| `%N` | Torrent name |
| `%L` | Category label (empty string if unset) |

Keep the quotes around `%F`, `%N`, and `%L` exactly as shown — they protect spaces and special characters like `[` in release names.

---

### Choose your setup

| qBittorrent runs on | JellyShift runs on | Section |
|---|---|---|
| Windows | Windows (same machine) | [Windows (native)](#windows-native) |
| Windows | WSL (same machine) | [Windows + WSL](#windows--wsl) |
| Linux | Linux (same machine) | [Linux](#linux) |
| macOS | macOS (same machine) | [macOS](#macos) |

---

### Windows (native)

Install Python and JellyShift on Windows. qBittorrent passes Windows paths (`D:\...`) directly — no conversion needed.

**Completion command** (adjust paths to your install):

```
C:\Users\<you>\JellyShift\.venv\Scripts\jellyshift.exe --config C:\Users\<you>\JellyShift\config.yaml "%F" --torrent-name "%N" --category "%L"
```

**`config.yaml` paths** — use Windows-style paths:

```yaml
movies_root: "D:/Media/Movies"
tv_root: "D:/Media/Shows"
review_dir: "D:/Media/Review"
```

**Test manually:**

```cmd
C:\Users\<you>\JellyShift\.venv\Scripts\jellyshift.exe --config C:\Users\<you>\JellyShift\config.yaml "D:\Downloads\movie.mkv" --category movies --dry-run
```

---

### Windows + WSL

Use this when qBittorrent runs on Windows but you want JellyShift in WSL — for example, Jellyfin also runs in WSL, or you prefer Linux paths under `/mnt/`.

JellyShift includes two helper scripts:

| File | Purpose |
|---|---|
| `run-hook.cmd` | Windows wrapper — logs to `%TEMP%\jellyshift-hook.log`, calls WSL with correct quoting |
| `run-hook.sh` | WSL script — converts `D:\...` paths via `wslpath`, invokes `jellyshift` |

#### 1. Install JellyShift inside WSL

```bash
cd ~/projects/JellyShift   # or wherever you cloned it
python3 -m venv .venv
source .venv/bin/activate
pip install .
cp config.example.yaml config.yaml
# edit config.yaml — use /mnt/ paths (see below)
chmod +x run-hook.sh
```

#### 2. Configure paths for WSL

```yaml
movies_root: "/mnt/d/Media/Movies"
tv_root: "/mnt/d/Media/Shows"
review_dir: "/mnt/d/Media/Review"
```

Map drive letters: `D:\` → `/mnt/d/`, `C:\` → `/mnt/c/`, etc.

#### 3. Edit `run-hook.cmd`

Open `run-hook.cmd` in the repo root and set three variables at the top (run `wsl -l -v` and `wsl whoami` to find the values):

```bat
set "WSL_DISTRO=Ubuntu-22.04"
set "WSL_USER=<your-wsl-username>"
set "HOOK_SH=/home/<your-wsl-username>/projects/JellyShift/run-hook.sh"
```

`run-hook.sh` resolves its own directory automatically — only `HOOK_SH` in `run-hook.cmd` needs to point at your clone location.

Optionally set `JELLYSHIFT_USER` in your WSL environment if qBittorrent launches WSL as root (root cannot write to `/mnt/*` drives).

#### 4. qBittorrent completion command

Point qBittorrent at the Windows wrapper (use whichever path form works on your system):

```
\\wsl.localhost\Ubuntu-22.04\home\<you>\projects\JellyShift\run-hook.cmd "%F" "%N" "%L"
```

Or copy `run-hook.cmd` to a native Windows location:

```
C:\Tools\JellyShift\run-hook.cmd "%F" "%N" "%L"
```

**Do not** call `wsl.exe ... run-hook.sh` directly from qBittorrent — Windows-side argument quoting (especially brackets in release names) often breaks silently. Always use `run-hook.cmd`.

#### 5. Test manually

From **Windows Command Prompt**:

```cmd
\\wsl.localhost\Ubuntu-22.04\home\<you>\projects\JellyShift\run-hook.cmd "D:\Downloads\test.mkv" "test.mkv" "tv"
```

From **WSL** (bypasses the Windows wrapper):

```bash
~/projects/JellyShift/run-hook.sh 'D:\Downloads\Show.S01E01.mkv' 'Show.S01E01.mkv' 'tv'
```

#### WSL troubleshooting logs

| Log | Location | Shows |
|---|---|---|
| Windows wrapper | `%TEMP%\jellyshift-hook.log` | Whether qBittorrent reached WSL |
| WSL bootstrap | `/tmp/jellyshift-hook.log` | Whether bash started, which user ran |
| Hook detail | `<JellyShift>/logs/hook.log` | Path conversion, jellyshift exit code |
| JellyShift | `<JellyShift>/logs/jellyshift.log` | TMDB lookup, file moves |

If qBittorrent logs "Running external program" but nothing appears in any log, the Windows wrapper was never reached — check the command path in qBittorrent settings.

---

### Linux

Install JellyShift on the same machine that runs qBittorrent.

**Completion command** (adjust paths):

```
/home/<you>/JellyShift/.venv/bin/jellyshift --config /home/<you>/JellyShift/config.yaml "%F" --torrent-name "%N" --category "%L"
```

Or use the included shell wrapper:

```
/home/<you>/JellyShift/run-hook-linux.sh "%F" "%N" "%L"
```

Make it executable first: `chmod +x run-hook-linux.sh`

**`config.yaml` paths** — use native Linux paths:

```yaml
movies_root: "/srv/jellyfin/Movies"
tv_root: "/srv/jellyfin/Shows"
review_dir: "/srv/jellyfin/Review"
```

**Test manually:**

```bash
jellyshift --config ~/JellyShift/config.yaml "/home/you/Downloads/movie.mkv" \
  --category movies --dry-run
```

> **Note:** The bundled `run-hook.sh` is designed for WSL (it calls `wslpath` to convert Windows paths). On native Linux, call `jellyshift` directly or write a thin wrapper — do not use `run-hook.sh`.

---

### macOS

Same approach as native Linux — qBittorrent passes macOS paths directly.

**Completion command** — call `jellyshift` directly (adjust paths):

```
/Users/<you>/JellyShift/.venv/bin/jellyshift --config /Users/<you>/JellyShift/config.yaml "%F" --torrent-name "%N" --category "%L"
```

Or use the shared Linux/macOS wrapper:

```
/Users/<you>/JellyShift/run-hook-linux.sh "%F" "%N" "%L"
```

Make it executable first: `chmod +x run-hook-linux.sh`

**`config.yaml` paths:**

```yaml
movies_root: "/Users/<you>/Media/Movies"
tv_root: "/Users/<you>/Media/Shows"
review_dir: "/Users/<you>/Media/Review"
```

If your library is on an external drive:

```yaml
movies_root: "/Volumes/Media/Movies"
tv_root: "/Volumes/Media/Shows"
```

**Test manually:**

```bash
jellyshift --config ~/JellyShift/config.yaml "/Users/you/Downloads/movie.mkv" \
  --category movies --dry-run
```

> **Tip:** If qBittorrent cannot find the binary, use the full absolute path to `.venv/bin/jellyshift` in the completion command. Avoid paths with spaces unless they are quoted.

---

## Manual / test run

```bash
# Dry-run a movie folder without moving anything
jellyshift --config config.yaml "/path/to/download" --category movies --dry-run

# Process a real TV episode
jellyshift --config config.yaml "/path/to/Show.S01E03.mkv" --category tv
```

Add `--dry-run` to preview moves. Add `--force` to overwrite an existing file at the destination.

## Review queue

Items in `review_dir` each have a `.manifest.json` sidecar:

```json
{
  "original_path": "/path/to/Some.Weird.Release.mkv",
  "moved_to": "/path/to/Review/Some.Weird.Release.mkv",
  "reason": "no episode code in Some.Weird.Release.mkv",
  "torrent_name": "Some.Weird.Release.1080p"
}
```

Re-run after fixing:

```bash
jellyshift --config config.yaml "/path/to/Review/Fixed.Show.S01E01.mkv" --category tv --force
```

## Web UI

JellyShift includes a local web interface for browsing invocation history, triaging the review queue, and editing all configuration (paths, TMDB key, category map, hook/WSL settings, and more).

Default URL: **http://127.0.0.1:8765**

| Page | URL | What it does |
|---|---|---|
| Invocations | `/` | List every JellyShift run; click one for media summary + logs |
| Review | `/review` | Rename, add notes, re-process, or delete review items |
| Settings | `/settings` | Edit all `config.yaml` and hook variables |

---

### 1. Install Web UI dependencies

From your JellyShift folder with the venv activated:

```bash
pip install ".[web]"
```

This adds FastAPI, Uvicorn, Jinja2, and ruamel.yaml on top of the base install.

---

### 2. Configure (optional)

The Web UI reads the same `config.yaml` as the CLI. Optional settings in [`config.example.yaml`](config.example.yaml):

```yaml
web:
  host: 127.0.0.1   # use 0.0.0.0 to allow LAN access
  port: 8765

hook:
  wsl_distro: Ubuntu-22.04
  wsl_user: sharath
  hook_sh: null     # null = auto
```

You can also change host, port, and all other settings from **Settings** in the browser after the server is running.

---

### 3. Start the server

**Quick test (foreground)** — stops when you close the terminal:

```bash
jellyshift serve --config config.yaml
```

Override bind address:

```bash
jellyshift serve --config config.yaml --host 127.0.0.1 --port 8765
```

**Persistent background** — keeps running after you close the terminal:

| Setup | Command |
|---|---|
| WSL / Linux with systemd | `jellyshift service install --config config.yaml` |
| WSL without systemd | `jellyshift service install --config config.yaml --background` |

Check whether it is running:

```bash
jellyshift service status --config config.yaml
```

Stop or remove:

```bash
jellyshift service stop --config config.yaml      # stop
jellyshift service restart --config config.yaml   # restart (systemd only)
jellyshift service uninstall --config config.yaml # stop and remove
```

---

### 4. WSL setup (recommended for Windows + WSL users)

If JellyShift runs in WSL, use these steps so the Web UI survives closing your terminal and optionally starts on Windows login.

#### 4a. Enable systemd in WSL

Edit `/etc/wsl.conf` inside WSL (requires `sudo`):

```ini
[boot]
systemd=true
```

From **Windows** PowerShell or Command Prompt:

```cmd
wsl --shutdown
```

Re-open WSL, then install the service:

```bash
cd ~/projects/JellyShift
source .venv/bin/activate
jellyshift service install --config config.yaml
```

Verify:

```bash
jellyshift service status --config config.yaml
journalctl --user -u jellyshift-web -f
```

#### 4b. If you see "Failed to connect to bus"

Systemd is not running yet. Either complete step 4a above, or use background mode (no systemd, no auto-restart on reboot):

```bash
jellyshift service install --config config.yaml --background
```

Logs for background mode: `<JellyShift>/logs/webui.log`

#### 4c. Keep WSL running when terminals are closed

Add to `%USERPROFILE%\.wslconfig` on **Windows** (create the file if it does not exist):

```ini
[wsl2]
vmIdleTimeout=-1
```

Run `wsl --shutdown` once after saving, then reopen WSL.

#### 4d. Start Web UI on Windows login (optional)

After the service is installed inside WSL:

1. Edit `WSL_DISTRO` and `WSL_USER` in [`run-web-service.cmd`](run-web-service.cmd) — use the same values as in [`run-hook.cmd`](run-hook.cmd).
2. Double-click or run [`install-web-autostart.cmd`](install-web-autostart.cmd) once from Windows. This registers a logon scheduled task that starts the Web UI inside WSL.

---

### 5. Linux / macOS setup

On native Linux with systemd:

```bash
jellyshift service install --config config.yaml
jellyshift service status --config config.yaml
```

On macOS (no systemd), use foreground mode or background mode:

```bash
jellyshift service install --config config.yaml --background
```

---

### Using the Web UI

**Invocations** — the home page lists every run triggered by qBittorrent hooks or manual CLI use. Each row shows time, torrent name, media type, status, and a short summary. Click a row to open:

- **Media summary** — classification, TMDB match, file moves/skips, review outcome
- **Logs** — full log output for that invocation only

New runs write a structured index to `logs/runs/<run_id>.json`. Older runs are recovered by parsing `logs/jellyshift.log`.

**Review queue** (`/review`) — triage items in `review_dir`:

- Edit notes and rename files
- Re-process with movie/TV category, dry-run, and force options
- Delete dismissed items

**Settings** (`/settings`) — edit every JellyShift variable:

- TMDB API key and similarity threshold
- Library paths (movies, TV, review) with writable-path test
- qBittorrent category map
- Processing and logging options
- Hook / WSL settings — saved to `config.yaml` and synced to `run-hook.cmd` and `hook.env`
- Web server host and port (restart required after changing)

If the `TMDB_API_KEY` environment variable is set, it overrides the config file at runtime; the settings page shows a warning when this is active.

---

### Web UI troubleshooting

| Problem | Fix |
|---|---|
| `Failed to connect to bus` on `service install` | Enable systemd (WSL step 4a) or use `--background` |
| Page not loading from Windows browser | Confirm server is running (`service status`); default URL is http://127.0.0.1:8765 |
| Web UI stops after closing all WSL windows | Set `vmIdleTimeout=-1` in `.wslconfig` (step 4c) |
| Settings changes to hook vars not applied | Save from Settings page; it writes `config.yaml`, patches `run-hook.cmd`, and updates `hook.env` |
| Invocations list empty | Run at least one `jellyshift` import first; check `logs/jellyshift.log` exists |


## Development

```bash
pip install ".[dev]"
pytest
```

## Logging

JellyShift logs to **stderr** and a rotating log file in `logs/jellyshift.log` inside the JellyShift folder (next to `config.yaml`). This is especially useful when debugging qBittorrent hook runs, since qBittorrent may not show stderr output.

Configure in `config.yaml`:

```yaml
log_level: INFO    # use DEBUG for verbose troubleshooting
# log_file: logs/jellyshift.log   # default when omitted
log_max_bytes: 5242880
log_backup_count: 3
```

Set `log_file: null` to disable file logging. The `logs/` directory is gitignored.

CLI overrides:

```bash
# Extra-verbose run (DEBUG level)
jellyshift --config config.yaml "/path/to/download" --category movies -v

# Custom log file
jellyshift --config config.yaml "/path/to/download" --log-file logs/debug.log -v
```

View logs:

```bash
tail -f logs/jellyshift.log
```
