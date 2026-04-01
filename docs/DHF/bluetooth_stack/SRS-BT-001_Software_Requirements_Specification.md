# Software Requirements Specification — Bluetooth Communication Stack
## Document ID: SRS-BT-001-RevA

| Field              | Value                                              |
|--------------------|----------------------------------------------------|
| **Document Title** | Software Requirements Specification — Bluetooth Communication Stack Firmware Module |
| **Document ID**    | SRS-BT-001-RevA                                    |
| **Module**         | BTSTACK-FW v1.0.0                                  |
| **Device**         | Class C Medical Device (Implantable / Wearable)    |
| **Software Safety Class** | Class C (IEC 62304:2006+AMD1:2015)          |
| **Prepared By**    | Software Engineering Lead                          |
| **Reviewed By**    | Software QA Engineer                               |
| **Approved By**    | VP Engineering                                     |
| **Approval Date**  | 2026-03-27                                         |
| **Revision**       | Rev A — Initial Release                            |
| **IEC 62304 Clause** | 5.2 — Software Requirements Analysis             |

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification (SRS) defines the verifiable software requirements for the **BTSTACK-FW** Bluetooth Communication Stack Firmware module. It serves as:
- The primary input to architectural design (→ **SAD-BT-001**).
- The traceability anchor for unit tests (→ **UTP-BT-001**) and integration tests (→ **ITP-BT-001**).
- A record of requirements reviewed under IEC 62304:2006+AMD1:2015 clause 5.2.

### 1.2 Scope

The requirements herein govern all software behaviour of BTSTACK-FW in its two constituent software items:
- **SI-01 (BT-LINK):** Bluetooth Link Layer Manager — described in **SAD-BT-001 §3**.
- **SI-02 (BT-GATT):** GATT Profile & Data Handler — described in **SAD-BT-001 §4**.

### 1.3 Applicable Documents

| Document ID     | Title                                              | Relationship |
|-----------------|----------------------------------------------------|--------------|
| **SDP-BT-001**  | Software Development Plan — BTSTACK-FW             | Parent plan  |
| **SAD-BT-001**  | Software Architecture Description — BTSTACK-FW    | Allocation target |
| **UTP-BT-001**  | Unit Test Plan — BTSTACK-FW                        | Verification |
| **ITP-BT-001**  | Integration Plan — BTSTACK-FW                      | Verification |
| ICD-DHF-DI-001  | Device-Level Design Input Requirements Spec        | Source       |
| ICD-DHF-SUP-001 | ISO 14971 Risk Management File Index               | Risk input   |
| Bluetooth Core Spec 5.3 | Bluetooth SIG Core Specification         | Technical standard |

---

## 2. System Overview

### 2.1 Product Context

The BTSTACK-FW module is an embedded firmware component operating on the device's Bluetooth subsystem microcontroller. It provides bidirectional BLE communication between the medical device and an authorized external host (clinician programmer or patient monitoring system). The module interfaces with:

```
┌──────────────────────────────────────────────────────┐
│                  HOST APPLICATION                    │
│         (Device Firmware — not in scope)             │
└────────────────────┬─────────────────────────────────┘
                     │ Callback API (SR-005)
┌────────────────────▼─────────────────────────────────┐
│              SI-02: BT-GATT                          │
│         GATT Profile & Data Handler                  │
└────────────────────┬─────────────────────────────────┘
                     │ Internal API (SAD-BT-001 §5)
┌────────────────────▼─────────────────────────────────┐
│              SI-01: BT-LINK                          │
│         Bluetooth Link Layer Manager                 │
└────────────────────┬─────────────────────────────────┘
                     │ Hardware Abstraction Layer (HAL)
┌────────────────────▼─────────────────────────────────┐
│              BLE RF Hardware                         │
│         (Bluetooth 5.3 Radio Controller)             │
└──────────────────────────────────────────────────────┘
```

### 2.2 Assumptions and Constraints

| ID     | Assumption / Constraint |
|--------|------------------------|
| AC-001 | The host device operates in the 2.4 GHz ISM band; radio frequency management is handled by SI-01. |
| AC-002 | The host application registers exactly one error callback before calling `btstack_init()`. |
| AC-003 | All BLE operations are restricted to Bluetooth LE (no Classic Bluetooth). |
| AC-004 | The system clock accuracy is ≤ ±50 ppm to support BLE connection interval requirements. |
| AC-005 | The hardware provides a hardware security module (HSM) or equivalent entropy source for key generation (SR-004). |

---

## 3. Software Requirements

All requirements are stated in the form: **"The BTSTACK-FW [condition] shall [action/constraint]."**

Each requirement carries:
- **Unique ID** — traceable through all downstream documents.
- **Safety Class** — all requirements are Class C.
- **Risk Reference** — links to ISO 14971 risk assessment in `ICD-DHF-SUP-001`.
- **Verification Method** — unit test (UTP-BT-001), integration test (ITP-BT-001), or review.
- **Allocated SI** — the software item(s) responsible (from **SAD-BT-001**).

---

### SR-001 — Connection Establishment Timing

| Field                | Value |
|----------------------|-------|
| **Requirement ID**   | SR-001 |
| **Title**            | BLE Connection Establishment Within Specified Timeout |
| **Safety Class**     | Class C |
| **Risk Reference**   | ICD-DHF-SUP-001 Hazard H-BT-001 (Loss of Communication) |
| **Priority**         | Critical |
| **Allocated SI**     | **SI-01 (BT-LINK)** |

**Requirement Text:**

> The BTSTACK-FW shall establish a valid BLE connection with an authorized paired host device within **5 seconds** of the connection procedure being initiated via the `btstack_connect()` API call, under the following conditions:
> - The host device is within RF range (RSSI ≥ −85 dBm).
> - The host device is advertising or scanning.
> - No active connection already exists.
>
> If connection is not established within 5 seconds, BTSTACK-FW shall invoke the registered error callback (see SR-005) with error code `BT_ERR_CONN_TIMEOUT` and reset to the idle state.

**Rationale:** Timely connection establishment is required to ensure the clinician programmer can communicate with the device during a patient consultation. A 5-second timeout aligns with clinical workflow expectations and prevents indefinite blocking of the host application.

**Verification:**
- Unit test: **UTP-BT-001 TC-LINK-001** (nominal connection), **TC-LINK-002** (timeout condition).
- Integration test: **ITP-BT-001 TC-INT-001**.

---

### SR-002 — Data Integrity via CRC Validation

| Field                | Value |
|----------------------|-------|
| **Requirement ID**   | SR-002 |
| **Title**            | CRC-32 Data Integrity Verification on All Received Packets |
| **Safety Class**     | Class C |
| **Risk Reference**   | ICD-DHF-SUP-001 Hazard H-BT-002 (Data Corruption) |
| **Priority**         | Critical |
| **Allocated SI**     | **SI-01 (BT-LINK)**, **SI-02 (BT-GATT)** |

**Requirement Text:**

> The BTSTACK-FW shall validate the integrity of every received BLE data packet using **CRC-32** (polynomial 0x04C11DB7, initial value 0xFFFFFFFF) before passing packet payload to SI-02 (BT-GATT).
>
> Upon detection of a CRC mismatch:
> 1. The packet shall be **discarded** without delivering payload to the application layer.
> 2. A `BT_WARN_CRC_FAIL` event shall be logged to the internal event ring buffer.
> 3. If ≥ **3 consecutive** CRC errors are detected on the same connection handle, BTSTACK-FW shall invoke the registered error callback with error code `BT_ERR_DATA_INTEGRITY` and terminate the connection.

**Rationale:** Corrupt data delivered to the host application could result in incorrect device configuration or false status readings, constituting a direct patient safety risk.

**Verification:**
- Unit test: **UTP-BT-001 TC-LINK-003** (single CRC error), **TC-LINK-004** (consecutive CRC threshold).
- Unit test: **UTP-BT-001 TC-GATT-001** (no corrupt payload forwarded to application).
- Integration test: **ITP-BT-001 TC-INT-003**.

---

### SR-003 — Connection Watchdog and Reconnection

| Field                | Value |
|----------------------|-------|
| **Requirement ID**   | SR-003 |
| **Title**            | Connection Loss Detection and Supervised Reconnection |
| **Safety Class**     | Class C |
| **Risk Reference**   | ICD-DHF-SUP-001 Hazard H-BT-001 (Loss of Communication) |
| **Priority**         | High |
| **Allocated SI**     | **SI-01 (BT-LINK)** |

**Requirement Text:**

> The BTSTACK-FW shall implement a connection supervision watchdog timer. The watchdog shall expire if no valid BLE packet (data or empty PDU) is received from the connected host within a **10-second** supervision window.
>
> Upon watchdog expiry:
> 1. BTSTACK-FW shall log a `BT_WARN_SUPERVISION_TIMEOUT` event.
> 2. BTSTACK-FW shall autonomously attempt to re-establish the connection, up to a maximum of **3 consecutive reconnection attempts**.
> 3. Each reconnection attempt shall be separated by an exponential back-off interval starting at **1 second**, doubling per attempt (1 s, 2 s, 4 s).
> 4. If all 3 attempts fail, BTSTACK-FW shall invoke the error callback with `BT_ERR_CONN_LOST` and enter the **disconnected idle** state.
>
> The reconnection attempt counter shall reset to zero upon successful connection establishment.

**Rationale:** Temporary RF interference or brief patient movement must not cause permanent loss of communication. Supervised reconnection with exponential back-off reduces RF congestion while ensuring eventual failure reporting.

**Verification:**
- Unit test: **UTP-BT-001 TC-LINK-005** (watchdog nominal fire), **TC-LINK-006** (reconnect success within 3 attempts), **TC-LINK-007** (all 3 attempts exhausted).
- Integration test: **ITP-BT-001 TC-INT-004**.

---

### SR-004 — BLE Security: LE Secure Connections with AES-128-CCM Encryption

| Field                | Value |
|----------------------|-------|
| **Requirement ID**   | SR-004 |
| **Title**            | LE Secure Connections Pairing and AES-128-CCM Encryption Enforcement |
| **Safety Class**     | Class C |
| **Risk Reference**   | ICD-DHF-SUP-001 Hazard H-BT-003 (Unauthorized Access / Command Injection) |
| **Priority**         | Critical |
| **Allocated SI**     | **SI-01 (BT-LINK)** |

**Requirement Text:**

> The BTSTACK-FW shall enforce **LE Secure Connections (LESC)** pairing as defined in Bluetooth Core Specification 5.3, Volume 3, Part H, Section 2.3.5, for all BLE connections carrying application data.
>
> Specifically:
> 1. BTSTACK-FW shall **reject** any pairing request that does not use LESC (i.e., LE Legacy Pairing requests shall be refused with pairing failed reason `0x05 — Authentication Requirements`).
> 2. All application data exchanged over an established connection shall be encrypted using **AES-128-CCM** with session keys derived from the LESC pairing procedure.
> 3. BTSTACK-FW shall verify the **Message Integrity Check (MIC)** on every received encrypted PDU and shall discard any PDU with a failed MIC, logging `BT_ERR_MIC_FAIL`.
> 4. Session keys shall not be stored in non-volatile memory; key derivation shall be re-executed on each pairing.

**Rationale:** Legacy BLE pairing is vulnerable to passive eavesdropping and MITM attacks. LESC with Numeric Comparison or Out-of-Band (OOB) ensures mutual authentication and forward secrecy, preventing adversarial command injection into the medical device.

**Verification:**
- Unit test: **UTP-BT-001 TC-LINK-008** (LESC pairing accepted), **TC-LINK-009** (legacy pairing rejected).
- Integration test: **ITP-BT-001 TC-INT-005** (end-to-end encrypted data exchange).
- Review: Security review against Bluetooth Core Spec 5.3.

---

### SR-005 — Error Reporting to Application Layer

| Field                | Value |
|----------------------|-------|
| **Requirement ID**   | SR-005 |
| **Title**            | Protocol Error and Connection State Change Reporting via Registered Callback |
| **Safety Class**     | Class C |
| **Risk Reference**   | ICD-DHF-SUP-001 Hazard H-BT-004 (Silent Failure — No Error Reported to Application) |
| **Priority**         | Critical |
| **Allocated SI**     | **SI-01 (BT-LINK)**, **SI-02 (BT-GATT)** |

**Requirement Text:**

> The BTSTACK-FW shall deliver all protocol errors and connection state changes to the host application via the registered error/event callback function within **100 milliseconds** of the event being detected internally.
>
> The callback shall provide:
> - An **event code** from the enumerated type `bt_event_t` (see API reference in SAD-BT-001 §5).
> - A **connection handle** identifying the affected connection (or `BT_HANDLE_NONE` if no connection).
> - An **event timestamp** in milliseconds since boot (32-bit, wraps at ~49 days).
>
> The following event codes shall be defined and reported as applicable:
>
> | Event Code              | Trigger Condition |
> |-------------------------|-------------------|
> | `BT_EVT_CONNECTED`      | BLE connection established (SI-01) |
> | `BT_EVT_DISCONNECTED`   | BLE connection terminated by either party (SI-01) |
> | `BT_ERR_CONN_TIMEOUT`   | Connection attempt timed out (SR-001) |
> | `BT_ERR_CONN_LOST`      | Connection lost after all reconnect attempts (SR-003) |
> | `BT_ERR_DATA_INTEGRITY` | CRC error threshold exceeded (SR-002) |
> | `BT_ERR_MIC_FAIL`       | AES-CCM MIC verification failure (SR-004) |
> | `BT_EVT_PAIRING_COMPLETE` | LESC pairing successfully completed (SR-004) |
> | `BT_ERR_PAIRING_FAILED` | Pairing failed — reason code included in payload (SR-004) |
> | `BT_EVT_DATA_RECEIVED`  | Application data successfully received (SI-02) |
> | `BT_ERR_GATT_WRITE_FAIL` | GATT write operation failed (SI-02) |
>
> If no callback has been registered at the time an event occurs, BTSTACK-FW shall log the event to the internal event ring buffer and shall not produce a null-pointer dereference.

**Rationale:** The host application must be immediately informed of all safety-relevant communication failures so that it can initiate safe-state transitions (e.g., display alert to clinician, log event to device audit trail). Silent failures are classified as a critical hazard.

**Verification:**
- Unit test: **UTP-BT-001 TC-LINK-010** (callback timing ≤ 100 ms), **TC-GATT-004** (GATT event delivery).
- Unit test: **UTP-BT-001 TC-LINK-011** (null callback — no crash).
- Integration test: **ITP-BT-001 TC-INT-006** (end-to-end event delivery from SI-01 through SI-02 to application).

---

## 4. External Interface Requirements

### 4.1 API Interface to Host Application

The BTSTACK-FW module exposes the following public C API to the host application firmware:

```c
/* Initialization */
bt_status_t btstack_init(bt_config_t *config, bt_event_cb_t callback);
bt_status_t btstack_deinit(void);

/* Connection control */
bt_status_t btstack_connect(bt_addr_t *peer_addr);
bt_status_t btstack_disconnect(bt_handle_t conn_handle);

/* Data transfer (via SI-02 BT-GATT) */
bt_status_t btstack_gatt_write(bt_handle_t conn_handle,
                               uint16_t char_uuid,
                               const uint8_t *data,
                               uint16_t length);
bt_status_t btstack_gatt_read(bt_handle_t conn_handle,
                              uint16_t char_uuid,
                              uint8_t *buf,
                              uint16_t *length);
```

### 4.2 Hardware Abstraction Layer Interface

SI-01 (BT-LINK) consumes the following HAL interface provided by the platform BSP:

```c
/* HAL functions consumed by SI-01 */
hal_status_t hal_ble_radio_init(hal_ble_config_t *cfg);
hal_status_t hal_ble_tx(const uint8_t *pdu, uint16_t len);
hal_status_t hal_ble_rx_register_callback(hal_ble_rx_cb_t cb);
uint32_t     hal_get_tick_ms(void);      /* For watchdog/timeout SR-003 */
hal_status_t hal_rng_get_bytes(uint8_t *buf, uint16_t len); /* For SR-004 key derivation */
```

---

## 5. Requirements Attributes Summary

| ID      | Title (abbreviated)             | Safety Class | Priority  | Allocated SI        | Verification          |
|---------|---------------------------------|--------------|-----------|---------------------|-----------------------|
| SR-001  | Connection establishment timing | Class C      | Critical  | SI-01               | TC-LINK-001,002 / TC-INT-001 |
| SR-002  | CRC-32 data integrity           | Class C      | Critical  | SI-01, SI-02        | TC-LINK-003,004 / TC-INT-003 |
| SR-003  | Connection watchdog & reconnect | Class C      | High      | SI-01               | TC-LINK-005,006,007 / TC-INT-004 |
| SR-004  | LESC + AES-128-CCM security     | Class C      | Critical  | SI-01               | TC-LINK-008,009 / TC-INT-005 |
| SR-005  | Error callback ≤ 100 ms         | Class C      | Critical  | SI-01, SI-02        | TC-LINK-010,011 / TC-INT-006 |

---

## 6. Traceability Matrix

### 6.1 System Requirement → Software Requirement

| Device System Req | BTSTACK-FW Software Req |
|-------------------|------------------------|
| SYS-COMM-001 (Establish wireless link) | SR-001, SR-003 |
| SYS-COMM-002 (Ensure data integrity) | SR-002 |
| SYS-COMM-003 (Encrypt all transmissions) | SR-004 |
| SYS-COMM-004 (Fault notification) | SR-005 |
| SYS-COMM-005 (Reject unauthorized connections) | SR-004 |

### 6.2 Software Requirement → Software Item → Test

| Req    | Allocated Software Item       | Unit Test Cases (UTP-BT-001)         | Integration Test Cases (ITP-BT-001) |
|--------|-------------------------------|--------------------------------------|-------------------------------------|
| SR-001 | SI-01 (BT-LINK)               | TC-LINK-001, TC-LINK-002             | TC-INT-001                          |
| SR-002 | SI-01 (BT-LINK), SI-02 (BT-GATT) | TC-LINK-003, TC-LINK-004, TC-GATT-001 | TC-INT-003                       |
| SR-003 | SI-01 (BT-LINK)               | TC-LINK-005, TC-LINK-006, TC-LINK-007 | TC-INT-004                         |
| SR-004 | SI-01 (BT-LINK)               | TC-LINK-008, TC-LINK-009             | TC-INT-005                          |
| SR-005 | SI-01 (BT-LINK), SI-02 (BT-GATT) | TC-LINK-010, TC-LINK-011, TC-GATT-004 | TC-INT-006                       |

> **Note:** This traceability matrix is the master traceability record for BTSTACK-FW. Any requirement added, removed, or modified shall trigger an impact assessment across all downstream documents (SAD-BT-001, UTP-BT-001, ITP-BT-001) per the change control process defined in **SDP-BT-001 §6**.

---

## 7. Requirements Review Record

| Reviewer               | Role                    | Date       | Finding Summary |
|------------------------|-------------------------|------------|-----------------|
| [Software QA Engineer] | Reviewer                | 2026-03-27 | All 5 requirements verified as complete, unambiguous, and testable. |
| [Systems Engineer]     | Allocations review      | 2026-03-27 | All requirements allocated to ≥ 1 software item. Traceability §6.1 verified. |
| [VP Engineering]       | Approver                | 2026-03-27 | Approved — no open actions. |

---

*End of SRS-BT-001-RevA*
