# LSR Integration for Home Assistant

![GitHub Release](https://img.shields.io/github/v/release/OddanN/lsr_for_home_assistant?style=flat-square)
![GitHub Activity](https://img.shields.io/github/commit-activity/m/OddanN/lsr_for_home_assistant?style=flat-square)
![GitHub Downloads](https://img.shields.io/github/downloads/OddanN/lsr_for_home_assistant/total?style=flat-square)
![License](https://img.shields.io/github/license/OddanN/lsr_for_home_assistant?style=flat-square)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://github.com/hacs/integration)

The LSR Integration allows you to connect your Home Assistant instance to the [LSR](https://www.lsr.ru/), providing access to communal account data, camera streams, and meter readings. This integration supports authentication via the LSR API and offers sensor entities for monitoring account status, notifications, and meter values.

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
instance.](https://my.home-assistant.io/badges/config_flow_start.svg?style=flat-square)](https://my.home-assistant.io/redirect/config_flow_start/?domain=lsr_for_home_assistant)

### Setup Wizard
- **Username**: Your LSR account username (usually the phone number). 
- **Password**: Your LSR account password.
- **Scan Interval**: Optional field to set the update interval (default is 12 hours, minimum 1 hour).

After successful authentication, the integration will automatically set up sensors.

## Usage

### Entities
Once configured, the following entities will be available. Entity IDs use a `<suffix>` based on the personal account
number (if present) or the last 8 characters of the account ID.

- **Sensors**:
  - `sensor.lsr_<suffix>_address`: Displays the address of the communal account.
  - `sensor.lsr_<suffix>_personal_account_number`: Personal account number.
  - `sensor.lsr_<suffix>_payment_status`: Payment status.
  - `sensor.lsr_<suffix>_notification_count`: Number of pending notifications.
  - `sensor.lsr_<suffix>_camera_count`: Number of associated cameras.
  - `sensor.lsr_<suffix>_last_refresh`: Timestamp of the last refresh.
  - `sensor.lsr_<suffix>_meter_count`: Total number of meters. Includes extra attributes with the latest values
    for each meter.
  - `sensor.lsr_<suffix>_meter_<number>_value`: Current reading of a specific meter. Attributes include:
    `title`, `meter_type`, `poverka_date`, `last_update`, `meter_id`.
  - `sensor.lsr_<suffix>_communalrequest_count_total`: Total communal requests. Attributes include counters by status:
    `done`, `atwork`, `onhold`, `waiting`.
  - `sensor.lsr_<suffix>_communalrequest_count_done`: Communal requests with status Done.
  - `sensor.lsr_<suffix>_communalrequest_count_atwork`: Communal requests with status AtWork.
  - `sensor.lsr_<suffix>_communalrequest_count_onhold`: Communal requests with status OnHold.
  - `sensor.lsr_<suffix>_communalrequest_count_waitingforregistration`: Communal requests waiting for registration.
  - `sensor.lsr_<suffix>_payment_due`: Amount of the latest accrual. Attributes include month-based amounts.
  - `sensor.lsr_<suffix>_skud`: Main SKUD PIN code. Attributes include guest passes and main pass metadata.

- **Numbers**:
  - `number.lsr_<suffix>_scan_interval`: Scan interval in hours (1-12).

- **Buttons**:
  - `button.lsr_<suffix>_force_update`: Force update of sensor data.

- **Cameras**:
  - `camera.lsr_<suffix>_camera_<camera_id>`: Live stream from LSR cameras (if available).
  - `camera.lsr_<suffix>_mainpass_qr`: QR code of the main pass (if available).

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
- For support or to report issues, please open an issue on the [GitHub repository](https://github.com/OddanN/lsr_for_home_assistant/issues).

## Debug

For DEBUG add to `configuration.yaml`
```yaml
logger:
  default: info
  logs:
    custom_components.lsr_for_home_assistant: debug
```
## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
