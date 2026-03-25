/**
 * @file gps_parser.c
 * @brief NMEA 0183 sentence parser implementation.
 */

#include "gps_parser.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <ctype.h>

/* -------------------------------------------------------------------------
 * Private helpers
 * ---------------------------------------------------------------------- */

/** Split sentence into fields by comma. Returns field count. */
static int _split_fields(const char *sentence,
                          char fields[][32],
                          int max_fields)
{
    int  count = 0;
    int  i     = 0;
    int  fi    = 0;

    while (sentence[i] != '\0' && count < max_fields) {
        if (sentence[i] == ',' || sentence[i] == '*') {
            fields[count][fi] = '\0';
            count++;
            fi = 0;
            if (sentence[i] == '*') break;
        } else {
            if (fi < 31) {
                fields[count][fi++] = sentence[i];
            }
        }
        i++;
    }
    if (fi > 0 && count < max_fields) {
        fields[count][fi] = '\0';
        count++;
    }
    return count;
}

static uint8_t _hex_to_byte(char c)
{
    if (c >= '0' && c <= '9') return (uint8_t)(c - '0');
    if (c >= 'A' && c <= 'F') return (uint8_t)(c - 'A' + 10);
    if (c >= 'a' && c <= 'f') return (uint8_t)(c - 'a' + 10);
    return 0xFF; /* invalid */
}

/* -------------------------------------------------------------------------
 * Public API
 * ---------------------------------------------------------------------- */

bool gps_validate_checksum(const char *sentence)
{
    if (sentence == NULL || sentence[0] != '$') return false;

    const char *star = strchr(sentence, '*');
    if (star == NULL || *(star + 1) == '\0' || *(star + 2) == '\0') {
        return false;
    }

    uint8_t hi = _hex_to_byte(*(star + 1));
    uint8_t lo = _hex_to_byte(*(star + 2));
    if (hi == 0xFF || lo == 0xFF) return false;

    uint8_t expected = (uint8_t)((hi << 4) | lo);
    uint8_t computed = 0;

    for (const char *p = sentence + 1; *p != '*' && *p != '\0'; p++) {
        computed ^= (uint8_t)*p;
    }
    return computed == expected;
}

double gps_nmea_to_decimal(double nmea_val, char hemisphere)
{
    if (isnan(nmea_val)) return NAN;
    int    deg      = (int)(nmea_val / 100.0);
    double minutes  = nmea_val - (double)(deg * 100);
    double decimal  = (double)deg + minutes / 60.0;
    if (hemisphere == 'S' || hemisphere == 'W') decimal = -decimal;
    return decimal;
}

GPSParseError gps_parse_gprmc(const char *sentence, GPSFix *out)
{
    if (sentence == NULL) return GPS_ERR_NULL_INPUT;
    if (out      == NULL) return GPS_ERR_NULL_INPUT;
    if (sentence[0] == '\0') return GPS_ERR_EMPTY;
    if (strlen(sentence) > GPS_SENTENCE_MAX_LEN) return GPS_ERR_SENTENCE_TOO_LONG;
    if (!gps_validate_checksum(sentence)) return GPS_ERR_BAD_CHECKSUM;

    char fields[GPS_MAX_FIELDS][32];
    memset(fields, 0, sizeof(fields));
    int count = _split_fields(sentence, fields, GPS_MAX_FIELDS);

    if (count < 10) return GPS_ERR_INSUFFICIENT_FIELDS;
    if (strncmp(fields[0], "$GPRMC", 6) != 0) return GPS_ERR_UNKNOWN_SENTENCE;

    /* Field 1: time HHMMSS.ss */
    if (strlen(fields[1]) >= 6) {
        char tmp[3] = {0};
        tmp[0] = fields[1][0]; tmp[1] = fields[1][1];
        out->hour   = (uint8_t)atoi(tmp);
        tmp[0] = fields[1][2]; tmp[1] = fields[1][3];
        out->minute = (uint8_t)atoi(tmp);
        tmp[0] = fields[1][4]; tmp[1] = fields[1][5];
        out->second = (uint8_t)atoi(tmp);
    } else {
        return GPS_ERR_INVALID_TIME;
    }

    /* Field 2: status A=valid V=void */
    out->fix_valid = (fields[2][0] == 'A');

    /* Fields 3-6: lat/lon */
    if (strlen(fields[3]) > 0 && strlen(fields[4]) > 0) {
        double raw_lat = atof(fields[3]);
        out->latitude = gps_nmea_to_decimal(raw_lat, fields[4][0]);
    } else {
        out->latitude = 0.0;
    }
    if (strlen(fields[5]) > 0 && strlen(fields[6]) > 0) {
        double raw_lon = atof(fields[5]);
        out->longitude = gps_nmea_to_decimal(raw_lon, fields[6][0]);
    } else {
        out->longitude = 0.0;
    }

    /* Field 7: speed knots */
    out->speed_knots = (strlen(fields[7]) > 0) ? (float)atof(fields[7]) : 0.0f;

    /* Field 8: course */
    out->course_deg = (strlen(fields[8]) > 0) ? (float)atof(fields[8]) : 0.0f;

    /* Field 9: date DDMMYY */
    if (strlen(fields[9]) >= 6) {
        char tmp[5] = {0};
        tmp[0] = fields[9][0]; tmp[1] = fields[9][1];
        out->day   = (uint8_t)atoi(tmp);
        tmp[0] = fields[9][2]; tmp[1] = fields[9][3];
        out->month = (uint8_t)atoi(tmp);
        tmp[0] = fields[9][4]; tmp[1] = fields[9][5];
        out->year  = (uint16_t)(2000 + atoi(tmp));
    }

    return GPS_OK;
}

GPSParseError gps_parse_gpgga(const char *sentence, GPSFix *out)
{
    if (sentence == NULL) return GPS_ERR_NULL_INPUT;
    if (out      == NULL) return GPS_ERR_NULL_INPUT;
    if (sentence[0] == '\0') return GPS_ERR_EMPTY;
    if (strlen(sentence) > GPS_SENTENCE_MAX_LEN) return GPS_ERR_SENTENCE_TOO_LONG;
    if (!gps_validate_checksum(sentence)) return GPS_ERR_BAD_CHECKSUM;

    char fields[GPS_MAX_FIELDS][32];
    memset(fields, 0, sizeof(fields));
    int count = _split_fields(sentence, fields, GPS_MAX_FIELDS);

    if (count < 10) return GPS_ERR_INSUFFICIENT_FIELDS;
    if (strncmp(fields[0], "$GPGGA", 6) != 0) return GPS_ERR_UNKNOWN_SENTENCE;

    /* Field 1: time */
    if (strlen(fields[1]) >= 6) {
        char tmp[3] = {0};
        tmp[0] = fields[1][0]; tmp[1] = fields[1][1];
        out->hour   = (uint8_t)atoi(tmp);
        tmp[0] = fields[1][2]; tmp[1] = fields[1][3];
        out->minute = (uint8_t)atoi(tmp);
        tmp[0] = fields[1][4]; tmp[1] = fields[1][5];
        out->second = (uint8_t)atoi(tmp);
    }

    /* Fields 2-5: lat/lon */
    if (strlen(fields[2]) > 0 && strlen(fields[3]) > 0) {
        double raw_lat = atof(fields[2]);
        out->latitude = gps_nmea_to_decimal(raw_lat, fields[3][0]);
    }
    if (strlen(fields[4]) > 0 && strlen(fields[5]) > 0) {
        double raw_lon = atof(fields[4]);
        out->longitude = gps_nmea_to_decimal(raw_lon, fields[5][0]);
    }

    /* Field 6: fix quality 0=none, 1=GPS, 2=DGPS */
    out->fix_quality = (uint8_t)atoi(fields[6]);
    out->fix_valid   = out->fix_quality > 0;

    /* Field 7: satellites */
    out->satellites = (uint8_t)atoi(fields[7]);

    /* Field 8: HDOP */
    out->hdop = (strlen(fields[8]) > 0) ? (float)atof(fields[8]) : 99.9f;

    /* Field 9: altitude */
    out->altitude_m = (strlen(fields[9]) > 0) ? (float)atof(fields[9]) : 0.0f;

    return GPS_OK;
}

GPSParseError gps_parse_sentence(const char *sentence, GPSFix *out)
{
    if (sentence == NULL) return GPS_ERR_NULL_INPUT;
    if (sentence[0] == '\0') return GPS_ERR_EMPTY;
    if (sentence[0] != '$') return GPS_ERR_NO_DOLLAR;
    if (strlen(sentence) > GPS_SENTENCE_MAX_LEN) return GPS_ERR_SENTENCE_TOO_LONG;

    if (strncmp(sentence + 1, "GPRMC", 5) == 0) {
        return gps_parse_gprmc(sentence, out);
    }
    if (strncmp(sentence + 1, "GPGGA", 5) == 0) {
        return gps_parse_gpgga(sentence, out);
    }
    return GPS_ERR_UNKNOWN_SENTENCE;
}
