# Secrets management with SOPS and age

Every non-trivial codebase eventually accumulates a pile of sensitive strings: database passwords, API tokens, TLS private keys, OAuth client secrets, third-party webhook signing secrets. The question is not whether you have secrets; the question is where they live. The lazy answer is "in a `.env` file that we pass around on Slack." The slightly less lazy answer is "in an environment-specific vault that only ops touches." The answer this lesson is about is **encrypted alongside your code, in Git, readable only by people who hold the right keys**.

The two tools that make that approach pleasant are **SOPS** (Secrets OPerationS) and **age**. SOPS is the editor and orchestrator; age is the encryption primitive. They are designed to work together, and once you understand why each one exists, the workflow is almost trivially simple.

## Why bother encrypting secrets in Git?

The instinct against secrets-in-Git is correct in its raw form. Committing `password: hunter2` to a public repository is a fast way to find your AWS bill quadrupled by a crypto miner. The whole point of SOPS+age is that the thing you commit is *not* `hunter2` — it is a ciphertext that says `ENC[AES256_GCM,data:...]`, and the plaintext only ever exists in memory on a machine that holds the right private key.

Once that property holds, encrypting secrets in Git gets you back the three things that make IaC and GitOps work in the first place:

- **Reproducibility.** A clone of the repo is a complete deployable artifact. No "and then fetch the production database password from this other system" step.
- **Reviewability.** Secret changes go through the same pull-request flow as everything else. Adding a new credential is reviewed; rotating one is reviewed; granting a new teammate access is reviewed.
- **Auditability.** `git log` tells you when each secret was added, rotated, and who approved the change.

The catch is operational: the *key that decrypts the secrets* has to live somewhere safe and outside the repo. SOPS+age makes the in-repo part cheap, but it does not solve key custody. We will come back to this at the end.

## What age actually is

[age](https://age-encryption.org/v1) — short for "Actually Good Encryption", though the name is also a pun on the German word for "key" — is a file encryption tool written by Filippo Valsorda, originally during his time on the Go security team. It was designed as a deliberate, opinionated alternative to GPG for the specific job of encrypting files to one or more recipients.

The design philosophy is *no choices*. Where GPG offers dozens of algorithms, cipher modes, expiry policies, signature schemes, and a 30-year-old key format, age picks one option for each and bakes it into the format:

- **X25519** for the asymmetric key exchange.
- **ChaCha20-Poly1305** for the authenticated symmetric encryption of the payload.
- **HKDF-SHA-256** for deriving keys.
- **scrypt** for passphrase-based encryption.

There is no `--cipher-algorithm` flag because there is no other cipher. The format spec fits on a handful of pages.

The keys are also deliberately small and obvious. A public key (a *recipient*) is a single line like:

```
age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p
```

A private key (an *identity*) looks like:

```
AGE-SECRET-KEY-1GFPYYSJZGFPYYSJZGFPYYSJZGFPYYSJZGFPYYSJZGFPYYSJZGFPYY7H7CCH
```

You can paste either of those into a Slack message or a YAML file without ceremony. There are no keyrings, no trust webs, no expiry handling — an age recipient is just a bit of bech32-encoded text.

A minimal age session looks like this:

```bash
# Generate a keypair. Public key is printed to stderr; private key written to file.
age-keygen -o key.txt

# Encrypt to a recipient, producing an ASCII-armored or binary blob.
age -r age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p \
    secrets.env > secrets.env.age

# Decrypt with the matching identity.
age -d -i key.txt secrets.env.age
```

age also accepts SSH keys as recipients (both `ssh-ed25519` and `ssh-rsa`), so you can encrypt to a teammate using their existing GitHub SSH keys without them having to install age first. Multiple recipients are supported — pass `-r` repeatedly and any one of them can decrypt the file.

That is, in essence, everything age does. It is a file encryption primitive, not a secrets manager. It does not know what YAML is, it does not understand directory structure, it does not edit files in place, and it does not pick keys for you. That is where SOPS comes in.

## What SOPS adds on top

[SOPS](https://getsops.io/) — Secrets OPerationS — started life inside Mozilla in 2015 and is now a Cloud Native Computing Foundation sandbox project under the `getsops` organisation on GitHub. It solves a problem age does not: how to encrypt **structured configuration files** in a way that is *still useful as a configuration file*.

If you just `age -r ... config.yaml > config.yaml.age`, you get an opaque blob. You cannot diff it. You cannot see in a code review that someone added a new key called `analytics_token`. You cannot let one tool read the `database.host` field (which is not sensitive) while restricting the `database.password` field (which is). And you cannot easily edit it without manually decrypting, editing, re-encrypting, and shredding the plaintext.

SOPS encrypts **only the values**, leaving keys and structure in plaintext. A YAML file that started as:

```yaml
database:
  host: db.internal
  user: app
  password: hunter2
api_keys:
  stripe: sk_live_abc123
```

becomes, after `sops encrypt`:

```yaml
database:
    host: ENC[AES256_GCM,data:9Hk=,iv:...,tag:...,type:str]
    user: ENC[AES256_GCM,data:cFc=,iv:...,tag:...,type:str]
    password: ENC[AES256_GCM,data:Jh9o=,iv:...,tag:...,type:str]
api_keys:
    stripe: ENC[AES256_GCM,data:vqVx...,iv:...,tag:...,type:str]
sops:
    age:
      - recipient: age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p
        enc: |
          -----BEGIN AGE ENCRYPTED FILE-----
          ...
          -----END AGE ENCRYPTED FILE-----
    lastmodified: "2026-05-16T14:30:03Z"
    mac: ENC[AES256_GCM,data:...]
    version: 3.13.1
```

Notice three things. First, the keys (`database`, `host`, `password`, `api_keys`, `stripe`) are still readable — so a code reviewer can see that a new credential was added even if they cannot decrypt its value. Second, every value has its own initialisation vector, so equal values do not produce equal ciphertexts. Third, the file gained a `sops` metadata block at the bottom listing how to recover the underlying encryption key.

That metadata block is the heart of the architecture, and it is what makes SOPS+age more than just "age plus YAML".

## The data key and master keys

When SOPS encrypts a file, it does not encrypt each value directly with your age key. Instead it generates a fresh random 256-bit symmetric key — the **data encryption key**, or DEK — and uses it to encrypt every leaf value with AES-256-GCM. Then it encrypts the DEK *itself* with each of your configured "master keys" — your age recipient, your AWS KMS key, your PGP fingerprint, whatever you have configured — and stores those wrapped copies in the metadata block.

```
            ┌───────────────────────────────┐
            │ Random data key (DEK, 256 bit)│
            └──────┬───────────────────┬────┘
                   │ encrypts          │ is wrapped by
       ┌───────────▼─────────┐ ┌───────▼──────────────┐
       │ Every leaf value in │ │ age recipient(s),    │
       │ the YAML/JSON/ENV   │ │ KMS key(s), PGP key, │
       │ document            │ │ ... (your masters)   │
       └─────────────────────┘ └──────────────────────┘
```

This two-layer design buys you several practical superpowers:

1. **Multiple recipients without re-encrypting the body.** Adding a new team member's age key only requires wrapping the existing DEK with one more recipient. The bulk of the file does not change, which keeps Git diffs sane.
2. **Mixing key types.** You can wrap the same DEK with an age key for local development *and* an AWS KMS key for production CI/CD, so a developer with their age key and a CI runner with KMS credentials can both decrypt without sharing material.
3. **Key rotation is cheap.** Re-wrapping the DEK with a new set of masters is fast. Re-keying the values themselves (with `sops rotate`) is also possible when you want to invalidate old copies.

For higher-stakes setups, SOPS supports **key groups** that split the DEK across multiple groups using Shamir's Secret Sharing. With a threshold of 2 out of 3 groups, decryption requires keys from any two of the three groups, which lets you require, say, both an age key from a developer *and* a cloud KMS key from CI in order to read production secrets.

## The .sops.yaml configuration file

You do not pass age recipients on the command line every time you encrypt something. SOPS reads a `.sops.yaml` file from the root of your repository (walking upward from the file being encrypted) and uses its **creation rules** to decide which keys to use based on the file path.

A typical config for a small project might look like this:

```yaml
creation_rules:
  # Production secrets — encrypted to the prod age key only.
  - path_regex: secrets/prod/.*\.yaml$
    age: >-
      age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p

  # Dev secrets — encrypted to every developer's age key.
  - path_regex: secrets/dev/.*\.yaml$
    age: >-
      age1devalicexxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,
      age1devbobxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

  # Kubernetes Secret manifests — only encrypt the data fields.
  - path_regex: k8s/.*-secret\.yaml$
    encrypted_regex: ^(data|stringData)$
    age: >-
      age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p
```

A few things to notice. The rules are evaluated in order and **the first match wins**, so put more specific paths above more general ones. The `encrypted_regex` field tells SOPS to only encrypt values whose *key* matches the pattern — useful for Kubernetes Secret manifests, where `apiVersion`, `kind`, and `metadata` must remain readable for `kubectl apply` to function, but the values under `data`/`stringData` carry the actual secrets. The sister knob `unencrypted_regex` flips the logic the other way.

With a `.sops.yaml` in place, the daily workflow becomes:

```bash
# Create a new encrypted file from scratch.
sops edit secrets/prod/api.yaml
# (your $EDITOR opens with a plaintext buffer; on save, SOPS encrypts it)

# Edit an existing encrypted file. Same command — SOPS detects it.
sops edit secrets/prod/api.yaml

# Show a decrypted view (no editing) to stdout.
sops decrypt secrets/prod/api.yaml

# Encrypt an existing plaintext file in place.
sops encrypt --in-place secrets/prod/api.yaml

# Rotate the data key (e.g. after a suspected leak).
sops rotate --in-place secrets/prod/api.yaml
```

The `edit` command is the one you will run most. It decrypts to a temporary file, opens your `$EDITOR`, watches for changes, and re-encrypts on exit — and crucially, the plaintext only ever exists for the duration of that edit and is shredded afterward.

## Where the private key lives

SOPS looks for age identities in a small number of places, in this order: the file pointed to by `$SOPS_AGE_KEY_FILE`, the literal value of `$SOPS_AGE_KEY`, or the default location `$XDG_CONFIG_HOME/sops/age/keys.txt` (which is typically `~/.config/sops/age/keys.txt` on Linux and `~/Library/Application Support/sops/age/keys.txt` on macOS).

That file holds one or more `AGE-SECRET-KEY-1...` lines, optionally with `# comment` lines describing each. SOPS will try every key in the file when decrypting, so you can keep your personal key, a CI key, and a shared team key all in the same place.

This separation is the load-bearing security boundary in the whole system. The **encrypted files are in Git**; the **private key is not**. If a developer leaves the team, you rotate the relevant secrets and re-encrypt them without that person's age recipient. If a CI runner is compromised, you revoke that machine's age identity and rotate. If the keys file leaks, all bets are off — so most teams treat `~/.config/sops/age/keys.txt` as the same class of sensitive artifact as an SSH private key.

For CI/CD and production decryption, the choices are roughly:

- **Age key as a CI secret.** Store the `AGE-SECRET-KEY-1...` string in your CI system's secret store, expose it as `$SOPS_AGE_KEY`, and the runner can decrypt. Simple, but the CI vault is now the new root of trust.
- **Cloud KMS as a co-recipient.** Wrap the same DEK with both an age recipient (for humans) and a KMS key (for CI). The CI runner authenticates to the cloud and decrypts via IAM — no long-lived secret to leak.
- **Kubernetes operator (Flux / kustomize-controller).** Mount the age private key as a Secret named `sops-age` and let Flux's kustomize-controller decrypt manifests on the fly as it reconciles. The cluster becomes the only place the key lives.

## Common patterns and watch-outs

A handful of patterns recur across nearly every SOPS+age deployment.

**One age key per developer, multiple recipients per file.** Each engineer generates their own age key once and shares only the public recipient. New hires get added to the `.sops.yaml`, and existing files are *updated in place* with `sops updatekeys` so they can decrypt without anyone re-typing the secrets.

**Partial encryption for Kubernetes Secrets.** Use `encrypted_regex: ^(data|stringData)$` so that `kubectl` can still read `metadata.name`, `kind`, and friends, but the credentials are encrypted. This is also what GitOps tools like Flux expect.

**Keep `.sops.yaml` in the repo, keep `keys.txt` out of it.** The recipient file is public configuration; the identity file is a credential. A `.gitignore` rule for `keys.txt` (or, better, keeping it entirely outside the repo) prevents the most common accident.

**Beware of editor swap files and shell history.** `sops edit` is safe, but `sops decrypt > /tmp/foo` and then editing `/tmp/foo` is not, because `/tmp/foo` is now an unencrypted plaintext copy of your production credentials. Stick with `sops edit`.

**Diff readability matters.** SOPS attempts to keep diffs small — the IVs for unchanged values stay stable across edits — but a rotated DEK *will* change every line. Treat `sops rotate` as a deliberate event, not something you do casually before a code review.

**It is encryption, not a secrets manager.** SOPS does not do access logging, automatic rotation, ephemeral credentials, or break-glass workflows. If you need any of those, SOPS is a building block, not the whole stack — pair it with a real secrets backend (Vault, AWS Secrets Manager, etc.) for the dynamic parts and use SOPS only for the static ones.

## When SOPS+age is the right answer

The combination shines for **small to mid-size teams doing GitOps**: a single Kubernetes platform team that owns its repositories, a startup whose dev and prod environments live in Terraform, an open-source project that wants encrypted CI configuration. The mental model is simple, the tooling is two static binaries, and there is no extra infrastructure to run.

It is less appropriate when you need centralised access logging, automatic credential rotation, short-lived dynamic credentials, or fine-grained per-secret ACLs that can change without a Git commit. At that point you have outgrown the "secrets in Git" model and should be looking at a dedicated secrets backend.

But for the very common case of "we have a handful of static credentials, we want them next to the code that uses them, and we want a code-review trail when they change" — SOPS plus age is the smallest amount of moving parts that gives you everything Git already gives you, with the secrets no longer in the clear.
