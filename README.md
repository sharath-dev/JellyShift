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

JellyShift includes a local web interface for managing invocations, the review queue, and all configuration.

### Install

```bash
pip install ".[web]"
```

### Start the server

```bash
jellyshift serve --config config.yaml
```

Open **http://127.0.0.1:8765** (default). Bind host and port can be set in `config.yaml` under `web:` or overridden with `--host` / `--port`.

### Keep running after closing WSL

Closing a WSL terminal stops foreground processes. Install the Web UI as a **systemd user service** so it keeps running in the background:

```bash
pip install ".[web]"
jellyshift service install --config config.yaml
```

Check status and logs:

```bash
jellyshift service status
journalctl --user -u jellyshift-web -f
```

Other service commands: `start`, `stop`, `restart`, `uninstall`.

**WSL requirements**

1. Enable systemd in `/etc/wsl.conf` (Ubuntu 22.04+):

   ```ini
   [boot]
   systemd=true
   ```

   Then run `wsl --shutdown` from Windows and reopen WSL.

2. Prevent WSL from idle-shutting down when all terminals are closed — add to `%USERPROFILE%\.wslconfig` on Windows:

   ```ini
   [wsl2]
   vmIdleTimeout=-1
   ```

**Start on Windows login (optional)**

If you want the Web UI to come back after a full reboot without opening WSL manually:

1. Install the service inside WSL (command above).
2. Edit `WSL_DISTRO` and `WSL_USER` in [`run-web-service.cmd`](run-web-service.cmd) (same values as `run-hook.cmd`).
3. Run [`install-web-autostart.cmd`](install-web-autostart.cmd) once from Windows — it registers a logon scheduled task that runs `systemctl --user start jellyshift-web` inside WSL.

### Invocations

The home page lists every JellyShift run (from qBittorrent hooks or manual CLI). Click a row to see:

- Media summary — classification, TMDB match, file moves/skips, review outcome
- Full logs for that specific invocation

New runs also write a structured index to `logs/runs/<run_id>.json`. Older runs are recovered by parsing `logs/jellyshift.log`.

### Review queue

At **/review**, triage items parked in `review_dir`:

- Edit notes and rename files
- Re-process with movie/TV category, dry-run, and force options
- Delete dismissed items

### Settings

At **/settings**, edit every JellyShift variable:

- TMDB API key and similarity threshold
- Library paths (movies, TV, review)
- qBittorrent category map
- Processing and logging options
- Hook / WSL settings (`wsl_distro`, `wsl_user`, `hook_sh`) — synced to `run-hook.cmd` and `hook.env` on save
- Web server host and port

If the `TMDB_API_KEY` environment variable is set, it overrides the config file at runtime; the settings page shows a warning when this is active.

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
