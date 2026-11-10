# Plan — Alerter distribution via CK Store API

## What exists
- Tool: `alert.py` (desktop popup, image + text, ACK/Cancel, repeating beep until ack'd)
- Skill doc: `SKILL.md` (agent-facing install/run guide)
- Manifest: `artifacts/manifest.json` (lists files, versions, download URLs)
- Sample image: `cafe_terrace.png`

## Repo (GitHub, AmitDJagtap/alerter.storeos.co.in)
1. `git init` + first commit
2. Create repo on GitHub using stored credential
3. `git push -u origin main`
4. Repo = source of truth; agents can also clone it directly if allowed.

## CK Store API — new endpoints (backend, ckapp)
| Endpoint | Method | Purpose |
|---|---|---|
| `/{domain}/skills` | GET | Return a single skill's `SKILL.md` (text/markdown) for a given domain. Example: `/alerter.storeos.co.in/skills`. Agents parse this to learn how to install/run the tool. |
| `/{domain}/skills` | POST | (optional) Register/update a skill from the repo maintainer. Only admin token. |
| `/{domain}/artifacts` | GET | List artifacts for a domain (JSON — the `manifest.json` content: file names, sizes, sha256, version). Lets an agent verify what it needs before downloading. |
| `/{domain}/artifacts/{filename}` | GET | Download one artifact file (binary or text). Example: `/alerter.storeos.co.in/artifacts/alert.py`. Agents save it to their own disk. |
| `/{domain}/artifacts` | POST | (optional) Upload a new artifact (multipart). Only admin token, so Amit can publish updates without re-deploying. |

## Auth model (all endpoints)
- Bearer token, same as existing `/ops/*` routes.
- GET = any valid agent token.
- POST = admin role only (like bills/vendors create).

## Storage behind the API
- Files stored on the server under `/opt/data/skills/{domain}/` (skills + artifacts), loaded/served by the route handler.
- Source of truth stays the GitHub repo; the API files get synced by a simple script (`git pull && cp`), or uploaded directly via the POST endpoint.

## Agent flow (how another agent uses this)
1. Agent has a CK store API token (already the case — bills/menu access).
2. GET `/{domain}/artifacts` → sees `alert.py` is needed.
3. GET `/{domain}/skills` → reads SKILL.md, learns usage.
4. GET `/{domain}/artifacts/alert.py` → saves the file locally.
5. Runs `python alert.py --title "..." --text "..."` — popup appears, user ACKs.

## Sequence (what happens now)
1. `git init` + commit + push repo            ← 10 min
2. Write the 4 route handlers in ckapp        ← backend PR (you review)
3. Deploy to server, test with curl           ← 15 min
4. Register the skill locally (skill_manage)  ← 5 min
