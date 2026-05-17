# Git basics for new developers

Almost every working developer touches Git every day. It is the tool you use to save your work, share it with teammates, branch off to try ideas, and reconcile changes when more than one person edits the same code. The commands look intimidating at first, but the underlying model is small and consistent. Once you have it, the day-to-day cycle becomes muscle memory.

This lesson walks through that model and the commands that go with it: creating and cloning repositories, staging and committing, working on feature branches, syncing with remotes, and resolving merge conflicts. We finish with a simple workflow you can use on real projects from day one.

## What Git is, in one paragraph

Git is a distributed version control system. "Version control" means it records snapshots of your files over time so you can review, compare, and roll back changes. "Distributed" means every clone of the repository is a full copy — there is no special central server in the protocol itself, only a server that teams *agree* to treat as the source of truth (typically hosted on GitHub, GitLab, Bitbucket, or a self-hosted instance). Every command you run operates on your local copy first; sharing is an extra step.

A Git repository keeps your project's history in a hidden `.git` directory at the root. That directory holds objects (the snapshots), refs (named pointers like branches and tags), and configuration. Everything else in the project folder is your *working tree* — the actual files you edit.

## Starting a repository

You can start a new repository from an existing folder with `git init`, or you can copy an existing remote repository with `git clone`.

```bash
# Brand new project: turn the current folder into a Git repo
mkdir my-project
cd my-project
git init -b main
```

The `-b main` flag sets the initial branch name. Older Git defaulted to `master`; modern projects almost always use `main`, and Git 3.0 will make `main` the default. You can set this globally once and forget about it:

```bash
git config --global init.defaultBranch main
```

Cloning a remote project is more common in practice:

```bash
git clone https://github.com/owner/repo.git
cd repo
```

`git clone` does several things at once: it downloads the full history, creates a working tree on disk, sets up a remote called `origin` pointing back at the URL you cloned from, and checks out the repository's default branch (usually `main`). From that point on, the local clone is a full, independent copy of the project's history.

## The three areas: working tree, index, repository

The piece of Git that confuses newcomers most is the **staging area** (also called the **index**). Git has three places a change can live:

1. **Working tree** — the files on disk that you edit.
2. **Index / staging area** — a holding pen for changes you have marked for the *next* commit.
3. **Repository** — the committed history inside `.git`.

The flow is always the same: edit a file, *stage* the changes you want to record, then *commit* them. The staging area lets you decide exactly what goes into each commit, so a single editing session can become several focused commits instead of one big blob.

```bash
git status            # see what's modified, staged, or untracked
git diff              # show unstaged changes
git diff --staged     # show what's about to be committed
git add path/to/file  # stage a specific file
git add .             # stage everything in the current directory
git commit -m "Add login form validation"
```

`git status` is the command you will run more than any other. It tells you, in plain English, which files are modified, which are staged, which are untracked, and which branch you are on. When you are unsure what state your repo is in, run it.

A small shortcut: `git commit -am "message"` stages all *already-tracked* files and commits in one step. It does not pick up new files — for those you still need `git add`.

## Ignoring files

You rarely want to commit build artifacts, log files, editor settings, or secrets. Create a `.gitignore` file at the repo root listing patterns Git should pretend do not exist:

```
# Dependencies
node_modules/

# Build output
dist/
build/

# Logs and local env
*.log
.env
.env.local

# Editor and OS junk
.vscode/
.DS_Store
```

`.gitignore` itself is committed; it is part of the project. If a file is already tracked, adding it to `.gitignore` does *not* untrack it — you need `git rm --cached <file>` to stop tracking it while keeping the file on disk.

## Writing good commits

A commit is a labeled snapshot of the repository. Two habits will make your history dramatically more useful:

- **Make commits small and focused.** Each commit should do one logical thing — fix one bug, add one feature, rename one symbol. If you find yourself writing "and" in the message, it is probably two commits.
- **Write a clear message.** The first line is a short summary, ideally under fifty characters, written in the imperative ("Add password reset endpoint", not "Added" or "Adds"). If more context is needed, leave a blank line and add a longer body explaining *why*.

```
Add password reset endpoint

Lets users request a reset link via email when they forget
their password. Tokens expire after one hour.
```

You will read these messages in `git log` weeks or months later, often while debugging an incident. Future-you will appreciate the effort.

## Branches

A branch in Git is just a movable pointer to a commit. Creating one is cheap — there is no copying of files, no separate folder, no server round-trip. That is why branches are the unit of work in almost every Git workflow.

The typical pattern is: branch off `main`, do your work on the branch, then merge it back into `main` when it is ready. The branch keeps your in-progress code isolated, so `main` stays in a known-good state.

```bash
# Create a branch and switch to it in one step
git switch -c feature/login-form

# ... edit, add, commit, repeat ...

# Move between existing branches
git switch main
git switch feature/login-form
git switch -            # jump back to the previous branch

# See your branches
git branch              # local branches; the current one has a *
git branch -a           # include remote-tracking branches
```

`git switch` is the modern command for moving between branches; `git switch -c` creates one. Older tutorials use `git checkout -b` for the same thing — both still work, but `switch` is the clearer name and what you should reach for in new code.

Branch names should describe the work, not the author or the date. Common conventions are `feature/...`, `fix/...`, or `chore/...`, but the only hard rule is "be descriptive": `fix/login-redirect-loop` is helpful, `tims-branch-2` is not.

## Remotes: fetch, pull, push

A **remote** is a named reference to another copy of the repository — usually a shared one on a hosting service. After `git clone`, you already have a remote called `origin`.

```bash
git remote -v
# origin  https://github.com/owner/repo.git (fetch)
# origin  https://github.com/owner/repo.git (push)
```

Three commands move commits between your clone and the remote:

- **`git fetch`** downloads new commits from the remote into *remote-tracking* branches (like `origin/main`). It does not touch your working tree or your local branches. Think of it as "check the mailbox."
- **`git pull`** is `git fetch` followed by an integration step — by default it merges the remote branch into your current local branch. It is the everyday "give me the latest" command.
- **`git push`** sends your local commits up to the remote so other people can see them.

```bash
git fetch origin                  # download without changing your branch
git pull                          # fetch and integrate into the current branch
git push                          # publish current branch to its remote
git push -u origin feature/login  # first push of a new branch; sets up tracking
```

The `-u` (short for `--set-upstream`) on the first push of a new branch tells Git which remote branch your local branch corresponds to. After that, plain `git pull` and `git push` know where to go.

A common gotcha: `git pull` will refuse to fast-forward if your local branch and the remote branch have diverged (you both made commits). At that point you choose how to integrate — either with a merge or a rebase. Many teams set `pull.rebase = true` or `pull.ff = only` in their config to make the behavior explicit:

```bash
git config --global pull.ff only      # only fast-forward; fail if diverged
# or
git config --global pull.rebase true  # always rebase your local commits on top
```

If `pull --ff-only` fails, you decide consciously: `git pull --rebase` to replay your commits on top, or `git pull --no-rebase` to create a merge commit.

## Merging branches

Once your feature branch is done, you bring its commits back into `main`. The mechanics are:

```bash
git switch main
git pull              # make sure main is up to date
git merge feature/login-form
```

Git performs one of two kinds of merge:

- **Fast-forward.** If `main` has not moved since you branched, Git just slides the `main` pointer forward to the tip of your branch. No new commit, perfectly linear history.
- **Three-way merge.** If `main` has new commits too, Git compares your branch, the current `main`, and their common ancestor, and creates a new *merge commit* that ties the histories together.

After a successful merge you can delete the feature branch — its commits live on in `main`:

```bash
git branch -d feature/login-form           # local
git push origin --delete feature/login-form # remote
```

In team workflows you usually do not merge locally. Instead you push the branch, open a pull request (or merge request) on the hosting service, get a review, and let the platform perform the merge. The mechanics underneath are exactly the same.

## Resolving merge conflicts

A **conflict** happens when the same lines of the same file have been changed on both sides of a merge, and Git cannot pick a winner automatically. Git pauses the merge and writes both versions into the file with markers:

```
<<<<<<< HEAD
const TIMEOUT_MS = 5000;
=======
const TIMEOUT_MS = 10000;
>>>>>>> feature/slow-network
```

The block between `<<<<<<<` and `=======` is your side (the branch you were on). The block between `=======` and `>>>>>>>` is the other side. Your job is to:

1. Open each conflicted file (`git status` lists them).
2. Edit the file so it contains the version you actually want — keeping one side, keeping both, or writing something new entirely.
3. Delete the conflict markers.
4. Stage the resolved file with `git add`.
5. Run `git commit` to finalize the merge (Git supplies a default message).

If you panic mid-merge, `git merge --abort` puts everything back the way it was. Conflicts feel scary the first few times; after a couple they are routine.

## A simple, sane workflow

For most teams, this is enough:

1. **Start from an up-to-date main.**
   ```bash
   git switch main
   git pull
   ```
2. **Create a branch for your work.**
   ```bash
   git switch -c fix/login-redirect-loop
   ```
3. **Make small, focused commits as you go.**
   ```bash
   git add .
   git commit -m "Stop redirecting on already-authenticated session"
   ```
4. **Push your branch and keep pushing as you commit.**
   ```bash
   git push -u origin fix/login-redirect-loop
   # later commits:
   git push
   ```
5. **Open a pull request on your hosting service** with a description of what you changed and why. Address review feedback by making more commits and pushing.
6. **Merge through the platform's UI** once it is approved and the checks pass. Delete the branch.
7. **Pull `main` back down locally** so your next piece of work starts from the merged result.

This is sometimes called **GitHub Flow**, and it scales surprisingly well — many large teams use a more elaborate variant of the same pattern. The reason it works is that `main` always represents shippable code, branches are short-lived, and integration happens through reviewed pull requests rather than ad-hoc local merges.

## Commands to commit to memory

If you only learn ten commands to start, learn these:

| Command | What it does |
|---|---|
| `git status` | Show what's changed, staged, and untracked. |
| `git add <path>` | Stage a change for the next commit. |
| `git commit -m "..."` | Record staged changes as a new commit. |
| `git switch <branch>` | Move to an existing branch. |
| `git switch -c <branch>` | Create a new branch and move to it. |
| `git pull` | Fetch from the remote and integrate. |
| `git push` | Send your commits to the remote. |
| `git log --oneline --graph --decorate` | Browse history in a readable form. |
| `git diff` | See what's changed since the last commit. |
| `git merge <branch>` | Merge another branch into the current one. |

Everything else — rebases, cherry-picks, reflogs, bisect, stashes, submodules — builds on these. Get fluent with the basics first, and the rest of Git stops looking like a foreign language and starts looking like a set of power tools you can pick up as you need them.
