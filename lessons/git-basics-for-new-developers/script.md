Almost every working developer touches Git every day. It is the tool you use to save your work, share it with teammates, branch off to try ideas, and reconcile changes when more than one person edits the same code. The commands look intimidating at first, but the underlying model is small and consistent. Once you have it, the day-to-day cycle becomes muscle memory.

In this lesson we will walk through that model and the commands that go with it. We will cover creating and cloning repositories, staging and committing, working on feature branches, syncing with remotes, and resolving merge conflicts. And we will finish with a simple workflow you can use on real projects from day one.

Let's start with what Git actually is, in one paragraph. Git is a distributed version control system. Version control means it records snapshots of your files over time, so you can review, compare, and roll back changes. Distributed means every clone of the repository is a full copy. There is no special central server built into the protocol itself. There is only a server that teams agree to treat as the source of truth, typically hosted on GitHub, GitLab, Bitbucket, or a self-hosted instance. Every command you run operates on your local copy first. Sharing is an extra step.

A Git repository keeps your project's history in a hidden directory called dot git, sitting at the root of the project. That directory holds the snapshots, named pointers like branches and tags, and the configuration. Everything else in the project folder is your working tree, which is just the actual files you edit.

Now let's look at how you start a repository. There are two ways. You can start a new repository from an existing folder using git init, or you can copy an existing remote repository using git clone.

For a brand new project, you make a folder, change into it, and run git init with the dash b flag set to main. That dash b flag sets the initial branch name. Older Git defaulted to a branch called master, but modern projects almost always use main, and Git 3.0 will make main the default. You can set this globally once and forget about it, by running git config dash dash global init.defaultBranch main.

Cloning a remote project is more common in practice. You run git clone followed by the URL of the repository. The clone command does several things at once. It downloads the full history. It creates a working tree on disk. It sets up a remote called origin, pointing back at the URL you cloned from. And it checks out the repository's default branch, usually main. From that point on, the local clone is a full, independent copy of the project's history.

Next, let's talk about the piece of Git that confuses newcomers the most, which is the staging area. The staging area is also called the index. Git has three places a change can live. The first is the working tree, which is the files on disk that you edit. The second is the index, or staging area, which is a holding pen for changes you have marked for the next commit. The third is the repository itself, which is the committed history inside the dot git directory.

The flow is always the same. You edit a file. You stage the changes you want to record. Then you commit them. The staging area lets you decide exactly what goes into each commit, so a single editing session can become several focused commits instead of one big blob.

The commands you use are git status, which tells you what is modified, staged, or untracked. Git diff, which shows unstaged changes. Git diff dash dash staged, which shows what is about to be committed. Git add, followed by a file path, which stages a specific file. Git add dot, which stages everything in the current directory. And git commit dash m, followed by a message in quotes, which records the staged changes.

Git status is the command you will run more than any other. It tells you, in plain English, which files are modified, which are staged, which are untracked, and which branch you are on. When you are unsure what state your repo is in, run it.

A small shortcut. Git commit dash a m with a message stages all already-tracked files and commits in one step. It does not pick up new files. For those, you still need git add.

Let's talk about ignoring files. You rarely want to commit build artifacts, log files, editor settings, or secrets. You create a dot gitignore file at the root of the repo, listing patterns that Git should pretend do not exist. A typical gitignore might list node_modules for dependencies, dist and build for output, star dot log for log files, dot env for environment files, dot vscode for editor settings, and dot DS_Store for macOS junk.

The gitignore file itself is committed. It is part of the project. One important detail. If a file is already tracked, adding it to gitignore does not untrack it. You need git rm dash dash cached, followed by the file name, to stop tracking it while keeping the file on disk.

Now, about writing good commits. A commit is a labeled snapshot of the repository. Two habits will make your history dramatically more useful.

The first habit is to make commits small and focused. Each commit should do one logical thing. Fix one bug, add one feature, rename one symbol. If you find yourself writing the word and in the message, it is probably two commits.

The second habit is to write a clear message. The first line is a short summary, ideally under fifty characters, written in the imperative. So you would write Add password reset endpoint, not Added or Adds. If more context is needed, leave a blank line and add a longer body explaining why the change was made. You will read these messages weeks or months later, often while debugging an incident, and future-you will appreciate the effort.

Let's move on to branches, which are the heart of how teams use Git. A branch in Git is just a movable pointer to a commit. Creating one is cheap. There is no copying of files, no separate folder, no server round-trip. That is why branches are the unit of work in almost every Git workflow.

The typical pattern is, branch off main, do your work on the branch, then merge it back into main when it is ready. The branch keeps your in-progress code isolated, so main stays in a known-good state.

The commands you use are git switch dash c, followed by a branch name, to create a branch and switch to it in one step. Git switch, followed by a branch name, to move between existing branches. Git switch dash, with just a dash, jumps back to the previous branch, which is handy. Git branch on its own lists your local branches, with a star next to the current one. Git branch dash a includes remote-tracking branches in that list.

Git switch is the modern command for moving between branches, and git switch dash c creates one. Older tutorials use git checkout dash b for the same thing. Both still work, but switch is the clearer name, and it is what you should reach for in new code.

Branch names should describe the work, not the author or the date. Common conventions are feature slash, fix slash, or chore slash, followed by a short description. The only hard rule is, be descriptive. Fix slash login-redirect-loop is helpful. Tims branch number two is not.

Now let's talk about remotes, and the three commands that move commits between your clone and a shared copy. A remote is a named reference to another copy of the repository, usually a shared one on a hosting service. After git clone, you already have a remote called origin. You can list your remotes with git remote dash v, which shows their fetch and push URLs.

Three commands move commits between your clone and the remote. The first is git fetch. Fetch downloads new commits from the remote into something called remote-tracking branches. For example, the remote main branch shows up locally as origin slash main. Fetch does not touch your working tree or your local branches. Think of it as checking the mailbox.

The second is git pull. Pull is git fetch followed by an integration step. By default it merges the remote branch into your current local branch. It is the everyday give me the latest command.

The third is git push. Push sends your local commits up to the remote, so other people can see them. The first time you push a new branch, you use git push dash u, followed by origin and the branch name. The dash u flag, short for set upstream, tells Git which remote branch your local branch corresponds to. After that first push, plain git pull and git push know where to go.

There is a common gotcha here. Git pull will refuse to fast-forward if your local branch and the remote branch have diverged, which means you both made commits. At that point you have to choose how to integrate, either with a merge or with a rebase. Many teams set pull.ff to only, or pull.rebase to true, in their config to make the behavior explicit. If pull dash dash ff dash only fails, you decide consciously. Git pull dash dash rebase replays your commits on top of the remote. Git pull dash dash no dash rebase creates a merge commit.

Once your feature branch is done, you bring its commits back into main. The mechanics are, switch to main, run git pull to make sure main is up to date, and then run git merge, followed by the name of your feature branch.

Git performs one of two kinds of merge. The first is a fast-forward. If main has not moved since you branched, Git just slides the main pointer forward to the tip of your branch. There is no new commit, and the history stays perfectly linear.

The second is a three-way merge. If main has new commits too, Git compares your branch, the current main, and their common ancestor, and creates a new merge commit that ties the histories together.

After a successful merge, you can delete the feature branch. Its commits live on in main. You use git branch dash d for the local branch, and git push origin dash dash delete for the remote.

In team workflows you usually do not merge locally. Instead, you push the branch, open a pull request or merge request on the hosting service, get a review, and let the platform perform the merge. The mechanics underneath are exactly the same.

Let's talk about the part everyone dreads at first, which is resolving merge conflicts. A conflict happens when the same lines of the same file have been changed on both sides of a merge, and Git cannot pick a winner automatically. Git pauses the merge and writes both versions into the file, surrounded by conflict markers.

The markers look like this. There is a line of angle brackets pointing left, followed by the word HEAD. Below it is your version of the code. Then there is a line of equals signs. Below that is the other side's version. And then a line of angle brackets pointing right, followed by the name of the other branch. The block between the left arrows and the equals signs is your side, the branch you were on. The block between the equals signs and the right arrows is the other side.

Your job is, first, open each conflicted file. Git status lists them. Second, edit the file so it contains the version you actually want. You can keep your side, keep theirs, keep both, or write something new entirely. Third, delete the conflict markers. Fourth, stage the resolved file with git add. And fifth, run git commit to finalize the merge. Git supplies a default message.

If you panic mid-merge, you can run git merge dash dash abort, which puts everything back the way it was. Conflicts feel scary the first few times. After a couple, they become routine.

Now let's tie it all together with a simple, sane workflow. For most teams, this is enough.

Step one. Start from an up-to-date main. Switch to main, then git pull.

Step two. Create a branch for your work. Use git switch dash c, followed by a descriptive name, like fix slash login-redirect-loop.

Step three. Make small, focused commits as you go. Stage with git add. Commit with git commit dash m and a clear message.

Step four. Push your branch, and keep pushing as you commit. The first push uses dash u to set the upstream. Later pushes are just plain git push.

Step five. Open a pull request on your hosting service, with a description of what you changed and why. Address review feedback by making more commits and pushing them up.

Step six. Once the pull request is approved and the checks pass, merge it through the platform's UI. Delete the branch.

Step seven. Pull main back down locally, so your next piece of work starts from the merged result.

This pattern is sometimes called GitHub Flow, and it scales surprisingly well. Many large teams use a more elaborate variant of the same pattern. The reason it works is that main always represents shippable code, branches are short-lived, and integration happens through reviewed pull requests rather than ad-hoc local merges.

Before we close, here are the ten commands worth committing to memory at the start.

Git status, which shows what is changed, staged, and untracked. Git add, followed by a path, which stages a change for the next commit. Git commit dash m, with a message, which records staged changes as a new commit. Git switch, with a branch name, which moves to an existing branch. Git switch dash c, with a branch name, which creates a new branch and moves to it. Git pull, which fetches from the remote and integrates. Git push, which sends your commits to the remote. Git log dash dash oneline dash dash graph dash dash decorate, which is the most readable way to browse history. Git diff, which shows what is changed since the last commit. And git merge, with a branch name, which merges another branch into the current one.

Everything else, like rebases, cherry-picks, reflogs, bisect, stashes, and submodules, builds on these. Get fluent with the basics first, and the rest of Git stops looking like a foreign language and starts looking like a set of power tools you can pick up as you need them.
