Welcome. In this lesson, we are going to build a clear mental model of Ansible before you write your first playbook.

Ansible is an open source automation tool. People use it to configure servers, deploy applications, and orchestrate changes across fleets of machines. It belongs to a family of tools called infrastructure as code. The idea is that you describe the state of your systems in plain text files, and you check those files into version control, the same way you would treat application source code.

Let's start with infrastructure as code itself, in about a minute.

Traditionally, configuring a server meant logging in over SSH and running commands by hand. You would install packages, edit config files, and restart services. That works for one box, but it does not scale, it is not reproducible, and there is no record of what changed.

Infrastructure as code flips that around. You write a file that describes what you want the server to look like. You might say the nginx package is installed, the config file matches this template, and the service is running. The tool then figures out the steps to get there.

Two ideas come along for free. The approach is declarative, which means you describe the destination, not every footstep, and re-running the same definition is safe. The approach is also idempotent, which means applying the configuration to a machine that is already in the desired state changes nothing.

Ansible is one of several tools in this space, alongside Terraform, Pulumi, Chef, Puppet, and Salt. Its niche is configuration management and ad-hoc orchestration, with a deliberately small learning curve.

Now let's look at the architecture. Ansible has two roles in its world.

The first is the control node. That is the machine where Ansible itself is installed and where you run commands like ansible-playbook. This is usually your laptop, a CI runner, or a dedicated automation host.

The second role is the managed node, sometimes just called a host. Managed nodes are the target machines Ansible configures. They can be Linux servers, Windows hosts, network switches, cloud APIs, or containers. Anything Ansible can reach.

The defining feature of Ansible is that it is agentless. You do not install a daemon on the managed nodes. Instead, the control node connects out over standard protocols. For Linux and similar systems, it uses SSH. For Windows, it uses WinRM. The control node copies a small Python program, called a module, over to the managed node, runs it, captures the result, and then deletes it. That is the entire wire protocol.

This is sometimes called a push model. The control node always initiates the conversation, and the managed nodes never call home. Compared to agent-based tools, this means there is nothing extra running on your fleet, nothing to upgrade on every box, and nothing that can drift independently of the definition on the control node.

So, to recap so far: a control node pushes work out to managed nodes over SSH or WinRM, with no agent on the other side.

Next, we need to talk about inventory. Ansible needs to know which hosts exist and how to group them. That information lives in an inventory file, which you can write in either INI format or YAML format.

In an inventory, you list your hosts and you organize them into groups. A webservers group might contain web01 and web02. A dbservers group might contain db01 and db02. The bracketed names in INI format, or the keys in YAML format, are your host groups.

Groups are the primary way you select what to act on later. You might say run this play against all webservers, or set these variables for every host in production. A single host can belong to many groups. Groups can also nest, so you could have a production group whose children are webservers and dbservers. Two special groups, named all and ungrouped, are always available automatically.

Inventories can also be dynamic. A plugin can generate them on the fly by querying AWS, GCP, vSphere, or any other source of truth. That is how teams use Ansible at scale without hand-editing host lists.

Now we get to the heart of Ansible: playbooks, plays, and tasks.

The unit you actually run is a playbook. A playbook is a YAML file that describes work to do. A playbook contains one or more plays, and each play contains one or more tasks.

A play binds a set of hosts to a list of tasks. For example, one play might target the webservers group and run tasks like making sure nginx is installed using the apt module, dropping a site config in place from a Jinja2 template, and reloading nginx if the config changed. A second play in the same file might target the dbservers group and install PostgreSQL. So one playbook can contain many plays, each targeting a different group.

A task is one step inside a play. Each task calls one module, with some arguments. Tasks run top to bottom, one at a time per host, but in parallel across hosts.

There is also a concept called privilege escalation, which is the equivalent of running sudo on the managed node. You enable it by setting a flag called become to true on a play or a task.

Another important idea is handlers. Handlers are special tasks that only run if another task notifies them, and they only run once, at the end of the play. They are the idiomatic way to restart a service after its config changes.

To execute a playbook, you run ansible-playbook on the control node and pass it the path to your playbook file and your inventory.

Modules are the units of work. A module is the actual code that runs on the managed node. Ansible ships with thousands of them. There are modules for package managers like apt, yum, dnf, and pacman. There are modules for files, like copy, template, and lineinfile. There are modules for services, for users, for cloud APIs, for network devices, and many more.

You will see modules referenced by what is called their fully qualified collection name. For example, the apt module is written as ansible.builtin.apt, and a timezone module from the community might be written as community.general.timezone. The first two parts identify the collection the module ships in. Collections are how Ansible content is packaged and distributed through Ansible Galaxy. The ansible.builtin collection is the core set that ships with Ansible itself.

Most modules are idempotent. They check the current state of the system first and only make changes when needed. That is what makes it safe to re-run a playbook on the same hosts again and again.

The key idea is this: a playbook is a list of plays, each play points at a group of hosts and runs a list of tasks, and each task calls one idempotent module.

Once a playbook grows past a few dozen tasks, you want to break it apart. The standard unit of reuse is a role. A role is a directory with a known layout that bundles tasks, templates, default variables, and metadata together.

A role for nginx might have a tasks folder containing the main task list, a handlers folder for events like restart and reload, a templates folder for Jinja2 template files, a files folder for static files to copy, a defaults folder for low-precedence default variables, a vars folder for high-precedence role variables, and a meta folder that describes the role's metadata and any dependencies on other roles.

Once you have roles, a playbook becomes much shorter. Instead of listing dozens of tasks, it just lists which roles to apply to which hosts. Roles can be shared through Ansible Galaxy, the community registry, the same way packages are shared on npm or PyPI.

Now let's walk through what a real Ansible project looks like on disk.

At the top of the project, you will usually find a file called ansible.cfg. That file sets project-wide defaults, like the inventory path, the default user, the number of parallel forks, plugin locations, and vault settings.

Ansible looks for this configuration file in a fixed order, and it stops at the first match. It checks the ANSIBLE_CONFIG environment variable first. If that is not set, it looks for ansible.cfg in the current directory. If that is missing, it checks for a dotfile version in your home directory. As a last resort, it falls back to a system-wide path under /etc/ansible. Keeping an ansible.cfg file at the root of your project pins everyone on the team to the same defaults.

Inside the project, you will typically also have an inventory folder, sometimes split into production and staging files. You will have a group_vars folder, which holds variables that automatically attach to a group. A file named webservers.yml inside group_vars supplies variables to every host in the webservers group. A file named all.yml supplies variables that apply to every host. There is a parallel folder called host_vars for variables that apply to a single host, where the file name matches the host name.

You will have a roles folder that contains the role directories we just talked about. And you will have one or more playbook files at the top level. A common pattern is a top-level playbook called site.yml that pulls everything together, plus narrower playbooks, like webservers.yml, for working with one slice of your fleet at a time.

Secrets are typically stored in files encrypted with Ansible Vault, using the ansible-vault encrypt command, so the encrypted blob can safely live in Git next to everything else.

Let's put it all together one more time, because the full mental model is now small enough to fit in a single paragraph.

From a control node, you run ansible-playbook against an inventory of managed nodes. The playbook contains plays, and each play maps a group of hosts to an ordered list of tasks. Each task calls a module, which is copied over SSH or WinRM, executed on the managed node, and then removed. Reusable bundles of tasks live in roles, distributed through collections on Ansible Galaxy. Project-wide settings live in ansible.cfg, host data lives in the inventory folder, and variables live in group_vars and host_vars.

From here, the natural next step is to install Ansible on your machine, point it at a single host, even just your own localhost, and run an ad-hoc command, such as a simple ping against all hosts in your inventory. Once that works, you have everything you need to start writing real playbooks.

Thanks for listening.
