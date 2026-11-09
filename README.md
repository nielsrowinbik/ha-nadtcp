[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# NAD (TCP) for Home Assistant

Control a NAD amplifier over your network from Home Assistant. Tested with the NAD C338. Other NAD models that use the same TCP control protocol on port 30001 may work, but are untested.

The amplifier shows up as a media player. You can turn it on and off, set and step the volume, mute it and pick an input source. Changes made with the remote or the front panel show up in Home Assistant straight away.

## Installation

1. Add this repository to HACS as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) of type Integration.
2. Download **NAD (TCP)** in HACS.
3. Restart Home Assistant.
4. Go to **Settings** > **Devices & services** > **Add integration** and search for **NAD (TCP)**.
5. Enter the IP address of your amplifier.

Home Assistant connects to the amplifier before adding it, so make sure it's switched on and reachable on your network.

## Configuration

Go to **Settings** > **Devices & services** > **NAD (TCP)** and select **Configure** to set:

- **Minimum volume**: the amplifier volume, in dB, that Home Assistant shows as 0%. Default: -80 dB.
- **Maximum volume**: the amplifier volume, in dB, that Home Assistant shows as 100%. Default: -10 dB.

Both must be between -80 and 0 dB, and the minimum must be lower than the maximum. Volume up and down use the amplifier's own step, and stop at these limits. If the volume is set beyond the limits with the remote, Home Assistant shows 0% or 100%.

## Changing the IP address

If the amplifier gets a new IP address, go to **Settings** > **Devices & services** > **NAD (TCP)**, open the menu next to the entry and select **Reconfigure**. Enter the new address. Your entity and its history stay the same.

## Upgrading from 1.x

Version 2.0.0 replaces YAML configuration with setup in the UI. To upgrade:

1. Remove the `nadtcp2` entry from `media_player:` in your `configuration.yaml`:
   ```yaml
   media_player:
     - platform: nadtcp2
       ...
   ```
2. Update the integration in HACS.
3. Delete the `custom_components/nadtcp2` folder from your Home Assistant config folder if it's still there. HACS may leave it behind.
4. Restart Home Assistant.
5. Add the integration in the UI as described under [Installation](#installation), and set your minimum and maximum volume under [Configuration](#configuration).
6. The entity ID may be different from before. Check your automations, scripts and dashboards.

`volume_step` is gone. Volume up and down now use the amplifier's own step.

## Credits

This is a fork of [martonperei/ha-nadtcp](https://github.com/martonperei/ha-nadtcp). The protocol code comes from the [nadtcp](https://gitlab.com/mindig.marton/nadtcp) library, and now lives in [pynadtcp](https://github.com/nielsrowinbik/pynadtcp).
