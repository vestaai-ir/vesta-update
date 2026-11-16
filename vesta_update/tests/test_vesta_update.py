# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
import hashlib
import io
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import config

from ..models import vesta_update
from ..models.vesta_update import changelog_between, parse_version, repo_of

HISTORY = """## 20.0.1.2.0

- Second change.

## 20.0.1.1.0

- First change.

## 20.0.1.0.0

- First version.
"""

RELEASES = [
    {
        "tag_name": "v20.0.1.2.0",
        "html_url": "https://github.com/vestaai-ir/vesta-l10n-iran/releases/tag/v20.0.1.2.0",
        "assets": [
            {"name": "vesta_fake.zip", "browser_download_url": "https://github.com/x/vesta_fake.zip"},
            {"name": "vesta_fake.zip.sha256", "browser_download_url": "https://github.com/x/vesta_fake.zip.sha256"},
        ],
    }
]


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@tagged("post_install", "-at_install")
class TestVestaUpdate(TransactionCase):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.addons = self.tmp / "addons"
        self.module_path = self.addons / "vesta_fake"
        self.module_path.mkdir(parents=True)
        (self.module_path / "__manifest__.py").write_text('{"version": "20.0.1.0.0"}')
        # error messages are checked in English
        self.Update = self.env["vesta.update"].with_context(lang="en_US")
        # a plain stub: new() records are emptied when a test expects an error
        self.fake = SimpleNamespace(name="vesta_fake", latest_version="20.0.1.0.0")
        manifest = {"version": "20.0.1.0.0", "website": "https://github.com/vestaai-ir/vesta-l10n-iran"}
        for target, value in (("_vesta_modules", lambda _self: [(self.fake, manifest, "vestaai-ir/vesta-l10n-iran")]),):
            patcher = patch.object(type(self.Update), target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, value in (
            ("get_module_path", lambda module: str(self.module_path)),
            ("get_manifest", lambda module: manifest),
        ):
            patcher = patch.object(vesta_update, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.dict(config.options, {"vesta_update_apply": "True", "data_dir": str(self.tmp / "data")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _check(self):
        files = {
            "vesta_fake/__manifest__.py": '{"version": "20.0.1.2.0"}',
            "vesta_fake/readme/HISTORY.md": HISTORY,
        }
        with (
            patch.object(type(self.Update), "_fetch_releases", lambda _self, repo: RELEASES),
            patch.object(type(self.Update), "_raw", lambda _self, repo, branch, path: files.get(path)),
        ):
            return self.Update.check_updates()["vesta_fake"]

    def _apply(self, archive, sha256=None):
        downloads = {
            "https://github.com/x/vesta_fake.zip": archive,
            "https://github.com/x/vesta_fake.zip.sha256": (sha256 or hashlib.sha256(archive).hexdigest()).encode()
            + b"  vesta_fake.zip\n",
        }
        with patch.object(type(self.Update), "_download", lambda _self, url, max_size=0: downloads[url]):
            return self.Update.apply_update("vesta_fake")

    def test_helpers(self):
        self.assertEqual(
            repo_of({"website": "https://github.com/vestaai-ir/vesta-l10n-iran"}), "vestaai-ir/vesta-l10n-iran"
        )
        self.assertIsNone(repo_of({"website": "https://vestaai.ir"}))
        self.assertGreater(parse_version("20.0.1.10.0"), parse_version("20.0.1.9.0"))
        notes = changelog_between(HISTORY, "20.0.1.0.0", "20.0.1.2.0")
        self.assertEqual([entry["version"] for entry in notes], ["20.0.1.2.0", "20.0.1.1.0"])

    def test_check(self):
        check = self._check()
        self.assertEqual(check["state"], "update_available")
        self.assertEqual(check["latest"], "20.0.1.2.0")
        self.assertEqual(check["release"]["tag"], "v20.0.1.2.0")
        self.assertEqual(len(check["changelog"]), 2)

    def test_apply_and_restore(self):
        self._check()
        archive = make_zip({"vesta_fake/__manifest__.py": '{"version": "20.0.1.2.0"}', "vesta_fake/new.py": "x = 1"})
        result = self._apply(archive)
        self.assertEqual(result["state"], "restart_required")
        self.assertIn("20.0.1.2.0", (self.module_path / "__manifest__.py").read_text())
        self.assertTrue((self.module_path / "new.py").exists())
        backup = Path(result["backup"])
        self.assertIn("20.0.1.0.0", (backup / "__manifest__.py").read_text())
        # nothing left behind in the addons folder
        self.assertEqual([path.name for path in self.addons.iterdir()], ["vesta_fake"])

        self.Update.restore_backup("vesta_fake")
        self.assertIn("20.0.1.0.0", (self.module_path / "__manifest__.py").read_text())
        self.assertFalse((self.module_path / "new.py").exists())

    def test_refusals(self):
        self._check()
        good = make_zip({"vesta_fake/__manifest__.py": '{"version": "20.0.1.2.0"}'})
        with self.assertRaisesRegex(UserError, "sha256"):
            self._apply(good, sha256="0" * 64)
        with self.assertRaisesRegex(UserError, "Unsafe path"):
            self._apply(make_zip({"vesta_fake/__manifest__.py": '{"version": "20.0.1.2.0"}', "../evil.py": ""}))
        with self.assertRaisesRegex(UserError, "only contain"):
            self._apply(make_zip({"vesta_fake/__manifest__.py": '{"version": "20.0.1.2.0"}', "other/x.py": ""}))
        with self.assertRaisesRegex(UserError, "not 20.0.1.2.0"):
            self._apply(make_zip({"vesta_fake/__manifest__.py": '{"version": "20.0.1.1.0"}'}))
        # the module folder was never touched
        self.assertIn("20.0.1.0.0", (self.module_path / "__manifest__.py").read_text())

    def test_blockers(self):
        self._check()
        (self.tmp / ".git").mkdir()
        with self.assertRaisesRegex(UserError, "git checkout"):
            self._apply(make_zip({"vesta_fake/__manifest__.py": '{"version": "20.0.1.2.0"}'}))
        with patch.dict(config.options, {"vesta_update_apply": False}):
            self.assertIn("not enabled", self.Update._apply_blocker("vesta_fake"))

    def test_download_only_from_github(self):
        with self.assertRaisesRegex(UserError, "only allowed from GitHub"):
            vesta_update.VestaUpdate._download(self.Update, "https://example.com/vesta_fake.zip")

    def test_cron_notifies_once(self):
        def notifications():
            return self.env["mail.message"].search_count([("subject", "=", "Vesta updates available")])

        before = notifications()
        files = {"vesta_fake/__manifest__.py": '{"version": "20.0.1.2.0"}', "vesta_fake/readme/HISTORY.md": HISTORY}
        with (
            patch.object(type(self.Update), "_fetch_releases", lambda _self, repo: RELEASES),
            patch.object(type(self.Update), "_raw", lambda _self, repo, branch, path: files.get(path)),
        ):
            self.Update.with_context(lang="en_US")._cron_check_updates()
            self.assertEqual(notifications(), before + 1)
            self.Update.with_context(lang="en_US")._cron_check_updates()
            self.assertEqual(notifications(), before + 1, "the same version is announced once")
