# 02 · Installation & running

## Requirements

| Item | Minimum |
|---|---|
| Operating system | Windows 10 / 11, Windows Server 2016+, macOS 12+, or any modern Linux |
| Python | **3.10 or newer** (3.12+ recommended); standard library only |
| Browser | Current Chrome, Edge, Firefox or Safari |
| Disk | ~5 MB for the program; the database grows by roughly 1 MB per 100 employees per year, plus uploaded documents |
| RAM | Under 100 MB |

## 1. Install Python (Windows)

1. Download the installer from <https://www.python.org/downloads/windows/>.
2. On the first screen, tick **"Add python.exe to PATH"** and click **Install Now**.
3. Check it worked: open *Command Prompt* and run `py --version`. It should print `Python 3.x.x`.

> If typing `python` opens the Microsoft Store, the Store alias is shadowing the real install. Use `py` instead, or turn the
> alias off in *Settings → Apps → Advanced app settings → App execution aliases*.

## 2. Start HR-MIS

**Double-click `start.bat`.** A console window opens and your browser goes to <http://127.0.0.1:8000>.
Keep the console window open while you use the system; closing it, or pressing **Ctrl+C**, stops HR-MIS.

Command-line options (run inside the HR-MIS folder):

| Command | Effect |
|---|---|
| `py run.py` | Start. On the very first run it creates `data\hrmis.db` and loads the demo organisation |
| `py run.py --empty` | First run **without** demo data: only the `admin` account, leave types and the holiday calendar |
| `py run.py --reset-demo` | Copy the current database to `data\backups\before-reset-….db`, then start again with fresh demo data |
| `py run.py --port 9000` | Use another port if 8000 is taken |
| `py run.py --lan` | Listen on the office network so other PCs can open `http://<this-pc-ip>:8000` |
| `py run.py --no-browser` | Do not open a browser automatically (for servers) |

Environment variables (optional): `HRMIS_PORT`, `HRMIS_HOST`, `HRMIS_DATA_DIR` (move the data folder, e.g. to a backed-up drive), `HRMIS_DB`, `HRMIS_SESSION_HOURS`.

## 3. Use it from other PCs (office LAN)

1. Start with `py run.py --lan` on the PC that will act as the server.
2. Allow it through Windows Firewall when prompted (private networks only).
3. On other PCs, open `http://<server-ip>:8000`. The console prints the address.

For more than a handful of users, or for access from outside the office, put HR-MIS behind a reverse proxy with HTTPS
(IIS ARR, nginx or Caddy). See [10-operations.md](10-operations.md#security-hardening).

## 4. Start automatically with Windows (server PC)

**Option A — Task Scheduler (built in)**
1. Open *Task Scheduler → Create Task*.
2. *General:* name it "HR-MIS" and tick **Run whether user is logged on or not**.
3. *Triggers:* **At startup**.
4. *Actions:* Program `C:\Path\To\Python\pythonw.exe`, arguments `run.py --lan --no-browser`, start in `C:\HR-MIS`.
5. *Settings:* untick "Stop the task if it runs longer than…".

**Option B — NSSM (Windows service)**
```bat
nssm install HR-MIS "C:\Path\To\Python\python.exe" "run.py --lan --no-browser"
nssm set HR-MIS AppDirectory C:\HR-MIS
nssm start HR-MIS
```

## 5. Verify the installation

```bat
py -m unittest discover tests -v
```
All tests should report `ok`. They use a temporary database and never touch `data\hrmis.db`.

Optional browser test of every feature (needs `py -m pip install playwright` and `py -m playwright install chromium`):
```bat
py run.py --reset-demo --no-browser --port 8765
py tests\e2e_features.py
```
`--reset-demo` replaces the current data with fresh demo data (keeping a backup), so only run it on a demo copy.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Python was not found` | Install Python and tick "Add to PATH", then open a new console |
| `Port 8000 is already in use` | HR-MIS is already running (look for another console window), or use `--port 8001` |
| Browser shows "This site can't be reached" | The console window was closed; start HR-MIS again |
| "Your session has expired" | Sessions last 12 hours by default; sign in again (`HRMIS_SESSION_HOURS` changes the length) |
| "Too many failed attempts" | 8 wrong passwords in 15 minutes locks that username for 15 minutes |
| Printing opens nothing | Allow pop-ups for `127.0.0.1` in the browser |
| The page looks old after an update | Refresh with Ctrl + F5 |
| Colours look wrong (very dark) | Use the moon/sun button in the top bar to switch theme |
| Forgot the admin password | Stop HR-MIS and run `py tools\reset_admin.py`, then sign in as `admin` / `Admin@123` and change it |
| Want to start over | `py run.py --reset-demo` (keeps a backup), or stop HR-MIS and delete the `data` folder |
