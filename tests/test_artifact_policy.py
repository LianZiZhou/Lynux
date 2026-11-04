import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("release_inputs", ROOT / "scripts/download-release-inputs.py")
release_inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_inputs)


class ArtifactPolicyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to execute the actual cleanup workflow script")
    def test_cleanup_snapshots_all_pages_and_preserves_active_runs(self):
        source = (ROOT / ".github/workflows/cleanup-artifacts.yml").read_text()
        script = textwrap.dedent(source.split("          script: |\n", 1)[1])
        harness = r'''
        const fs = require('fs');
        const assert = require('assert/strict');
        const script = JSON.parse(fs.readFileSync(0, 'utf8'));
        const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
        const execute = new AsyncFunction('github', 'context', 'core', script);
        async function test(fail) {
          let listed = false;
          const deleted = [];
          const actions = {
            listArtifactsForRepo: () => {},
            getWorkflowRun: async ({run_id}) => ({data:{status:run_id === 20 ? 'in_progress' : 'completed'}}),
            deleteArtifact: async ({artifact_id}) => {
              assert(listed);
              if (fail) throw Object.assign(new Error('denied'), {status:403});
              deleted.push(artifact_id);
              if (artifact_id === 3) throw Object.assign(new Error('gone'), {status:404});
            },
          };
          const github = {rest:{actions}, paginate:async () => {
            listed = true;
            return [
              {id:1,size_in_bytes:10,workflow_run:{id:10}},
              {id:2,size_in_bytes:20,workflow_run:{id:20}},
              {id:3,size_in_bytes:30,workflow_run:{id:30}},
              {id:4,size_in_bytes:40,workflow_run:{id:10}},
            ];
          }};
          const summary = {addHeading(){return this},addRaw(){return this},async write(){}};
          const run = execute(github, {repo:{owner:'test',repo:'repo'}}, {summary});
          if (fail) await assert.rejects(run, /denied/);
          else {
            await run;
            assert.deepEqual(deleted, [1,4,3]);
            assert(!deleted.includes(2));
          }
        }
        (async () => {await test(false); await test(true)})().catch(error => {console.error(error);process.exit(1)});
        '''
        subprocess.run(["node", "-e", harness], input=json.dumps(script), text=True, check=True, timeout=20)

    def test_release_iso_link_must_match_architecture_and_filename(self):
        meta = {"arch": "aarch64", "iso": "lynux-test-aarch64-signed.iso"}
        url = "https://download.example/lynux-test-aarch64-signed.iso"
        self.assertEqual(release_inputs.iso_url({"body": f"[aarch64 ISO]({url})"}, meta, "aarch64"), url)
        with self.assertRaises(ValueError):
            release_inputs.iso_url({"body": "[aarch64 ISO](https://download.example/other.iso)"}, meta, "aarch64")
        tidy = {"arch": "aarch64", "iso": "lynux-test-aarch64.iso"}
        url = "https://download.example/lynux-test-aarch64.iso"
        body = (f"| aarch64 | [lynux-test-aarch64.iso]({url}) |\n"
                "| x86_64 | [lynux-test-x86_64.iso](https://download.example/lynux-test-x86_64.iso) |")
        self.assertEqual(release_inputs.iso_url({"body": body}, tidy, "aarch64"), url)
        with self.assertRaises(ValueError):
            release_inputs.iso_url({"body": body}, {"arch": "aarch64", "iso": "lynux-test-aarch64.img"}, "aarch64")

    def test_dependency_archive_rejects_traversal_and_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, name in enumerate(("dependency-lock/../../escape", "dependency-lock/link")):
                archive = root / f"bad-{index}.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    member = tarfile.TarInfo(name)
                    if index:
                        member.type = tarfile.SYMTYPE
                        member.linkname = "/etc/passwd"
                    else:
                        member.size = 1
                    bundle.addfile(member, io.BytesIO(b"x") if not index else None)
                with self.assertRaises(ValueError):
                    release_inputs.extract_lock(archive, root / "lock")
            self.assertFalse((root / "escape").exists())
