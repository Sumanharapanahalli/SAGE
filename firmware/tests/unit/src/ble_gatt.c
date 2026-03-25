/**
 * @file ble_gatt.c
 * @brief BLE GATT server attribute handling implementation.
 */

#include "ble_gatt.h"
#include <string.h>

/* -------------------------------------------------------------------------
 * Private state
 * ---------------------------------------------------------------------- */

static GATTAttribute    s_attributes[BLE_MAX_ATTRIBUTES];
static int              s_attr_count;
static BLENotifyCallback s_notify_cb;
static uint32_t         s_notify_count;

/* -------------------------------------------------------------------------
 * Private helpers
 * ---------------------------------------------------------------------- */

static GATTAttribute *_find_attr(uint16_t handle)
{
    for (int i = 0; i < s_attr_count; i++) {
        if (s_attributes[i].handle == handle) {
            return &s_attributes[i];
        }
    }
    return NULL;
}

static void _register_attr(uint16_t handle, uint8_t props,
                            const uint8_t *init_data, uint16_t init_len)
{
    if (s_attr_count >= BLE_MAX_ATTRIBUTES) return;
    GATTAttribute *a = &s_attributes[s_attr_count++];
    a->handle         = handle;
    a->properties     = props;
    a->notify_enabled = false;
    a->cccd           = BLE_CCCD_DISABLED;
    if (init_data && init_len > 0 && init_len <= BLE_ATTR_MAX_LEN) {
        memcpy(a->data, init_data, init_len);
        a->data_len = init_len;
    } else {
        memset(a->data, 0, BLE_ATTR_MAX_LEN);
        a->data_len = 0;
    }
}

/* -------------------------------------------------------------------------
 * Public API
 * ---------------------------------------------------------------------- */

void ble_gatt_init(void)
{
    memset(s_attributes, 0, sizeof(s_attributes));
    s_attr_count   = 0;
    s_notify_cb    = NULL;
    s_notify_count = 0;

    uint8_t batt_init = 100U;

    _register_attr(HANDLE_FALL_ALERT_CHAR,
                   BLE_PROP_READ | BLE_PROP_NOTIFY, NULL, 0);
    _register_attr(HANDLE_LOCATION_CHAR,
                   BLE_PROP_READ | BLE_PROP_NOTIFY, NULL, 0);
    _register_attr(HANDLE_BATTERY_CHAR,
                   BLE_PROP_READ | BLE_PROP_NOTIFY, &batt_init, 1);
    _register_attr(HANDLE_SOS_CHAR,
                   BLE_PROP_READ | BLE_PROP_WRITE | BLE_PROP_NOTIFY, NULL, 0);
    _register_attr(HANDLE_DEVICE_STATUS_CHAR,
                   BLE_PROP_READ | BLE_PROP_NOTIFY, NULL, 0);
    _register_attr(HANDLE_CONFIG_CHAR,
                   BLE_PROP_READ | BLE_PROP_WRITE, NULL, 0);
}

BLEError ble_gatt_read(uint16_t handle, uint8_t *buf, uint16_t *len)
{
    if (buf == NULL || len == NULL) return BLE_ERR_NULL_PARAM;

    GATTAttribute *a = _find_attr(handle);
    if (a == NULL) return BLE_ERR_INVALID_HANDLE;
    if (!(a->properties & BLE_PROP_READ)) return BLE_ERR_READ_NOT_PERM;

    uint16_t copy_len = (a->data_len < *len) ? a->data_len : *len;
    memcpy(buf, a->data, copy_len);
    *len = copy_len;
    return BLE_OK;
}

BLEError ble_gatt_write(uint16_t handle, const uint8_t *data, uint16_t len)
{
    if (data == NULL) return BLE_ERR_NULL_PARAM;
    if (len > BLE_ATTR_MAX_LEN) return BLE_ERR_INVALID_LENGTH;

    GATTAttribute *a = _find_attr(handle);
    if (a == NULL) return BLE_ERR_INVALID_HANDLE;
    if (!(a->properties & (BLE_PROP_WRITE | BLE_PROP_WRITE_NR)))
        return BLE_ERR_WRITE_NOT_PERM;

    memcpy(a->data, data, len);
    a->data_len = len;
    return BLE_OK;
}

BLEError ble_gatt_notify(uint16_t handle, const uint8_t *data, uint16_t len)
{
    if (data == NULL) return BLE_ERR_NULL_PARAM;
    if (len > BLE_ATTR_MAX_LEN) return BLE_ERR_INVALID_LENGTH;

    GATTAttribute *a = _find_attr(handle);
    if (a == NULL) return BLE_ERR_INVALID_HANDLE;
    if (!(a->properties & BLE_PROP_NOTIFY)) return BLE_ERR_NOTIFY_DISABLED;
    if (!a->notify_enabled) return BLE_ERR_NOTIFY_DISABLED;

    /* Update attribute data */
    memcpy(a->data, data, len);
    a->data_len = len;
    s_notify_count++;

    if (s_notify_cb != NULL) {
        s_notify_cb(handle, data, len);
    }
    return BLE_OK;
}

BLEError ble_gatt_set_cccd(uint16_t handle, uint8_t cccd_value)
{
    GATTAttribute *a = _find_attr(handle);
    if (a == NULL) return BLE_ERR_INVALID_HANDLE;
    if (!(a->properties & (BLE_PROP_NOTIFY | BLE_PROP_INDICATE)))
        return BLE_ERR_NOTIFY_DISABLED;

    a->cccd           = cccd_value;
    a->notify_enabled = (cccd_value == BLE_CCCD_NOTIFY);
    return BLE_OK;
}

bool ble_gatt_is_notify_enabled(uint16_t handle)
{
    GATTAttribute *a = _find_attr(handle);
    return (a != NULL) && a->notify_enabled;
}

void ble_gatt_set_notify_callback(BLENotifyCallback cb)
{
    s_notify_cb = cb;
}

uint32_t ble_gatt_get_notify_count(void)
{
    return s_notify_count;
}

void ble_gatt_reset(void)
{
    memset(s_attributes, 0, sizeof(s_attributes));
    s_attr_count   = 0;
    s_notify_cb    = NULL;
    s_notify_count = 0;
}
