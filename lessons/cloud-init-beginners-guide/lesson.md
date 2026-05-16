# Cloud-init beginners guide

When you launch a virtual machine on AWS, Azure, GCP, DigitalOcean, OpenStack, or any modern cloud, *something* turns that generic base image into your specific instance — sets the hostname, installs your SSH key, creates your user, applies your packages, and runs your first-boot scripts. On almost every Linux cloud image, that something is **cloud-init**.

This lesson walks you through what cloud-init is, the boot stages it runs through, the datasources it reads, the cloud-config YAML you write, and how to test it on your own laptop before you ever pay for a cloud instance.

## What cloud-init is

Cloud-init is an open source program that initializes a cloud instance on first boot. The idea is simple: cloud providers want to ship one generic image (one "golden" Ubuntu, one "golden" RHEL, one "golden" Amazon Linux) and have every customer's instance customize itself the first time it powers on. Cloud-init is the standard mechanism for doing that customization in a way that works across providers.

It is pre-installed on the official cloud images for Ubuntu, Debian, Fedora, RHEL, CentOS Stream, Rocky, AlmaLinux, openSUSE, FreeBSD, and others. It supports more than thirty datasources, including Amazon EC2, Microsoft Azure, Google Compute Engine, Oracle Cloud, OpenStack, DigitalOcean, VMware, LXD, and the local "NoCloud" datasource you will see later. It works equally well on cloud VMs, on-premises hypervisors, and bare metal.

The problem it solves is mundane but ubiquitous: configuring a fresh instance is a complex, error-prone task, and doing it the same way across many clouds, distros, and instance counts is much worse. Cloud-init turns that task into a single YAML file.

## How cloud-init works at a glance

Cloud-init runs early in the boot process and is driven by three inputs:

- **Meta-data** — facts about the instance, provided by the cloud platform: instance ID, hostname, region, availability zone, network configuration. You do not write this; the platform does.
- **User-data** — what *you* hand the cloud at launch time, telling cloud-init what to do. Most often this is a `#cloud-config` YAML document.
- **Vendor-data** — optional extra configuration the cloud provider injects for you (for example, installing the provider's CLI tool).

Cloud-init pulls all three from a **datasource**, merges them into a plan, and executes that plan in a series of stages.

## Boot stages and execution flow

Cloud-init runs in **five sequential stages**, each implemented by a systemd unit. Understanding the order matters when you are debugging or trying to figure out *why* a particular module did not run when you expected.

1. **Detect (`ds-identify`).** Before cloud-init really starts, a small shell tool called `ds-identify` inspects the running system — DMI strings, kernel command line, available block devices — to figure out which cloud the instance is on. The result decides whether cloud-init runs at all and which datasource it should use.

2. **Local stage (`cloud-init-local.service`).** Runs as soon as the root filesystem is mounted read-write, *before* networking comes up. Its job is to find a *local* datasource (a config drive, a NoCloud seed disk, kernel command-line arguments) and apply network configuration. This stage blocks network bring-up so that the network is configured correctly the first time.

3. **Network stage (`cloud-init-network.service`).** Runs once networking is online. This is the heavy stage: cloud-init reaches out to any remote metadata service, fetches user-data, decompresses or decodes it, processes `#include` directives and MIME parts, then runs the early modules — disk setup, filesystem creation, mount configuration, `bootcmd`. SSH and console login are blocked until this stage finishes.

4. **Config stage (`cloud-config.service`).** Runs the bulk of non-critical configuration modules — things like setting the timezone, installing CA certificates, configuring apt sources. This stage does not block the rest of boot.

5. **Final stage (`cloud-final.service`).** The "rc.local" of cloud-init. Installs packages, runs `runcmd`, applies any configuration-management hand-off (Chef, Puppet, Ansible-pull), and emits a final status. Other scripts that need to wait for cloud-init to finish can do so with `cloud-init status --wait`.

The key intuition: networking-sensitive work goes early (local + network), most YAML directives run in *config* or *final*, and your custom shell commands almost always run at the very end.

## Datasources and environment detection

A **datasource** is cloud-init's name for "the way this particular cloud hands me my data." Each supported cloud has its own datasource module that knows the right URL to hit, the right disk to look at, or the right kernel argument to read. Examples:

- **EC2** — fetches data from the link-local HTTP endpoint at `http://169.254.169.254/`.
- **Azure** — combines a small ovf-env.xml file on an attached CD-ROM with the Instance Metadata Service.
- **GCE** — reads metadata from `metadata.google.internal`.
- **ConfigDrive** — reads from a small attached ISO formatted by the OpenStack provider.
- **NoCloud** — reads user-data and meta-data from a local filesystem labeled `cidata`, with no network involved at all. This is the datasource you will use for local testing.

Detection is almost always automatic — `ds-identify` figures it out. You only need to intervene if you are running cloud-init somewhere unusual; in that case you can pin the datasource list with `/etc/cloud/cloud.cfg.d/99-datasource.cfg`:

```yaml
datasource_list: [ NoCloud, None ]
```

## Writing cloud-config user-data

User-data can take several formats. The most common, and the one you will spend almost all of your time on, is **cloud-config**: a YAML document whose very first line is the literal comment `#cloud-config`. That magic header is how cloud-init recognizes the format — without it, your YAML is silently ignored.

Other supported formats include shell scripts (anything starting with `#!`), `#include` files, gzip-compressed payloads, MIME multipart archives, and Jinja-templated documents.

Here is a small but realistic cloud-config that touches the most common modules:

```yaml
#cloud-config

# Set identity
hostname: web-01
fqdn: web-01.example.com
timezone: Europe/London

# Create a user with an SSH key and sudo access
users:
  - name: deploy
    gecos: Deployment user
    groups: [sudo]
    shell: /bin/bash
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    lock_passwd: true
    ssh_authorized_keys:
      - ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... you@laptop

# Refresh apt and install packages on first boot
package_update: true
package_upgrade: true
packages:
  - nginx
  - git
  - curl

# Drop a config file in place with explicit ownership and mode
write_files:
  - path: /etc/nginx/sites-available/hello.conf
    owner: root:root
    permissions: "0644"
    content: |
      server {
        listen 80 default_server;
        root /var/www/html;
        index index.html;
      }

# Run shell commands at the very end of boot
runcmd:
  - [ ln, -sf, /etc/nginx/sites-available/hello.conf, /etc/nginx/sites-enabled/default ]
  - [ systemctl, restart, nginx ]
  - [ sh, -c, "echo 'hello from cloud-init' > /var/www/html/index.html" ]
```

A few details that catch beginners out:

- The `#cloud-config` line is **not** optional and **not** a comment in the YAML sense — cloud-init parses it as a format marker. Forget it and the rest of the file does nothing.
- `runcmd` runs in the *final* stage. If you need something earlier, use `bootcmd`, which runs on *every* boot in the network stage.
- `users:` replaces the default user list. If you want to keep the cloud image's default user (e.g. `ubuntu`) and *add* one, include `- default` as the first entry.
- Cloud-config is processed once per **instance ID**, not once per boot. Re-running it requires either a new instance ID or a `cloud-init clean` followed by a reboot.

## Other useful modules

The cloud-config schema covers a lot more ground than this lesson can. A non-exhaustive tour of what is commonly used:

- `apt:` and `yum_repos:` — configure package repositories and pinning.
- `ssh_authorized_keys:` and `ssh_keys:` — manage SSH keys and host keys.
- `disk_setup:` and `fs_setup:` and `mounts:` — partition disks, create filesystems, write `/etc/fstab` entries.
- `ca_certs:` — install trusted CA certificates.
- `power_state:` — reboot or power off when cloud-init finishes.
- `chef:`, `puppet:`, `ansible:` — hand off to a real configuration-management system once the box is reachable.

Every module has a JSON schema, and `cloud-init schema --system` will validate your real user-data against it.

## Testing and debugging cloud-init locally

You do not need a cloud account to learn cloud-init. The **NoCloud** datasource exists precisely so you can hand cloud-init a `user-data` and a `meta-data` file from a local disk image and watch it run inside a VM.

The fastest path on a laptop is the `cloud-localds` helper (Debian/Ubuntu) or the `cloud-init` snap, together with `qemu`. The recipe is:

```bash
# 1. Write a minimal meta-data file. The instance-id determines "first boot".
cat > meta-data <<'EOF'
instance-id: iid-local01
local-hostname: cloudinit-demo
EOF

# 2. Write the cloud-config user-data.
cat > user-data <<'EOF'
#cloud-config
hostname: cloudinit-demo
users:
  - default
  - name: tester
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    lock_passwd: true
    ssh_authorized_keys:
      - ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... you@laptop
runcmd:
  - [ sh, -c, "echo it works > /tmp/hello" ]
EOF

# 3. Bake them into a seed ISO labelled "cidata".
cloud-localds seed.iso user-data meta-data

# 4. Boot an Ubuntu cloud image with the seed ISO attached.
qemu-system-x86_64 \
  -enable-kvm -m 2048 -nographic \
  -drive file=ubuntu-cloudimg.qcow2,if=virtio \
  -drive file=seed.iso,if=virtio,format=raw \
  -netdev user,id=n0,hostfwd=tcp::2222-:22 -device virtio-net,netdev=n0
```

On the booted VM, four commands cover almost all debugging:

- `cloud-init status --long` — has cloud-init finished, and which datasource did it pick?
- `cloud-init schema --system --annotate` — validates the user-data you actually received, with inline error annotations.
- `cloud-init query userdata` — prints the user-data cloud-init saw, after any decoding.
- `cloud-init clean --logs` — wipes all cloud-init state so the next boot behaves like first boot. Essential when iterating.

Two log files are worth bookmarking:

- `/var/log/cloud-init.log` — cloud-init's own structured log of everything it did, by stage and module. Most "why didn't my module run?" answers live here.
- `/var/log/cloud-init-output.log` — the captured stdout and stderr from `runcmd`, `bootcmd`, and package installs. When your shell snippet misbehaves, this is where you find the error.

For an even faster loop, modern Linux distributions support `multipass launch --cloud-init user-data.yaml` (Ubuntu) and `lxc launch --config=user.user-data=...` (LXD), which spin up a container or lightweight VM with your cloud-config in under ten seconds.

## Putting it together

The full mental model fits in one paragraph. A cloud-init-enabled image boots, `ds-identify` decides which **datasource** to use, cloud-init runs through the **local**, **network**, **config**, and **final** stages, pulling **meta-data**, **user-data**, and **vendor-data** from that datasource. Your contribution is a `#cloud-config` YAML document — users, packages, files, commands — that cloud-init's modules apply at the right stage. Locally you can reproduce the whole thing with a `seed.iso` and a cloud image, and you debug it with `cloud-init status`, `cloud-init schema`, and the two log files under `/var/log/`.

From here, the natural next step is to write a one-page cloud-config that creates your user, installs your favourite packages, and prints a banner — and to launch it twice: once locally with NoCloud, and once on whatever cloud you actually use. Once the same YAML works in both places, you have learned cloud-init.
