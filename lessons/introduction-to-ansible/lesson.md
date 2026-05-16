# Introduction to Ansible

Ansible is an open source automation tool used to configure servers, deploy applications, and orchestrate changes across fleets of machines. It belongs to a family of tools called **infrastructure as code**, which lets you describe the state of your systems in plain text files and check those files into version control the same way you would application source code.

This lesson builds the mental model you need *before* writing your first playbook: what Ansible is, what pieces it has, and where everything lives on disk.

## Infrastructure as Code, in one minute

Traditionally, configuring a server meant logging in over SSH and running commands by hand — installing packages, editing config files, restarting services. That works for one box, but it does not scale, it is not reproducible, and there is no record of what changed.

Infrastructure as code flips that around. You write a file that *describes* what you want the server to look like ("the `nginx` package is installed, the config file matches this template, the service is running"), and a tool figures out the steps to get there. Two ideas come along for free:

- **Declarative** — you describe the destination, not every footstep. Re-running the same definition is safe.
- **Idempotent** — applying the configuration to a machine that is already in the desired state changes nothing.

Ansible is one of several tools in this space (Terraform, Pulumi, Chef, Puppet, Salt). Its niche is configuration management and ad-hoc orchestration, with a deliberately small learning curve.

## Architecture: control node and managed nodes

Ansible has two roles in its world:

- **Control node** — the machine where Ansible itself is installed and where you run commands like `ansible-playbook`. This is usually your laptop, a CI runner, or a dedicated automation host.
- **Managed nodes** (also called *hosts*) — the target machines Ansible configures. These can be Linux servers, Windows hosts, network switches, cloud APIs, containers — anything Ansible can reach.

The defining feature is that Ansible is **agentless**. You do not install a daemon on the managed nodes. The control node connects out over standard protocols — SSH for Linux and similar, WinRM for Windows — copies a small Python program (a *module*) over, runs it, captures the result, and deletes it. That is the entire wire protocol.

This is sometimes called a **push** model: the control node initiates every conversation, the managed nodes never call home. Compared to agent-based tools, it means there is nothing extra to keep running on your fleet, nothing to upgrade, and nothing that can drift independently of the source-of-truth definition on the control node.

```
+----------------+        SSH / WinRM        +-----------------+
|  Control node  | ------------------------> |  Managed node   |
|  (ansible-     |   copy + run module       |  (no agent)     |
|   playbook)    | <------------------------ |                 |
+----------------+        result JSON        +-----------------+
```

## Inventory: telling Ansible what to manage

Ansible needs to know which hosts exist and how to group them. That information lives in an **inventory** file, in either INI or YAML format. A minimal INI inventory looks like this:

```ini
mail.example.com

[webservers]
web01.example.com
web02.example.com

[dbservers]
db01.example.com
db02.example.com
```

The bracketed names are **host groups**. Groups are the primary way you select what to act on later: "run this play against all `webservers`," "set these variables for every host in `production`." A host can belong to many groups, groups can nest (a `production` group whose children are `webservers` and `dbservers`), and two special groups, `all` and `ungrouped`, are always available.

The same inventory in YAML:

```yaml
all:
  hosts:
    mail.example.com:
  children:
    webservers:
      hosts:
        web01.example.com:
        web02.example.com:
    dbservers:
      hosts:
        db01.example.com:
        db02.example.com:
```

Inventories can also be **dynamic** — generated on the fly by a plugin that queries AWS, GCP, vSphere, or any other source of truth — which is how teams use Ansible at scale without hand-editing host lists.

## Playbooks, plays, and tasks

The unit you actually run is a **playbook** — a YAML file that describes work to do. A playbook contains one or more **plays**, and each play contains one or more **tasks**.

```yaml
- name: Configure web servers
  hosts: webservers
  become: true

  tasks:
    - name: Ensure nginx is installed
      ansible.builtin.apt:
        name: nginx
        state: present

    - name: Drop the site config in place
      ansible.builtin.template:
        src: site.conf.j2
        dest: /etc/nginx/sites-enabled/site.conf
      notify: Reload nginx

  handlers:
    - name: Reload nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded

- name: Configure database servers
  hosts: dbservers
  become: true
  tasks:
    - name: Ensure postgresql is installed
      ansible.builtin.apt:
        name: postgresql
        state: present
```

A few things to notice:

- A **play** binds a set of hosts (`hosts: webservers`) to a list of tasks. One playbook can contain many plays, each targeting a different group.
- A **task** calls one **module** (`apt`, `template`, `service`) with arguments. Tasks run top-to-bottom, one at a time per host, but in parallel *across* hosts.
- `become: true` is privilege escalation — the equivalent of `sudo` on the managed node.
- **Handlers** are special tasks that only run if something notifies them, and only once at the end of the play. They are the idiomatic way to restart a service after its config changes.

You run a playbook from the control node with `ansible-playbook site.yml -i inventory.ini`.

## Modules: the units of work

A **module** is the actual code that runs on the managed node. Ansible ships with thousands of them — for package managers (`apt`, `yum`, `dnf`, `pacman`), files (`copy`, `template`, `lineinfile`), services (`service`, `systemd`), users, cloud APIs, network devices, and so on.

You will see modules referenced by their **fully qualified collection name** (FQCN), like `ansible.builtin.apt` or `community.general.timezone`. The first two segments identify the **collection** the module ships in. Collections are how Ansible content is packaged and distributed via Ansible Galaxy; `ansible.builtin` is the core set that ships with Ansible itself.

Most modules are **idempotent** — they check the current state first and only make changes when needed. That is what makes it safe to re-run a playbook on the same hosts again and again.

## Roles: reusable bundles

Once a playbook grows past a few dozen tasks, you want to break it apart. The standard unit of reuse is a **role** — a directory with a known layout that bundles tasks, templates, default variables, and metadata together:

```
roles/
  nginx/
    tasks/main.yml          # the role's task list
    handlers/main.yml       # event handlers (restart, reload, ...)
    templates/              # Jinja2 templates (.j2)
    files/                  # static files to copy
    defaults/main.yml       # low-precedence default variables
    vars/main.yml           # high-precedence role variables
    meta/main.yml           # role metadata + dependencies
```

A playbook then becomes a short list of which roles to apply to which hosts:

```yaml
- hosts: webservers
  become: true
  roles:
    - common
    - nginx
    - app
```

Roles can be shared via **Ansible Galaxy**, the community registry, the same way packages are shared on npm or PyPI.

## Project structure: where things live

A typical Ansible project on disk looks like this:

```
my-project/
  ansible.cfg              # project-level configuration
  inventory/
    production             # inventory for prod
    staging                # inventory for staging
  group_vars/
    webservers.yml         # variables for the 'webservers' group
    all.yml                # variables that apply to every host
  host_vars/
    db01.example.com.yml   # variables for a single host
  roles/
    nginx/
    postgres/
  site.yml                 # top-level playbook
  webservers.yml           # narrower playbooks for specific groups
```

A few of these are worth calling out:

- **`ansible.cfg`** sets project-wide defaults: inventory path, default user, number of parallel forks, plugin locations, vault settings. Ansible looks for it in this order and stops at the first match: the `ANSIBLE_CONFIG` environment variable, `./ansible.cfg` in the current directory, `~/.ansible.cfg` in your home directory, then `/etc/ansible/ansible.cfg`. Keeping an `ansible.cfg` at the project root pins everyone on the team to the same defaults.
- **`group_vars/`** and **`host_vars/`** hold variables that automatically attach to a group or a single host. The file name matches the group or host name.
- **`inventory/`** can be one file, several files, or a directory containing both static files and dynamic inventory scripts.
- **Secrets** are typically stored in files encrypted with **Ansible Vault** (`ansible-vault encrypt`), so the encrypted blob can safely live in Git.

## Putting it together

The full mental model is now small enough to fit in one paragraph: from a **control node**, you run `ansible-playbook` against an **inventory** of **managed nodes**. The playbook contains **plays** that map host groups to ordered **tasks**. Each task calls a **module**, which is copied over SSH or WinRM, executed on the managed node, and removed. Reusable bundles of tasks live in **roles**, distributed through **collections** on Ansible Galaxy. Project-wide settings live in `ansible.cfg`, host data in `inventory/`, and variables in `group_vars/` and `host_vars/`.

From here, the natural next step is to install Ansible, point it at a single host (even `localhost`), and run an ad-hoc command like `ansible all -i inventory -m ping`. Once that works, you have everything you need to start writing real playbooks.
