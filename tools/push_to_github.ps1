# Uploads this HR-MIS folder to GitHub in one go:
#   1. finds Git (offers to install it if missing)
#   2. signs in to GitHub through Git Credential Manager (browser window)
#   3. creates the private repository if it does not exist yet
#   4. commits every file except data/ (employee records never leave this PC)
#   5. pushes to GitHub
# Started by push-to-github.bat in the HR-MIS folder. Safe to run again: later
# runs upload only what changed.

$Owner   = 'Mashrur-Shakhawat-Sayan'   # GitHub account to upload to
$Repo    = 'HR-MIS'                    # repository name
$Private = $true                       # create the repository as private

$ErrorActionPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Set-Location (Split-Path $PSScriptRoot -Parent)

function Say([string]$Text, [string]$Color = 'Gray') { Write-Host $Text -ForegroundColor $Color }
function Fail([string]$Text) { Write-Host ''; Write-Host $Text -ForegroundColor Red; exit 1 }
function Ask([string]$Question) { (Read-Host "$Question (Y/N)") -match '^\s*(y|yes)\s*$' }

$web = "https://github.com/$Owner/$Repo"
Say "HR-MIS  ->  $web" 'Cyan'
Say 'Uploads every program file. The data folder (employee records, salaries) is never uploaded.'
Say ''
$null = Read-Host 'Press Enter to start, or close this window to cancel'

# 1. Git ---------------------------------------------------------------------
function Find-Git {
    $cmd = Get-Command git.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Path }
    $candidates = @("$env:ProgramFiles\Git\cmd\git.exe",
                    "${env:ProgramFiles(x86)}\Git\cmd\git.exe",
                    "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe")
    foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
    return $null
}

$gitExe = Find-Git
if (-not $gitExe) {
    Say 'Git is not installed on this PC.' 'Yellow'
    if ((Get-Command winget.exe -ErrorAction SilentlyContinue) -and (Ask 'Install Git now')) {
        winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
        $gitExe = Find-Git
    }
    if (-not $gitExe) {
        Fail 'Install Git from https://git-scm.com/download/win (default options), then run push-to-github.bat again.'
    }
}
$env:Path = (Split-Path $gitExe -Parent) + ';' + $env:Path

# 2. Local repository ------------------------------------------------------------
if (-not (Test-Path '.git')) {
    git init -q
    git symbolic-ref HEAD refs/heads/main
}
git check-ignore -q data/hrmis.db
if ($LASTEXITCODE -ne 0) {
    Fail 'Stopped: .gitignore is missing or no longer excludes the data folder, so employee data could be uploaded.'
}

# 3. Sign in to GitHub ---------------------------------------------------------------
Say ''
Say "Signing in to GitHub. If a sign-in window opens, use the $Owner account." 'Cyan'
$credRequest = @('protocol=https', 'host=github.com', "username=$Owner", '')
$credOut = $credRequest | git credential fill 2>$null
$token = $null
foreach ($line in @($credOut)) { if ($line -like 'password=*') { $token = $line.Substring(9) } }
if (-not $token) { Fail 'GitHub sign-in was cancelled or did not finish. Run push-to-github.bat again to retry.' }

# Windows PowerShell 5.1 refuses User-Agent / Accept inside -Headers, so only
# Authorization goes there and the user agent uses its own parameter.
$headers = @{ Authorization = "token $token" }

function Invoke-GitHub([string]$Method, [string]$Path, $Body = $null) {
    $params = @{ Method = $Method; Uri = "https://api.github.com$Path"; Headers = $headers; UserAgent = 'HR-MIS-uploader' }
    if ($Body) { $params.Body = ($Body | ConvertTo-Json); $params.ContentType = 'application/json' }
    try {
        return @{ Ok = $true; Status = 200; Data = (Invoke-RestMethod @params) }
    } catch {
        $code = 0
        if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
        return @{ Ok = $false; Status = $code; Error = $_.Exception.Message }
    }
}

$me = Invoke-GitHub 'GET' '/user'
if ($me.Status -eq 401) {
    $credRequest | git credential reject 2>$null
    Fail 'GitHub did not accept the sign-in. Run push-to-github.bat again to sign in afresh.'
}
if (-not $me.Ok) { Fail "Could not reach GitHub: $($me.Error)" }
$login = $me.Data.login
if ($login -ne $Owner) {
    $credRequest | git credential reject 2>$null
    Fail "You signed in as $login, but this uploads to $Owner. In your browser, sign out of GitHub and sign in as $Owner, then run push-to-github.bat again."
}
@('protocol=https', 'host=github.com', "username=$Owner", "password=$token", '') | git credential approve 2>$null
Say "Signed in as $login." 'Green'

# Label commits with the GitHub account if this PC has no Git identity yet.
# The private no-reply address keeps any personal email out of the history.
$email = git config user.email
if (-not $email) {
    $name = $me.Data.name
    if (-not $name) { $name = $login }
    git config user.name "$name"
    git config user.email "$($me.Data.id)+$login@users.noreply.github.com"
}

# 4. Make sure the repository exists ----------------------------------------------------
$repoCheck = Invoke-GitHub 'GET' "/repos/$Owner/$Repo"
if ($repoCheck.Status -eq 404) {
    Say "Creating the private repository $Owner/$Repo ..." 'Cyan'
    $created = Invoke-GitHub 'POST' '/user/repos' @{
        name        = $Repo
        private     = $Private
        description = 'HR-MIS: human resource management information system (Python + SQLite)'
    }
    if (-not $created.Ok -and $created.Status -ne 422) {
        Fail "Could not create the repository: $($created.Error)`nCreate an empty repository named $Repo at https://github.com/new, then run push-to-github.bat again."
    }
} elseif (-not $repoCheck.Ok) {
    Fail "Could not check the repository: $($repoCheck.Error)"
}

# 5. Commit -----------------------------------------------------------------------------
$version = '1.1'
$cfg = Select-String -Path 'backend\config.py' -Pattern 'VERSION\s*=\s*"([^"]+)"' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($cfg) { $version = $cfg.Matches[0].Groups[1].Value }
git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    $null = git rev-parse --verify -q HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        $msg = "HR-MIS $version`n`nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`nClaude-Session: https://claude.ai/code/session_012gguBArgmKCdZYYGvXNQcA`n"
    } else {
        $msg = 'Update HR-MIS (' + (Get-Date -Format 'yyyy-MM-dd HH:mm') + ")`n"
    }
    $msgFile = Join-Path $env:TEMP 'hrmis-commit-msg.txt'
    [IO.File]::WriteAllText($msgFile, $msg)
    git commit -q -F $msgFile
    $commitCode = $LASTEXITCODE
    Remove-Item $msgFile -ErrorAction SilentlyContinue
    if ($commitCode -ne 0) { Fail 'Saving the files into Git failed (see the message above).' }
} else {
    Say 'No new changes since the last upload; checking GitHub is up to date.'
}

# 6. Push -------------------------------------------------------------------------------
git branch -M main
$remoteUrl = "https://$Owner@github.com/$Owner/$Repo.git"
$null = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) { git remote add origin $remoteUrl } else { git remote set-url origin $remoteUrl }

Say ''
Say 'Uploading ...' 'Cyan'
git push -u origin main
$pushed = ($LASTEXITCODE -eq 0)

if (-not $pushed) {
    # Usually this means GitHub already has commits this folder does not (for
    # example a README added on the website).
    $null = git fetch -q origin main 2>$null
    if ($LASTEXITCODE -eq 0) {
        git merge-base --is-ancestor origin/main HEAD
        if ($LASTEXITCODE -ne 0) {
            Say ''
            Say 'The GitHub repository already has files that are not in this folder (for example a README made on GitHub).' 'Yellow'
            if (Ask 'Replace what is on GitHub with this folder') {
                git push -u --force-with-lease origin main
                $pushed = ($LASTEXITCODE -eq 0)
            }
        }
    }
}
if (-not $pushed) { Fail 'The upload did not finish (see the message above).' }

Say ''
Say "Done. Your files are at $web" 'Green'
Say 'Run push-to-github.bat again whenever you want to upload new changes.'
if (Ask 'Open it in your browser now') { Start-Process $web }
exit 0
