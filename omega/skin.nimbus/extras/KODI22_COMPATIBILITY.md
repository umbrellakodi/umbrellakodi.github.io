# Nimbus Kodi compatibility fixes — October 28, 2026

Applied to `D:/kodi212/portable_data/addons/skin.nimbus` and the companion
`script.nimbus.helper`, then deployed and checked on the Shield with Kodi 22 RC1.
Prepared locally as Nimbus 0.1.44 with Nimbus Helper 0.0.54. No repository packages have been published.

## Changes

- Closed the missing visibility-condition brackets in `DialogVideoInfo.xml`
  and `View_51_PosterFlow.xml`.
- Moved hidden-button focus actions out of focused item layouts and onto their
  list containers. The action conditions and existing container actions are
  retained. Wall, PosterFlow and trailer timers reset on navigation; Home/search
  trailer delay resets while user input is active.
- Added comment children to empty menu/widget includes. Kodi requires a child
  node before registering a named include, even when its body is intentionally
  empty. Updated the helper's default templates and shipped blank templates so
  recreating menus does not reintroduce the warning.
- Made helper-generated XML writes atomic and validated XML before replacement.
  Invalid XML or a failed replacement preserves the previous file. Readers see
  either the old complete file or the new complete file during skin reloads.

The relevant Kodi behavior is documented in its implementation:
[supported list-item controls](https://github.com/xbmc/xbmc/blob/master/xbmc/guilib/GUIListGroup.cpp),
[named include registration](https://github.com/xbmc/xbmc/blob/master/xbmc/guilib/GUIIncludes.cpp),
and [container focus actions](https://github.com/xbmc/xbmc/blob/master/xbmc/guilib/GUIBaseContainer.cpp).

## Verification

- All six checks in `tests/test_compat.py` pass, including real temporary-file
  publication and rollback tests. All skin XML parses, conditions balance, and
  expanded item layouts contain supported control types.
- `python scripts/check_case.py xml` passes.
- Shield configured menus/widgets were preserved. Only genuinely empty generated
  includes were patched; source placeholders were not copied over populated ones.
- Shield restarted with the patched skin/helper. Home, Add-on browser, a watched
  movie list with 20 entries, and the movie-information dialog were exercised.
  The information screen was visually inspected.
- The fresh log contained **zero** unsupported-control-type-7 warnings, invalid
  include warnings, unmatched-bracket errors, boolean-expression parsing errors,
  invalid `dialogbusy` lookups, or Python tracebacks during these checks.

Automatic trailer playback was disabled in the user's existing settings and was
not enabled for testing. Full autoplay/scroll-delay behavior and playback remain
outside this smoke test. Other add-ons' network/artwork/repository warnings are
not addressed by this skin patch. The invalid `dialogbusy` lookup was not found
in the local skin/helper sources and did not recur during the checked flows.

To repeat the checks from the skin folder:

```powershell
python -m unittest discover -s tests -q
python scripts/check_case.py xml
```

The helper-dependent tests skip when the companion helper is not installed beside
the skin. Deploy the helper changes together with the skin so future generated
menus retain the fixes.

## Backups

Original local files:
`C:/Users/josh/AppData/Local/Temp/nimbus-kodi22-backup-20261028-7fu8k8zw/`.

Original active Shield files:
`special://temp/nimbus-kodi22-backup-20261028-26437699/`.
The functional skin/helper files were backed up before replacement. Local blank
template originals are also in the local backup above.
