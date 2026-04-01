# Software Architecture Description — Bluetooth Communication Stack
## Document ID: SAD-BT-001-RevA

| Field              | Value                                              |
|--------------------|----------------------------------------------------|
| **Document Title** | Software Architecture Description — Bluetooth Communication Stack Firmware Module |
| **Document ID**    | SAD-BT-001-RevA                                    |
| **Module**         | BTSTACK-FW v1.0.0                                  |
| **Device**         | Class C Medical Device (Implantable / Wearable)    |
| **Software Safety Class** | Class C (IEC 62304:2006+AMD1:2015)          |
| **Prepared By**    | Software Engineering Lead                          |
| **Reviewed By**    | Software QA Engineer                               |
| **Approved By**    | VP Engineering                                     |
| **Approval Date**  | 2026-03-27                                         |
| **Revision**       | Rev A — Initial Release                            |
| **IEC 62304 Clause** | 5.3 — Software Architectural Design              |

---

## 1. Introduction

### 1.1 Purpose

This Software Architecture Description (SAD) defines the software architecture of the **BTSTACK-FW** module, decomposing it into two software items and specifying their interfaces. It satisfies IEC 62304:2006+AMD1:2015 clause **5.3 — Software Architectural Design**.

This document is the primary traceability link between:
- The requirements defined in **SRS-BT-001** (upstream).
- The detailed designs, unit tests (**UTP-BT-001**), and integration tests (**ITP-BT-001**) (downstream).

### 1.2 Scope

This SAD covers the internal architecture of BTSTACK-FW, comprising:
- **SI-01 (BT-LINK):** Bluetooth Link Layer Manager.
- **SI-02 (BT-GATT):** GATT Profile & Data Handler.

The architecture of the host application firmware and the BLE hardware controller are out of scope, but their interfaces to BTSTACK-FW are documented.

### 1.3 Applicable Documents

| Document ID     | Title                                              | Relationship |
|-----------------|----------------------------------------------------|--------------|
| **SDP-BT-001**  | Software Development Plan — BTSTACK-FW             | Parent plan  |
| **SRS-BT-001**  | Software Requirements Specification — BTSTACK-FW  | Requirements source |
| **UTP-BT-001**  | Unit Test Plan — BTSTACK-FW                        | Verification |
| **ITP-BT-001**  | Integration Plan — BTSTACK-FW                      | Verification |

---

## 2. Architecture Overview

### 2.1 Decomposition Rationale

BTSTACK-FW is decomposed into two software items based on protocol layer responsibilities aligned with the Bluetooth protocol stack architecture:

| Layer (Bottom-up) | Software Item | Responsibility |
|-------------------|---------------|---------------|
| Link Layer / Security | **SI-01 (BT-LINK)** | RF management, connection lifecycle, CRC, encryption |
| Attribute Protocol / GATT | **SI-02 (BT-GATT)** | Service/characteristic model, data routing to application |

This boundary is chosen because:
1. **Testability:** SI-01 can be unit-tested with a simulated HAL; SI-02 can be unit-tested against a simulated SI-01.
2. **Replaceability:** Either software item can be replaced or upgraded independently (e.g., upgrading SI-01 for Bluetooth 6.0 without changing SI-02).
3. **Traceability:** Security requirements (SR-004) and timing requirements (SR-001, SR-003) map cleanly to SI-01; data-path requirements (SR-002 application-side, SR-005 GATT events) map to SI-02.

### 2.2 Architecture Block Diagram

```
╔══════════════════════════════════════════════════════════════╗
║                    HOST APPLICATION                          ║
║            (outside BTSTACK-FW boundary)                     ║
║   btstack_init() │ btstack_connect() │ gatt_write/read()    ║
╚══════════════════╪══════════════════════════════════════════╝
                   │ Public API (Section 4.3 of SRS-BT-001)
                   │ Callback: bt_event_cb_t (SR-005)
╔══════════════════▼══════════════════════════════════════════╗
║             SI-02: BT-GATT (Section 4 of this document)     ║
║  ┌────────────────────────────────────────────────────────┐ ║
║  │ Service Registry │ Characteristic Handler │ ATT Engine │ ║
║  │ Notification Manager │ GATT Event Dispatcher          │ ║
║  └────────────────────────────────────────────────────────┘ ║
╚══════════════════╪══════════════════════════════════════════╝
                   │ Internal API: bt_link_api_t (Section 5)
╔══════════════════▼══════════════════════════════════════════╗
║             SI-01: BT-LINK (Section 3 of this document)     ║
║  ┌────────────────────────────────────────────────────────┐ ║
║  │ Connection Manager │ CRC Engine │ Watchdog Timer       │ ║
║  │ LESC Pairing Engine │ AES-128-CCM Crypto               │ ║
║  │ Event Logger (Ring Buffer)                             │ ║
║  └────────────────────────────────────────────────────────┘ ║
╚══════════════════╪══════════════════════════════════════════╝
                   │ HAL Interface (SRS-BT-001 §4.2)
╔══════════════════▼══════════════════════════════════════════╗
║         Hardware Abstraction Layer (HAL) / BSP              ║
║             BLE Radio Controller (HW)                       ║
╚════════════════════════════════════════════════════════════╝
```

---

## 3. Software Item SI-01: BT-LINK — Bluetooth Link Layer Manager

### 3.1 Identification

| Attribute         | Value |
|-------------------|-------|
| **Software Item ID** | SI-01 |
| **Name**          | BT-LINK |
| **Version**       | 1.0.0 |
| **Source Files**  | `src/bt_link.c`, `include/bt_link.h` |
| **Safety Class**  | Class C |

### 3.2 Responsibilities

SI-01 (BT-LINK) is the lower-layer software item responsible for all Bluetooth link management and security functions. Its responsibilities are:

1. **Connection Lifecycle Management (→ SR-001, SR-003)**
   - Initiates and manages BLE connection establishment via the HAL radio interface.
   - Implements the 5-second connection timeout (SR-001) using `hal_get_tick_ms()`.
   - Implements the 10-second supervision watchdog and exponential back-off reconnection strategy (SR-003).

2. **CRC Verification (→ SR-002)**
   - Validates CRC-32 on every incoming PDU before decrypting or forwarding.
   - Maintains a per-connection CRC error counter; enforces the threshold of 3 consecutive errors.
   - Logs `BT_WARN_CRC_FAIL` to the event ring buffer on each failure.

3. **LE Secure Connections Pairing and Encryption (→ SR-004)**
   - Implements LESC pairing state machine per Bluetooth Core Spec 5.3, Vol 3, Part H.
   - Rejects legacy pairing requests with reason code `0x05`.
   - Derives session keys using the LESC key agreement protocol; uses `hal_rng_get_bytes()` for entropy.
   - Encrypts outgoing PDUs and decrypts/verifies incoming PDUs using AES-128-CCM.
   - Verifies MIC on all received encrypted PDUs; discards and logs `BT_ERR_MIC_FAIL` on failure.

4. **Event Generation (→ SR-005)**
   - Generates `bt_event_t` events for all connection state changes and errors.
   - Dispatches events upward to SI-02 via the internal API (`bt_link_api_t`).
   - Ensures dispatch latency ≤ 100 ms from event detection to callback invocation.

5. **Event Ring Buffer**
   - Maintains a 32-entry circular ring buffer of `bt_log_entry_t` for diagnostic logging.
   - Does not block on ring buffer full — oldest entry overwritten (non-blocking design for RTOS safety).

### 3.3 Internal Sub-components

| Sub-component          | Description |
|------------------------|-------------|
| Connection Manager     | FSM with states: IDLE → SCANNING → CONNECTING → CONNECTED → RECONNECTING |
| CRC Engine             | CRC-32 implementation (table-driven, polynomial 0x04C11DB7) |
| Watchdog Timer         | Software timer using `hal_get_tick_ms()`, reset on each valid PDU receipt |
| LESC Pairing Engine    | LESC state machine: Key exchange → Confirm → Random → DHKey check |
| AES-128-CCM Crypto     | AES encryption/decryption using platform or software AES implementation |
| Event Logger           | Circular ring buffer, 32 entries, `bt_log_entry_t` struct |

### 3.4 State Machine — Connection Manager

```
     ┌──────────────────────────────────────────────────────────────┐
     │                                                              │
  IDLE ──btstack_connect()──► SCANNING ──PDU received──► CONNECTING│
   ▲                                                      │        │
   │ BT_ERR_CONN_LOST                                     │        │
   │ (3 reconnect attempts                               Connected  │
   │  exhausted)                                          │        │
   │                                                      ▼        │
   └─────────────────── RECONNECTING ◄──── CONNECTED ─────────────┘
         ▲                    │               │
         │        watchdog    │               │ btstack_disconnect()
         │        expiry      │               ▼
         └────────────────────┘             IDLE
```

### 3.5 Requirement Allocation to SI-01

| Requirement | Allocated | Addressed by Sub-component |
|-------------|-----------|---------------------------|
| SR-001      | Yes       | Connection Manager (5 s timer) |
| SR-002      | Yes       | CRC Engine (validate), Connection Manager (threshold) |
| SR-003      | Yes       | Watchdog Timer, Connection Manager (reconnect FSM) |
| SR-004      | Yes       | LESC Pairing Engine, AES-128-CCM Crypto |
| SR-005      | Yes       | Event Logger, Internal API dispatch |

---

## 4. Software Item SI-02: BT-GATT — GATT Profile & Data Handler

### 4.1 Identification

| Attribute         | Value |
|-------------------|-------|
| **Software Item ID** | SI-02 |
| **Name**          | BT-GATT |
| **Version**       | 1.0.0 |
| **Source Files**  | `src/bt_gatt.c`, `include/bt_gatt.h` |
| **Safety Class**  | Class C |

### 4.2 Responsibilities

SI-02 (BT-GATT) is the upper-layer software item responsible for GATT profile management and application data routing. Its responsibilities are:

1. **Service and Characteristic Registry (→ SR-002, SR-005)**
   - Maintains a static table of GATT services and characteristics registered at initialisation.
   - Routes incoming ATT read/write requests to the correct characteristic handler.

2. **Data Integrity Gate (→ SR-002)**
   - Acts as the final application-layer data integrity gate: only forwards payloads that have been validated by SI-01 (CRC passed and MIC verified).
   - Verifies that payload length matches the characteristic's declared maximum length; discards oversized payloads.

3. **Application Event Dispatch (→ SR-005)**
   - Translates raw SI-01 `bt_event_t` events into application-level `bt_gatt_event_t` events.
   - Invokes the registered `bt_event_cb_t` callback within the 100 ms latency budget (SR-005).
   - Guards against null callback pointer (SR-005 null-callback safety).

4. **GATT Notification and Indication Management**
   - Manages client characteristic configuration descriptor (CCCD) state per connected peer.
   - Sends notifications/indications for subscribed characteristics when `btstack_gatt_notify()` is called.

5. **Read/Write Operations (→ SR-005 BT_EVT_DATA_RECEIVED, BT_ERR_GATT_WRITE_FAIL)**
   - Handles `btstack_gatt_read()` by fetching from the local characteristic value store.
   - Handles `btstack_gatt_write()` by validating and writing to the characteristic value store, invoking the write handler callback if registered.

### 4.3 Internal Sub-components

| Sub-component              | Description |
|----------------------------|-------------|
| Service Registry           | Static array of `bt_service_t` with UUID, handle range, and characteristics |
| Characteristic Handler     | Per-characteristic read/write callback dispatch |
| ATT Engine                 | Minimal ATT protocol layer: PDU decode, handle lookup, response construction |
| Notification Manager       | CCCD state table, notification/indication queuing |
| GATT Event Dispatcher      | `bt_event_t` → `bt_gatt_event_t` translation, callback invocation, timing enforcement |

### 4.4 Requirement Allocation to SI-02

| Requirement | Allocated | Addressed by Sub-component |
|-------------|-----------|---------------------------|
| SR-001      | No        | (Handled entirely by SI-01) |
| SR-002      | Partial   | Characteristic Handler (payload length check, data gate) |
| SR-003      | No        | (Handled entirely by SI-01) |
| SR-004      | No        | (Handled entirely by SI-01) |
| SR-005      | Yes       | GATT Event Dispatcher (callback dispatch ≤ 100 ms) |

---

## 5. Inter-Item Interface Description

### 5.1 Internal API: `bt_link_api_t`

SI-02 communicates with SI-01 through the `bt_link_api_t` internal interface, defined in `include/bt_link_internal.h`. This interface is **not exposed** to the host application.

```c
/* bt_link_internal.h — Internal API between SI-01 and SI-02 */

typedef struct {
    /* Called by SI-01 to deliver a received, verified payload to SI-02 */
    void (*on_data_received)(bt_handle_t handle,
                             const uint8_t *payload,
                             uint16_t length);

    /* Called by SI-01 to deliver a connection/error event to SI-02 */
    void (*on_event)(bt_event_t event,
                     bt_handle_t handle,
                     uint32_t timestamp_ms);
} bt_link_callbacks_t;

/* SI-02 registers its callbacks with SI-01 at initialisation */
bt_status_t bt_link_register_callbacks(const bt_link_callbacks_t *cbs);

/* SI-02 calls SI-01 to send a PDU */
bt_status_t bt_link_send(bt_handle_t handle,
                         const uint8_t *payload,
                         uint16_t length);
```

### 5.2 Interface Constraints

| Constraint | Description |
|------------|-------------|
| **IC-001** | `bt_link_register_callbacks()` shall be called before `btstack_init()` returns to the host application; failure to do so is a programming error detected at init by assert. |
| **IC-002** | `on_data_received` shall only be called by SI-01 with payloads that have passed CRC and MIC verification (SR-002, SR-004). SI-02 shall not perform redundant CRC computation. |
| **IC-003** | `on_event` shall be called with an accurate `timestamp_ms` from `hal_get_tick_ms()`, not a zero or estimated value. |
| **IC-004** | The total latency from SI-01 event detection to SI-02 callback invocation of the registered host application callback shall be ≤ 100 ms (SR-005 requirement). |

### 5.3 External Interface: Host Application API

The host application calls the public API defined in `include/btstack.h` (see SRS-BT-001 §4.1). SI-02 is the primary handler for:
- `btstack_gatt_write()` / `btstack_gatt_read()`
- `bt_event_cb_t` callback registration and invocation

SI-01 is the primary handler for:
- `btstack_connect()` / `btstack_disconnect()`
- `btstack_init()` / `btstack_deinit()` (joint responsibility: SI-01 for radio, SI-02 for GATT state)

### 5.4 External Interface: HAL

SI-01 exclusively consumes the HAL interface (see SRS-BT-001 §4.2). SI-02 does not call the HAL directly. This constraint enforces the layered architecture and ensures SI-02 can be tested entirely without HAL.

---

## 6. Requirement-to-Architecture Traceability

The following table confirms that every requirement in **SRS-BT-001** is fully allocated to ≥ 1 software item, satisfying IEC 62304 §5.3.1.

| Requirement | Description (abbreviated)          | SI-01 (BT-LINK) | SI-02 (BT-GATT) | Unallocated? |
|-------------|------------------------------------|:---------------:|:---------------:|:------------:|
| SR-001      | Connection establishment ≤ 5 s     | ✓ Primary       | —               | No           |
| SR-002      | CRC-32 data integrity              | ✓ Primary       | ✓ Partial gate  | No           |
| SR-003      | Watchdog + reconnection            | ✓ Primary       | —               | No           |
| SR-004      | LESC + AES-128-CCM                 | ✓ Primary       | —               | No           |
| SR-005      | Error callback ≤ 100 ms            | ✓ Events source | ✓ Dispatcher    | No           |

**Finding:** All 5 requirements are fully allocated. No requirement is unallocated. Architecture review complete.

---

## 7. Safety and Security Considerations

### 7.1 Safety-Critical Paths

The following data flows are identified as safety-critical and subject to heightened scrutiny during code review and testing:

| Path | SI Involved | Hazard (from ICD-DHF-SUP-001) | Mitigated by |
|------|-------------|-------------------------------|--------------|
| Connection timeout → callback | SI-01 | H-BT-001 (loss of comms) | SR-001, SR-003, SR-005 |
| CRC failure → threshold → disconnect | SI-01 | H-BT-002 (data corruption) | SR-002 |
| Legacy pairing rejection | SI-01 | H-BT-003 (unauthorized access) | SR-004 |
| MIC failure → discard | SI-01 | H-BT-003 | SR-004 |
| Null callback guard | SI-02 | H-BT-004 (silent failure) | SR-005 |

### 7.2 Memory Safety

- SI-01 and SI-02 shall not use dynamic heap allocation (`malloc`/`free`). All buffers are statically allocated.
- The event ring buffer in SI-01 uses index masking (not modulo) for overflow protection.
- All public API inputs are validated for null pointer and length bounds before use.

### 7.3 Stack Usage

Stack usage for SI-01 and SI-02 shall be measured during unit testing and reported in the Unit Test Report (UTR-BT-001). Maximum stack depth shall not exceed the HAL-specified safe stack limit.

---

## 8. Architecture Review Record

| Reviewer               | Role                    | Date       | Finding |
|------------------------|-------------------------|------------|---------|
| [Software QA Engineer] | Architecture review     | 2026-03-27 | Decomposition adequate; all requirements allocated; interfaces well-defined. |
| [Systems Engineer]     | Traceability check      | 2026-03-27 | §6 matrix verified complete. |
| [VP Engineering]       | Approval                | 2026-03-27 | Approved. |

---

*End of SAD-BT-001-RevA*
