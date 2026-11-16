#!/usr/bin/env python3
# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Build the release assets that Vesta Updates installs: ``<module>.zip`` and its sha256.

Usage::

    python3 tools/vesta_release.py vesta_update --out dist

Attach the files of ``dist/`` to a GitHub release of this repository. Each archive holds
the module folder only (no ``__pycache__``, ``*.pyc`` or links), as checked by the updater.

With ``--sign-key key.pem`` (an Ed25519 private key, kept out of the repository) each
archive also gets ``<module>.zip.sig``, the base64 signature that Vesta Updates checks
against the public keys of ``vesta_update/keys``.
"""

import argparse
import ast
import base64
import hashlib
import zipfile
from pathlib import Path

SKIPPED = {"__pycache__", ".DS_Store"}


def load_key(path):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key  # noqa: PLC0415

    return load_pem_private_key(Path(path).read_bytes(), password=None)


def build(module_dir, out_dir, key=None):
    module = module_dir.name
    version = ast.literal_eval((module_dir / "__manifest__.py").read_text()).get("version")
    archive_path = out_dir / f"{module}.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(module_dir.rglob("*")):
            relative = path.relative_to(module_dir.parent)
            if path.is_symlink() or SKIPPED & set(relative.parts) or path.suffix == ".pyc":
                continue
            if path.is_file():
                archive.write(path, relative.as_posix())
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    (out_dir / f"{module}.zip.sha256").write_text(f"{digest}  {module}.zip\n")
    if key:
        signature = base64.b64encode(key.sign(archive_path.read_bytes())).decode()
        (out_dir / f"{module}.zip.sig").write_text(signature + "\n")
    return module, version, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("modules", nargs="+", help="module folders to package")
    parser.add_argument("--out", default="dist", help="output folder (default: dist)")
    parser.add_argument("--sign-key", help="Ed25519 private key (PEM) to sign the archives with")
    args = parser.parse_args()
    key = load_key(args.sign_key) if args.sign_key else None
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in args.modules:
        module, version, digest = build(Path(name).resolve(), out_dir, key)
        print(f"{module} {version}  sha256 {digest}")


if __name__ == "__main__":
    main()
