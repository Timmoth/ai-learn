Welcome. In this lesson we are going to talk about managing secrets in code repositories using two tools that fit together very well: SOPS and age. SOPS stands for Secrets OPerationS, and age is a modern file encryption tool. By the end of this lesson you should understand why encrypted secrets in Git is even a sensible idea, how SOPS and age each contribute to that idea, what an encrypted file actually looks like under the hood, and what the day-to-day workflow looks like once you have it set up.

Let us start with the obvious question. Every non-trivial codebase eventually accumulates a pile of sensitive strings. Database passwords. API tokens. TLS private keys. OAuth client secrets. Third-party webhook signing secrets. The question is not whether you have secrets. The question is where they live.

The lazy answer is a .env file that you pass around on Slack. The slightly less lazy answer is some environment-specific vault that only the ops team touches. The answer this lesson is about is encrypted alongside your code, in Git, readable only by people who hold the right keys.

Now, the instinct against secrets in Git is correct in its raw form. Committing the literal value password equals hunter2 to a public repository is a fast way to find your AWS bill quadrupled by a crypto miner. The whole point of SOPS and age is that the thing you commit is not the password itself. It is a ciphertext. The plaintext only ever exists in memory on a machine that holds the right private key.

Once that property holds, encrypting secrets in Git gets you back the three things that make infrastructure as code and GitOps work in the first place.

The first is reproducibility. A fresh clone of the repository is a complete deployable artifact. There is no separate step where you go fetch the production database password from another system.

The second is reviewability. Secret changes go through the same pull request flow as everything else. Adding a new credential is reviewed. Rotating one is reviewed. Granting a new teammate access is reviewed.

The third is auditability. Your git log tells you when each secret was added, when it was rotated, and who approved the change.

There is a catch, and it is operational. The key that decrypts the secrets has to live somewhere safe, and outside the repository. SOPS and age make the in-repo part cheap, but they do not magically solve key custody. We will come back to that toward the end.

So, let us talk about what age actually is. The name is short for Actually Good Encryption, and it is also a pun on the German word for key. It was written by Filippo Valsorda, originally during his time on the Go security team. It was designed as a deliberate, opinionated alternative to GPG for one specific job, which is encrypting a file to one or more recipients.

The design philosophy is, essentially, no choices. Where GPG offers dozens of algorithms, cipher modes, expiry policies, signature schemes, and a thirty-year-old key format, age picks one option for each and bakes it into the format.

Under the hood, age uses X25519 for the asymmetric key exchange. It uses ChaCha20-Poly1305 for the authenticated symmetric encryption of the file payload. It uses HKDF with SHA-256 for deriving keys. And it uses scrypt for passphrase-based encryption. There is no flag to pick a different cipher, because there is no other cipher. The format specification fits on a handful of pages.

The keys are also deliberately small and obvious. A public key, which age calls a recipient, is a single line that starts with age1 followed by a long string of bech32 characters. A private key, which age calls an identity, looks similar but starts with the literal string AGE-SECRET-KEY-1. You can paste either of those into a chat message or a YAML file without any ceremony. There are no keyrings, no webs of trust, no expiry handling. An age recipient is just a small piece of text.

The workflow for age alone is about as simple as you would expect. You run age-keygen to produce a keypair. The public recipient is printed to your terminal and the private identity is written to a file. To encrypt, you pass age the recipient string with the -r flag, give it some input, and it writes a ciphertext to standard output. To decrypt, you pass it the -d flag along with your identity file using -i. That is essentially the whole command-line interface.

age also accepts SSH keys as recipients. Both ssh-ed25519 and ssh-rsa keys work. That means you can encrypt to a teammate using their existing GitHub SSH keys without them having to install age first. You can also encrypt to multiple recipients by passing -r repeatedly, and then any one of those recipients can decrypt the file.

So that is, in essence, everything age does. It is a file encryption primitive, not a secrets manager. It does not know what YAML is. It does not understand directory structure. It does not edit files in place. And it does not pick keys for you. That is where SOPS comes in.

SOPS started life inside Mozilla in 2015 and is now a Cloud Native Computing Foundation sandbox project under the getsops organisation on GitHub. It solves a problem that age does not. If you just run age on a YAML configuration file, you get back an opaque blob. You cannot diff it. You cannot see in a code review that someone added a new key called analytics_token. You cannot let one tool read the database host field, which is not sensitive, while restricting the database password field, which is. And you cannot easily edit it, because every edit would mean manually decrypting, opening the editor, re-encrypting, and shredding the plaintext.

The key idea is that SOPS encrypts only the values, leaving the keys and the structure of the document in plaintext. So if your file started as a YAML document with a database section containing a host, a user, and a password, and an api_keys section containing a Stripe key, after SOPS encrypts it the keys themselves, the literal words database, host, user, password, and api_keys, are all still readable. But each of their values has been replaced with a string that begins with ENC AES256 GCM and ends with a base64 ciphertext blob, an initialisation vector, and an authentication tag.

There are three things worth noticing about this. First, the structure is still readable, so a code reviewer can see that a new credential was added even if they cannot decrypt its value. Second, every value gets its own initialisation vector, so two equal plaintext values do not produce two equal ciphertexts. And third, the file gains a sops metadata block at the bottom, which lists how to recover the underlying encryption key.

That metadata block is the heart of the architecture, and understanding it is what makes SOPS plus age more than just age plus YAML.

Here is the mental model. When SOPS encrypts a file, it does not encrypt each individual value directly with your age key. Instead, it generates a fresh random 256-bit symmetric key, called the data encryption key, or DEK for short. It uses that data key to encrypt every leaf value in the document with AES-256 in GCM mode. Then, separately, it encrypts the data key itself with each of your configured master keys. That could be your age recipient, an AWS KMS key, a PGP fingerprint, whatever you have set up. Those wrapped copies of the data key are what gets stored in the metadata block.

This two-layer design buys you several practical superpowers.

You get multiple recipients without re-encrypting the body. Adding a new team member's age key only requires wrapping the existing data key with one more recipient. The bulk of the file does not change, which keeps Git diffs sane.

You can also mix key types. You can wrap the same data key with an age key for local development and an AWS KMS key for your CI pipeline. So a developer with their age key and a CI runner with KMS credentials can both decrypt without sharing any key material.

And key rotation is cheap. Re-wrapping the data key with a new set of masters is fast. Re-keying the values themselves with sops rotate is also possible when you want to invalidate old copies.

For higher-stakes setups, SOPS also supports something called key groups, which split the data key across multiple groups using Shamir's Secret Sharing. With a threshold of two out of three groups, decryption requires keys from any two of the three groups. That lets you require, say, both a developer's age key and a cloud KMS key from CI in order to read production secrets.

Now let us talk about how SOPS knows which key to use for which file. You do not pass age recipients on the command line every time. SOPS reads a .sops.yaml file from the root of your repository, walking upward from the file being encrypted, and uses its creation rules to decide which keys to use based on the file's path.

A typical configuration has a list of creation rules, each with a path regex and a list of age recipients. You might have one rule that matches files under secrets/prod that encrypts to a single production age key. Another rule that matches files under secrets/dev that encrypts to every developer's age key. And a third rule for Kubernetes Secret manifests that uses an encrypted_regex setting to encrypt only values under the data and stringData fields, leaving the rest of the manifest readable so that kubectl apply still works.

A few things are worth knowing about creation rules. They are evaluated in order, and the first match wins, so put more specific paths above more general ones. The encrypted_regex field tells SOPS to only encrypt values whose keys match the pattern, which is what you want for Kubernetes Secrets, because apiVersion, kind, and metadata must stay readable. There is also a sister knob called unencrypted_regex that flips the logic the other way. It encrypts everything except keys matching the pattern.

With a .sops.yaml file in place, the day-to-day workflow becomes pleasant. To create a new encrypted file from scratch, you run sops edit followed by the path. Your editor opens with a plaintext buffer. You type the secret. You save. And SOPS encrypts the file when you exit the editor.

To edit an existing encrypted file, you run the same command. SOPS detects that it is encrypted, decrypts it into the editor, watches for changes, and re-encrypts on exit. Crucially, the plaintext only exists for the duration of that edit and is shredded afterward.

To just look at the decrypted contents, you run sops decrypt. To encrypt an existing plaintext file in place, you run sops encrypt with the --in-place flag. And to rotate the data key, for example after a suspected leak, you run sops rotate with --in-place.

The edit command is the one you will run most. It is the safe path. Anything that writes plaintext to a temporary file outside of sops edit is a footgun, because you now have an unencrypted copy of your production credentials sitting on disk.

Now, where does the private key live? SOPS looks for age identities in a small number of places, in order. First, the file pointed to by the SOPS_AGE_KEY_FILE environment variable. Second, the literal contents of the SOPS_AGE_KEY environment variable. And finally, a default location at XDG_CONFIG_HOME/sops/age/keys.txt, which on Linux is usually under your home directory in .config, and on macOS is under Library and then Application Support.

That file holds one or more identity lines, optionally with comment lines describing each. SOPS will try every key in the file when decrypting, so you can keep your personal key, a CI key, and a shared team key all in the same place if you like.

This separation between encrypted files and private keys is the load-bearing security boundary in the whole system. The encrypted files are in Git. The private key is not. If a developer leaves the team, you rotate the relevant secrets and re-encrypt them without that person's age recipient. If a CI runner is compromised, you revoke that machine's age identity and rotate. If the keys file itself leaks, all bets are off, so most teams treat it as the same class of sensitive artifact as an SSH private key.

For CI/CD and production decryption, you have roughly three choices.

The first is to store the age private key as a CI secret, expose it through the SOPS_AGE_KEY environment variable, and let the runner decrypt. Simple, but the CI vault is now the new root of trust.

The second is to use a cloud KMS as a co-recipient. You wrap the same data key with both an age recipient for humans and a cloud KMS key for CI. The CI runner authenticates to the cloud and decrypts through its IAM identity, so there is no long-lived secret to leak.

The third is common in Kubernetes-native setups. A controller like Flux's kustomize-controller has the age private key mounted as a Kubernetes Secret called sops-age, and it decrypts manifests on the fly as it reconciles. The cluster becomes the only place the key lives.

A handful of patterns recur across nearly every SOPS and age deployment.

One age key per developer, with multiple recipients per file. Each engineer generates their own age key once and shares only the public recipient. New hires get added to the .sops.yaml, and existing files are updated in place with sops updatekeys so they can decrypt without anyone re-typing the secrets.

Partial encryption for Kubernetes Secrets, using encrypted_regex so that kubectl can still read fields like name and kind, but the credentials themselves are encrypted. This is also what GitOps tools like Flux expect.

Keep .sops.yaml in the repo, and keep the keys file out of it. The recipient file is public configuration. The identity file is a credential. A gitignore rule for keys.txt, or better still keeping it entirely outside the repo, prevents the most common accident.

Beware of editor swap files and shell history. sops edit is safe. But running sops decrypt into some temporary file in /tmp and then editing that is not safe, because that file is now an unencrypted plaintext copy of your production credentials. Stick with sops edit.

Diff readability matters. SOPS tries to keep diffs small. The initialisation vectors for unchanged values stay stable across edits. But a rotated data key will change every line. So treat sops rotate as a deliberate event, not something you do casually before a code review.

And to say it out loud one more time: SOPS is encryption, not a full secrets manager. It does not do access logging. It does not do automatic rotation. It does not issue short-lived dynamic credentials. It does not give you fine-grained per-secret access control that can change without a Git commit. If you need any of those things, SOPS is a building block, not the whole stack. Pair it with a real secrets backend like Vault or AWS Secrets Manager for the dynamic parts, and use SOPS only for the static ones.

So when is the SOPS and age combination the right answer? It shines for small to mid-size teams doing GitOps. A single Kubernetes platform team that owns its repositories. A startup whose dev and production environments live in Terraform. An open-source project that wants encrypted CI configuration. The mental model is simple, the tooling is two static binaries, and there is no extra infrastructure to run.

It is less appropriate when you need centralised access logging, automatic credential rotation, short-lived dynamic credentials, or fine-grained per-secret access control that can change without a Git commit. At that point you have outgrown the secrets-in-Git model and should be reaching for a dedicated secrets backend.

But for the very common case where you have a handful of static credentials, you want them next to the code that uses them, and you want a code-review trail when they change, SOPS and age is the smallest amount of moving parts that gives you everything Git already gives you, with the secrets no longer in the clear.

To recap. age is a small, opinionated file encryption tool with tiny keys and no algorithm choices. SOPS sits on top of it and encrypts only the values of structured configuration files, leaving keys and structure readable. The architecture works by generating a per-file data key, encrypting every leaf value with it, and then wrapping that data key once per master key in the metadata block. A .sops.yaml file maps file paths to recipients. The daily commands are sops edit, sops decrypt, sops encrypt, sops rotate, and sops updatekeys. The private key lives outside the repo, usually in keys.txt or a CI secret or a cloud KMS. And the whole approach gives you reproducibility, reviewability, and auditability for static credentials, without pretending to replace a full secrets manager. Thanks for listening.
