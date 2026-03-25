/**
 * @file ota_update.h
 * @brief OTA (Over-The-Air) Firmware Update Manager
 *
 * IEC 62304 Software Class B — safety-relevant update path.
 *
 * Architecture: dual-bank flash.
 *   Bank A (active)  — running firmware
 *   Bank B (staging) — receives new image
 *   On verified completion: set boot flag → reset → bootloader swaps banks.
 *
 * Security:
 *   - Image authenticated with ECDSA-P256 signature (mbedTLS).
 *   - CRC32 verified before signature check.
 *   - Version anti-rollback: firmware version must be >= current.
 *
 * Failure modes:
 *   - Incomplete write   → staging bank never marked valid → boot A unchanged.
 *   - Bad signature      → abort, staging bank erased.
 *   - Reset during write → watchdog reboot → boot A unchanged.
 *   - Failed boot of B   → bootloader rollback to A after 3 consecutive failures.
 *
 * @version 1.0.0
 * @date    2026-03-21
 */

#ifndef OTA_UPDATE_H
#define OTA_UPDATE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* =========================================================================
 * Constants
 * ========================================================================= */
#define OTA_MAGIC              0x4F544155UL  /**< "OTAU"                       */
#define OTA_SIGNATURE_LEN      64u           /**< ECDSA-P256 raw signature bytes*/
#define OTA_HASH_LEN           32u           /**< SHA-256 hash bytes            */
#define OTA_VERSION_STR_LEN    16u           /**< e.g. "1.2.3"                 */
#define OTA_MAX_IMAGE_SIZE     (512u * 1024u)/**< 512 KB max image              */
#define OTA_CHUNK_SIZE         256u          /**< Write chunk size (bytes)      */
#define OTA_ROLLBACK_ATTEMPTS  3u            /**< Failed boots before rollback  */

/* =========================================================================
 * Error codes
 * ========================================================================= */
typedef enum {
    OTA_ERR_OK              =  0,
    OTA_ERR_NULL_PTR        = -1,
    OTA_ERR_BAD_MAGIC       = -2,
    OTA_ERR_BAD_VERSION     = -3,   /**< Anti-rollback: image version too old */
    OTA_ERR_BAD_SIZE        = -4,
    OTA_ERR_CRC_FAIL        = -5,
    OTA_ERR_SIG_FAIL        = -6,
    OTA_ERR_FLASH_ERASE     = -7,
    OTA_ERR_FLASH_WRITE     = -8,
    OTA_ERR_NOT_STARTED     = -9,
    OTA_ERR_ALREADY_STARTED = -10,
    OTA_ERR_CHUNK_OVERFLOW  = -11,
    OTA_ERR_NOT_COMPLETE    = -12,
    OTA_ERR_HAL             = -13,
} OtaErr;

/* =========================================================================
 * OTA image header (written at offset 0 of staging bank)
 * ========================================================================= */
typedef struct __attribute__((packed)) {
    uint32_t magic;                         /**< Must equal OTA_MAGIC          */
    uint32_t image_size;                    /**< Payload bytes after header    */
    uint32_t crc32;                         /**< CRC32 over image payload      */
    uint8_t  hash[OTA_HASH_LEN];            /**< SHA-256 of image payload      */
    uint8_t  signature[OTA_SIGNATURE_LEN];  /**< ECDSA-P256 over hash          */
    uint32_t version_major;
    uint32_t version_minor;
    uint32_t version_patch;
    char     version_str[OTA_VERSION_STR_LEN];
    uint8_t  reserved[32];
} OtaImageHeader;

/* =========================================================================
 * Progress callback
 * ========================================================================= */
typedef void (*OtaProgressCb)(uint32_t bytes_written,
                               uint32_t total_bytes,
                               void    *user_data);

/* =========================================================================
 * Public API
 * ========================================================================= */

/**
 * @brief  Initialise OTA subsystem; reads current firmware version.
 * @return OTA_ERR_OK or error code.
 */
OtaErr ota_init(void);

/**
 * @brief  Begin an OTA session. Erases staging bank.
 * @param  header  Authenticated image header (caller validates before calling).
 * @return OTA_ERR_OK or OTA_ERR_ALREADY_STARTED / OTA_ERR_BAD_VERSION.
 */
OtaErr ota_begin(const OtaImageHeader *header);

/**
 * @brief  Write the next chunk of image payload to staging flash.
 * @param  data   Pointer to chunk data.
 * @param  len    Length of chunk (must be <= OTA_CHUNK_SIZE).
 * @return OTA_ERR_OK or flash/overflow error.
 */
OtaErr ota_write_chunk(const uint8_t *data, uint32_t len);

/**
 * @brief  Finalise: verify CRC32, verify ECDSA signature, then set boot flag.
 *         After this call the device should be reset to apply the update.
 * @return OTA_ERR_OK on verified success, error code otherwise.
 *         On failure: staging bank is erased automatically.
 */
OtaErr ota_finalize(void);

/**
 * @brief  Abort an in-progress OTA session and erase staging bank.
 */
void ota_abort(void);

/**
 * @brief  Query whether a verified update is pending reboot.
 */
bool ota_update_pending(void);

/**
 * @brief  Register a progress callback (optional).
 */
void ota_set_progress_cb(OtaProgressCb cb, void *user_data);

/**
 * @brief  Returns the running firmware version.
 */
void ota_get_current_version(uint32_t *major, uint32_t *minor, uint32_t *patch);

/**
 * @brief  Confirm the new image booted successfully (call early in main).
 *         Clears rollback counter. If not called within OTA_CONFIRM_TIMEOUT_MS,
 *         watchdog triggers a reset and bootloader rolls back.
 */
OtaErr ota_confirm_boot(void);

#ifdef __cplusplus
}
#endif

#endif /* OTA_UPDATE_H */
