=============
Vesta Updates
=============

|badge1| |badge2|

.. |badge1| image:: https://img.shields.io/badge/Odoo-20.0-714B67
.. |badge2| image:: https://img.shields.io/badge/license-LGPL--3-blue.svg
    :target: https://www.gnu.org/licenses/lgpl-3.0-standalone.html

One page (*Settings > Vesta Updates*) for the versions and updates of every installed
Vesta module whose manifest names a public GitHub repository of Vesta AI:

- **Versions**: installed in the database, present on the server, published on GitHub.
- **Check for updates**: reads the version on the release branch and the latest release
  that ships ``<module>.zip`` with ``<module>.zip.sha256``; shows what's new between the
  installed and the published version (``readme/HISTORY.md``). A daily check notifies the
  administrators once per new version.
- **Install files** (optional, see Configuration): downloads the archive from GitHub,
  checks its sha256 and content, keeps a backup of the current folder and replaces it.
  After a restart of Odoo, **Upgrade** applies the new version to the database.
  **Restore previous version** puts the backup back.

Configuration
=============

Checking for updates needs nothing. Installing them from the page changes code on the
server, so the server owner enables it in the Odoo configuration file:

::

    [options]
    vesta_update_apply = True
    ; optional, GitHub owners whose repositories may be installed (default: vestaai-ir)
    vesta_update_owners = vestaai-ir

Every archive must carry a valid signature (``<module>.zip.sig``, built with
``tools/vesta_release.py --sign-key``). The public keys of Vesta AI are in
``vesta_update/keys``; a fork adds its own keys:

::

    ; optional, more trusted public keys (PEM files, comma separated)
    vesta_update_signing_keys = /etc/odoo/my-release.pub
    ; not recommended: install archives without a signature
    vesta_update_allow_unsigned = False

Modules of a private repository (such as the Enterprise modules of Vesta) need a GitHub
token that can read it:

::

    vesta_update_github_token = github_pat_...

The module folders must be writable by the Odoo process and must not be in a git
checkout (a server deployed with git is updated with git). Backups go to
``<data_dir>/vesta_update/backups/<database>/``. The release branch is the system parameter
``vesta_update.branch`` (default ``20.0``).

Usage
=====

1. *Settings > Vesta Updates > Check for updates*.
2. Read *What's new*, then **Install files** (or download the archive from the release
   and replace the module folder by hand).
3. Restart Odoo, open the page again and press **Upgrade** (or start Odoo once with
   ``-u <module>``).
4. If something goes wrong: **Restore previous version**, then restart Odoo.

To publish a release: ``python3 tools/vesta_release.py <module> ... --out dist``, then
attach the files of ``dist/`` to a GitHub release of the repository.

Changelog
=========

20.0.1.1.0
----------

- Releases are signed: an archive is installed only with a valid Ed25519 signature
  (``<module>.zip.sig``) of a key in ``vesta_update/keys`` or ``vesta_update_signing_keys``.
- Private repositories: with ``vesta_update_github_token``, the check and the download use
  the GitHub API.

20.0.1.0.0
----------

- First version.

Bug Tracker
===========

Report bugs on `GitHub Issues <https://github.com/vestaai-ir/vesta-l10n-iran/issues>`_.

Credits
=======

Authors
-------

- Vesta AI

Contributors
------------

- `Vesta AI <https://vestaai.ir>`_

Maintainers
-----------

This module is part of the `vestaai-ir/vesta-l10n-iran <https://github.com/vestaai-ir/vesta-l10n-iran/tree/20.0/vesta_update>`_ project on GitHub.
