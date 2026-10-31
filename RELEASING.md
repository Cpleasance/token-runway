# Releasing Token Runway

Releases are cut by pushing a `v*` tag. `.github/workflows/release.yml` then builds the sdist +
wheel, creates a GitHub Release with checksums, and publishes directly to PyPI.

## One-time PyPI Setup (before the first release)

Publishing to PyPI uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) — no API tokens need to be generated or stored.

1. Go to <https://pypi.org/manage/account/publishing/>
2. Under **"Add a pending publisher"**, enter:
   - **PyPI Project Name**: `token-runway`
   - **Owner**: `Cpleasance`
   - **Repository Name**: `token-runway`
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi`
3. In GitHub repo Settings (<https://github.com/Cpleasance/token-runway/settings/environments>):
   - Click **New environment**
   - Name it `pypi`

## Cutting a Release

Once the pending publisher is added on PyPI:

1. Create and push the `v0.1.0` tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
2. Watch the **Release** workflow on GitHub Actions.
3. Upon completion, `token-runway 0.1.0` is published to PyPI and available via `uvx token-runway` or `pip install token-runway`.

## Alternative: Direct CLI Upload (Twine)

If you prefer uploading directly from your terminal using a PyPI API token:

```bash
pip install twine
twine upload dist/*
# Username: __token__
# Password: <your-pypi-api-token>
```
