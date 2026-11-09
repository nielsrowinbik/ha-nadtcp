# NAD (TCP)

Control a NAD amplifier (tested with the C338) over your network from Home Assistant.

After installing, restart Home Assistant and go to **Settings** > **Devices & services**. Your amplifier shows up under **Discovered**. If it doesn't, select **Add integration** > **NAD (TCP)** and enter its IP address. Set the minimum and maximum volume under **Configure**.

**Upgrading from 1.x?** YAML configuration is no longer supported. Remove the `nadtcp2` entry from your `configuration.yaml`, delete the old `custom_components/nadtcp2` folder, restart, and add the integration in the UI. The entity ID may change, so check your automations and dashboards. See the README for details.
