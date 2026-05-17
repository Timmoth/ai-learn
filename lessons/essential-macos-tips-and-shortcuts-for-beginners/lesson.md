# Essential macOS tips and shortcuts for beginners

A new Mac is one of those tools that feels great out of the box and quietly gets faster the more you learn about it. macOS hides a lot of its best behaviour behind keyboard shortcuts, trackpad gestures, and a handful of System Settings toggles that ship turned off. None of it is hard — it just isn't obvious. This lesson is the tour you wish someone had given you on day one.

We will cover the keyboard shortcuts that pay back the most per minute of learning, the trackpad gestures that make moving around feel effortless, how to use Spotlight as your launcher and personal calculator, how to manage windows with Mission Control and the new tiling system, the System Settings worth changing first, and a handful of Finder tricks that turn it from "the thing files live in" into a real navigation tool.

## The modifier keys, and how to read shortcuts

Before anything else, learn the symbols. Mac shortcuts are written with glyphs that the keyboard does not actually print, which catches beginners out.

- `⌘` is **Command** — the workhorse modifier, equivalent to Ctrl on Windows.
- `⌥` is **Option** (also labelled "alt" on some keyboards).
- `⌃` is **Control** — used less often than on Windows.
- `⇧` is **Shift**.
- `fn` is the **Function** key, usually bottom-left.

So `⇧⌘5` means "hold Shift and Command, then press 5". In this lesson we will write shortcuts in words (`Shift + Command + 5`) for clarity. Press and hold the modifiers first, then tap the last key.

## The shortcuts that earn their keep

These are the ones to commit to muscle memory. They work in almost every Mac app.

| Shortcut | What it does |
|---|---|
| `Command + C` / `Command + V` / `Command + X` | Copy, paste, cut |
| `Command + Z` / `Shift + Command + Z` | Undo, redo |
| `Command + S` | Save |
| `Command + A` | Select all |
| `Command + F` | Find in current document or page |
| `Command + W` | Close the current window or tab |
| `Command + Q` | Quit the current app (note: closing the last window does *not* quit the app) |
| `Command + Tab` | Switch between running apps |
| `Command + Backtick` (the key above Tab) | Cycle between windows of the *current* app |
| `Command + H` | Hide the current app |
| `Command + M` | Minimize the front window to the Dock |
| `Command + Space` | Open Spotlight |
| `Shift + Command + 5` | Screenshot and screen recording tool |
| `Option + Command + Esc` | Force-quit picker, the Mac equivalent of Task Manager |
| `Control + Command + Q` | Lock the screen instantly |

A subtle one to internalise: on a Mac, **closing the last window does not quit the app**. The menu bar at the top of the screen still shows it as running. `Command + Q` is what actually quits. This trips up almost everyone coming from Windows.

### Screenshots, properly

`Shift + Command + 5` opens a small toolbar with everything you need: full-screen capture, window capture, region capture, screen recording, and a timer. There are direct shortcuts too:

- `Shift + Command + 3` — capture the whole screen.
- `Shift + Command + 4` — drag a region. Press Space mid-drag to switch to "capture a window" mode, which gives you a clean window screenshot with a subtle drop shadow.
- Hold `Control` with any of the above to copy to clipboard instead of saving a file to the desktop.

## Trackpad gestures

The Mac trackpad is the part most worth learning gestures for — Apple has spent twenty years making it the best in the industry, and the gestures are how you unlock it. Open `System Settings → Trackpad` to see them all animated; the highlights are below.

**Two fingers:**

- Scroll by sliding two fingers up or down.
- Pinch to zoom on photos, PDFs, and web pages.
- Two-finger tap is right-click (a.k.a. "secondary click").
- Swipe left or right to go back and forward in Safari, Finder, and most native apps.
- Swipe in from the right edge to open Notification Center.

**Three fingers:**

- Tap with three fingers on a word to look it up in the dictionary.
- Enable "three-finger drag" in `System Settings → Accessibility → Pointer Control → Trackpad Options` to drag windows and select text without clicking. Once you have used it for a day, going back feels broken.

**Four fingers:**

- Swipe up to open Mission Control (an overview of every open window).
- Swipe down for App Exposé (every window of the *current* app).
- Swipe left or right between full-screen apps and desktop "Spaces".
- Pinch with thumb and three fingers to show Launchpad. Spread to show the desktop.

If a gesture isn't doing what you expect, the Trackpad settings panel shows a short video clip of every gesture next to a toggle. It is the single most useful settings page on the machine for a new user.

## Spotlight is the front door

`Command + Space` opens Spotlight. Most people learn it as "the way to launch apps without leaving the keyboard", which is true, but it does a lot more.

```
Calendar           → launches Calendar.app
cal                → also launches Calendar.app (initials match)
weather london     → embedded weather forecast
1450 * 1.2         → calculator: shows 1740 inline
50 usd in eur      → currency conversion
12 stone in kg     → unit conversion
define ephemeral   → dictionary definition
report.pdf         → opens or reveals the file
kind:pdf budget    → filter by file kind
```

A few habits make Spotlight pay off:

- **Type initials, not full names.** "ST" launches Sublime Text, "DT" launches DeepL Translate, and so on. Spotlight learns which match you actually pick and prioritises it next time.
- **Use it as a calculator** for quick arithmetic — there is no need to open the Calculator app.
- **Hold Command** when a result is highlighted to see the full path of the file underneath. Press `Command + Return` to reveal the file in Finder instead of opening it.
- **Trim the noise.** `System Settings → Spotlight` lets you turn off categories you never use (Mail messages, Siri Suggestions, Bookmarks, etc.) so search results stay sharp. The Privacy tab lets you exclude folders entirely from indexing.

If Spotlight starts feeling slow or returning nothing for a folder, force a reindex by adding the folder to the Privacy list, then removing it again.

## Mission Control, Spaces, and Stage Manager

macOS gives you three different lenses on your open windows. They sound similar but solve different problems.

**Mission Control** (`F3` on most keyboards, or four-finger swipe up) zooms out to show every window across every desktop, tiled so you can see what is open. Click a window to jump to it. Drag a window to the top of the screen to put it on a new desktop.

**Spaces** are virtual desktops. Each Space is a separate canvas, and any full-screen app gets its own Space automatically. Switch between them with `Control + Left/Right Arrow` or by swiping left or right with four fingers. A useful pattern is one Space for communication (Mail, Slack, Messages), one for the work you are focused on, and one full-screen for video calls.

**Stage Manager** is the newer option, off by default. Turn it on from Control Center (the icon in the menu bar that looks like two sliders) or in `System Settings → Desktop & Dock`. Stage Manager keeps the window you are using in the centre of the screen and parks the rest as small thumbnails on the left. Click a thumbnail to swap in that app. Drag a thumbnail into the centre to group apps together so they come back as a set. It is a great fit for people who like a focused, single-task workspace; less so if you rely on having many windows visible at once.

You do not need to use all three. Most people pick a primary mode — typically Mission Control plus Spaces — and ignore the others.

## Window tiling, the native way

macOS Sequoia (2024) finally added native window tiling, the snap-to-edge behaviour Windows has had for years.

The three ways to use it:

1. **Drag to an edge.** Drag any window to the top, left, right, or a corner. A translucent preview shows where it will snap. Release to drop it in.
2. **Hover the green button.** Park your pointer over the green traffic-light button at the top-left of any window. A menu appears with layout options: left half, right half, top/bottom halves, quarters, and the classic full screen.
3. **Keyboard shortcuts.** `Fn + Control + Left Arrow` snaps the active window to the left half. `Right Arrow`, `Up Arrow`, and `Down Arrow` do the obvious equivalents. `Fn + Control + F` fills the screen without entering full-screen mode (i.e. without giving up the menu bar).

If you prefer the old "drag does not tile" behaviour, hold `Option` while dragging to suppress the snap. The opposite — making tiling more aggressive — is also configurable in `System Settings → Desktop & Dock → Windows`.

## Finder, beyond pointing and clicking

Finder is the file browser, and like everything else on macOS it gets faster the more keyboard shortcuts you use.

| Shortcut | What it does |
|---|---|
| `Command + N` | New Finder window |
| `Command + T` | New Finder tab |
| `Shift + Command + N` | New folder |
| `Control + Command + N` | New folder *from the selection* (great for tidying downloads) |
| `Command + 1` / `2` / `3` / `4` | Icon, list, column, gallery view |
| `Command + Down Arrow` | Open the selected folder or file |
| `Command + Up Arrow` | Go to the enclosing folder |
| `Space` | Quick Look — instant preview of any selected file |
| `Command + Y` | Quick Look in a full window (toggleable) |
| `Shift + Command + .` | Show or hide hidden files |
| `Command + Delete` | Move to Trash |
| `Shift + Command + Delete` | Empty the Trash |
| `Option + Command + V` | "Move" (after a `Command + C` copy) — paste-and-delete-original |
| `Shift + Command + G` | "Go to folder" — type any path, including `~` for home |

`Shift + Command + G` is the closest thing macOS has to a command-line shortcut inside Finder. Type `~/Library` to get into your user library (which is hidden by default), or `/etc` to peek at system config files.

**Quick Look** (`Space` on any file) is one of those features that nobody mentions and everybody loves once they discover it. It previews PDFs, images, video, audio, code, and most office documents instantly without opening the parent app. Select several files and press `Space` to flip through them.

**Tabs and tags.** Finder windows can have tabs like a browser (`Command + T`). And every file can be assigned a colour-tagged label from the right-click menu, which then shows up in the Finder sidebar as a saved filter. Tags work well for cross-cutting groups — "active project", "to read", "tax documents" — that don't map cleanly to a single folder.

## Settings worth changing on day one

The macOS defaults are sensible, but a handful of toggles dramatically improve daily life. Open `System Settings` (Apple menu → System Settings) and work through these.

**Trackpad (or Mouse).** Turn on "Tap to click" so you don't have to physically depress the trackpad to click. While you are here, check the tracking speed — the default is conservative.

**Keyboard.** Set "Key repeat" to fast and "Delay until repeat" to short. The defaults make holding down arrow keys feel sluggish. Also worth enabling: full keyboard access (`Keyboard → Keyboard navigation`) so you can `Tab` through buttons in dialog boxes.

**Dock & Menu Bar.** Shrink the Dock, enable "Automatically hide and show the Dock" if you want the screen real estate, and turn off "Show recent applications in Dock" if you find that clutter unhelpful.

**Desktop & Dock → Hot Corners.** Hot Corners are an underused gem. Assign each corner of the screen to a quick action: bottom-left to Mission Control, top-right to lock screen, top-left to show the desktop. Slamming the cursor into a corner is faster than any shortcut.

**Privacy & Security → FileVault.** Turn this on. FileVault encrypts your entire disk with your login password. If the laptop is ever lost or stolen, your files stay unreadable. There is essentially no downside on modern Macs — the encryption is hardware-accelerated.

**Privacy & Security → Analytics & Improvements.** Turn off "Share Mac Analytics" and "Improve Siri & Dictation" if you would rather not send usage data to Apple. Personal preference, but worth a glance.

**General → Time Machine.** Plug in an external drive and let Time Machine back up to it. Versioned snapshots every hour, with no thought required, are a quiet superpower the first time you accidentally delete something important.

**Accessibility → Display → Reduce motion.** Optional. The big sweeping desktop-switch and Mission Control animations look slick but eat real time over the course of a day. Reducing motion makes them snap.

**Battery → Low Power Mode** (laptops only). Set it to kick in automatically on battery. Modern Macs lose almost nothing in real-world performance and gain meaningful battery life.

## A short workflow that ties it together

Once these pieces are in your hands, the loop looks like this:

1. `Command + Space`, type two or three letters, hit Return — your app is open.
2. `Fn + Control + Left Arrow` to tile it to the left half of the screen, then `Command + Tab` to bring the next app over and tile it to the right.
3. Four-finger swipe up to peek at Mission Control if you've lost a window.
4. `Space` in Finder to preview a file before bothering to open it.
5. `Shift + Command + 5` when you need to capture or record something.
6. `Control + Command + Q` to lock the screen when you walk away.

None of these is a power-user trick. They are just the standard macOS controls, used the way they were designed to be used. Spend a week deliberately reaching for them and they become reflex.

## Where to learn more

- `System Settings → Keyboard → Keyboard Shortcuts` lets you see (and rebind) every shortcut macOS knows about, including per-app menu shortcuts.
- The official Apple shortcuts reference, "Mac keyboard shortcuts" (support.apple.com), is exhaustive and kept up to date with each macOS release.
- The Help menu of any app has a search box that finds menu items by name and shows their shortcut next to them — type half a command and macOS will tell you which menu it lives in and what the keystroke is.

That last one is worth remembering on its own. Whenever you find yourself reaching for the menu, look at the shortcut next to the item you clicked. That is how the inventory of shortcuts in your head grows.
