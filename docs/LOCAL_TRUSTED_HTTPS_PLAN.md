# Trusted local HTTPS for https://localhost:5176 — approval plan (13 November 2026)

**Status: EXECUTED 13 Nov 2026 (approved).** CA created with localhost-only name constraints (verified: a www.google.com certificate it signs fails with *permitted subtree violation*), leaf issued, Vite restarted (strict `openssl` verify 0/ok), CA imported by the owner into Chrome; padlock confirmed. Expires 13 Dec 2026.

## Diagnosis (read-only)

| Check | Result |
|-------|--------|
| Served certificate | `private/local-https/localhost.pem`: issuer = subject = `CN=localhost`, `CA:TRUE`, SAN `DNS:localhost, IP:127.0.0.1`, no key usage / serverAuth |
| `openssl s_client -connect localhost:5176` | `Verify return code: 18 (self-signed certificate)` |
| Chrome | Google Chrome 156; shows `NET::ERR_CERT_AUTHORITY_INVALID` / "Not secure" |
| Tooling | No `mkcert`, no `certutil` (libnss3-tools), no `~/.pki/nssdb` yet; OpenSSL 3.5.3 present |

**Root cause:** the hostname is right, but the certificate is a self-signed leaf that chains to nothing Chrome trusts. Any fix needs Chrome to trust a local issuer, which is a trust-store change.

## Proposed fix (no downloads, no system-wide change)

1. **Create a local development CA with OpenSSL** in `private/local-https/ca/` (git-ignored, key mode 0600):
   - Subject `CN=Governance Studio Local Dev CA (atiya laptop)`, valid **30 days**.
   - `basicConstraints=critical,CA:TRUE,pathlen:0`, `keyUsage=critical,keyCertSign,cRLSign`.
   - **`nameConstraints=critical,permitted;DNS:localhost,permitted;IP:127.0.0.1/255.255.255.255`.** Even if the CA key leaked, the CA could only vouch for localhost, never for a real website.
2. **Issue the server certificate** signed by that CA: `CN=localhost`, SAN `DNS:localhost, IP:127.0.0.1`, `CA:FALSE`, `extendedKeyUsage=serverAuth`, valid 30 days. Same file paths Vite already uses, so no config change.
3. **Trust the CA in your Chrome profile only** (you do this in the Chrome UI): Settings → Privacy and security → Security → Manage certificates → *Local certificates* / *Custom* → **Import** `private/local-https/ca/governance-local-dev-ca.pem` → trust for **identifying websites** only. No OS trust store, `/usr/local/share/ca-certificates`, `update-ca-certificates`, apt packages or other users are touched.
4. **Restart only Vite on 5176** (frontend; no data) so it loads the new certificate. The backend, Entra redirect URI `https://localhost:5176/api/sso/callback`, `/api` proxy and cookies are unchanged.
5. **Verify:** `openssl s_client -CAfile ca.pem -verify_hostname localhost` returns `Verify return code: 0 (ok)`; Chrome shows the padlock without "Not secure"; Admin and User SSO sign-in still work.

## Rollback

Chrome → Manage certificates → remove "Governance Studio Local Dev CA"; delete `private/local-https/ca/`; restart Vite with the previous certificate. The CA also expires by itself after 30 days.

## Not done

No publicly trusted certificate, no change to Azure-hosted certificates or the Entra app registration, no TLS verification disabled anywhere.
