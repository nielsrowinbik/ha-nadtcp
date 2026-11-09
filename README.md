[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# NAD (TCP) for Home Assistant

Control a NAD amplifier over your network from Home Assistant. Tested with the NAD C338. Other NAD models that use the same TCP control protocol on port 30001 may work, but aren't known to.

The amplifier shows up as a media player. You can turn it on and off, set and step the volume, mute it and pick an input source. Changes made with the remote or the front panel show up in Home Assistant straight away.

## Installation

1. Add this repository to HACS as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories/) of type Integration.
2. Download **NAD (TCP)** in HACS.
3. Restart Home Assistant.
4. Go to **Settings** > **Devices & services**. Home Assistant finds the amplifier on your network and shows it under **Discovered**. Select **Add** and confirm.

If the amplifier doesn't show up, add it by IP address: select **Add integration**, search for **NAD (TCP)** and enter the IP address of your amplifier.

Home Assistant connects to the amplifier before adding it, so make sure it's switched on or in standby and reachable on your network.

### How discovery works

The C338 has Chromecast built in and announces itself on the network as a Cast device. Home Assistant picks up any Cast device whose model name starts with "NAD", checks that it answers on port 30001, and only then offers it. Other NAD models with Chromecast built in will be offered if they speak the same protocol, but they aren't known to work.

Discovery needs Home Assistant to receive mDNS (multicast) traffic from the amplifier. If the amplifier is on another network or VLAN than Home Assistant, add it by IP address.

## Configuration

Go to **Settings** > **Devices & services** > **NAD (TCP)** and select **Configure** to set:

- **Minimum volume**: the amplifier volume, in dB, that Home Assistant shows as 0%. Default: -80 dB.
- **Maximum volume**: the amplifier volume, in dB, that Home Assistant shows as 100%. Default: -10 dB.

Both must be between -80 and 0 dB, and the minimum must be lower than the maximum. Volume up and down use the amplifier's own step, and stop at these limits. If the volume is set beyond the limits with the remote, Home Assistant shows 0% or 100%.

## Changing the IP address

If the amplifier gets a new IP address, Home Assistant normally picks up the new address on its own when it sees the amplifier's next network announcement. That also works for an amplifier you added by IP address, once Home Assistant has discovered it at that address.

If that doesn't happen, go to **Settings** > **Devices & services** > **NAD (TCP)**, open the menu next to the entry and select **Reconfigure**. Enter the new address. Your entity and its history stay the same.

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
