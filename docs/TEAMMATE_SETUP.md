# Set up your own environment without copying someone else's .env

This guide targets Windows PowerShell, Docker Desktop with Compose v2, Node 20+, and `Feature/Integration`. Run commands from the repository root. Generated files contain secrets: keep them in ignored `.integration/`, not Git, screenshots or group chat.

## 1. Decide what you are sharing

The default below gives you **your own module database on RDS and your own local services, with the team's shared accounts**. Infrastructure must allocate that dedicated module database first. You can sign in with an existing account, but you will ingest your own datasets; this does not copy another machine's catalog.

If you need exactly the same existing ingested files, search index, source connections and download packages, ask for access to the centrally hosted application or a deliberately configured shared backend. Sharing only RDS is insufficient: Vault contains source credentials, Qdrant contains vectors, Kafka/Redis coordinate workers, and packages live in storage. Do not launch a second independent worker stack against the existing shared module database with unrelated local Vault/queues/indexes.

## 2. Obtain only the values that cannot be generated locally

Request these through an approved private secret-sharing channel:

| Required input | Owner / purpose |
|---|---|
| RDS hostname, port, database user/password, dedicated module database name | Infrastructure; separate database for your module stack. Never use shared `samsungdb`. |
| Shared identity connection (database `smsprsm_integration`, schema `identity`) | Infrastructure; permits login using the team's existing accounts. May use different credentials from your module connection. |
| Team `NEXUS_JWT_SECRET` | Application owner; use the same login-signing key as the shared identity environment. |
| Assigned user/admin login | Application administrator; do not distribute a common admin password broadly. |
| RDS network access | Infrastructure; approve your actual Docker egress IP or private/VPN route on TCP 5432. |
| Source access when needed | S3 role authorization or development credentials; NAS account and private-network access. Enter these in the connector UI, not the frontend build. |

The generator creates fresh internal-service, Vault, watermark, bootstrap and Grafana values. These are appropriate for an independent stack. New watermark keys cannot authenticate another stack's old watermark signatures; cross-stack forensic verification requires deliberately shared/retained watermark keys and matching forensic records. Do not rotate existing keys by rerunning setup.

## 3. Get current code and generate the files

Preserve any local edits before switching/pulling.

```powershell
git switch Feature/Integration
git pull --ff-only origin Feature/Integration
./scripts/New-TeammateEnvironment.ps1
```

The script creates `.integration/stack.env`, `.integration/rds-runtime.env`, and `.integration/monitoring.env`. It refuses to overwrite any of them and does not contact services or create a database. To generate a separate reference copy, use `-OutputDirectory .integration/env-reference`.

Open the files in your editor and replace every `REPLACE_` placeholder:

- `AUTH_DATABASE_URL_SYNC`: shared identity database connection.
- `NEXUS_JWT_SECRET`: team signing key, obtained privately.
- `RDS_DATABASE_URL` and `RDS_DATABASE_URL_SYNC`: your dedicated module database, using the same host/user/password/database in both URLs. Preserve their different driver names and TLS query parameters.

Percent-encode the username/password components of database URLs. For example, `@` within a password becomes `%40`; do not encode the entire URL. These development URLs require encryption; production must additionally configure certificate/hostname verification and least-privilege database roles.

Do not replace existing shared admin credentials with the generated `BOOTSTRAP_ADMIN_PASSWORD`: bootstrap settings do not reset existing users. Use your assigned account. Generated bootstrap credentials matter only when initializing an empty identity store.

Verify ignore rules and missing placeholders without printing secret values:

```powershell
git check-ignore .integration/stack.env .integration/rds-runtime.env .integration/monitoring.env
$unfinished = Select-String -Path .integration/*.env -Pattern 'REPLACE_' | Where-Object { $_.Line -notmatch '^#' }
if ($unfinished) { throw 'Environment placeholders remain. Complete them in your editor.' }
```

## 4. Build and initialize your approved dedicated database

Do not run the migration step against somebody else's existing module database. Shared identity login needs access to existing tables, not a teammate-triggered identity migration.

```powershell
$composeArgs = @(
  '-p', 'smsprsm-teammate',
  '--env-file', '.integration/stack.env',
  '--env-file', '.integration/rds-runtime.env',
  '--env-file', '.integration/monitoring.env',
  '-f', 'deploy/integration/compose.yml',
  '-f', 'deploy/integration/rds.yml',
  '-f', 'deploy/integration/low-memory.yml',
  '-f', 'deploy/integration/monitoring.yml'
)
# Checks interpolation without printing resolved secrets.
docker compose @composeArgs config --quiet
docker volume create smsprsm-integration_models
Push-Location frontend
npm ci
npm run build
Pop-Location
docker compose @composeArgs build gateway
docker compose @composeArgs build search ai download
docker compose @composeArgs up -d redis kafka qdrant vault-persistent vault-init
docker compose @composeArgs run --rm -e AUTH_DATABASE_URL_SYNC= migrate
```

The migration command deliberately clears the identity override **for that one container**, so any identity DDL also stays in your dedicated module database. Normal gateway startup still uses the shared identity connection from `stack.env`. Do not omit this override when following this shared-account setup.

The RDS override disables local PostgreSQL. The generated `POSTGRES_PASSWORD` exists only to satisfy base Compose interpolation. The model volume is local to your Docker installation and initially empty; it does not download another person's models.

Check each command succeeds before continuing. Do not start workers until models have been provisioned:

```powershell
docker compose @composeArgs run --rm --no-deps --entrypoint python ai scripts/provision_ai_models.py
docker compose @composeArgs up -d --no-build
docker compose @composeArgs ps
```

Provisioning downloads and checks the complete AI manifest and can take substantial time/disk/RAM. Do not run concurrent provisioners. Use [runtime setup](../deploy/integration/README.md) for model troubleshooting. The generated environment starts with metadata watermarking; the optional native-codec build/profile is described in [watermark acceptance and limits](NAS_AND_WATERMARK_ACCEPTANCE_20260921.md).

## 5. Verify and use

- Open `http://localhost:18000/login/user` or `/login/admin` with your assigned account.
- Check `http://localhost:18000/ready`; investigate a non-ready response before a demo. `/health` alone only proves process liveness.
- Create your own source connector, test access, and run a small manual scan. Source credentials are stored in your local persistent Vault.
- Empty Search is expected in a fresh module environment until enrichment and indexing finish.
- If login fails: confirm the current branch, shared identity URL/key, assigned role, and RDS access **from Docker**. Do not regenerate shared keys or reset the database.

For ordinary restarts reuse the same files and Compose arguments and run `docker compose @composeArgs up -d --no-build`. Preserve credentials and volumes; do not use `down -v` or prune volumes as recovery. Never print or share resolved `docker compose config` output, which contains secrets.

This generator is a configuration helper, not credential issuance or infrastructure provisioning. A teammate still needs the approved shared inputs and model downloads. End-to-end operation on her machine must be verified there.
