# Encrypted storage

**English** | [中文](persistence.zh.md)

By default the live system writes to a temporary layer, so everything is gone after a reboot. If you want to keep things, create an encrypted container file on a USB drive or disk. It holds two things only: the CLIs' logins and settings, and `/workspace`. System updates, desktop settings and caches are not saved.

## Creating and unlocking

First mount the drive you want to store the file on, in Dolphin.

On a Ventoy drive (1.1.18 or newer) the data partition shows up as `/dev/mapper/VentoyPart`, and the welcome window's **挂载 Ventoy 数据分区** (Mount Ventoy data partition) button mounts it for you. If that mapping doesn't exist, Lynux won't guess a disk from its label, and it never formats anything.

When Lynux boots from Ventoy through the UKI, it finds the partition holding the ISO and mounts it read-only. If it's already mounted that way, the same button switches it to read-write so you can create the container. It doesn't mount the device a second time.

```bash
sudo mkdir -p /run/media/live/Ventoy/Lynux
sudo lynux-state create /run/media/live/Ventoy/Lynux/state.luks --size-gib 8
sudo lynux-state status
sudo lynux-state lock
sudo lynux-state unlock /run/media/live/Ventoy/Lynux/state.luks
```

These paths are just examples. Use wherever your desktop actually mounted the drive. You type the password at a prompt. It's never passed as an argument or environment variable.

Run these from a normal Konsole with sudo, or use the buttons in the welcome window. Close all AI CLIs and the root admin terminal first. If any are open, the switch is refused, so a running session can't end up with its workspace hidden under a new mount.

## Details

- The container is LUKS2 with Argon2id (256 MiB memory, tuned to about 2 seconds) and ext4 inside.
- Space is allocated up front, and creation leaves at least 512 MiB free on the drive.
- FAT32 can't hold files of 4 GiB or more. The welcome window defaults to 8 GiB, so on FAT32 create a smaller one from the command line.
- On first creation you can import the current CLI state and workspace, as long as no CLI is running.
- When unlocking, if the folders it would mount over already have files in them, it refuses rather than hide them. Move those files somewhere else, empty the folders, then unlock again.
- On a normal shutdown it stops the CLI sessions, syncs, unmounts and closes the container.

## What's inside

- `format.json`: the format version. Unknown versions are refused, not migrated.
- `cli/x86_64/` and `cli/aarch64/`: CLI config, logins and sessions, kept separate per architecture.
- `workspace/`: your files, shared between both architectures.

Claude gets its own HOME at `/root/.lynux/claude`. It replaces `.claude.json` atomically, so that file can't be bind-mounted on its own. State paths for the other tools are listed in `config/harnesses.json`. Temporary caches go to `/run/lynux/cache`.

## Things to know

- A newer CLI may change its own data format, and an older CLI may not read it back. Lynux doesn't downgrade your data. Before switching to a new weekly ISO, you can back up the whole container file while it's locked.
- If the container is damaged, read-only, full, the password is wrong or the layout is unknown, nothing gets formatted or overwritten. A file left over from an interrupted create stays put too, so you can check it and decide what to do.
- Encryption isn't a backup. Your workspace is only readable while the container is unlocked.
