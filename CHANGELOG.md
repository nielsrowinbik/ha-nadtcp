## [2.0.0](https://github.com/nielsrowinbik/ha-nadtcp/compare/v1.1.0...v2.0.0) (2026-11-11)

### ⚠ BREAKING CHANGES

* the integration domain changes from nadtcp2 to nad_tcp and YAML configuration is no longer supported. Set the amplifier up under Settings > Devices & services instead. volume_step is removed; volume up/down use the amplifier's own step.

- Add config flow (user and reconfigure steps) and an options flow for min/max volume
- Use the pynadtcp library instead of embedded protocol code
- Fix volume down at the minimum raising ValueError
- Fix volume up lowering the volume when the amp is above the maximum
- Fix volume steps being half the configured size
- Fix multiple amplifiers overwriting each other's state
- Fix one unparseable line dropping the connection
- Log one warning on disconnect and one on reconnect instead of an error every 10 seconds
- Use the config entry ID as the unique ID instead of the IP address
- Add tests (100% coverage), hassfest and pytest CI jobs, and local brand icons
- Remove docker-compose.yml

### Features

* discover NAD amplifiers through their Google Cast announcement ([1b873fd](https://github.com/nielsrowinbik/ha-nadtcp/commit/1b873fdecb2455b5a09abc595245085c38b0649e))
* replace nadtcp2 with UI-configured nad_tcp integration ([7ff2a93](https://github.com/nielsrowinbik/ha-nadtcp/commit/7ff2a93a1a6a8e491e1c11c6c7be3deaca5f3ce0))
