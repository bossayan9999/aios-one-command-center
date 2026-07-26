# AIOS ONE remote access

## Connection path

Use the protected hostname:

`https://aios.bossayan.com`

The supported path is:

`Phone → HTTPS → Cloudflare Access → Cloudflare Tunnel → 127.0.0.1:8000`

Port 8000 must remain bound to localhost. Do not add a router port-forward.

## Installed configuration

- `cloudflared` runs as an Automatic Windows service using a managed tunnel token.
- The Cloudflare edge hostname resolves and Cloudflare Access protects it.
- AIOS runs from this repository through the `AIOS ONE Hidden Startup` scheduled
  task and `scripts/start_aios_hidden.ps1`.
- The startup task uses `.venv`, starts when available, and retries three times.
- Public HTTPS logins force Secure session and CSRF cookies.

Tunnel tokens and owner credentials must never be committed to the repository.

## Phone setup

1. Leave the Windows computer powered on and connected to the internet.
2. Open `https://aios.bossayan.com` on the phone from Wi-Fi or cellular data.
3. Complete Cloudflare Access authentication.
4. Complete AIOS owner authentication.
5. Use Command Center for Copilot tasks.
6. Pair the phone from Mobile Control for the limited remote command controls.

MCP is optional. It extends the reviewed tool registry but does not replace
Cloudflare Tunnel, Cloudflare Access, AIOS authentication, or owner approvals.

## Verification

On the computer:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Get-Service Cloudflared
Get-ScheduledTask -TaskName "AIOS ONE Hidden Startup"
```

From a separate network, open the public hostname and confirm both login layers
appear before Command Center. The full origin path cannot be verified by an
anonymous probe because Cloudflare Access intentionally intercepts it first.

## Recovery

```powershell
Start-Service Cloudflared
Start-ScheduledTask -TaskName "AIOS ONE Hidden Startup"
```

If local health fails, inspect `logs/aios-startup-error.log`. If Cloudflare
Access appears but AIOS does not load after authorization, verify that the
managed tunnel's public hostname route targets `http://127.0.0.1:8000`.
