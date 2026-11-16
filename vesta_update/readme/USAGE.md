1. *Settings > Vesta Updates > Check for updates*.
2. Read *What's new*, then **Install files** (or download the archive from the release
   and replace the module folder by hand).
3. Restart Odoo, open the page again and press **Upgrade** (or start Odoo once with
   `-u <module>`).
4. If something goes wrong: **Restore previous version**, then restart Odoo.

To publish a release: `python3 tools/vesta_release.py <module> ... --out dist`, then
attach the files of `dist/` to a GitHub release of the repository.
