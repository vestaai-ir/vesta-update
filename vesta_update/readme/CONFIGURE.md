Checking for updates needs nothing. Installing them from the page changes code on the
server, so the server owner enables it in the Odoo configuration file:

```ini
[options]
vesta_update_apply = True
; optional, GitHub owners whose repositories may be installed (default: vestaai-ir)
vesta_update_owners = vestaai-ir
```

Every archive must carry a valid signature (`<module>.zip.sig`, built with
`tools/vesta_release.py --sign-key`). The public keys of Vesta AI are in
`vesta_update/keys`; a fork adds its own keys:

```ini
; optional, more trusted public keys (PEM files, comma separated)
vesta_update_signing_keys = /etc/odoo/my-release.pub
; not recommended: install archives without a signature
vesta_update_allow_unsigned = False
```

Modules of a private repository (such as the Enterprise modules of Vesta) need a GitHub
token that can read it:

```ini
vesta_update_github_token = github_pat_...
```

The module folders must be writable by the Odoo process and must not be in a git
checkout (a server deployed with git is updated with git). Backups go to
`<data_dir>/vesta_update/backups/<database>/`. The release branch is the system parameter
`vesta_update.branch` (default `20.0`).
