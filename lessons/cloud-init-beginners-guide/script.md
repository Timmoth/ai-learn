When you launch a virtual machine on AWS, Azure, GCP, DigitalOcean, OpenStack, or really any modern cloud, something has to turn that generic base image into your specific instance. Something sets the hostname, installs your SSH key, creates your user, applies your packages, and runs your first-boot scripts. On almost every Linux cloud image, that something is cloud-init.

In this lesson we will build a clear mental model of cloud-init. We will cover what it is, the boot stages it runs through, the datasources it reads, the cloud-config YAML you write, and how to test it on your own laptop before you ever pay for a cloud instance.

So let's start with what cloud-init actually is. Cloud-init is an open source program that initializes a cloud instance on first boot. The idea is simple. Cloud providers want to ship one generic image, one golden Ubuntu, one golden RHEL, one golden Amazon Linux, and have every customer's instance customize itself the first time it powers on. Cloud-init is the standard mechanism for doing that customization in a way that works across providers.

It is pre-installed on the official cloud images for Ubuntu, Debian, Fedora, RHEL, CentOS Stream, Rocky, AlmaLinux, openSUSE, FreeBSD, and others. It supports more than thirty datasources, including Amazon EC2, Microsoft Azure, Google Compute Engine, Oracle Cloud, OpenStack, DigitalOcean, VMware, LXD, and a local datasource called NoCloud that we will come back to. And it works equally well on cloud VMs, on-premises hypervisors, and bare metal.

The problem cloud-init solves is mundane but everywhere. Configuring a fresh instance is complex and error-prone. Doing it the same way across many clouds, many distributions, and many instance counts is much worse. Cloud-init turns that whole task into a single YAML file.

Now let's look at how cloud-init works at a high level. It is driven by three inputs.

The first is meta-data. That is the set of facts about the instance, provided by the cloud platform. The instance ID, the hostname, the region, the availability zone, the network configuration. You do not write this. The platform does.

The second is user-data. That is what you hand to the cloud at launch time, telling cloud-init what to do. Most often this is a cloud-config YAML document.

The third is vendor-data. That is optional extra configuration the cloud provider injects for you, for example to install that provider's CLI tool.

Cloud-init pulls all three of these from something called a datasource, merges them into a plan, and then executes that plan in a series of stages.

Now let's walk through those stages, because the order really matters when you are debugging. Cloud-init runs in five sequential stages, and each one is implemented by a systemd unit.

The first stage is detection. Before cloud-init really starts, a small shell tool called ds-identify inspects the running system. It looks at DMI strings, the kernel command line, and the available block devices, and from those clues it figures out which cloud the instance is on. That result decides whether cloud-init runs at all, and which datasource it should use.

The second stage is the local stage, run by the cloud-init-local service. This runs as soon as the root filesystem is mounted read-write, before networking comes up. Its job is to find a local datasource, such as a config drive, a NoCloud seed disk, or kernel command-line arguments, and to apply network configuration. It actually blocks network bring-up so that the network is configured correctly the first time.

The third stage is the network stage, run by the cloud-init-network service. This runs once networking is online, and it is the heavy stage. Cloud-init reaches out to any remote metadata service, fetches the user-data, decompresses or decodes it, processes any include directives and MIME parts, and runs the early modules. That includes disk setup, filesystem creation, mount configuration, and bootcmd. SSH and console login are blocked until this stage finishes.

The fourth stage is the config stage, run by the cloud-config service. This is the bulk of the non-critical configuration. Things like setting the timezone, installing CA certificates, and configuring apt sources happen here. This stage does not block the rest of boot.

The fifth and final stage is called final, run by the cloud-final service. This is the rc.local of cloud-init. It installs packages, runs your runcmd commands, hands off to a real configuration management system like Chef, Puppet, or Ansible-pull if you have asked it to, and emits a final status. Other scripts that need to wait for cloud-init to finish can do that by running cloud-init status with the wait flag.

So here is the key intuition. Networking-sensitive work happens early, in the local and network stages. Most YAML directives run in the config or final stage. And your custom shell commands almost always run at the very end.

Now let's talk about datasources and environment detection. A datasource is cloud-init's name for the way a particular cloud hands cloud-init its data. Each supported cloud has its own datasource module that knows the right URL to hit, the right disk to look at, or the right kernel argument to read.

A few examples will make this concrete. The EC2 datasource fetches data from a link-local HTTP endpoint, at the well-known address 169.254.169.254. The Azure datasource combines a small ovf-env.xml file on an attached CD-ROM with the Instance Metadata Service. The GCE datasource reads from an internal hostname called metadata.google.internal. The ConfigDrive datasource reads from a small attached ISO formatted by the OpenStack provider. And NoCloud reads user-data and meta-data from a local filesystem labelled cidata, with no network involved at all. That is the datasource you will use for local testing.

Detection is almost always automatic. The ds-identify tool figures it out for you. You only need to intervene if you are running cloud-init somewhere unusual. In that case you can pin the datasource list by dropping a small configuration file under /etc/cloud/cloud.cfg.d, listing only the datasources you want cloud-init to try.

Now let's get to the most important part, which is writing cloud-config user-data. User-data can take several formats. The one you will spend almost all of your time on is cloud-config. Cloud-config is a YAML document whose very first line is the literal comment hash cloud-config. That magic header is how cloud-init recognizes the format. Without it, your YAML is silently ignored.

Other supported formats include shell scripts, anything starting with a shebang, include files, gzip-compressed payloads, MIME multipart archives, and Jinja-templated documents. But cloud-config is the one to focus on.

Let's walk through what a realistic cloud-config document looks like, in prose.

At the top, you set identity. You set the hostname to something like web-01. You set the fully qualified domain name to web-01.example.com. You set the timezone to Europe/London.

Next, you create a user. You give the user a name like deploy. You add a description, put them in the sudo group, set their shell to bash, and give them a sudoers rule that lets them run anything as root without a password. You usually set lock_passwd to true, so the user can only log in by key. And you provide one or more public keys under ssh_authorized_keys.

After that comes package management. You set package_update to true to refresh apt, package_upgrade to true to upgrade everything, and you list packages like nginx, git, and curl under the packages key.

Then there is write_files, which drops configuration files into place. For each file you specify a path, an owner, a permissions string like 0644, and the content inline. A common example is writing a small nginx server block that listens on port 80 and serves files from /var/www/html.

And finally there is runcmd, a list of shell commands cloud-init should run at the very end of boot. You might symlink your nginx site config into the enabled directory, restart nginx, and write a small greeting into the web root.

There are a few details that catch beginners out, and they are worth calling out explicitly.

The hash cloud-config line is not optional, and it is not a comment in the YAML sense. Cloud-init parses it as a format marker. Forget it and the rest of the file does nothing.

Next, runcmd runs in the final stage. If you need something earlier, use bootcmd, which runs on every boot, in the network stage.

Also, if you define a users list, it replaces the default user list. If you want to keep the cloud image's default user, like ubuntu, and just add one of your own, include the special value default as the first entry in the users list.

And finally, cloud-config is processed once per instance ID, not once per boot. Re-running it requires either a new instance ID, or running cloud-init clean followed by a reboot.

So, quick recap. Hash cloud-config header is mandatory. Runcmd runs at the end, bootcmd runs earlier on every boot. The users list replaces the default unless you include default. And cloud-init runs once per instance ID.

Now, the cloud-config schema covers a lot more ground than we have time for. Here is a short tour. There are modules to configure apt and yum repositories. There are modules to manage SSH keys and host keys. There are modules to partition disks, create filesystems, and write fstab entries. There is a module to install trusted CA certificates. There is a module to reboot or power off when cloud-init finishes. And there are modules to hand off to Chef, Puppet, or Ansible once the box is reachable. Every module has a JSON schema, and cloud-init schema with the system flag will validate your real user-data against it.

Now let's talk about testing and debugging cloud-init locally. You do not need a cloud account to learn cloud-init. The NoCloud datasource exists precisely so you can hand cloud-init a user-data file and a meta-data file from a local disk image and watch it run inside a VM on your laptop.

The fastest path on a laptop is the cloud-localds helper on Debian or Ubuntu, or the cloud-init snap, together with QEMU. The recipe is short.

First, you write a minimal meta-data file. It contains an instance ID and a local hostname. The instance ID is what cloud-init uses to decide whether this is the first boot, so changing it forces cloud-init to run again.

Then, you write your cloud-config user-data file. Start with the hash cloud-config header. Set a hostname. Define a user with an SSH key. And include a runcmd that does something simple, like writing a marker file under /tmp so you can confirm later that it ran.

Then, you use cloud-localds to bake those two files into a seed ISO with the volume label cidata.

And finally, you boot an Ubuntu cloud image in QEMU. You attach the seed ISO as a second drive, and you forward a local port to the guest's port 22 so you can SSH in. Cloud-init will detect the seed ISO as a NoCloud datasource and apply your configuration.

Once the VM is up, four commands cover almost all of your debugging.

The first is cloud-init status with the long flag. That tells you whether cloud-init has finished and which datasource it picked.

The second is cloud-init schema with the system and annotate flags. That validates the user-data the instance actually received, with inline error annotations.

The third is cloud-init query userdata. That prints the user-data cloud-init saw, after any decoding.

The fourth is cloud-init clean with the logs flag. That wipes all cloud-init state so the next boot behaves like a first boot. This one is essential when you are iterating.

Two log files are worth bookmarking on every cloud-init system you touch. The first is cloud-init.log, under /var/log. This is cloud-init's own structured log of everything it did, by stage and by module. Most "why didn't my module run" questions are answered here. The second is cloud-init-output.log, also under /var/log. That captures the standard output and standard error from runcmd, bootcmd, and package installs. When your shell snippet misbehaves, this is where you find the error.

For an even faster feedback loop, modern Linux distributions support tools like Multipass on Ubuntu and LXD, which spin up a container or a lightweight VM with your cloud-config in under ten seconds.

So let's put it all together. Here is the full mental model in one paragraph. A cloud-init-enabled image boots. The ds-identify tool decides which datasource to use. Cloud-init runs through the local, network, config, and final stages, pulling meta-data, user-data, and vendor-data from that datasource. Your contribution is a hash cloud-config YAML document covering users, packages, files, and commands, and cloud-init's modules apply it at the right stage. Locally, you can reproduce the whole thing with a seed ISO and a cloud image, and you debug it with cloud-init status, cloud-init schema, and the two log files under /var/log.

From here, the natural next step is to write a one-page cloud-config that creates your user, installs your favourite packages, and prints a banner. Then launch it twice. Once locally with NoCloud, and once on whatever cloud you actually use. When the same YAML works in both places, you have learned cloud-init.
