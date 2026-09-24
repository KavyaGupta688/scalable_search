# Shared accounts for teammates running separate copies

For a new teammate, start with [the environment generator and setup guide](TEAMMATE_SETUP.md). It creates private local keys without copying another developer's full environment, and identifies the shared credentials that still need secure distribution.

The application verifies credentials in its gateway process, while **accounts, password hashes, roles and revocable sessions live in AWS RDS**. This PC uses database `smsprsm_integration`, schema `identity`, over TLS. The relevant tables are `identity.platform_users` and `identity.auth_tokens`. Shared `samsungdb` is unchanged.

Each teammate can run their own frontend/gateway and use the same account. They do not need to connect to this PC's localhost or copy its `users.json`, SQLite files, browser storage or Docker auth volume. Registering an account through one configured copy makes it available to the others. Each browser normally signs in separately; logout revokes that session, not every session belonging to the account.

## Required configuration

1. Obtain the shared identity database connection and the team's `NEXUS_JWT_SECRET` through the team's private secret-sharing channel. Do not put them in Git or frontend variables.
2. Put the following in the ignored `.integration/stack.env` or a later-loaded private environment file. Replace placeholders and URL-encode the database password:

   ```text
   AUTH_DATABASE_URL_SYNC=postgresql+psycopg2://USER:PASSWORD@HOST:5432/smsprsm_integration?sslmode=require
   NEXUS_JWT_SECRET=the-same-private-signing-key-used-by-the-team
   ```

   `AUTH_DATABASE_URL_SYNC` configures only the `identity` connection. Module databases continue to use their existing `DATABASE_URL` and `DATABASE_URL_SYNC`. If the authentication override is blank, identity uses `DATABASE_URL_SYNC`; in the approved RDS profile that already points to `smsprsm_integration`. Missing or non-PostgreSQL configuration returns a clear 503 instead of silently creating local accounts. A database outage never activates a local fallback.

3. Have infrastructure allow the teammate's actual Docker egress address on RDS TCP 5432, or provide the approved private network/VPN route. Confirm access from Docker, not only from pgAdmin on Windows. The identity database role needs access to the existing identity tables; routine login needs no schema migration.
4. Start the configured stack using the [runtime setup guide](../deploy/integration/README.md), including the RDS override and [monitoring override](MONITORING.md) where applicable. Recreate the gateway after environment changes. A source checkout uses the development mount; a teammate running built images must rebuild the gateway image to include updated code.
5. Use `/login/user` or `/login/admin` with the account's assigned role. Public registration creates standard users only. Bootstrap settings initialize an empty identity database; they do not reset existing administrators' passwords.

All copies that share sessions need the same `NEXUS_JWT_SECRET`; changing it invalidates JWTs signed with the old value. `INTERNAL_JWT_SECRET` only needs to match the services within each teammate's own stack. Browser bearer tokens still reside in that browser's local storage; they are credentials for server-side sessions, not a local user database.

This shares authentication, not the whole runtime. Separate Kafka, Vault, Qdrant and download-storage instances do not automatically synchronize because accounts are shared. Use isolated module databases for independent test stacks or deliberately configure shared services. Do not run independent workers against a shared module database while assuming their local queues, Vault secrets or indexes are interchangeable. Keep `AUTH_DATABASE_URL_SYNC` pointed to the shared identity database when separating module data.

This is cloud-persisted application authentication, not Cognito/SSO. The website and login API continue running on each teammate's machine as requested. A centrally hosted website or managed identity provider would be a separate deployment change.

## Verification on 21 September 2026

- Confirmed the running identity database is AWS RDS `smsprsm_integration`, with TLS enabled.
- Confirmed existing users and sessions are already stored there; no account migration was necessary.
- All 38 authentication/gateway tests passed, covering absent/invalid configuration, rejection of local SQLite, database outages without local fallback, shared-backend selection, and isolation of module database connections from the identity override. Focused Python correctness lint passed.
- A live RDS test initialized two independent authentication service instances before account creation. An account registered through the first was immediately visible through the second, could log in there, could have its session validated/revoked through the first, and remained available after another instance initialized. The random test account and its sessions were removed afterward; existing accounts were untouched.
- This verifies independent instances against the actual database, not connectivity from teammates' computers. They still need their environment settings and RDS network access.
- After the gateway was recreated, real HTTP login, profile access, logout and rejection of the revoked session passed with an existing RDS account.

Repeat the bounded live check from the gateway with `python tests/integration/shared_auth.py`. It creates and cleans up one uniquely named test account in the integration database.
