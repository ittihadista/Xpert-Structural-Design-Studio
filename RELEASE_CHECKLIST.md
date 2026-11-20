# Xpert Structural Design Studio — Release Checklist

## Pre-Release (before committing a new version)
- [ ] Update `STUDIO_VERSION` in `xpert_project_io.py`.
- [ ] Update `STUDIO_VERSION` in `xpert_studio_app.py`.
- [ ] Add a new `test_vXXXX_*` test to `test_studio_engine.py`.
- [ ] Run full test suite: `pytest test_studio_engine.py -v`.
- [ ] Confirm 0 failures, 0 errors.
- [ ] Verify 0 Arabic characters in production files (100% English).

## Commit & Tag
- [ ] Commit: `git commit -am "vX.Y.Z: <one-line summary>"`.
- [ ] Push commit: `git push origin main`.
- [ ] Tag (annotated): `git tag -a vX.Y.Z -m "Release vX.Y.Z: <summary>"`.
- [ ] Push tag: `git push origin vX.Y.Z`.

## Post-Release
- [ ] Verify tag on GitHub → Releases → Tags.
- [ ] Create GitHub Release from the tag (optional, recommended).
- [ ] Update `VERSION_HISTORY.md` with the new entry.
- [ ] Automated Tagging Helper:
      Alternatively, run the release helper script to create and push the annotated tag:
      ```powershell
      .\scripts\tag_release.ps1 -Version "X.Y.Z" -Summary "<summary>"
      ```

## Diffing for Review
- Compare any two versions:
      git diff vOLD vNEW > review_<old>_<new>.diff
- Example:
      git diff v2.4.10 v2.4.11 > review_v2410_to_v2411.diff
