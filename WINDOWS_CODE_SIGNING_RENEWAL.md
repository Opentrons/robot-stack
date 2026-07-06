# Flex Windows code signing renewal (DigiCert Keylocker)

Summary of what fixed Windows desktop app signing in GitHub Actions after the 2026 DigiCert renewal. Applies to release builds in `Opentrons/opentrons` (`.github/workflows/app-test-build-deploy.yaml`).

## What broke

The Windows release job failed at `smctl sign` on `Opentrons.exe` with:

```text
SignerSign() failed (-2146893779 / 0x8009002d)
```

Checkout, frontend bundle, and DigiCert client setup (`smctl healthcheck`) still passed. Mac and Linux release jobs succeeded. The failure was limited to **Windows code signing**.

## Two different credential layers

Do not confuse these:

| Layer | Purpose | GitHub secrets | Renew with code-signing cert? |
|-------|---------|----------------|-------------------------------|
| **Service user / CI auth** | Lets GitHub Actions talk to DigiCert Signing Manager | `SM_HOST_V2`, `SM_API_KEY_V2`, `SM_CLIENT_CERT_FILE_B64_V2`, `SM_CLIENT_CERT_PASSWORD_V2` | **No** (still valid; e.g. "Github Actions integration cert V2" through 2029) |
| **Code signing cert + Keylocker keypair** | Actually signs `Opentrons.exe` | `SM_KEYPAIR_ALIAS_V3`, `SM_CODE_SIGNING_CERT_SHA1_HASH_V3`, `WINDOWS_CSC_B64_V2` | **Yes** |

After renewal, only the **three signing secrets** needed to change. The service user **Windows Signer 20241107**, its API key, and client auth cert did not need rotation.

## Which keypair to use

CertCentral listed multiple code-signing orders. The active renewal for this cycle:

| Order ID | Keypair alias | Status | Notes |
|----------|---------------|--------|-------|
| **1544514382** | **`key_1544514382`** | **Issued** (16-Jun-2026) | **Use this one** |
| 1306713762 | `key_1306713762` | Issued (30-Jun-2025) | Previous renewal |
| 832868516 | `key_832868516` | Pending | Not usable |

Download the public signing certificate from **`cert_1544514382`** (not a similarly numbered but different keypair).

Verify the cert locally:

```bash
openssl x509 -in cert_1544514382.crt -noout -subject -dates -fingerprint -sha1
```

Expected thumbprint (no colons):

```text
43cfd344b4fe3344f6979e2af2a168402cdb1559
```

Validity: **16-Jun-2026** through **21-Jul-2027**.

## What we updated in GitHub

Only these three secrets on `Opentrons/opentrons`:

```bash
gh secret set SM_KEYPAIR_ALIAS_V3 --repo Opentrons/opentrons --body "key_1544514382"

gh secret set SM_CODE_SIGNING_CERT_SHA1_HASH_V3 --repo Opentrons/opentrons \
  --body "43cfd344b4fe3344f6979e2af2a168402cdb1559"

gh secret set WINDOWS_CSC_B64_V2 --repo Opentrons/opentrons \
  --body "$(base64 -i cert_1544514382.crt | tr -d '\n')"
```

All three values must refer to the **same** keypair and certificate. A mix of old alias, new cert, or wrong thumbprint reproduces the `SignerSign()` failure.

## How CI uses them

From `app-test-build-deploy.yaml` on Windows release jobs:

1. Decode `WINDOWS_CSC_B64_V2` to `D:\opentrons_labworks_inc.crt`
2. Authenticate with `SM_HOST_V2`, `SM_API_KEY_V2`, and the client PKCS12 secrets
3. Install DigiCert Keylocker tools and run `smctl healthcheck`
4. During `app-shell` build, `windows-custom-sign.js` runs:

   ```text
   smctl sign --keypair-alias="$SM_KEYPAIR_ALIAS" \
     --input="...\Opentrons.exe" \
     --certificate="D:\opentrons_labworks_inc.crt"
   ```

5. Verify with `SM_CODE_SIGNING_CERT_SHA1_HASH`

## Checklist for the next renewal

1. In **CertCentral / Signing Manager**, identify the new **Issued** order and **`key_*` alias**.
2. Download the public **`.crt`** from the matching **`cert_*`** on that keypair.
3. Confirm SHA1 with `openssl x509 -fingerprint -sha1`.
4. Update **`SM_KEYPAIR_ALIAS_V3`**, **`SM_CODE_SIGNING_CERT_SHA1_HASH_V3`**, and **`WINDOWS_CSC_B64_V2`** together.
5. Re-run the failed **Build release desktop app on windows-2022** job (or push a new tag).
6. Leave client/API secrets alone unless DigiCert reissues the GitHub Actions integration certificate.

## Result

After updating those three secrets, Windows release signing succeeded and the Flex external release build completed.
