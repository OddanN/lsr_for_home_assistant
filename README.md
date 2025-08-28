# LSR Integration for Home Assistant

The LSR Integration allows you to connect your Home Assistant instance to the LSR (Leader-Smart Realty) system, providing access to communal account data, camera streams, and meter readings. This integration supports authentication via the LSR API and offers sensor entities for monitoring account status, notifications, and meter values.

## Installation

### Manual Installation

1. **Download the Integration**:
   - Clone or download this repository to your Home Assistant `custom_components` directory:
     ```
     git clone https://github.com/yourusername/hass-lsr.git custom_components/lsr
     ```
   - Alternatively, download the ZIP file and extract it to `custom_components/lsr`.

2. **Restart Home Assistant**:
   - Restart your Home Assistant instance to load the new integration:
     ```
     ha core restart
     ```

3. **Configure the Integration**:
   - Go to **Settings > Devices & Services > Add Integration** in the Home Assistant UI.
   - Search for "LSR" and follow the setup wizard to enter your credentials.

### HACS Installation (Optional)

If you use [HACS](https://hacs.xyz/):
1. Add this repository as a custom repository under HACS > Integrations.
2. Install the "LSR" integration.
3. Restart Home Assistant and configure via the UI as described above.

## Configuration

The LSR Integration is configured through the Home Assistant UI. No manual YAML configuration is required.

### Setup Wizard
- **Username**: Your LSR account username.
- **Password**: Your LSR account password.
- **Scan Interval**: Optional field to set the update interval (default is 12 hours, minimum 1 hour).

After successful authentication, the integration will automatically set up sensors and camera entities based on your account data.

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
- Camera streams depend on the availability of `videoUrl` in the API response.
- The integration uses a 12-hour default scan interval, adjustable via the configuration flow.
- For support or to report issues, please open an issue on the [GitHub repository](https://github.com/yourusername/hass-lsr/issues).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.