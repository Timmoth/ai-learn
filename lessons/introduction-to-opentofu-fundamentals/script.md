Welcome. In this lesson, we are going to build a clear mental model of OpenTofu, before you ever touch your first configuration file.

OpenTofu is an open source infrastructure as code tool. You describe your cloud or on-premises infrastructure in plain text files, and OpenTofu figures out how to create it, update it, and tear it down. It is governed by the Linux Foundation, written in Go, and licensed under the Mozilla Public License version 2.

By the end of this lesson, you will know what OpenTofu is, where it came from, what the pieces of a configuration look like, what files live on disk, and the four commands that drive the whole tool.

So let's start with where OpenTofu came from. OpenTofu began life as a fork of HashiCorp's Terraform. In August 2023, HashiCorp re-licensed Terraform under something called the Business Source License, which restricts commercial use by anyone offering a competing product. In response, a coalition of companies — Gruntwork, Spacelift, Harness, Env0, Scalr, and others — forked the last open source release of Terraform and donated the project to the Linux Foundation. The result is OpenTofu. It keeps the original open source spirit, and it is governed by a multi-vendor technical steering committee, so that no single company controls its direction.

Here is what that means for you as a beginner. OpenTofu uses the same configuration language as Terraform 1.5, called HashiCorp Configuration Language, or HCL. It uses the same state file format. It uses the same provider plugin protocol. The command line tool is named tofu instead of terraform, and for most existing projects, migrating is as simple as replacing the binary.

OpenTofu has also started to diverge with features of its own, like native state encryption, early variable evaluation, and ephemeral values. But the fundamentals you learn here apply identically to Terraform. So for the rest of this lesson, just treat OpenTofu as the tool. Anything you learn transfers cleanly back to Terraform if you ever need it.

Now, let's talk about infrastructure as code itself, in about a minute.

Traditionally, provisioning a cloud server meant clicking through a web console or running ad-hoc shell commands. You would create a virtual machine, attach a disk, open a port. That works for one box, but it does not scale, it is not reproducible, and there is no record of who changed what.

Infrastructure as code flips that around. You write a file that describes what you want. For example, you might say, I want an AWS EC2 instance of this size, in this subnet, with this security group. The tool then figures out the API calls needed to make it happen.

Two important ideas come along for free. The first is that the approach is declarative. You describe the destination, not every footstep. Re-running the same configuration is safe. The second is that the approach is idempotent. Applying a configuration to infrastructure that is already in the desired state changes nothing.

OpenTofu sits in the same family as Terraform, Pulumi, AWS CloudFormation, and Crossplane. Its niche is being cloud-agnostic. One configuration language, one workflow, that works against thousands of providers.

Now to the heart of the model. Almost every OpenTofu configuration you will ever write is built from three concepts: providers, resources, and data sources.

A provider is a plugin that teaches OpenTofu how to talk to a specific API. So there is an AWS provider, an Azure provider, a Google Cloud provider, a Kubernetes provider, a GitHub provider, a Cloudflare provider, a Datadog provider, and many more. The Public OpenTofu Registry hosts thousands of them. Without providers, OpenTofu cannot manage any infrastructure at all. It is the providers that know how to translate something like "create a virtual machine" into the right HTTP calls.

You declare which providers you need in a special block at the top of your configuration. That block, somewhat confusingly, is still called the terraform block, since it is part of the shared language. Inside it, you list each provider you depend on, including where to download it from and which versions are acceptable. Then, in a separate provider block, you configure each one with things like which region to use.

A resource is a single object that OpenTofu will create, update, or destroy on your behalf. A virtual machine, a DNS record, an S3 bucket, a Kubernetes deployment. Every resource type is implemented by a provider.

When you declare a resource, you give it two labels. The first label is the resource type, for example aws_instance, where the aws prefix tells you which provider implements it. The second label is a local name you choose, like web, which you use to refer to that resource elsewhere in your configuration. You might reference its identifier as aws_instance.web.id, for example.

A data source is the read-only cousin of a resource. It lets OpenTofu look up information about something that already exists, without managing it, and use that information elsewhere in your configuration. Fetching the latest Amazon Linux AMI identifier, reading a secret from Vault, looking up an existing VPC — those are all data sources.

The mental shorthand is simple: resources write, data sources read.

So that is the language. Let's look at the files on disk.

A configuration file in OpenTofu is any file ending in .tf, or in .tofu, which OpenTofu prefers over a same-named .tf and which Terraform ignores. Every .tf file in the same directory is concatenated together into one module before evaluation. That means splitting your configuration into multiple files is purely for human readability. It has zero effect on behaviour.

By convention, a small project has three files at the root. The first is main.tf. It holds the core resources, data sources, and provider blocks. Think of it as the "what to build" file. The second is variables.tf. This declares the input variables your configuration accepts. Think of it as the "what's adjustable" file. The third is outputs.tf. This declares the values your configuration exposes after it runs. Think of it as the "what's worth knowing" file.

There is nothing magical about these names. OpenTofu would behave identically if you put everything in one big file called everything.tf. The convention exists because human readers expect it.

Let's go a bit deeper on those last two files.

Input variables are how you parameterise a configuration, so that the same code can deploy to dev, staging, and production. Each variable has a type, an optional description, an optional default value, and optional validation rules. For instance, you can require that an instance count is between one and ten, and provide an error message that explains why. You supply values on the command line with the dash var flag, through .tfvars files, or through environment variables prefixed with TF_VAR_. Inside the configuration, you reference them as var dot, followed by the variable name.

Outputs surface useful values after tofu apply finishes. Things like a public IP address, a generated name, or a connection string. They are useful both for humans reading the output, and for other configurations that consume your state remotely. You can also mark an output as sensitive, which hides its value from the CLI output.

Now we come to the part that confuses newcomers most: state files and the .terraform directory.

OpenTofu does not just read your configuration and call APIs. It also keeps a state file.

When you create a resource, OpenTofu records its real-world identity in a JSON file called terraform.tfstate, in your project directory. So if it creates an AWS instance, it records the instance identifier. The next time you run OpenTofu, it uses the state file to answer the question: does the thing I described already exist, and what is its real-world identifier? Without state, OpenTofu would have no way to map your friendly aws_instance.web back to the actual instance it created last time.

Three things to remember about state.

First, the state file is the source of truth for OpenTofu's view of reality. Editing it by hand is strongly discouraged. There is a dedicated tofu state subcommand for any surgery you need to perform.

Second, state often contains secrets. Database passwords, private IPs, generated tokens — anything OpenTofu touches gets recorded. So treat the state file as sensitive.

Third, for team use, store the state remotely. A local terraform.tfstate works fine for one developer. But real teams configure a backend, such as S3, GCS, a TACOS platform, or OpenTofu Cloud. The backend stores state centrally, with locking, so that two people cannot apply at the same time. OpenTofu version 1.7 and later also supports native state encryption.

Sitting next to your state file is the .terraform directory. This is a hidden directory that OpenTofu creates and manages for you when you run tofu init. You do not write to it by hand, and you do not commit it to Git. It holds the cached provider plugin binaries downloaded from the registry, copies of any external modules your configuration references, and a record of the currently active workspace and the last known backend configuration, so that it can migrate state if you reconfigure the backend.

There is one more file worth knowing about, and it is an important one. It is the dependency lock file, called .terraform.lock.hcl. This file sits alongside your .tf files, not inside the .terraform directory. It is automatically created or updated by tofu init, and it records the exact provider versions and cryptographic checksums that were selected for your project. You do commit this file to version control. It pins your teammates and your CI to the same provider builds, and it protects you from someone publishing a tampered provider version. Today, the lock file tracks providers only. Module versions are not yet locked.

So, a typical project on disk has your main.tf, variables.tf, and outputs.tf, possibly a terraform.tfvars file with the variable values (often gitignored if it contains secrets), the .terraform.lock.hcl file which you commit, the hidden .terraform directory which you ignore, and a local terraform.tfstate file, which you also do not commit for real projects.

Quick recap. You write configuration in .tf files. The state file remembers what OpenTofu created. The .terraform directory caches providers and modules. The lock file pins the exact provider versions.

Now to the last big piece: the workflow. Almost everything you do with OpenTofu boils down to four commands, run from your project directory.

The first command is tofu init. This initialises a working directory. It is the first thing you run in any new project. It downloads the providers declared in your required_providers block into the .terraform directory. It downloads any external modules your configuration references. It configures the backend, that is, where state lives. And it creates or updates the lock file. You re-run init whenever you add a new provider, change a backend, or upgrade dependencies.

The second command is tofu plan. This is the preview step. OpenTofu reads your configuration, reads the current state, and queries each provider to see what really exists in the world. It then computes the diff and prints what it would do. What would be created, what would be updated, and what would be destroyed. It does not change anything yet. You might see a summary line at the end, like Plan: 3 to add, 1 to change, 0 to destroy. You read that, sanity-check it, and only then apply. In team workflows, the plan is typically posted as a comment on a pull request for review.

The third command is tofu apply. This executes the change. By default, it computes a plan, prints it, and asks you to type yes before doing anything irreversible. Behind the scenes, it calls each provider's API to bring the world into line with your configuration, and it writes the resulting resource identifiers back into the state file. You can also save a plan to a file using the dash out flag, and apply that exact plan later. That is a common pattern in CI pipelines.

The fourth command is tofu destroy. This is the opposite of apply. It destroys everything currently tracked in state for the active workspace. It is very useful for tearing down temporary environments, like test infrastructure or short-lived demos, without manually deleting resources or editing your configuration. Like apply, destroy shows you a plan first and asks for confirmation.

The whole development loop is short. You edit your .tf files. You run tofu plan to see what would change. You run tofu apply to actually make the change. And later, when you no longer need the infrastructure, you run tofu destroy to remove it all.

Now let's put it together one more time, because the full mental model is small enough to fit in a single paragraph.

You write .tf files describing resources, and read-only data sources, each of which belongs to a provider plugin. You run tofu init to download those providers into the .terraform directory, and to record their versions in .terraform.lock.hcl. You run tofu plan to preview the diff between your configuration and reality, and then tofu apply to make it real. OpenTofu records what it created in terraform.tfstate, so the next run knows what to do. Reusable building blocks live in modules. Parameters live in variables. Useful return values live in outputs. And when you no longer need the infrastructure, tofu destroy tears it down.

From here, the natural next step is to install OpenTofu, write a tiny main.tf that creates a single local resource, and run the full cycle. A classic starter is the local_file resource in the hashicorp/local provider. It just writes a file to disk, and it needs no cloud account. Run tofu init, then tofu plan, then tofu apply, and finally tofu destroy. Once that works, you have everything you need to point OpenTofu at a real cloud.

Thanks for listening.
