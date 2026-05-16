# Hardening a Debian installation

A fresh Debian server is a remarkably sensible default: a small base system, sane permissions, no listening services beyond SSH, and a release cadence that values "boring" above all else. But it is not, out of the box, *hardened*. The defaults are tuned for compatibility and convenience — root can be SSH'd into with a key, the firewall is not enabled, kernel knobs are set for maximum interoperability, and there is nothing watching the auth log for brute-force attempts.

Hardening is the process of reducing what your server exposes and reacting faster when something tries to abuse it. It is not a checkbox you tick once; it is a small handful of layered habits, each of which is cheap on its own. This lesson walks through six of those layers — user accounts, SSH, the firewall, intrusion prevention, patch management, and kernel sysctl knobs — in roughly the order you would apply them to a new machine.

A note on scope: this is the baseline you would apply to a public-facing Linux box that runs a couple of services. It is not a hardened-bastion or a CIS-compliant build. The goal is to push attack surface down by an order of magnitude with an evening's work.

## The threat model in one paragraph

Most attacks against a public Linux server are not bespoke. They are commodity: SSH credential stuffing from a botnet, exploitation of an unpatched service whose CVE was published yesterday, password reuse from a breached dump, kernel exploits aimed at a service running as root. The defences in this lesson are aimed at exactly that population of attacks. Sophisticated, targeted attackers are a different problem and are not what we are solving here.

## Layer 1: user accounts and sudo

The first thing to fix is that you should not be logging in as root. Root SSH access is the single most attractive credential on any Linux box, so the first move is to create a regular admin user and use `sudo` to escalate when needed.

```bash
# As root, once.
adduser tim
usermod -aG sudo tim
```

Debian uses the `sudo` group, not `wheel` — membership of the `sudo` group is what `/etc/sudoers` recognises by default. From this point on, every administrative task should be `sudo <command>`, not a root shell.

A few `sudo` policies are worth getting right early:

- **Always edit `/etc/sudoers` with `visudo`.** It validates syntax before saving. A bad sudoers file can lock you out of `sudo` entirely.
- **Require a password.** `NOPASSWD` is convenient on CI runners but removes the authentication checkpoint that catches an attacker who has gained a shell but not the password.
- **Drop file-specific exemptions rather than blanket exemptions.** If a script genuinely needs to run one specific command without a password, scope the `NOPASSWD` entry to that command, not the whole user.
- **Audit `getent group sudo` periodically.** People leave. Their privileges should leave with them.

While you are here, lock the root password so that nobody can log in as root locally either:

```bash
sudo passwd -l root
```

You can still get a root shell via `sudo -i` because `sudo` doesn't care about root's password; locking it just removes a credential nobody should be using.

A separate concern is password quality for the human accounts that remain. Debian ships with `libpam-pwquality`, which lets you set minimum length, character class requirements, and dictionary checks via `/etc/security/pwquality.conf`. For a server where the only password is a sudo password, requiring twelve characters with at least one of each class is reasonable. For a server where humans never type a password at all (key-only SSH, sudo with `pam_ssh_agent_auth` or similar), it matters less.

## Layer 2: SSH hardening

SSH is the front door and almost certainly the only service exposed to the internet. The threats are well understood: credential brute-forcing, weak ciphers, and the occasional vulnerability in `sshd` itself. The defences are correspondingly well understood.

### Switch to key-based authentication

Generate an Ed25519 keypair on your workstation (not on the server):

```bash
ssh-keygen -t ed25519 -C "tim@workstation"
```

Ed25519 is the right default in 2026. It produces a 32-byte private key, a public key that fits on one line, and it is faster and smaller than RSA for the same security level. The only reason to use RSA today is to talk to a system running OpenSSH older than 6.5, which is rare on anything you would call a server.

Copy the public key to the server:

```bash
ssh-copy-id tim@server.example.com
```

That places it in `~/.ssh/authorized_keys` with the right permissions. Test that you can log in with the key *before* disabling password auth.

### Edit `/etc/ssh/sshd_config`

The hardened settings are small and predictable. Most live in `/etc/ssh/sshd_config`, though on modern Debian the file ends with `Include /etc/ssh/sshd_config.d/*.conf`, so dropping a file under that directory (e.g. `99-hardening.conf`) is usually neater than editing the main file:

```text
# Disable root SSH entirely.
PermitRootLogin no

# Key-only authentication.
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no

# Restrict who may even attempt to log in.
AllowUsers tim

# Limit brute-force exposure.
MaxAuthTries 3
MaxSessions 4
LoginGraceTime 30

# Drop idle/half-dead sessions.
ClientAliveInterval 300
ClientAliveCountMax 2

# Misc lockdown.
X11Forwarding no
AllowTcpForwarding no
PermitUserEnvironment no
```

Brief notes on each block. `PermitRootLogin no` is stricter than Debian's default of `prohibit-password` and is the right choice once your sudo user works. `PasswordAuthentication no` is the single highest-impact change on the whole list — it removes the entire population of credential-stuffing attacks, because there is no password to stuff. `AllowUsers` is a positive allowlist: even if a future package adds a system user, that user cannot SSH in unless they are on this line. `MaxAuthTries` of 3 is enough for a typo and not enough for a brute-force, and combined with the small `LoginGraceTime` it makes the per-connection cost of a brute-force attack noticeable.

### Test the configuration before restarting

The number-one hardening mistake on a remote server is locking yourself out. Always:

```bash
# Validate syntax. No output means OK.
sudo sshd -t

# Keep your current SSH session open. In a new terminal:
sudo systemctl reload ssh
ssh tim@server.example.com   # confirm key login still works
```

If anything goes wrong, the open session lets you fix it. Only close your original session after you have verified a fresh login.

### Cipher hygiene (optional, low effort)

Modern OpenSSH defaults are already good. If you want belt-and-braces, you can pin the algorithms to the modern set:

```text
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org
HostKeyAlgorithms ssh-ed25519,rsa-sha2-512
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
```

You can let `ssh-audit` (a small Python tool) tell you exactly what your `sshd` is currently advertising and where the weak spots are.

### About changing the SSH port

Moving SSH off port 22 is folklore advice. It does cut a lot of noise out of your auth log, because the loudest scanners only hit port 22, but it is not a security feature — a real scanner finds the new port in seconds. Treat it as log hygiene, not as defence. If you change the port, remember to update your firewall rule and your fail2ban jail.

## Layer 3: the firewall

On a fresh Debian, the kernel's `netfilter` framework is sitting there doing nothing useful, because no rules are loaded. The job of a firewall on a server is to enforce *default deny* on inbound traffic — explicitly allow the ports your services need, drop everything else. On Debian, the easiest way to do that is UFW.

### What UFW actually is

UFW — Uncomplicated Firewall — is a thin frontend over the kernel's packet filter. On Debian 12 (Bookworm) the backend is `iptables`; on Debian 13 (Trixie) and on modern distributions in general it has shifted to `nftables`. From the user's perspective UFW behaves the same; the commands you type produce rules that the kernel enforces.

UFW is not the only option. `nftables` directly is more powerful and is the modern Linux standard. `firewalld` is common on Red Hat-family distributions. For a single Debian server, UFW's terseness is its main selling point — it is hard to write a confused UFW rule.

### A safe baseline

The fundamental gotcha with any firewall configuration over SSH is identical to the SSH gotcha: you can lock yourself out. The cure is to allow SSH *first*, then enable the firewall:

```bash
sudo apt install ufw

# Set defaults. Block all inbound, permit all outbound.
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Explicitly allow SSH on whatever port you use.
sudo ufw limit 22/tcp

# Permit the application ports this server actually serves.
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Now enable.
sudo ufw enable
```

The `limit` verb is worth knowing: it allows the connection but rate-limits a source IP to roughly six attempts in 30 seconds, dropping anything past that. It is a small, free rate-limiter on the SSH port and stacks well with fail2ban below.

`ufw status verbose` shows the current ruleset. `ufw status numbered` is the variant you want when you need to delete a specific rule by its index.

### IPv6

If your server has IPv6 — and most modern hosting does — confirm that `/etc/default/ufw` contains `IPv6=yes`. UFW will then apply equivalent rules to both stacks, which is what you want; otherwise you may have a tightly closed IPv4 perimeter and a wide-open IPv6 one. This is one of the more common ways a "hardened" server is silently exposed.

### When to drop down to nftables/iptables

UFW is fine for a single-purpose server. If you need stateful matching beyond simple port rules — say, geo-blocking, complex NAT, or per-service rate limiting at the packet level — you should be reaching for `nftables` directly. The configuration lives in `/etc/nftables.conf` and is a much more expressive language. UFW is the right starting point; it is not the only stop.

## Layer 4: fail2ban and intrusion prevention

Fail2ban is a daemon that does one thing: it tails log files and, when it sees a pattern that matches "this IP just failed authentication N times," it adds a firewall rule that blocks the IP for a while. It is conceptually trivial. It is also remarkably effective against the commodity brute-force traffic that is the single largest source of noise in any public Linux server's auth log.

### Concepts: jail, filter, action

The vocabulary is a little jargon-heavy but small:

- A **filter** is a regex (and a small amount of helper logic) that knows what a "failed auth" line looks like for a particular service. Debian ships filters for sshd, postfix, dovecot, apache-auth, nginx-limit-req, and dozens of others, in `/etc/fail2ban/filter.d/`.
- An **action** is what to do when the filter trips: by default, "add an iptables/nftables rule that drops packets from this IP." Other actions exist (send an email, call a webhook, write to an `ipset`), but the firewall-drop action is the workhorse.
- A **jail** ties a filter to an action and adds the thresholds: which log to watch, how many failures within how much time count as a ban, and how long the ban lasts.

### Configuration

The thing not to do is edit `jail.conf` directly. It is overwritten on package upgrade. Drop your overrides in `/etc/fail2ban/jail.local`:

```ini
[DEFAULT]
# Don't ban these IPs even if they look bad.
ignoreip = 127.0.0.1/8 ::1 10.0.0.0/8

# Window and threshold: 5 failures within 10 minutes triggers a ban.
findtime = 10m
maxretry = 5

# Ban duration. Use longer values once you have confidence.
bantime  = 1h

# Optional: exponentially increase bantime on repeat offenders.
bantime.increment = true
bantime.factor   = 2

[sshd]
enabled  = true
port     = ssh
logpath  = %(sshd_log)s
backend  = systemd
```

Two things in there are worth a moment. First, `backend = systemd` tells fail2ban to read the journal directly rather than tail `/var/log/auth.log`. On modern Debian that is the more reliable source, because `auth.log` may not exist if `rsyslog` is not installed. Second, `bantime.increment = true` is a useful pattern: a first offence gets the configured `bantime`, a second gets twice that, a third gets four times, and so on. The cumulative effect on a determined botnet is significant.

After editing, validate and reload:

```bash
sudo fail2ban-client -t          # check config
sudo systemctl reload fail2ban

# Inspect a jail's current state.
sudo fail2ban-client status sshd

# Manually unban an address if you fat-fingered yourself in.
sudo fail2ban-client set sshd unbanip 198.51.100.7
```

### The honest assessment

Fail2ban is not a substitute for key-based auth, and the project's own README says so. If passwords are off, the brute-forcers cannot succeed anyway, and fail2ban's main contribution becomes keeping your log volume manageable and absorbing some of the connection cost. Run both: key-only auth is the actual defence, fail2ban is the cleanup crew.

## Layer 5: unattended security updates

The most common way a hardened server gets compromised is not a clever attack. It is a published CVE in a service the server runs, and an admin who was meaning to update next week. Automatic security patching closes that window.

Debian's tool for this is `unattended-upgrades`, and on recent releases it is installed by default, just not always enabled. The job is to:

1. Confirm it is installed.
2. Tell it to run.
3. Tell it which origins (security only? security and stable updates? backports?) it is allowed to install from.

```bash
sudo apt install unattended-upgrades apt-listchanges
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

That `dpkg-reconfigure` writes `/etc/apt/apt.conf.d/20auto-upgrades`, which contains the two switches that decide whether anything happens at all:

```text
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
```

The actual policy — *which* upgrades to install — lives in `/etc/apt/apt.conf.d/50unattended-upgrades`. On Debian Bookworm and Trixie the default `Origins-Pattern` includes the security suite and not much else, which is the sane default. You can also enable stable updates by uncommenting the relevant line if you want patch-level releases of stable packages to flow automatically.

A few options in that file are worth setting deliberately:

```text
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-New-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-WithUsers "false";
Unattended-Upgrade::Automatic-Reboot-Time "03:00";
Unattended-Upgrade::Mail "root";
```

`Automatic-Reboot` is the contentious one. A kernel update is not really applied until the system reboots; if you never reboot, you are running with a vulnerable kernel even though the package is installed. For a single-purpose server that can tolerate a brief outage at 03:00, automatic reboots are the right default. For a database primary or anything stateful, you probably want manual reboots and a monitoring rule that nags you if the file `/var/run/reboot-required` exists.

On modern Debian, the scheduler is a pair of systemd timers, `apt-daily.timer` and `apt-daily-upgrade.timer`. You can see when they will next fire with:

```bash
systemctl list-timers apt-daily*
```

You can also do a dry run to see what unattended-upgrades *would* install right now:

```bash
sudo unattended-upgrade --dry-run --debug
```

That is worth running once after the initial setup to confirm everything is wired up.

## Layer 6: kernel and sysctl hardening

`sysctl` is the interface to runtime kernel parameters, most of which can be set persistently in `/etc/sysctl.conf` or, more idiomatically on modern Debian, a file under `/etc/sysctl.d/`. The kernel exposes thousands of parameters; a small subset of them have direct security implications.

The goal of sysctl hardening is to flip off a number of legacy networking behaviours that an attacker can use to spoof traffic, redirect routes, or probe for information about the kernel.

Drop a file at `/etc/sysctl.d/99-hardening.conf`:

```text
# --- Network: spoofing and source-routing ---

# Reject packets whose source address doesn't match the route they came in on.
# Stops most IP spoofing.
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Don't accept attacker-specified routing.
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv6.conf.default.accept_source_route = 0

# Don't trust ICMP redirects from anyone; we're not a router.
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0

# Log anything claiming an unroutable source address.
net.ipv4.conf.all.log_martians = 1

# --- Network: DoS resistance ---

# Cookie out the SYN backlog on flood.
net.ipv4.tcp_syncookies = 1

# Ignore broadcast pings (Smurf amplification).
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1

# --- Kernel: ASLR, info leaks, ptrace ---

# Full address-space layout randomisation.
kernel.randomize_va_space = 2

# Hide kernel pointers from /proc readers.
kernel.kptr_restrict = 2

# Don't let unprivileged users read the kernel ring buffer.
kernel.dmesg_restrict = 1

# Restrict ptrace to direct parent processes. Hard mode is 2 or 3.
kernel.yama.ptrace_scope = 1

# --- Filesystem: link-following races ---

# Block well-known TOCTOU exploits with symlink/hardlink permissions.
fs.protected_symlinks = 1
fs.protected_hardlinks = 1
fs.protected_fifos = 2
fs.protected_regular = 2

# Suid binaries don't write core dumps containing privileged memory.
fs.suid_dumpable = 0
```

Apply without rebooting:

```bash
sudo sysctl --system
```

That re-reads everything under `/etc/sysctl.d/`, `/run/sysctl.d/`, and `/etc/sysctl.conf`.

A note on cargo culting. Every one of those settings has a reason, but some of them have already been the default on Debian for years. `kernel.randomize_va_space = 2`, for example, is already on. Setting it explicitly is harmless and makes the intent legible to the next admin who reads the file, which is the main argument for being explicit. Other settings have real trade-offs: `kernel.modules_disabled = 1` (which some hardening guides suggest) prevents you from loading any kernel module after boot, which is a clean security win and also means you cannot debug an issue by loading `nf_conntrack_ftp` from a recovery shell. Choose what fits your operational model.

## What this leaves uncovered

A pragmatic baseline like this does not address several real concerns. AppArmor is shipped and enabled on Debian — you have a basic mandatory access control layer for free — but writing custom profiles for the services you run is a separate exercise. Centralised log shipping is essential if you actually want to *notice* an attack rather than just deter one; `journald-remote`, `rsyslog`, or a more ambitious tool like Loki or Elastic all play that role. File integrity monitoring (AIDE, Tripwire) and intrusion detection (`auditd`, OSSEC, Wazuh) sit above this baseline. Two-factor auth on SSH via `pam_google_authenticator` or a hardware token via `pam_u2f` is the next obvious step after key-only auth.

The point of the baseline is that it gets you 80% of the way for an evening's work. The remaining 20% are not less important — they are just bigger projects with their own learning curves.

## A reasonable order of operations

A sensible sequence on a brand-new Debian VM:

1. Update everything: `apt update && apt full-upgrade`.
2. Create a sudo user, lock root, get key-based SSH working as the sudo user.
3. Edit `sshd_config`, validate with `sshd -t`, reload, confirm a fresh login still works.
4. Install and configure UFW with default deny and an explicit allowlist (SSH, plus whatever your services need).
5. Install fail2ban with a sane `jail.local`.
6. Install and enable `unattended-upgrades`; do a `--dry-run` to confirm.
7. Drop a `/etc/sysctl.d/99-hardening.conf` and apply.
8. Reboot once, to prove that the box still comes up correctly with every change in place.

That last point is the only one that requires courage. A configuration that works "until the next reboot" is a footgun waiting for the next power event. Cycle the box once while you are still paying attention.
