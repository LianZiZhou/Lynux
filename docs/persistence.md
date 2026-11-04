# Encrypted storage

**English** | [中文](persistence.zh.md)

By default the live system writes to a temporary layer, so everything is gone after a reboot. If you want to keep things, create an encrypted container file on a USB drive or disk. It holds two things only: the CLIs' logins and settings, and `/workspace`. System updates, desktop settings and caches are not saved.

## In the welcome window

Open **Encrypted storage** in the Lynux Welcome window.

- **Create encrypted storage…** asks for a drive, a file name (one folder level is created for you), a size and a password typed twice. It shows how much fits on the drive, warns about FAT32's 4 GiB limit, and shows progress while it reserves space and encrypts.
- **Unlock…** lists containers it found on mounted drives (in `Lynux/` or the drive's top folder), or lets you browse for one. A wrong password shows an error right there and you can try again.
- **Lock** saves everything and closes the storage. If programs are still using it, Lynux lists them: AI tool sessions as one entry each, other programs by name, PID and user. Pick which to end. Lynux asks them to quit first. Any that don't close within 5 seconds are listed again with the option to force them.

The password goes to the system helper over a pipe. It never appears in a command line, the environment or a log.

### Ventoy drives

On a Ventoy drive (1.1.18 or newer) the data partition shows up as `/dev/mapper/VentoyPart`, and the page has a button to mount it. If that mapping doesn't exist, Lynux won't guess a disk from its label, and it never formats anything.

When Lynux boots from Ventoy through the UKI, it finds the partition holding the ISO and mounts it read-only. The page then offers **Make writable**, which remounts that same mount read-write so you can create the container. It doesn't mount the device a second time.

## From a terminal

```bash
sudo mkdir -p /run/media/live/Ventoy/Lynux
sudo lynux-state create /run/media/live/Ventoy/Lynux/state.luks --size-gib 8
sudo lynux-state status
sudo lynux-state lock
sudo lynux-state unlock /run/media/live/Ventoy/Lynux/state.luks
```

These paths are just examples. Use wherever your desktop actually mounted the drive. You type the password at a prompt. It's never passed as an argument or environment variable. Add `--make-parent` to `create` to make the container's folder too.

Run these from a normal Konsole with sudo. Close all AI CLIs and the root admin terminal before creating, unlocking or locking. If any are open, the command is refused, so a running session can't end up with its workspace hidden under a new mount.

`sudo lynux-state holders` lists what keeps the storage busy, with an id per entry. `sudo lynux-state lock --end ID…` ends those first (add `--force` to kill instead of asking them to quit). Before signalling, it checks each id is still a holder and that the PID still belongs to the same process.

## Details

- The container is LUKS2 with Argon2id (256 MiB memory, tuned to about 2 seconds) and ext4 inside.
- Space is allocated up front, and creation leaves at least 512 MiB free on the drive.
- FAT32 can't hold files of 4 GiB or more. On a FAT32 drive the welcome window caps the size at 3 GiB.
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
