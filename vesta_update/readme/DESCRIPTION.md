One page (*Settings > Vesta Updates*) for the versions and updates of every installed
Vesta module whose manifest names a public GitHub repository of Vesta AI:

- **Versions**: installed in the database, present on the server, published on GitHub.
- **Check for updates**: reads the version on the release branch and the latest release
  that ships `<module>.zip` with `<module>.zip.sha256`; shows what's new between the
  installed and the published version (`readme/HISTORY.md`). A daily check notifies the
  administrators once per new version.
- **Install files** (optional, see Configuration): downloads the archive from GitHub,
  checks its sha256 and content, keeps a backup of the current folder and replaces it.
  After a restart of Odoo, **Upgrade** applies the new version to the database.
  **Restore previous version** puts the backup back.
