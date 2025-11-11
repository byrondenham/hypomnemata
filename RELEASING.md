# Release Process

This document describes the release process for Hypomnemata maintainers.

## Overview

Releases are triggered by pushing a version tag to GitHub. The CI/CD pipeline automatically:

1. Runs tests on all platforms
2. Builds distribution artifacts (sdist, wheel, .pyz files)
3. Publishes to PyPI
4. Creates a GitHub Release with all artifacts

## Prerequisites

- Write access to the repository
- Access to PyPI project (for manual releases)
- Familiarity with Semantic Versioning

## Versioning

Hypomnemata follows [Semantic Versioning](https://semver.org/):

- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality, backward compatible
- **PATCH**: Backward compatible bug fixes

## Pre-Release Checklist

Before creating a release:

- [ ] All tests pass on main branch
- [ ] CHANGELOG.md is updated with the new version
- [ ] Version number in `src/hypomnemata/__init__.py` is updated
- [ ] Documentation is up to date
- [ ] No outstanding critical bugs

## Release Steps

### 1. Update Version and Changelog

Edit `src/hypomnemata/__init__.py`:

```python
__version__ = "0.9.1"  # Update to new version
```

Update `CHANGELOG.md`:

```markdown
## [0.9.1] - 2025-11-11

### Added
- New feature X

### Fixed
- Bug Y

### Changed
- Improved Z
```

Commit these changes:

```bash
git add src/hypomnemata/__init__.py CHANGELOG.md
git commit -m "Bump version to 0.9.1"
git push origin main
```

### 2. Create and Push Tag

Create an annotated tag:

```bash
# Format: v{MAJOR}.{MINOR}.{PATCH}
git tag -a v0.9.1 -m "Release v0.9.1"
git push origin v0.9.1
```

### 3. Monitor CI/CD

After pushing the tag:

1. Go to [GitHub Actions](https://github.com/byrondenham/hypomnemata/actions)
2. Watch the "Release" workflow
3. Verify all jobs complete successfully:
   - Build distribution
   - Publish to PyPI
   - Create GitHub Release

### 4. Verify Release

Check that the release was successful:

1. **GitHub Release:**
   - Visit https://github.com/byrondenham/hypomnemata/releases
   - Verify the new release appears with all artifacts:
     - `hypomnemata-X.Y.Z.tar.gz` (sdist)
     - `hypomnemata-X.Y.Z-py3-none-any.whl` (wheel)
     - `hypo-linux-x86_64.pyz`
     - `hypo-macos.pyz`
     - `hypo-windows.pyz`
     - `SHA256SUMS.txt`

2. **PyPI:**
   - Visit https://pypi.org/project/hypomnemata/
   - Verify the new version appears
   - Check that the package metadata is correct

3. **Installation Test:**
   ```bash
   # In a fresh environment
   pipx install hypomnemata
   hypo --version
   # Should show the new version
   ```

### 5. Announce Release

After verification:

1. Tweet/post about the release (if applicable)
2. Update documentation site (if applicable)
3. Notify users in relevant channels

## Troubleshooting

### Release Workflow Failed

If the release workflow fails:

1. **Check the logs:**
   - Go to Actions → Failed workflow
   - Check which job failed and why

2. **Common issues:**
   - **Build failed:** Fix the build issue, commit, and create a new tag (e.g., v0.9.2)
   - **PyPI publish failed:** May need to manually publish (see below)
   - **GitHub Release failed:** Can manually create release (see below)

### Manual PyPI Publish

If automated publishing fails:

```bash
# Install build tools
pip install build twine

# Build distributions
python -m build

# Upload to PyPI
twine upload dist/*
```

You'll need a PyPI API token configured in `~/.pypirc` or pass it via command line.

### Manual GitHub Release

If automated release creation fails:

1. Go to https://github.com/byrondenham/hypomnemata/releases/new
2. Select the tag (e.g., v0.9.1)
3. Set release title: "Release v0.9.1"
4. Copy release notes from CHANGELOG.md
5. Upload artifacts manually:
   - Download from CI artifacts
   - Or build locally and upload
6. Publish release

### Delete/Redo a Tag

If you need to redo a release:

```bash
# Delete local tag
git tag -d v0.9.1

# Delete remote tag
git push origin :refs/tags/v0.9.1

# Create new tag
git tag -a v0.9.1 -m "Release v0.9.1"
git push origin v0.9.1
```

**Note:** Once published to PyPI, you cannot replace a version. You'll need to create a new patch version (e.g., v0.9.2).

## Release Checklist Template

Use this checklist for each release:

```markdown
## Release vX.Y.Z Checklist

- [ ] Version updated in `src/hypomnemata/__init__.py`
- [ ] CHANGELOG.md updated with release notes
- [ ] All tests passing on main
- [ ] Documentation reviewed and updated
- [ ] Version bump committed to main
- [ ] Tag created and pushed
- [ ] CI/CD pipeline completed successfully
- [ ] PyPI package verified
- [ ] GitHub Release verified
- [ ] All artifacts present and checksums valid
- [ ] Installation tested with pipx
- [ ] Single-file executable tested
- [ ] Release announced
```

## Post-Release

After a successful release:

1. Start a new "Unreleased" section in CHANGELOG.md
2. Consider creating a blog post or announcement
3. Monitor issue tracker for any release-related issues
4. Update documentation if needed

## Hotfix Releases

For critical bugs requiring immediate release:

1. Create a hotfix branch from the release tag:
   ```bash
   git checkout -b hotfix/v0.9.2 v0.9.1
   ```

2. Apply the fix and test thoroughly

3. Update version and CHANGELOG

4. Merge to main and create tag:
   ```bash
   git checkout main
   git merge hotfix/v0.9.2
   git tag -a v0.9.2 -m "Hotfix v0.9.2"
   git push origin main v0.9.2
   ```

## Beta/RC Releases

For pre-releases (beta, release candidates):

```bash
# Update version to include suffix
__version__ = "1.0.0-beta.1"

# Create tag with suffix
git tag -a v1.0.0-beta.1 -m "Beta release v1.0.0-beta.1"
git push origin v1.0.0-beta.1
```

On GitHub Release, mark it as "pre-release".

## Security Releases

For security-related releases:

1. Follow the hotfix process
2. Do NOT disclose details until the release is available
3. Coordinate with the security team
4. Include security advisory in the release notes
5. Update SECURITY.md if needed

## Continuous Improvement

After each release, consider:

- What went well?
- What could be improved?
- Any automation to add?
- Documentation updates needed?

Update this document based on lessons learned.
