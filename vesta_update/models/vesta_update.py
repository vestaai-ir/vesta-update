# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Versions and updates of the Vesta modules installed in this database.

Each Vesta module names its GitHub repository in its manifest (``website``). A check reads
the module's version on the release branch and the latest GitHub release that ships
``<module>.zip`` with its ``<module>.zip.sha256`` and ``<module>.zip.sig``. Private
repositories (the Enterprise modules) are read with the server's read-only token
(``vesta_update_github_token``).

Applying an update replaces the module's folder on the server, so it is guarded:

- the server owner must allow it in the Odoo configuration (``vesta_update_apply = True``);
- the repository must belong to an allowed GitHub owner (``vesta_update_owners``,
  ``vestaai-ir`` by default);
- the archive is downloaded from GitHub only, checked against its sha256 and its Ed25519
  signature (keys in ``keys/``, or ``vesta_update_signing_keys``; ``vesta_update_allow_unsigned``
  turns the signature off for forks), must contain only the module's folder (no absolute
  path, ``..`` or link) and the announced version;
- the module folder must be writable and not part of a git checkout (developers update
  with git, not here).

The previous folder is moved to a backup in Odoo's data directory; any error puts it back.
Python code is loaded when Odoo starts, so the new version is used after a restart; the
database is then upgraded with *Upgrade*, like any module whose code is newer than the
database.
"""

import ast
import base64
import hashlib
import io
import json
import logging
import os
import re
import shutil
import stat
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_manifest, get_module_path

_logger = logging.getLogger(__name__)

PARAM_BRANCH = "vesta_update.branch"
PARAM_STATUS = "vesta_update.status"
DEFAULT_BRANCH = "20.0"
DEFAULT_OWNERS = ("vestaai-ir",)
TIMEOUT = 8
DOWNLOAD_TIMEOUT = 60
MAX_ARCHIVE_SIZE = 50 * 1024 * 1024
DOWNLOAD_HOSTS = {
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
KEYS_DIR = Path(__file__).resolve().parent.parent / "keys"
REPO_RE = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?(?:$|/)")
HISTORY_TITLE_RE = re.compile(r"^##\s+(\S+)\s*$", re.MULTILINE)


def parse_version(version):
    """``"20.0.1.2.3"`` -> ``(20, 0, 1, 2, 3)``; non numeric parts count as 0."""
    return tuple(int(part) if part.isdigit() else 0 for part in (version or "").lstrip("v").split("."))


def repo_of(manifest):
    """``owner/name`` of the GitHub repository named in the manifest ``website``, or None."""
    match = REPO_RE.match(manifest.get("website") or "")
    return f"{match[1]}/{match[2]}" if match else None


def changelog_between(history, installed, latest):
    """Sections of ``readme/HISTORY.md`` newer than ``installed`` and up to ``latest``."""
    sections = []
    titles = list(HISTORY_TITLE_RE.finditer(history or ""))
    for index, title in enumerate(titles):
        version = parse_version(title[1])
        if parse_version(installed) < version <= parse_version(latest):
            end = titles[index + 1].start() if index + 1 < len(titles) else len(history)
            sections.append({"version": title[1], "notes": history[title.end() : end].strip()})
    return sections


def in_git_checkout(path):
    """Whether ``path`` is inside a git repository or worktree (``.git`` folder or file)."""
    for folder in [Path(path).resolve(), *Path(path).resolve().parents]:
        if (folder / ".git").exists():
            return True
    return False


def safe_members(archive, module):
    """Members of the release archive, checked: one ``<module>/`` folder, regular files only."""
    members = archive.infolist()
    if not members:
        raise UserError(_("The archive is empty."))
    for member in members:
        name = member.filename
        if name.startswith(("/", "\\")) or ".." in Path(name).parts or ":" in name:
            raise UserError(_("Unsafe path in the archive: %s", name))
        if not (name == f"{module}/" or name.startswith(f"{module}/")):
            raise UserError(
                _("The archive must only contain the folder %(module)s/ (found %(name)s).", module=module, name=name)
            )
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise UserError(_("Links are not allowed in the archive: %s", name))
    return members


class VestaUpdate(models.AbstractModel):
    _name = "vesta.update"
    _description = "Vesta module updates"

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _check_admin(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can do this."))

    def _branch(self):
        return self.env["ir.config_parameter"].sudo().get_str(PARAM_BRANCH) or DEFAULT_BRANCH

    def _allowed_owners(self):
        configured = tools.config.get("vesta_update_owners")
        return tuple(owner.strip() for owner in configured.split(",")) if configured else DEFAULT_OWNERS

    def _apply_enabled(self):
        return str(tools.config.get("vesta_update_apply") or "").lower() in ("1", "true", "yes")

    def _vesta_modules(self):
        """Installed modules that name a GitHub repository of an allowed owner."""
        modules = self.env["ir.module.module"].sudo().search([("state", "=", "installed")], order="name")
        result = []
        for module in modules:
            manifest = get_manifest(module.name)
            repo = repo_of(manifest) if manifest else None
            if repo and repo.split("/")[0] in self._allowed_owners():
                result.append((module, manifest, repo))
        return result

    def _load_status(self):
        raw = self.env["ir.config_parameter"].sudo().get_str(PARAM_STATUS)
        try:
            return json.loads(raw) if raw else {}
        except ValueError:
            return {}

    def _save_status(self, status):
        self.env["ir.config_parameter"].sudo().set_str(PARAM_STATUS, json.dumps(status))

    def _apply_blocker(self, module_name):
        """Why the files of this module cannot be replaced from here, or None."""
        if not self._apply_enabled():
            return _("Applying updates is not enabled on this server (vesta_update_apply = True in odoo.conf).")
        path = get_module_path(module_name)
        if not path:
            return _("The module folder was not found.")
        if in_git_checkout(path):
            return _("The module is in a git checkout: update it with git.")
        if not os.access(path, os.W_OK) or not os.access(os.path.dirname(path), os.W_OK):
            return _("The module folder is not writable by the Odoo server.")
        return None

    @api.model
    def get_update_data(self):
        is_admin = self.env.user.has_group("base.group_system")
        status = self._load_status()
        modules = []
        for module, manifest, repo in self._vesta_modules():
            code = manifest.get("version", "")
            installed = module.latest_version or ""
            modules.append(
                {
                    "name": module.name,
                    "title": module.shortdesc,
                    "repo": repo,
                    "code": code,
                    "installed": installed,
                    "upgrade_pending": parse_version(code) > parse_version(installed),
                    "check": status.get(module.name, {}),
                    "blocker": self._apply_blocker(module.name) if is_admin else None,
                }
            )
        return {
            "is_admin": is_admin,
            "branch": self._branch(),
            "apply_enabled": self._apply_enabled(),
            "checked_at": status.get("_checked_at"),
            "modules": modules,
        }

    # ------------------------------------------------------------------
    # Check (GitHub)
    # ------------------------------------------------------------------

    def _github_token(self):
        """Read-only GitHub token of the server (``vesta_update_github_token``), for private repositories."""
        return tools.config.get("vesta_update_github_token") or None

    def _headers(self, accept="application/vnd.github+json"):
        headers = {"Accept": accept}
        if token := self._github_token():
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _get(self, url, **kwargs):
        kwargs.setdefault("headers", self._headers())
        response = requests.get(url, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response

    def _fetch_releases(self, repo):
        response = self._get(f"https://api.github.com/repos/{repo}/releases?per_page=30")
        return response.json() if response is not None else []

    def _find_release(self, releases, module):
        """Latest release shipping ``<module>.zip`` and its sha256 (and signature, ``.sig``).

        Each file has its public URL and its API URL; the API one works for private repositories.
        """
        files = {"zip": f"{module}.zip", "sha256": f"{module}.zip.sha256", "sig": f"{module}.zip.sig"}
        for release in releases:
            if release.get("draft") or release.get("prerelease"):
                continue
            assets = {asset.get("name"): asset for asset in release.get("assets", [])}
            if files["zip"] in assets and files["sha256"] in assets:
                result = {
                    "tag": release.get("tag_name"),
                    "url": release.get("html_url"),
                    "published_at": release.get("published_at"),
                }
                for key, name in files.items():
                    if asset := assets.get(name):
                        result[f"{key}_url"] = asset.get("browser_download_url")
                        result[f"{key}_api_url"] = asset.get("url")
                return result
        return None

    def _raw(self, repo, branch, path):
        response = self._get(f"https://raw.githubusercontent.com/{repo}/{branch}/{path}")
        return response.text if response is not None else None

    def _check_module(self, module, repo, branch, releases):
        installed = module.latest_version or ""
        result = {"checked_at": fields.Datetime.to_string(fields.Datetime.now()), "installed": installed}
        manifest_text = self._raw(repo, branch, f"{module.name}/__manifest__.py")
        if not manifest_text:
            return {**result, "state": "not_published"}
        latest = ast.literal_eval(manifest_text).get("version", "")
        release = self._find_release(releases, module.name)
        if parse_version(latest) <= parse_version(installed):
            return {**result, "state": "up_to_date", "latest": latest, "release": release}
        history = self._raw(repo, branch, f"{module.name}/readme/HISTORY.md") or ""
        return {
            **result,
            "state": "update_available",
            "latest": latest,
            "release": release,
            "changelog": changelog_between(history, installed, latest),
        }

    @api.model
    def check_updates(self):
        """Ask GitHub for the latest version of every Vesta module and keep the answer."""
        self._check_admin()
        return self._check_updates()

    def _check_updates(self):
        branch = self._branch()
        status = self._load_status()
        releases_by_repo = {}
        for module, _manifest, repo in self._vesta_modules():
            try:
                if repo not in releases_by_repo:
                    releases_by_repo[repo] = self._fetch_releases(repo)
                result = self._check_module(module, repo, branch, releases_by_repo[repo])
            except (requests.RequestException, ValueError, SyntaxError) as error:
                _logger.info("Vesta update check of %s failed: %s", module.name, error)
                result = {"state": "error", "error": str(error)}
            previous = status.get(module.name, {})
            # keep what happened on this server (files replaced, backup) across checks
            for key in ("applied_version", "backup", "notified_version"):
                if key in previous:
                    result[key] = previous[key]
            status[module.name] = result
        status["_checked_at"] = fields.Datetime.to_string(fields.Datetime.now())
        self._save_status(status)
        return status

    @api.model
    def _cron_check_updates(self):
        """Daily check; administrators get one notification per new version."""
        status = self._check_updates()
        news = [
            (name, result["latest"])
            for name, result in status.items()
            if isinstance(result, dict)
            and result.get("state") == "update_available"
            and result.get("notified_version") != result.get("latest")
        ]
        if not news:
            return
        admins = self.env.ref("base.group_system").sudo().all_user_ids.filtered(lambda user: not user.share)
        lines = "".join(f"<li>{name} {version}</li>" for name, version in news)
        self.env["mail.thread"].sudo().message_notify(
            partner_ids=admins.partner_id.ids,
            subject=_("Vesta updates available"),
            body=_("New versions are published:") + f"<ul>{lines}</ul>",
        )
        for name, version in news:
            status[name]["notified_version"] = version
        self._save_status(status)

    # ------------------------------------------------------------------
    # Apply, restore, upgrade
    # ------------------------------------------------------------------

    def _download(self, url, max_size=MAX_ARCHIVE_SIZE):
        if urlparse(url).hostname not in DOWNLOAD_HOSTS or urlparse(url).scheme != "https":
            raise UserError(_("Downloads are only allowed from GitHub: %s", url))
        # requests drops the token when GitHub redirects to its file storage
        headers = self._headers("application/octet-stream")
        response = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True, headers=headers)
        response.raise_for_status()
        if urlparse(response.url).hostname not in DOWNLOAD_HOSTS:
            raise UserError(_("The download was redirected outside GitHub: %s", response.url))
        data = io.BytesIO()
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            data.write(chunk)
            if data.tell() > max_size:
                raise UserError(_("The archive is larger than %s MB.", max_size // (1024 * 1024)))
        return data.getvalue()

    def _asset_url(self, release, key):
        """API URL with a token (private repositories), public URL otherwise."""
        if self._github_token() and release.get(f"{key}_api_url"):
            return release[f"{key}_api_url"]
        return release.get(f"{key}_url")

    def _trusted_keys(self):
        """Ed25519 public keys of the Vesta releases (``keys/*.pub``) and ``vesta_update_signing_keys``."""
        paths = sorted(KEYS_DIR.glob("*.pub"))
        if extra := tools.config.get("vesta_update_signing_keys"):
            paths += [Path(path.strip()) for path in extra.split(",") if path.strip()]
        keys = []
        for path in paths:
            key = serialization.load_pem_public_key(path.read_bytes())
            if isinstance(key, Ed25519PublicKey):
                keys.append(key)
        return keys

    def _check_signature(self, content, release):
        """Refuse an archive without a valid signature of a trusted key."""
        if str(tools.config.get("vesta_update_allow_unsigned") or "").lower() in ("1", "true", "yes"):
            return
        if not self._asset_url(release, "sig"):
            raise UserError(_("The release has no signature (.sig): nothing was changed."))
        try:
            signature = base64.b64decode(self._download(self._asset_url(release, "sig"), max_size=4096).strip())
        except ValueError:
            signature = b""
        for key in self._trusted_keys():
            try:
                key.verify(signature, content)
                return
            except InvalidSignature:
                continue
        raise UserError(_("The signature of the archive is not valid: nothing was changed."))

    def _backup_root(self):
        return Path(tools.config["data_dir"]) / "vesta_update" / "backups" / self.env.cr.dbname

    def _install_archive(self, module_name, content, expected_version):
        """Replace the module folder by the archive's; returns the backup path."""
        module_path = Path(get_module_path(module_name))
        archive = zipfile.ZipFile(io.BytesIO(content))
        members = safe_members(archive, module_name)
        manifest_name = f"{module_name}/__manifest__.py"
        if manifest_name not in archive.namelist():
            raise UserError(_("The archive has no %s.", manifest_name))
        version = ast.literal_eval(archive.read(manifest_name).decode()).get("version")
        if version != expected_version:
            raise UserError(
                _("The archive contains version %(found)s, not %(expected)s.", found=version, expected=expected_version)
            )
        staging = Path(tempfile.mkdtemp(prefix=f".vesta_update_{module_name}_", dir=module_path.parent))
        backup = self._backup_root() / f"{module_name}-{get_manifest(module_name).get('version')}-{int(time.time())}"
        try:
            archive.extractall(staging, members=members)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(module_path), str(backup))
            try:
                os.replace(staging / module_name, module_path)
            except OSError:
                shutil.move(str(backup), str(module_path))  # put the previous version back
                raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return backup

    @api.model
    def apply_update(self, module_name):
        """Download the published version of ``module_name`` and replace its files."""
        self._check_admin()
        status = self._load_status()
        check = status.get(module_name) or {}
        release = check.get("release") or {}
        if check.get("state") != "update_available" or not self._asset_url(release, "zip"):
            raise UserError(_("No published update to apply: check for updates first."))
        if blocker := self._apply_blocker(module_name):
            raise UserError(blocker)
        if module_name not in {module.name for module, _manifest, _repo in self._vesta_modules()}:
            raise UserError(_("%s is not a Vesta module of an allowed repository.", module_name))
        content = self._download(self._asset_url(release, "zip"))
        expected = self._download(self._asset_url(release, "sha256"), max_size=4096).decode().split()[0].lower()
        if hashlib.sha256(content).hexdigest() != expected:
            raise UserError(_("The archive does not match its sha256: nothing was changed."))
        self._check_signature(content, release)
        backup = self._install_archive(module_name, content, check["latest"])
        _logger.info(
            "Vesta update: %s %s installed in place, previous files in %s", module_name, check["latest"], backup
        )
        check.update(state="restart_required", applied_version=check["latest"], backup=str(backup))
        status[module_name] = check
        self._save_status(status)
        return check

    @api.model
    def restore_backup(self, module_name):
        """Put back the files saved before the last update of ``module_name``."""
        self._check_admin()
        status = self._load_status()
        check = status.get(module_name) or {}
        backup = Path(check.get("backup") or "")
        if not check.get("backup") or not backup.is_dir() or self._backup_root() not in backup.parents:
            raise UserError(_("There is no backup of %s to restore.", module_name))
        if blocker := self._apply_blocker(module_name):
            raise UserError(blocker)
        module_path = Path(get_module_path(module_name))
        replaced = backup.with_name(f"{module_name}-replaced-{int(time.time())}")
        shutil.move(str(module_path), str(replaced))
        try:
            shutil.move(str(backup), str(module_path))
        except OSError:
            shutil.move(str(replaced), str(module_path))
            raise
        check.update(state="restart_required", applied_version=None, backup=None, restored=True)
        status[module_name] = check
        self._save_status(status)
        return check

    @api.model
    def upgrade_module(self, module_name):
        """Upgrade the database to the code on the server (after a restart)."""
        self._check_admin()
        module = self.env["ir.module.module"].sudo().search([("name", "=", module_name), ("state", "=", "installed")])
        if not module:
            raise UserError(_("%s is not installed.", module_name))
        if parse_version(get_manifest(module_name).get("version")) <= parse_version(module.latest_version):
            raise UserError(_("The database is already up to date with the code on the server."))
        return module.button_immediate_upgrade()
