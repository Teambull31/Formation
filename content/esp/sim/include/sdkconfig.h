/* Fake ESP-IDF v5.x: sdkconfig.h (subset). In a real project this file is generated from menuconfig. The two Wi-Fi
 * symbols are those of the Kconfig.projbuild of the official station example (examples/wifi/getting_started/station):
 * the SSID and the password come from the build configuration, never from the source code. The values below are
 * SAMPLES for the simulator, not a real network. */
#pragma once

#define CONFIG_ESP_WIFI_SSID "reseau-exemple"
#define CONFIG_ESP_WIFI_PASSWORD "exemple-motdepasse"

/* The bootloader rolls an OTA image back when it was not confirmed before the next reset (see esp_ota_ops.h).
 * Always on in the simulator. */
#define CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE 1
