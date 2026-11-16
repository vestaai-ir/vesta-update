Checking for updates needs nothing. Installing them from the page changes code on the
server, so the server owner enables it in the Odoo configuration file:

```ini
[options]
vesta_update_apply = True
; optional, GitHub owners whose repositories may be installed (default: vestaai-ir)
vesta_update_owners = vestaai-ir
```

The module folders must be writable by the Odoo process and must not be in a git
checkout (a server deployed with git is updated with git). Backups go to
`<data_dir>/vesta_update/backups/<database>/`. The release branch is the system parameter
`vesta_update.branch` (default `20.0`).
