# Core concepts of infrastructure as code

**Infrastructure as code** (IaC) is the practice of managing servers, networks, databases, and everything else in your stack the same way you manage application source code: in plain text files, kept in version control, applied by a tool. This lesson is not about any one tool. It is about the **vocabulary and mental models** that show up in every IaC tool — Terraform, OpenTofu, Pulumi, AWS CloudFormation, Ansible, Chef, Puppet, Crossplane — so the rest of the ecosystem stops feeling like a wall of jargon.

We will work through six pairs of ideas: declarative versus imperative, idempotency and convergence, state and the source of truth, drift and reconciliation, mutable versus immutable infrastructure, and the cattle-not-pets philosophy that ties it all together.

## Why "infrastructure as code" at all?

Before code, infrastructure was a human activity. An engineer would SSH into a box, run a few `apt install` commands, edit a config file, restart a service, and write a paragraph in a runbook so the next person could maybe reproduce it. The result was reasonably reliable on day one and almost impossible to reproduce on day three hundred. Servers drifted apart. A "production-like" staging environment turned out to be production-shaped at best. Knowledge lived in heads.

IaC, which emerged as a discipline around 2006 alongside the early cloud, treats that same setup work as a **machine-readable artifact**. Instead of clicking through a console or running ad-hoc commands, you write a file:

```hcl
resource "aws_instance" "web" {
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.micro"
  tags = { Name = "web-server" }
}
```

Then a tool reads that file and makes the cloud match. Three big things come along for free:

- **Reproducibility** — the same file produces the same environment, every time, anywhere.
- **Reviewability** — infrastructure changes go through pull requests, code review, and CI like any other code.
- **Auditability** — `git log` is now an audit log of every change to your fleet.

Everything else in this lesson is the conceptual machinery that makes those three benefits actually hold up under pressure.

## Declarative vs imperative

There are two fundamentally different ways to tell a computer how to set up infrastructure.

**Imperative** is the procedural style: a list of steps, in order. *Create the server, then attach the disk, then open the port, then install nginx, then start it.* It reads like a recipe. Shell scripts are imperative. Old-school configuration playbooks are largely imperative. The system does exactly what you say, in the order you say it.

**Declarative** is the destination style: a description of the desired *end state*, with no commitment to a particular path. *I want a server of this size, with this disk attached, with this port open, running this version of nginx.* The tool figures out the steps to get there from wherever it currently is. Most modern IaC tools — Terraform, OpenTofu, CloudFormation, Pulumi's higher-level resources, Kubernetes manifests — are declarative.

The two styles look superficially similar but behave very differently on the second run.

```bash
# imperative — runs the commands every time
apt install nginx
systemctl start nginx
```

```yaml
# declarative — describes the goal
package: { name: nginx, state: present }
service: { name: nginx, state: started }
```

Run the imperative script twice and it either does redundant work or, worse, errors out because the second `install` does something unexpected. Run the declarative spec twice and the tool notices nginx is already installed and running, and does nothing. **Declarative configurations are safe to re-run.** That property is the foundation everything else in this lesson is built on.

The trade-off is expressiveness. Imperative gives you total control over ordering and side effects, which is sometimes what you need (think: bespoke migration scripts). Declarative gives up some of that control to gain repeatability and safety. The 2010s industry trend was a steady move from imperative to declarative; today the line is blurrier — tools like Pulumi let you write declarative resource definitions in a general-purpose programming language, getting both the loops and conditionals of imperative code and the desired-state semantics of declarative.

## Idempotency and convergence

Two related words that get used almost interchangeably but mean slightly different things.

**Idempotency** is a property of a single operation: applying it once and applying it many times produce the same result. Setting a light switch to "on" is idempotent — flipping it on when it is already on changes nothing. Toggling it is not. In IaC, an idempotent `apply` is one you can re-run safely; it only does work when something is actually out of place.

**Convergence** is a property of a *system over time*: it keeps moving the world closer to the desired state, run after run, until reality matches the configuration. Puppet, for example, is famous for its convergence model — its agent wakes up every thirty minutes, compares the live system to the catalog, and corrects whatever has drifted. Convergence is what gives you a self-healing system: even if a human SSHs in and edits a file, the next run nudges it back.

A helpful one-liner: **idempotency means "running it twice is safe"; convergence means "running it repeatedly fixes things."** Most well-behaved IaC tools are both — Ansible, Chef, Puppet, Terraform — but the emphasis differs. Ansible runs on demand and is strongly idempotent. Puppet runs continuously and is strongly convergent. Terraform is idempotent on apply and converges only when you re-run it (no agent).

## State and the source of truth

Here is the question that separates a script from a real IaC tool: *how does the tool know which thing in the cloud corresponds to which line in your config?*

You wrote `resource "aws_instance" "web"`. The tool created an EC2 instance. AWS assigned it an ID like `i-0a1b2c3d4e5f6g7h8`. The next time you run `apply`, the tool has to map your friendly name `web` back to that specific instance, so it knows whether to create a new one, update the existing one, or do nothing.

The answer is **state**. Most declarative IaC tools maintain a state file — often JSON — that records the real-world identity, attributes, and dependencies of every resource the tool has created. Terraform and OpenTofu call this `terraform.tfstate`. Pulumi has a state backend. CloudFormation tracks state inside AWS itself, as the stack. Kubernetes stores it in `etcd`. Different format, same idea.

State has three properties worth internalising early:

1. **It is the tool's view of reality.** When you ask for a plan, the tool diffs your config against state — not against the live cloud directly. (It usually *refreshes* state from the cloud first, but the diff itself is config-vs-state.)
2. **It is sensitive.** State files routinely contain database passwords, private IPs, generated tokens, and other secrets that live in the resources you manage. Treat them like credentials.
3. **For teams, it has to live somewhere shared.** A local state file is fine for one person, but two engineers with separate copies will trample each other's changes. Real teams use a **remote backend** — an S3 bucket, a Postgres database, a hosted platform — that supports **state locking** so concurrent applies are impossible.

Closely related is the question of the **source of truth**: when the world disagrees with the code, who wins? The IaC discipline insists the answer is *the code*. The Git repository is the source of truth. The state file is the tool's *bookkeeping* about what it did to make reality match the code, not an independent authority. If your state ever drifts from your code, you reconcile by changing one or the other and re-applying — never by editing the state by hand on the side. This GitOps-style principle is what lets `git log` function as an honest audit log.

## Drift detection and reconciliation

**Drift** is what happens when reality stops matching your code. Someone opens the AWS console at 3am during an outage and bumps a security group rule to unblock traffic. A cloud provider auto-rotates a certificate. A teammate runs a one-off `kubectl edit` to debug. None of those changes are in Git. The next time you run a plan, your tool either silently undoes the fix, or shows a confusing diff for a resource nobody intentionally changed.

**Drift detection** is the practice of regularly comparing real infrastructure to the code (and to state) so drift surfaces *as a finding* rather than as a 2am surprise. Most managed IaC platforms — Terraform Cloud, Spacelift, env0, Harness, OpenTofu Cloud — run drift checks on a schedule and post an alert when something has changed outside the pipeline. You can also do it by hand: `tofu plan` with no changes will tell you whether anything has drifted since last apply.

**Reconciliation** is the act of resolving drift. You have three legitimate options:

1. **Pull reality back to code** — re-run apply and let the tool revert the manual change. The right answer when the drift was unauthorised.
2. **Push code up to reality** — codify the manual change in Git, then apply. The right answer when the drift was a legitimate emergency fix worth keeping.
3. **Adopt** — if the drifted resource shouldn't exist in code at all, either remove it from the cloud or import it into state so the tool can manage it going forward.

Some systems take reconciliation further into a *continuous* loop. Kubernetes is the canonical example: its controllers wake up constantly, observe live state, compare to the spec, and act to close the gap. Crossplane and other Kubernetes-native infrastructure tools extend that pattern to cloud resources. The mental model is identical to Puppet's convergence loop, just with a different runtime — **observe, diff, act, repeat**.

## Mutable vs immutable infrastructure

The previous concepts are about how you describe and track infrastructure. This one is about **how you change it once it exists**.

**Mutable infrastructure** is the traditional model: a server is provisioned once and then evolves in place. You SSH in (or run a configuration management agent) and apply patches, upgrade packages, edit config files, restart services. The server has a long life and a long history of in-place modifications. Most pre-cloud datacentres ran this way, and many legacy systems still do.

**Immutable infrastructure** flips the model: once a server is deployed, you never modify it. If you need a change — even a single-line config tweak — you build a new machine image with the change baked in, deploy fresh instances from that image, and tear down the old ones. The unit of update is the whole machine, not the file on the machine. Containers and golden AMIs (Amazon Machine Images) are the canonical building blocks.

The mutable approach is fast for small changes — pushing a config update with Ansible takes seconds. But it is also the breeding ground for **configuration drift** and the dreaded **snowflake server**: a long-lived, hand-tuned instance whose exact configuration is no longer documented anywhere, terrifying to reboot and impossible to scale because nobody knows the combination of settings keeping it alive.

The immutable approach trades that fragility for two big wins:

- **Predictability.** The image you deploy is the same image you tested. There is no "config drift" because there is no config to drift.
- **Easy rollback.** Reverting a bad deploy is just deploying the previous image. No hot-fix scripts, no comparing yesterday's state to today's.

The cost is a longer change cycle (you have to bake an image before you can deploy), more compute churn (every change replaces VMs), and a hard problem around state: anything that holds data — a database, an attached disk, persistent caches — cannot itself be immutable. Most real systems end up *hybrid*: immutable for stateless application tiers, mutable (and carefully managed) for the stateful underlay.

A useful related phrase is **"burn and rebuild"** versus **"in-place update"**. Burn-and-rebuild — destroy the broken thing, create a fresh one from the spec — is the immutable mindset applied to a single resource. It is often safer than trying to patch a partial failure back into a known-good state.

## Cattle, not pets

The cultural phrase that wraps up everything above is **"cattle, not pets."**

The analogy traces back to a 2011-era talk on scaling SQL Server by Microsoft's Bill Baker, and was reframed for cloud computing by Randy Bias around the same time. Bias' elevator pitch: *"In the old way, we treat servers like pets. Each one has a name. If Bob goes down, it is all hands on deck. In the new way, servers are numbered, like cattle. When one goes down, it is taken out back, shot, and replaced."*

The point is not that cruelty to servers is funny. It is that **how you treat a server changes what you can build with it.**

- **Pets** are unique, named, hand-cared-for individuals. You back them up, you nurse them through outages, you remember their quirks. The cost of losing one is high, so every action around them is careful and manual.
- **Cattle** are interchangeable, numbered, disposable. You don't notice an individual cow's identity; you notice the size of the herd. If one dies, the autoscaler spins up a replacement and nobody loses sleep.

This is fundamentally a property of *your team's habits*, not of the hardware. Two teams running identical EC2 instances can be in completely different worlds: one is hand-patching a small zoo of pets, the other is letting an autoscaler cycle anonymous cattle every hour. The IaC concepts above — declarative configuration, state, immutable images, drift detection — are what let you actually live in the cattle world. Without them, you end up treating cloud VMs like pets and wondering why the cloud is more expensive than the datacentre was.

The arc of modern infrastructure is the steady push down the cattle path: ephemeral containers, autoscaling groups, blue-green and canary deployments, GitOps, serverless. Each one is another move away from "this particular machine matters" toward "the herd matters."

## Putting it together

The whole mental model fits in a paragraph. You write **declarative** configurations that describe the desired state of your infrastructure. You apply them with a tool that is **idempotent** (safe to re-run) and that **converges** the world toward your description. The tool tracks what it did in **state**, which is its private map between your code and reality. Reality sometimes diverges from code — that's **drift** — and you detect it and **reconcile**, by either reverting reality or codifying the change. To minimise drift in the first place, you favour **immutable** components that are burned and rebuilt rather than patched in place. And underneath all of it is a cultural shift: you stop treating individual machines as **pets** with names and personalities, and start treating them as anonymous, replaceable **cattle**. The tools enforce the discipline; the discipline is what makes infrastructure scale.

From here, the natural next step is to pick one tool — Terraform or OpenTofu for cloud provisioning, Ansible or Puppet for configuration management, Kubernetes for orchestration — and watch how each of these abstract ideas shows up as a concrete file, command, or controller. The vocabulary travels.
