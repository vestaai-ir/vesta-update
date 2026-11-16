<p align="center">
  <a href="https://github.com/vestaai-ir/vesta-update/releases/latest"><img src="https://img.shields.io/github/v/release/vestaai-ir/vesta-update?label=download&style=for-the-badge&color=e8392e" alt="Download"></a>
  <img src="https://img.shields.io/badge/Odoo-20.0-714B67?style=for-the-badge" alt="Odoo 20.0">
  <img src="https://img.shields.io/badge/license-LGPL--3-5b3cc4?style=for-the-badge" alt="LGPL-3">
</p>

<p align="center"><a href="#fa">فارسی</a> · <a href="#en">English</a></p>

---

<div dir="rtl" id="fa">

## به‌روزرسانی‌های وستا

یک صفحه برای نسخه، تغییرات و به‌روزرسانی همه‌ی ماژول‌های وستا: بررسی روزانه‌ی release گیت‌هاب، نمایش «تازه‌ها» و نصب امن نسخه‌ی جدید از داخل اودو (فقط اگر صاحب سرور اجازه بدهد). هر فایل باید امضای Ed25519 معتبر و sha256 درست داشته باشد، قبل از نصب پشتیبان گرفته می‌شود و هر خطا نسخه‌ی قبلی را برمی‌گرداند. ماژول‌های مخزن خصوصی با توکن گیت‌هاب بررسی می‌شوند.

تنظیمات: [`vesta_update/readme/CONFIGURE.md`](vesta_update/readme/CONFIGURE.md). ساخت release امضاشده: `python3 tools/vesta_release.py <module> --sign-key key.pem`.

### نصب

فایل [`vesta_update.zip`](https://github.com/vestaai-ir/vesta-update/releases/latest/download/vesta_update.zip) را از [آخرین نسخه](https://github.com/vestaai-ir/vesta-update/releases/latest) در پوشه‌ی addons باز کنید، یا:

```bash
cd /opt/odoo/custom-addons
git clone -b 20.0 https://github.com/vestaai-ir/vesta-update.git
odoo -c /etc/odoo/odoo.conf -d YOUR_DB -i vesta_update --stop-after-init
```

[وستا](https://vestaai.ir) · [info@vestaai.ir](mailto:info@vestaai.ir)

</div>

---

<div id="en">

## Vesta Updates

One page for the versions, changelogs and updates of all Vesta modules: a daily check of the GitHub releases, the changes between versions, and a safe install of a new version from Odoo (only when the server owner allows it). Every archive needs a valid Ed25519 signature and sha256; the previous folder is backed up and restored on any error. Modules of private repositories are checked with a GitHub token.

Configuration: [`vesta_update/readme/CONFIGURE.md`](vesta_update/readme/CONFIGURE.md). Signed releases: `python3 tools/vesta_release.py <module> --sign-key key.pem`.

### Install

Unzip [`vesta_update.zip`](https://github.com/vestaai-ir/vesta-update/releases/latest/download/vesta_update.zip) from the [latest release](https://github.com/vestaai-ir/vesta-update/releases/latest) into your addons folder, or:

```bash
cd /opt/odoo/custom-addons
git clone -b 20.0 https://github.com/vestaai-ir/vesta-update.git
odoo -c /etc/odoo/odoo.conf -d YOUR_DB -i vesta_update --stop-after-init
```

[Vesta AI](https://vestaai.ir) · [info@vestaai.ir](mailto:info@vestaai.ir)

</div>
