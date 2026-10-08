# Releasing Mint Meter

The project uses the MIT license. Public maintainer metadata uses `saeedt20`
and GitHub's noreply email. The upstream repository is
https://github.com/saeedt20/mint-meter.

## Validate a release

Update `src/mint_meter/__init__.py` and the Debian changelog together; the
builder checks their versions match. Update `CHANGELOG.md` and review the
physical-session checklist in `TESTING.md`.

```sh
./scripts/build-deb.sh
./scripts/gui-check.sh
./scripts/gui-check.sh --composited
./scripts/gui-check.sh --hidpi
dpkg-deb --info dist/mint-meter_0.2.0-1_all.deb
dpkg-deb --contents dist/mint-meter_0.2.0-1_all.deb
lintian dist/mint-meter_0.2.0-1_all.deb
(cd dist && sha256sum -c SHA256SUMS)
```

Verify installation, upgrade, launch outside the checkout, and removal on a
disposable target machine. Test real desktop integration, suspend/resume,
display changes, and login startup separately from virtual-display checks.

Rootless builds use stable source timestamps (`SOURCE_DATE_EPOCH` can override
the default), sorted staging, and root ownership. Conventional builds use
`dpkg-buildpackage -us -uc -b` and write to the checkout's parent directory.

## Privacy review before publication

Review `git diff --cached` and `git ls-files` before each push. Exclude local
configuration, usage history, credentials, private environment reports, live
screenshots, build caches, and generated packages. GUI artifacts stay under
ignored `dist/`; package staging copies only the public Markdown docs.
Review package contents as well as source: packages include maintainer metadata
and documentation. Use the public noreply identity for commit authorship.

## Publish a release

First ensure main-branch CI passed. An explicitly pushed `v*` tag triggers
`.github/workflows/release.yml`:

```sh
git tag -a v0.2.0 -m "Mint Meter 0.2.0"
git push origin v0.2.0
```

The workflow checks the license, public maintainer metadata, and matching
version; runs tests and isolated GUI checks; builds and validates the package;
then creates a release with the `.deb` and `SHA256SUMS`. Only that job receives
contents-write permission. A normal main-branch push does not create a release.
Keep built packages out of Git and attach them as release assets instead.
