/**
 * @file     ota.c
 * @brief    OTA firmware update implementation.
 *
 * IEC 62304 Class: B
 */
#include "ota.h"
#include "stm32l4xx_hal.h"
#include "modem_hal.h"
#include <string.h>

static OtaState_t      s_state           = OTA_STATE_IDLE;
static uint32_t        s_expected_crc    = 0;
static uint32_t        s_expected_size   = 0;
static uint32_t        s_written_bytes   = 0;
static uint32_t        s_pending_version = 0;
static CRC_HandleTypeDef hcrc_local;

/* ---------------------------------------------------------------------------
 * Private helpers
 * -------------------------------------------------------------------------*/
static bool flash_erase_bank2(void)
{
    FLASH_EraseInitTypeDef erase = {
        .TypeErase = FLASH_TYPEERASE_MASSERASE,
        .Banks     = FLASH_BANK_2,
    };
    uint32_t page_err;
    HAL_FLASH_Unlock();
    HAL_StatusTypeDef rc = HAL_FLASHEx_Erase(&erase, &page_err);
    HAL_FLASH_Lock();
    return rc == HAL_OK;
}

static bool flash_write_chunk(uint32_t dst_addr, const uint8_t *data, uint16_t len)
{
    if ((dst_addr & 7U) != 0) return false;
    HAL_FLASH_Unlock();
    HAL_StatusTypeDef rc = HAL_OK;
    for (uint16_t i = 0; i < len && rc == HAL_OK; i += 8) {
        uint64_t dword = 0xFFFFFFFFFFFFFFFFULL;
        uint16_t n = (len - i >= 8) ? 8 : (len - i);
        memcpy(&dword, data + i, n);
        rc = HAL_FLASH_Program(FLASH_TYPEPROGRAM_DOUBLEWORD, dst_addr + i, dword);
    }
    HAL_FLASH_Lock();
    return rc == HAL_OK;
}

static uint32_t compute_crc32(uint32_t base_addr, uint32_t size)
{
    hcrc_local.Instance = CRC;
    hcrc_local.Init.DefaultPolynomialUse    = DEFAULT_POLYNOMIAL_ENABLE;
    hcrc_local.Init.DefaultInitValueUse     = DEFAULT_INIT_VALUE_ENABLE;
    hcrc_local.Init.InputDataInversionMode  = CRC_INPUTDATA_INVERSION_NONE;
    hcrc_local.Init.OutputDataInversionMode = CRC_OUTPUTDATA_INVERSION_DISABLE;
    hcrc_local.InputDataFormat              = CRC_INPUTDATA_FORMAT_BYTES;
    HAL_CRC_Init(&hcrc_local);
    return HAL_CRC_Calculate(&hcrc_local, (uint32_t *)base_addr, size);
}

static bool write_ota_descriptor(const OtaDescriptor_t *desc)
{
    FLASH_EraseInitTypeDef erase = {
        .TypeErase = FLASH_TYPEERASE_PAGES,
        .Banks     = FLASH_BANK_1,
        .Page      = 255U,
        .NbPages   = 1U,
    };
    uint32_t page_err;
    HAL_FLASH_Unlock();
    HAL_StatusTypeDef rc = HAL_FLASHEx_Erase(&erase, &page_err);
    if (rc == HAL_OK) {
        /* Write descriptor in two 8-byte double-words */
        uint64_t w0, w1;
        memcpy(&w0, (const uint8_t *)desc,     8);
        memcpy(&w1, (const uint8_t *)desc + 8, sizeof(OtaDescriptor_t) - 8);
        rc = HAL_FLASH_Program(FLASH_TYPEPROGRAM_DOUBLEWORD, OTA_DESC_ADDR,      w0);
        if (rc == HAL_OK)
            rc = HAL_FLASH_Program(FLASH_TYPEPROGRAM_DOUBLEWORD, OTA_DESC_ADDR + 8, w1);
    }
    HAL_FLASH_Lock();
    return rc == HAL_OK;
}

/* ===========================================================================
 * Public API
 * =========================================================================*/

void OTA_Init(void)
{
    s_state         = OTA_STATE_IDLE;
    s_written_bytes = 0;

    const OtaDescriptor_t *desc = (const OtaDescriptor_t *)OTA_DESC_ADDR;
    if (desc->magic == OTA_MAGIC && desc->pending) {
        OtaDescriptor_t updated = *desc;
        updated.pending = 0;
        write_ota_descriptor(&updated);
    }
}

bool OTA_StartDownload(const char *fw_url, uint32_t expected_crc,
                        uint32_t expected_size, uint32_t version)
{
    (void)fw_url;
    if (expected_size > OTA_BANK2_SIZE)      return false;
    if (s_state == OTA_STATE_DOWNLOADING)    return false;
    if (!flash_erase_bank2())                return false;

    s_expected_crc    = expected_crc;
    s_expected_size   = expected_size;
    s_pending_version = version;
    s_written_bytes   = 0;
    s_state           = OTA_STATE_DOWNLOADING;
    return true;
}

bool OTA_WriteChunk(uint32_t offset, const uint8_t *data, uint16_t len)
{
    if (s_state != OTA_STATE_DOWNLOADING)    return false;
    if (!data || len == 0 || len > OTA_CHUNK_SIZE) return false;
    if (offset + len > OTA_BANK2_SIZE)       return false;

    if (!flash_write_chunk(OTA_BANK2_BASE + offset, data, len)) {
        s_state = OTA_STATE_FAILED;
        return false;
    }
    s_written_bytes += len;
    return true;
}

bool OTA_Finalise(void)
{
    if (s_state != OTA_STATE_DOWNLOADING)    return false;
    if (s_written_bytes != s_expected_size)  return false;

    s_state = OTA_STATE_VERIFYING;

    uint32_t actual_crc = compute_crc32(OTA_BANK2_BASE, s_expected_size);
    if (actual_crc != s_expected_crc) {
        s_state = OTA_STATE_FAILED;
        return false;
    }

    OtaDescriptor_t desc = {
        .magic      = OTA_MAGIC,
        .image_size = s_expected_size,
        .crc32      = s_expected_crc,
        .version    = s_pending_version,
        .pending    = 1,
    };
    if (!write_ota_descriptor(&desc)) {
        s_state = OTA_STATE_FAILED;
        return false;
    }

    s_state = OTA_STATE_READY;
    return true;
}

void OTA_Abort(void)
{
    flash_erase_bank2();
    s_state         = OTA_STATE_IDLE;
    s_written_bytes = 0;
}

OtaState_t OTA_GetState(void) { return s_state; }

uint32_t OTA_GetRunningVersion(void)
{
    const OtaDescriptor_t *desc = (const OtaDescriptor_t *)OTA_DESC_ADDR;
    if (desc->magic == OTA_MAGIC && !desc->pending) return desc->version;
    return 0;
}
