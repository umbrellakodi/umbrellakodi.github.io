# How to Install Magneto and Set It as Umbrella's External Scraper

This guide covers installing the Magneto Module and selecting it as the external scraper in the Kodi Umbrella add-on.

## Before you start

- Have Umbrella installed in Kodi.
- For sources that require a debrid service, authorize your account in Umbrella and make sure it is active.
- Menu names may vary slightly depending on your Kodi skin, language, and Umbrella version.

## 1. Add the Kodifitzwell repository

1. From Kodi's home screen, open **Settings** (the gear icon).
2. Go to **System → Add-ons** and enable **Unknown sources** if it is disabled. Accept Kodi's confirmation to allow installation from this source.
3. Return to **Settings → File manager → Add source**.
4. Select **<None>** and enter this address exactly:

   ```text
   https://kodifitzwell.github.io/repo/
   ```

5. Name the source **Kodifitzwell**, then select **OK**.
6. Go to **Settings → Add-ons → Install from zip file**.
7. Select **Kodifitzwell**, then select **repository.kodifitzwell-0.0.1.zip**, or the newer repository ZIP if the download page lists one.
8. Wait for Kodi's repository installation notification.

## 2. Install the Magneto Module

When the repository offers Magneto:

1. Open **Settings → Add-ons → Install from repository**.
2. Select the **Kodifitzwell** repository.
3. Open **Program add-ons**.
4. Select **Magneto Module → Install**.
5. Accept any required dependencies and wait for the installation notification.


## 3. Select Magneto in Umbrella

1. Go to **Add-ons → Video add-ons** and highlight **Umbrella**.
2. Open its context menu by right-clicking, long-pressing, or using your remote's menu button, then choose **Settings**.
3. Open the **Providers** category.
4. Turn on **Enable External Providers**.
5. Select **External Provider:**.
6. Choose **Magneto Module** from the list of installed add-ons.
7. If the settings window closes, reopen it and check **Providers**. The selected provider should show:

   ```text
   script.module.magneto
   ```

8. Select **OK** to save and close the settings.

**Already using CocoScrapers?** Follow the same selection steps and choose Magneto. You can leave CocoScrapers installed and select it again later.

## 4. Check the setup

Reopen Umbrella's settings and confirm that **Enable External Providers** is on and **External Provider:** shows `script.module.magneto`. Then run a fresh source search in Umbrella. Available results depend on the title, scraper providers, account access, and your filters.

## Troubleshooting

### Magneto does not appear in Umbrella's selection list

- Confirm that **Magneto Module** itself is installed; installing only the repository is not enough.
- Check **Kodi → Add-ons → My add-ons → Program add-ons** for Magneto and enable it if it is disabled.
- Fully exit Kodi, reopen it, and try selecting the provider again.

### The External Provider option is missing

Turn on **Enable External Providers** first. Umbrella hides the provider selection option while that setting is off. In some older versions or translations, the settings category may be labeled **Accounts(Non-Debrid)** instead of **Providers**.

### External providers turned off after opening the selection list

Re-enable **Enable External Providers**, open **External Provider:**, and select Magneto. Canceling the selection dialog can disable external providers and clear the selected module in Umbrella.

### Magneto is selected, but no sources are returned

- Recheck that your required debrid account is authorized and active in Umbrella.
- Review your source filters and Magneto's provider settings.
- Try a fresh search for another title to see whether the issue is limited to one title.
- Try a health check in the Magneto addon's settings.
