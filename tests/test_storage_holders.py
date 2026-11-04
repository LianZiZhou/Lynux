"""Encrypted storage: what keeps it busy, ending only those programs, and the desktop app's JSON."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from lynux import common, state  # noqa: E402

GIB = 1024 ** 3


def fake_proc(folder, processes):
    """Write /proc-like entries. `processes` maps pid -> (comm, cmdline, cgroup leaf, start, uid)."""
    for pid, (comm, cmdline, leaf, start, uid) in processes.items():
        entry = folder / str(pid)
        entry.mkdir()
        (entry / "comm").write_text(comm + "\n")
        (entry / "cmdline").write_bytes("\0".join(cmdline).encode() + b"\0")
        (entry / "cgroup").write_text(f"0::/system.slice/{leaf}\n")
        fields = ["S"] + ["0"] * 18 + [start] + ["0"] * 5
        (entry / "stat").write_text(f"{pid} ({comm}) " + " ".join(fields) + "\n")
        (entry / "status").write_text(f"Name:\t{comm}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n")
    (folder / "self").mkdir()


class HolderTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        fake_proc(self.folder, {
            100: ("python", ["/usr/bin/python", "/usr/local/bin/lynux-harness", "run", "claude"],
                  "lynux-harness-abc.scope", "500", 0),
            101: ("claude", ["/opt/lynux/harnesses/claude/bin/claude"], "lynux-harness-abc.scope", "501", 0),
            200: ("dolphin", ["dolphin", "/workspace"], "app-dolphin.scope", "900", 1000),
            300: ("plasmashell", ["plasmashell"], "plasma-plasmashell.service", "50", 1000),
        })
        paths = {"200": ["/workspace/notes", "socket:[42]"], "300": ["/home/live/.config", "/"]}
        self.patches = [
            patch.object(state, "PROC", self.folder),
            patch.object(state, "registry", return_value={"claude": {"name": "Claude Code"}}),
            patch.object(state, "_process_paths", lambda folder: paths.get(folder.name, [])),
            patch("pwd.getpwuid", create=True,
                  side_effect=lambda uid: type("U", (), {"pw_name": {0: "root", 1000: "live"}[uid]})),
        ]
        if sys.platform == "win32":
            sys.modules.setdefault("pwd", type(sys)("pwd"))
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_sessions_are_grouped_and_only_storage_users_are_listed(self):
        groups = state.holders([Path("/run/lynux/state"), Path("/workspace")])
        self.assertEqual([group["id"] for group in groups], ["unit:lynux-harness-abc.scope", "pid:200:900"])
        session, other = groups
        self.assertEqual((session["kind"], session["tool"], session["title"]), ("session", "claude", "Claude Code"))
        self.assertEqual([info["pid"] for info in session["processes"]], [100, 101])
        self.assertEqual((other["title"], other["processes"][0]["user"]), ("dolphin", "live"))

    def test_locked_storage_only_reports_sessions(self):
        self.assertEqual([group["kind"] for group in state.holders([])], ["session"])

    def test_ending_skips_a_reused_pid_and_stops_sessions_through_systemd(self):
        with patch.object(state, "storage_roots", return_value=[Path("/workspace")]), \
             patch.object(state.os, "kill") as kill, patch.object(state, "run") as execute:
            remaining = state.end_holders(["pid:200:111", "unit:lynux-harness-abc.scope"], wait=0)
        kill.assert_not_called()  # pid 200 now has a different start time: another process
        execute.assert_called_once_with("systemctl", "kill", "--signal", "TERM", "lynux-harness-abc.scope",
                                        check=False)
        self.assertEqual(remaining, ["unit:lynux-harness-abc.scope"])

    def test_force_kills_a_matching_process(self):
        signals = SimpleNamespace(SIGTERM=15, SIGKILL=9)  # Windows has no SIGKILL
        with patch.object(state, "storage_roots", return_value=[Path("/workspace")]), \
             patch.object(state, "signal", signals), patch.object(state.os, "kill") as kill, \
             patch.object(state, "run"):
            state.end_holders(["pid:200:900"], force=True, wait=0)
        kill.assert_called_once_with(200, 9)


class JsonTests(unittest.TestCase):
    def run_state(self, argv, stdin=""):
        out = io.StringIO()
        with patch.object(sys, "argv", ["lynux-state", *argv]), patch.object(sys, "stdin", io.StringIO(stdin)), \
             patch.object(state, "root_required"), patch.object(state, "session_lock", contextlib.nullcontext), \
             patch.object(state, "holders", return_value=[]), patch.object(state, "active_scopes", return_value=""), \
             contextlib.redirect_stdout(out):
            try:
                state.main()
                code = 0
            except SystemExit as exc:
                code = exc.code
        return code, [json.loads(line) for line in out.getvalue().splitlines()]

    def test_wrong_password_is_a_coded_json_error(self):
        with patch.object(state, "validate_container"), patch.object(state, "ensure_inactive"), \
             patch.object(state, "run", return_value=type("R", (), {"returncode": 2})()):
            code, lines = self.run_state(["unlock", "/media/state.luks", "--password-stdin", "--json"], "secret\n")
        self.assertEqual(code, 1)
        self.assertEqual((lines[-1]["ok"], lines[-1]["code"]), (False, "wrong_password"))

    def test_password_comes_from_stdin_without_its_newline(self):
        with patch.object(state, "validate_container"), patch.object(state, "ensure_inactive"), \
             patch.object(state, "activate") as activate:
            code, lines = self.run_state(["unlock", "/media/state.luks", "--password-stdin", "--json"],
                                         "pass word\n")
        self.assertEqual((code, lines[-1]), (0, {"ok": True}))
        self.assertEqual(activate.call_args.args[1], "pass word")

    def test_lock_reports_busy_programs_instead_of_failing_to_unmount(self):
        busy = [{"id": "pid:7:1", "kind": "process", "processes": []}]
        with patch.object(state, "close") as close:
            out = io.StringIO()
            with patch.object(sys, "argv", ["lynux-state", "lock", "--json"]), \
                 patch.object(state, "root_required"), patch.object(state, "holders", return_value=busy), \
                 contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
                state.main()
        close.assert_not_called()
        result = json.loads(out.getvalue().splitlines()[-1])
        self.assertEqual((result["code"], result["holders"]), ("busy", busy))

    def test_empty_password_is_refused(self):
        with patch.object(state, "validate_container"), patch.object(state, "ensure_inactive"):
            code, lines = self.run_state(["unlock", "/media/state.luks", "--password-stdin", "--json"], "\n")
        self.assertEqual((code, lines[-1]["code"]), (1, "empty_password"))


class LocationTests(unittest.TestCase):
    def test_only_real_drives_are_offered(self):
        table = [
            {"source": "/dev/sdb1", "target": "/run/media/live/USB", "fstype": "vfat", "options": "rw,relatime",
             "label": "USB"},
            {"source": "/dev/loop0", "target": "/run/archiso/airootfs", "fstype": "squashfs", "options": "ro"},
            {"source": "overlay", "target": "/", "fstype": "overlay", "options": "rw"},
            {"source": "/dev/sda2", "target": "/home", "fstype": "ext4", "options": "rw"},
            {"source": "/dev/sdc1", "target": "/run/media/live/DVD", "fstype": "iso9660", "options": "ro"},
            {"source": "/dev/mapper/VentoyPart", "target": "/run/initramfs/ventoy", "fstype": "exfat",
             "options": "ro"},
        ]
        usage = type("Usage", (), {"free": 10 * GIB, "total": 32 * GIB})()
        with patch.object(state.shutil, "disk_usage", return_value=usage), \
             patch.object(state, "find_containers", return_value=[]):
            found = state.locations(table, ventoy=[{"mount": "/run/initramfs/ventoy"}])
        self.assertEqual([item["mount"] for item in found], ["/run/initramfs/ventoy", "/run/media/live/USB"])
        self.assertEqual((found[0]["ventoy"], found[0]["writable"]), (True, False))
        self.assertTrue(found[1]["fat"])

    def test_containers_are_found_without_following_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            drive = Path(folder)
            (drive / "Lynux").mkdir()
            (drive / "Lynux" / "state.luks").write_bytes(b"x" * 10)
            (drive / "old.luks").write_bytes(b"x")
            (drive / "notes.txt").write_text("not a container")
            found = state.find_containers(drive)
        self.assertEqual([Path(item["path"]).name for item in found], ["state.luks", "old.luks"])
        self.assertEqual(found[0]["size"], 10)

    def test_make_parent_checks_space_before_creating_the_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "Lynux" / "state.luks"
            with patch.object(state, "ensure_inactive"), \
                 patch.object(state, "check_capacity", side_effect=common.LynuxError("full", "no_space")):
                with self.assertRaises(common.LynuxError):
                    state.create(target, GIB, "password", make_parent=True)
            self.assertFalse(target.parent.exists())


if __name__ == "__main__":
    unittest.main()
