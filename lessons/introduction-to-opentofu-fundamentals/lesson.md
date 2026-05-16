# Introduction to OpenTofu fundamentals

OpenTofu is an open source **infrastructure as code** tool: you describe cloud or on-prem infrastructure in plain text files, and OpenTofu figures out how to create, update, and tear it down. It is governed by the Linux Foundation, written in Go, and licensed under the Mozilla Public License 2.0.

This lesson builds the mental model you need *before* writing your first `.tf` file: what OpenTofu is, where it came from, the pieces of a configuration, the files on disk, and the four commands that drive everything.

## OpenTofu and Terraform: the short story

OpenTofu started life as a fork of HashiCorp's Terraform. In August 2023, HashiCorp re-licensed Terraform under the Business Source License, which restricts commercial use by anyone offering a "competing" product. A coalition of companies — Gruntwork, Spacelift, Harness, Env0, Scalr, and others — forked the last MPL-licensed Terraform release and donated the project to the Linux Foundation. The result is OpenTofu, which keeps the original open source spirit and is governed by a multi-vendor technical steering committee so no single company controls its direction.

The practical consequences for you as a beginner:

- OpenTofu uses the same configuration language (**HCL**, HashiCorp Configuration Language), the same state file format, and the same provider plugin protocol as Terraform 1.5.x.
- The CLI binary is named `tofu` instead of `terraform`. For most existing projects, migrating is as simple as replacing the binary.
- OpenTofu has begun to diverge with features of its own — native state encryption, early variable evaluation, ephemeral values — but the fundamentals you learn here apply identically to Terraform.

For the rest of this lesson, treat OpenTofu as **the** tool. Anything you learn transfers cleanly back to Terraform if you ever need it.

## Infrastructure as code, in one minute

Traditionally, provisioning a cloud server meant clicking through a web console or running ad-hoc shell commands: create a virtual machine, attach a disk, open a port. That works for one box, but it does not scale, it is not reproducible, and there is no record of who changed what.

Infrastructure as code flips that around. You write a file that *describes* what you want — "an AWS EC2 instance of this size, in this subnet, with this security group" — and the tool figures out the API calls needed to get there. Two ideas come along for free:

- **Declarative** — you describe the destination, not every footstep. Re-running the same configuration is safe.
- **Idempotent** — applying a configuration to infrastructure that is already in the desired state changes nothing.

OpenTofu sits in the same family as Terraform, Pulumi, AWS CloudFormation, and Crossplane. Its niche is being **cloud-agnostic**: one configuration language, one workflow, that works against thousands of providers.

## Providers, resources, and data sources

Three concepts make up almost every OpenTofu configuration you will ever write.

### Providers

A **provider** is a plugin that teaches OpenTofu how to talk to a specific API — AWS, Azure, Google Cloud, Kubernetes, GitHub, Cloudflare, Datadog, and so on. The Public OpenTofu Registry hosts thousands of them. Without providers, OpenTofu cannot manage any infrastructure at all; it is the providers that know how to translate "create a virtual machine" into the right HTTP calls.

You declare which providers you need and configure them like this:

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-1"
}
```

The `terraform { required_providers { ... } }` block (yes, still called `terraform` — it is part of the shared language) tells OpenTofu where to download the provider and which versions are acceptable. The `provider "aws" { ... }` block configures the provider itself.

### Resources

A **resource** is a single object that OpenTofu will create, update, or destroy on your behalf — a virtual machine, a DNS record, an S3 bucket, a Kubernetes deployment. Every resource type is implemented by a provider:

```hcl
resource "aws_instance" "web" {
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.micro"

  tags = {
    Name = "web-server"
  }
}
```

The two labels after `resource` are the **type** (`aws_instance` — the `aws` prefix tells you which provider implements it) and a **local name** (`web`) you use to refer to it elsewhere in your configuration, for example as `aws_instance.web.id`.

### Data sources

A **data source** is the read-only cousin of a resource. It lets OpenTofu *look up* information about something that already exists — without managing it — and use that information elsewhere in your configuration. Fetching the latest Amazon Linux AMI ID, reading a secret from Vault, looking up an existing VPC: all data sources.

```hcl
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "web" {
  ami           = data.aws_ami.amazon_linux.id   # <-- using the data source
  instance_type = "t3.micro"
}
```

The mental shorthand: **resources write, data sources read**.

## Essential project files

A configuration file in OpenTofu is any file ending in `.tf` (or `.tofu`, which OpenTofu prefers over a same-named `.tf` and which Terraform ignores). Every `.tf` file in the same directory is concatenated together into one **module** before evaluation — splitting your config into multiple files is purely for human readability and has zero effect on behaviour.

By convention, a small project has three files at the root:

- **`main.tf`** — the core resources, data sources, and provider blocks. The "what to build" file.
- **`variables.tf`** — the input variables your configuration accepts. The "what's adjustable" file.
- **`outputs.tf`** — the values your configuration exposes after it runs. The "what's worth knowing" file.

There is nothing magical about the names; OpenTofu would behave identically if you put everything in `everything.tf`. The convention exists because human readers expect it.

### `variables.tf`

Input variables are how you parameterise a configuration so the same code can deploy to dev, staging, and production:

```hcl
variable "region" {
  type        = string
  description = "AWS region to deploy into"
  default     = "eu-west-1"
}

variable "instance_count" {
  type        = number
  description = "Number of web servers to launch"
  default     = 2

  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 10
    error_message = "instance_count must be between 1 and 10."
  }
}
```

Values are supplied on the command line (`-var`), through `.tfvars` files, or via environment variables prefixed with `TF_VAR_`. Inside the configuration you reference them as `var.region`, `var.instance_count`, and so on.

### `outputs.tf`

Outputs surface useful values after `tofu apply` finishes — IP addresses, generated names, connection strings — for human readers and for other configurations that consume your state remotely:

```hcl
output "web_public_ip" {
  description = "Public IP of the web server"
  value       = aws_instance.web.public_ip
}

output "db_password" {
  value     = aws_db_instance.main.password
  sensitive = true   # hidden in CLI output
}
```

## State files and the `.terraform` directory

Now the part that confuses newcomers most: OpenTofu does not just read your configuration and call APIs. It also keeps a **state file**.

### `terraform.tfstate`

When you create a resource, OpenTofu records its real-world identity — for example, the AWS instance ID `i-0abc123...` — in a JSON file called `terraform.tfstate` in your project directory. The next time you run OpenTofu, it uses the state to answer the question "does the thing I described already exist, and what is its real-world ID?" Without state, OpenTofu would have no way to map your friendly `aws_instance.web` back to the actual instance it created last time.

Three things to remember about state:

1. **It is the source of truth for OpenTofu's view of reality.** Editing it by hand is strongly discouraged — use `tofu state` subcommands instead.
2. **It often contains secrets.** Database passwords, private IPs, generated tokens — anything OpenTofu touches gets recorded. Treat the state file as sensitive.
3. **For team use, store it remotely.** A local `terraform.tfstate` works for one developer, but real teams configure a **backend** (S3, GCS, a TACOS platform, OpenTofu Cloud, etc.) that stores state centrally with locking so two people cannot apply at the same time. OpenTofu 1.7+ also supports native state encryption.

### The `.terraform` directory

`.terraform/` is a hidden directory that OpenTofu creates and manages for you when you run `tofu init`. You do not write to it by hand, and you do not commit it to Git. It holds:

- **Cached provider plugins** — the actual provider binaries downloaded from the registry.
- **Cached modules** — copies of any external modules your configuration references.
- A record of the **currently active workspace** and the **last known backend configuration** (so it can migrate state if you reconfigure the backend).

### The `.terraform.lock.hcl` file

Sitting alongside your `.tf` files (not inside `.terraform/`) is the **dependency lock file**, `.terraform.lock.hcl`. It is automatically created or updated by `tofu init` and records the exact provider versions and cryptographic checksums that were selected for your project. **You commit this file to version control.** It pins your team — and CI — to the same provider builds, and it protects you from someone publishing a tampered provider version. Today the lock file tracks providers only; module versions are not yet locked.

A typical project on disk:

```
my-project/
  main.tf
  variables.tf
  outputs.tf
  terraform.tfvars        # variable values (often gitignored if it has secrets)
  .terraform.lock.hcl     # COMMIT this
  .terraform/             # IGNORE this (.gitignore)
  terraform.tfstate       # local state (don't commit for real projects)
  terraform.tfstate.backup
```

## The init, plan, apply, destroy workflow

Almost everything you do with OpenTofu boils down to four commands, run from your project directory.

### `tofu init`

Initialises a working directory. The first thing you run in any new project. It:

- Downloads the providers declared in `required_providers` into `.terraform/`.
- Downloads any external modules your configuration references.
- Configures the backend (where state lives).
- Creates or updates `.terraform.lock.hcl`.

You re-run `tofu init` whenever you add a new provider, change a backend, or upgrade dependencies.

### `tofu plan`

The preview step. OpenTofu reads your configuration, reads the current state, and queries each provider to see what really exists in the world. It then computes the diff and prints what it would do — what would be **created** (`+`), **updated** (`~`), or **destroyed** (`-`) — without changing anything yet.

```
$ tofu plan
...
Plan: 3 to add, 1 to change, 0 to destroy.
```

You read the plan, sanity-check it, and only then apply. In team workflows the plan is typically posted as a comment on a pull request for review.

### `tofu apply`

Executes the change. By default it computes a plan, prints it, and asks you to type `yes` before doing anything irreversible. Behind the scenes it calls each provider's API to bring the world into line with the configuration, and writes the resulting resource IDs back into the state file. You can save a plan to a file (`tofu plan -out=plan.tfplan`) and apply that exact plan later — a common pattern in CI.

### `tofu destroy`

The opposite of apply. Destroys everything currently tracked in state for the active workspace. Useful for tearing down temporary environments (test infrastructure, ephemeral demos) without manually deleting resources or editing your configuration. Like `apply`, it shows a plan and asks for confirmation first.

The whole development loop:

```
edit *.tf
tofu plan     # what would change?
tofu apply    # do it
# ... later ...
tofu destroy  # remove everything
```

## Putting it together

The full mental model fits in one paragraph. You write **`.tf` files** describing **resources** (and read-only **data sources**), each of which belongs to a **provider** plugin. You run **`tofu init`** to download those providers into the **`.terraform/`** directory and to record their versions in **`.terraform.lock.hcl`**. You run **`tofu plan`** to preview the diff between your configuration and reality, then **`tofu apply`** to make it real. OpenTofu records what it created in **`terraform.tfstate`** so the next run knows what to do. Reusable building blocks live in **modules**, parameters in **variables**, and useful return values in **outputs**. When you no longer need the infrastructure, **`tofu destroy`** tears it down.

From here, the natural next step is to install OpenTofu, write a tiny `main.tf` that creates a single local resource (the `local_file` resource in the `hashicorp/local` provider is a classic starter — it just writes a file to disk and needs no cloud account), and run the full `init` → `plan` → `apply` → `destroy` cycle once. Once that works, you have everything you need to point OpenTofu at a real cloud.
