# PunchPlay in Umbrella

The registered Umbrella client ID is configured in the `CLIENT_ID` constant in `resources/lib/modules/punchplay.py`. Fill in `CLIENT_SECRET` in that same file locally. Restart Kodi after saving your changes. Open **Umbrella settings → Accounts → PunchPlay** and select **Authorize PunchPlay**. Enter the displayed code at the displayed verification URL using your browser. You do not need to share your secret in chat.

This integration uses the PunchPlay Platform v1 developer API and its device authorization flow. It does not require an OAuth redirect URI. Your app must permit device authorization and these scopes:

```
profile:read history:read history:write playback:read playback:write
lists:read lists:write ratings:read ratings:write collection:read collection:write
```

After authorization, select **PunchPlay** for watched indicators and the playback/resume provider in Umbrella's tracking settings. PunchPlay can also receive playback events alongside your selected provider through its additional tracking toggle. The initial authorization downloads your watched history, lists, collection, watch statuses, and resume records. **Force sync** refreshes these manually; background sync runs at the configured interval when playback is idle.

The movie and TV PunchPlay menus provide watched/progress views, unfinished playback, lists, collection, favourites, and watch statuses. The **PunchPlay Manager** context menu supports watched history, watchlist and list membership, collection editions, ratings, favourites, and show status. Imported lists and dynamic list contents remain read only as required by the API. Playback reports start, pause, resume, periodic progress, and completion, including specials and repeat watches.

If the separate `script.punchplay` addon is also reporting the same playback, disable its playback reporting while testing this integration to avoid duplicate reports. It is not a dependency of Umbrella's provider.

Validation uses mocked HTTP responses and the published OpenAPI contract in `tests/fixtures/punchplay-contract.json`. Actual developer-app authorization and playback still need a live account check. The API is currently a beta, so server behavior may change.

API references: [authentication](https://docs.punchplay.tv/authentication), [playback](https://docs.punchplay.tv/playback-api), [sync](https://docs.punchplay.tv/partner-sync).
