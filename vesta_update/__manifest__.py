# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Vesta Updates",
    "summary": "Versions, changelogs and updates of the Vesta modules",
    "version": "20.0.1.1.0",
    "category": "Hidden/Tools",
    "website": "https://github.com/vestaai-ir/vesta-l10n-iran",
    "author": "Vesta AI",
    "license": "LGPL-3",
    "installable": True,
    "depends": ["web", "mail"],
    "data": [
        "data/ir_cron_data.xml",
        "views/vesta_update_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "vesta_update/static/src/**/*",
        ],
    },
}
