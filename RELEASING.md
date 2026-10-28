# Releasing

`epub2web` publishes to PyPI with **Trusted Publishing** from GitHub Actions.
No API token or password is stored in the repository.

## One-time setup

1. Sign in to [PyPI](https://pypi.org/) and verify your email address.
2. Open **Publishing** and add a **pending publisher** with:

   | Field | Value |
   |---|---|
   | PyPI project name | `epub2web` |
   | Owner | `Gowwre` |
   | Repository | `epub2web` |
   | Workflow name | `publish.yml` |
   | Environment | `pypi` |

3. On GitHub, open **Settings → Environments** and create an environment
   named `pypi`. Add protection rules if you want a manual approval step.

The workflow in `.github/workflows/publish.yml` requests an OIDC token and
publishes the distributions; nothing else needs configuring.

## Cutting a release

1. Update `__version__` in `epub2web/__init__.py` and add an entry to
   `CHANGELOG.md`.
2. Run the full checks locally:

   ```bash
   make test
   make check-dist
   ```

3. Commit, push, and wait for CI to pass.
4. Tag the release and push the tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

   The **Release** workflow verifies that the tag matches
   `epub2web.__version__`, builds the sdist and wheel, builds the portable
   Windows/macOS/Linux GUI through the reusable **Portable GUI** workflow,
   creates the GitHub release with generated notes and all assets, and then
   triggers the **Publish** workflow for PyPI.

   Do not create the GitHub release first. If you do, the older
   release-published triggers for **Publish** and **Portable GUI** still work,
   but the automated path is the tag push.

   PyPI publishing is dispatched asynchronously. Wait for the **Publish**
   workflow run to succeed before checking the package index.

5. Verify the release:

   ```bash
   uvx epub2web --version
   pip install --upgrade epub2web
   ```

   Check that the release has the PyPI files, the portable GUI assets, and
   `SHA256SUMS.txt`.

You can also run **Actions → Publish → Run workflow** manually after bumping
the version.

## If publishing fails

- Confirm the pending publisher matches owner, repository, workflow filename,
  and environment exactly.
- Check that the GitHub environment is named `pypi`.
- Confirm the version has not already been uploaded; PyPI rejects duplicate
  filenames and versions.
