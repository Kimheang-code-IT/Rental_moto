# HollyWing Motor

Motorcycle rental management - Nuxt frontend, FastAPI backend, Docker Compose stack.

## Fast client install (Windows)

**One command** on a new PC (or to update an existing install). Requires Git and Docker Desktop.

Paste in **PowerShell**:

```powershell
irm https://raw.githubusercontent.com/Kimheang-code-IT/Rental_moto/main/scripts/install-client.ps1 | iex
```

That will:

1. Clone into `%USERPROFILE%\Rental_moto` (or `git pull` if it already exists)
2. Create `.env` from `.env.example` when missing
3. Start Docker Desktop if needed
4. `docker compose up -d --build` (rebuilds/updates containers from the latest code)
5. Install the **HollyWing Motor** desktop shortcut + Windows logon task
6. Wait until healthy and open the app

**Update later:** run the same command again - it pulls GitHub and rebuilds Docker automatically.

From an existing clone:

```powershell
cd $HOME\Rental_moto
.\scripts\install-client.ps1
```

Optional flags:

```powershell
.\scripts\install-client.ps1 -SkipWindowsStartup   # code + Docker only
.\scripts\install-client.ps1 -SkipOpenBrowser      # do not open the app window
.\scripts\install-client.ps1 -SkipGitPull          # rebuild without pulling
```

## Windows Client Startup

Use this so staff never open Docker, CMD, or PowerShell by hand.

### Shortcut / logon only

If the project is already cloned and built:

```powershell
.\scripts\windows\install-windows-startup.ps1
```

This will:

1. Create a **HollyWing Motor** desktop shortcut (and Start Menu entry)
2. Register a hidden Task Scheduler task at Windows logon (short delay for Docker Desktop)
3. Best-effort enable Docker Desktop start-at-login

### How the client starts the system

Double-click **HollyWing Motor** on the Desktop.

1. Checks `http://localhost:<FRONTEND_PORT>` and `/api/v2/auth/setup-status` (default port **80**)
2. If healthy -> open Chrome/Edge app mode immediately
3. If not -> start Docker Desktop if needed, `docker compose up -d`, wait, then open
4. Skips a second app window if one is already open

### Automatic startup after Windows login

1. Docker Desktop starts (enable "Start Docker Desktop when you log in" if needed)
2. Scheduled task runs after a short delay
3. Containers come up via `restart: unless-stopped`
4. App opens in Chrome/Edge app mode when healthy

Startup log: `%LOCALAPPDATA%\HollyWingMotor\startup.log`

### Uninstall startup integration

```powershell
.\scripts\windows\uninstall-windows-startup.ps1
```

Removes only the scheduled task and HollyWing Motor shortcuts. Does not remove Docker, project files, databases, or volumes.

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| Shortcut does nothing | `%LOCALAPPDATA%\HollyWingMotor\startup.log` |
| Docker not running | Start Docker Desktop; enable start-at-login |
| App never opens | `docker compose ps` and `docker compose logs frontend api` |
| Wrong port | Set `FRONTEND_PORT` in `.env` (default `80`) |

### Scripts

| File | Purpose |
| --- | --- |
| `scripts/install-client.ps1` | One-command clone/pull + Docker build + Windows startup |
| `scripts/windows/start-hollywing.ps1` | Hidden launcher |
| `scripts/windows/install-windows-startup.ps1` | Shortcut + Task Scheduler only |
| `scripts/windows/uninstall-windows-startup.ps1` | Remove task + shortcuts |
