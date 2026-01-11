# LSR Integration for Home Assistant

![GitHub Release](https://img.shields.io/github/v/release/OddanN/lsr_for_home_assistant?style=flat-square)
![GitHub Activity](https://img.shields.io/github/commit-activity/m/OddanN/lsr_for_home_assistant?style=flat-square)
![GitHub Downloads](https://img.shields.io/github/downloads/OddanN/lsr_for_home_assistant/total?style=flat-square)
![License](https://img.shields.io/github/license/OddanN/lsr_for_home_assistant?style=flat-square)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://github.com/hacs/integration)

The LSR Integration allows you to connect your Home Assistant instance to the LSR (Leader-Smart Realty) system, providing access to communal account data, camera streams, and meter readings. This integration supports authentication via the LSR API and offers sensor entities for monitoring account status, notifications, and meter values.

## Installation

Installation is easiest via the [Home Assistant Community Store
(HACS)](https://hacs.xyz/), which is the best place to get third-party
integrations for Home Assistant. Once you have HACS set up, simply click the button below (requires My Homeassistant configured) or
follow the [instructions for adding a custom
repository](https://hacs.xyz/docs/faq/custom_repositories) and then
the integration will be available to install like any other.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg?style=flat-square)](https://my.home-assistant.io/redirect/hacs_repository/?owner=OddanN&repository=lsr_for_home_assistant&category=integration)

## Configuration

After installing, you can easily configure your devices using the Integrations configuration UI (No manual YAML configuration is required).  Go to Settings / Devices & Services and press the Add Integration button, or click the shortcut button below (requires My Homeassistant configured).

[![Add Integration to your Home Assistant
instance.](https://my.home-assistant.io/badges/config_flow_start.svg?style=flat-square)](https://my.home-assistant.io/redirect/config_flow_start/?domain=lsr)

### Setup Wizard
- **Username**: Your LSR account username (usually the phone number is in the format 79991234567, without the +). 
- **Password**: Your LSR account password.
- **Scan Interval**: Optional field to set the update interval (default is 12 hours, minimum 1 hour).

After successful authentication, the integration will automatically set up sensors.

## Usage

### Entities
Once configured, the following entities will be available:

- **Sensors**:
  - `sensor.lsr_<account_id>_account_address`: Displays the address of the communal account.
  - `sensor.lsr_<account_id>_payment_status`: Shows the payment status.
  - `sensor.lsr_<account_id>_notification_count`: Number of pending notifications.
  - `sensor.lsr_<account_id>_camera_count`: Number of associated cameras.
  - `sensor.lsr_<account_id>_meter_<number>_value`: Current reading of a specific meter.
  - `sensor.lsr_<account_id>_meter_<number>_title`: Meter title.
  - `sensor.lsr_<account_id>_meter_<number>_poverka`: Meter verification date.

- **Cameras**:
  - `camera.lsr_<account_id>_cam_<camera_id>`: Live stream from LSR cameras (if available).

### Example Automation
Create an automation to notify you when a new notification is detected:
```yaml
automation:
  - alias: LSR Notification Alert
    trigger:
      platform: state
      entity_id: sensor.lsr_<account_id>_notification_count
      to: "1"
    action:
      - service: notify.mobile_app_<your_device>
        data:
          message: "New LSR notification detected!"
```

## Notes
- This integration requires an active LSR account with API access.
- The integration uses a 12-hour default scan interval, adjustable via the configuration flow.
- For support or to report issues, please open an issue on the [GitHub repository](https://github.com/yourusername/hass-lsr/issues).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.