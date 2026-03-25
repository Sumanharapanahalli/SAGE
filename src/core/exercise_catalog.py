"""
SAGE Framework — Exercise Catalog
====================================
Scalable exercise generation system for Agent Gym.

Architecture:
  Seed exercises (hand-crafted, ~50-100 per domain)
      ↓
  Template engine (LLM generates variants from seeds)
      ↓
  Variant exercises (~200 per seed = 10,000+ per domain)
      ↓
  Difficulty auto-calibration (agent success rate determines true difficulty)
      ↓
  Prerequisite graph (exercise B requires mastering exercise A)

Exercise sources:
  1. Runner-defined exercises (get_exercises) — hardcoded, always available
  2. Skill YAML catalogs — seed exercises shipped with skills
  3. Generated variants — LLM-expanded from seeds
  4. Community-contributed — loaded from SAGE_EXERCISES_DIR

Thread-safe. SQLite-backed. Domain-agnostic orchestration with domain-specific seeds.
"""

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import yaml

logger = logging.getLogger("ExerciseCatalog")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Exercise:
    """A single training exercise for the Agent Gym."""
    id: str
    domain: str          # runner name (openfw, openswe, openml, etc.)
    skill: str           # skill name from skill YAML
    title: str
    description: str     # full exercise prompt — what the agent must do
    difficulty: str      # beginner, intermediate, advanced, expert
    tags: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    context: str = ""    # setup info, background, constraints
    task_type: str = ""  # maps to runner task types
    time_limit: int = 300  # seconds
    prerequisites: list[str] = field(default_factory=list)  # exercise IDs that must be mastered first
    seed_id: str = ""    # if this is a variant, the seed exercise it was generated from
    variant_axis: str = ""  # what dimension this variant explores (e.g., "platform", "concurrency")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "skill": self.skill,
            "title": self.title,
            "description": self.description[:500] + ("..." if len(self.description) > 500 else ""),
            "difficulty": self.difficulty,
            "tags": self.tags,
            "acceptance_criteria": self.acceptance_criteria,
            "task_type": self.task_type,
            "time_limit": self.time_limit,
            "prerequisites": self.prerequisites,
            "seed_id": self.seed_id,
            "variant_axis": self.variant_axis,
        }


# ---------------------------------------------------------------------------
# Seed catalog definitions — per domain
# Each domain has ~50-100 seed exercises organized by difficulty
# ---------------------------------------------------------------------------

# Variant axes: dimensions along which exercises can be expanded
VARIANT_AXES = {
    "openfw": [
        "platform", "rtos", "peripheral", "optimization", "safety",
        "concurrency", "power_management", "communication_protocol",
        "memory_constraint", "error_recovery",
    ],
    "openswe": [
        "language", "framework", "scale", "pattern", "testing",
        "concurrency", "api_design", "database", "security", "performance",
    ],
    "openml": [
        "dataset_size", "model_type", "metric", "feature_engineering",
        "deployment", "monitoring", "fairness", "interpretability",
        "pipeline_stage", "domain_application",
    ],
    "openeda": [
        "layer_count", "signal_integrity", "power_delivery", "thermal",
        "component_density", "manufacturing_constraint", "emc_compliance",
        "impedance_matching", "via_strategy", "bom_optimization",
    ],
    "opensim": [
        "simulation_type", "clock_domain", "power_rail", "timing_constraint",
        "noise_analysis", "corner_case", "temperature_range",
        "process_variation", "testbench_complexity", "verification_method",
    ],
    "opendoc": [
        "document_type", "regulatory_standard", "audience", "compliance_level",
        "cross_reference", "traceability", "revision_control",
        "template_format", "review_stage", "localization",
    ],
    "opendesign": [
        "accessibility_level", "viewport", "interaction_pattern", "branding",
        "design_system", "animation", "dark_mode", "rtl_support",
        "component_complexity", "user_flow",
    ],
    "openstrategy": [
        "market_size", "competition_level", "go_to_market", "pricing_model",
        "customer_segment", "regulatory_environment", "geographic_scope",
        "technology_readiness", "team_size", "funding_stage",
    ],
}


def _generate_seed_catalog() -> dict[str, list[dict]]:
    """
    Generate comprehensive seed exercise catalog — ~100 seeds per domain.

    Each seed is a template that can spawn hundreds of variants.
    Seeds are organized by difficulty tier within each domain.
    """
    catalog = {}

    # ── OpenFW (Firmware Engineering) ────────────────────────────────
    catalog["openfw"] = [
        # Beginner (20 seeds)
        {"title": "LED blink timer", "difficulty": "beginner", "tags": ["gpio", "timer", "basics"],
         "description": "Implement a timer-driven LED blink pattern on GPIO. Toggle an LED at 1Hz using a hardware timer interrupt, not a delay loop. Include proper timer initialization and ISR.",
         "acceptance_criteria": ["Timer ISR implemented", "No busy-wait loop", "LED toggles at correct frequency"],
         "task_type": "firmware_implementation"},
        {"title": "UART echo", "difficulty": "beginner", "tags": ["uart", "serial", "basics"],
         "description": "Implement UART receive and transmit. Echo received characters back with case inversion. Handle buffer overflow gracefully.",
         "acceptance_criteria": ["UART init correct", "Echo works", "Buffer overflow handled"],
         "task_type": "firmware_implementation"},
        {"title": "GPIO debounce", "difficulty": "beginner", "tags": ["gpio", "debounce", "input"],
         "description": "Implement software debouncing for a mechanical button on GPIO. Use timer-based debounce with configurable delay. Report clean press/release events.",
         "acceptance_criteria": ["Debounce timer used", "No false triggers", "Configurable delay"],
         "task_type": "firmware_implementation"},
        {"title": "Watchdog timer setup", "difficulty": "beginner", "tags": ["watchdog", "safety", "basics"],
         "description": "Configure a hardware watchdog timer with appropriate timeout. Implement watchdog kick in the main loop. Add early warning interrupt before reset.",
         "acceptance_criteria": ["Watchdog configured", "Kick in main loop", "Early warning ISR"],
         "task_type": "firmware_implementation"},
        {"title": "ADC single channel read", "difficulty": "beginner", "tags": ["adc", "analog", "basics"],
         "description": "Initialize ADC for single channel conversion. Read analog voltage with averaging (16 samples). Convert to millivolts with proper scaling.",
         "acceptance_criteria": ["ADC initialized", "Averaging implemented", "mV conversion correct"],
         "task_type": "firmware_implementation"},
        {"title": "SPI master basic", "difficulty": "beginner", "tags": ["spi", "communication", "basics"],
         "description": "Implement SPI master with configurable clock polarity and phase. Send and receive a byte. Handle chip select properly.",
         "acceptance_criteria": ["SPI config correct", "CS handling proper", "Full duplex works"],
         "task_type": "firmware_implementation"},
        {"title": "I2C scanner", "difficulty": "beginner", "tags": ["i2c", "communication", "basics"],
         "description": "Implement I2C bus scanner that probes all addresses (0x00-0x7F). Report found devices. Handle NACK correctly.",
         "acceptance_criteria": ["All addresses scanned", "Found devices reported", "NACK handled"],
         "task_type": "firmware_implementation"},
        {"title": "PWM output", "difficulty": "beginner", "tags": ["pwm", "timer", "output"],
         "description": "Generate PWM output with configurable frequency (100Hz-100kHz) and duty cycle (0-100%). Use hardware timer, not software toggle.",
         "acceptance_criteria": ["Hardware timer PWM", "Frequency configurable", "Duty cycle accurate"],
         "task_type": "firmware_implementation"},
        {"title": "Ring buffer implementation", "difficulty": "beginner", "tags": ["data_structure", "buffer", "basics"],
         "description": "Implement a thread-safe ring buffer for byte data. Support push, pop, peek, full/empty checks. Use volatile and proper memory barriers.",
         "acceptance_criteria": ["Thread-safe operations", "Overflow detection", "Memory barriers correct"],
         "task_type": "firmware_implementation"},
        {"title": "Delay functions", "difficulty": "beginner", "tags": ["timing", "basics", "systick"],
         "description": "Implement microsecond and millisecond delay functions using SysTick timer. No busy-wait for ms delays — use interrupt-based approach.",
         "acceptance_criteria": ["SysTick configured", "us delay with busy-wait", "ms delay interrupt-based"],
         "task_type": "firmware_implementation"},
        {"title": "CRC-16 calculation", "difficulty": "beginner", "tags": ["crc", "data_integrity", "algorithm"],
         "description": "Implement CRC-16/CCITT calculation for data integrity verification. Support both lookup table and bitwise methods. Validate against known test vectors.",
         "acceptance_criteria": ["CRC-16 correct", "Test vectors pass", "Both methods implemented"],
         "task_type": "firmware_implementation"},
        {"title": "Simple state machine", "difficulty": "beginner", "tags": ["state_machine", "architecture", "basics"],
         "description": "Implement a table-driven state machine for a 3-state system (IDLE, ACTIVE, ERROR). Support transition guards, entry/exit actions, and event queuing.",
         "acceptance_criteria": ["Table-driven design", "Guards work", "Entry/exit actions fire"],
         "task_type": "firmware_implementation"},
        {"title": "Flash read/write", "difficulty": "beginner", "tags": ["flash", "nvm", "storage"],
         "description": "Implement flash memory read/write with proper erase-before-write. Handle page boundaries. Include wear-leveling awareness (don't write same page repeatedly).",
         "acceptance_criteria": ["Erase-before-write", "Page boundary handling", "Write verification"],
         "task_type": "firmware_implementation"},
        {"title": "Boot sequence", "difficulty": "beginner", "tags": ["boot", "initialization", "basics"],
         "description": "Implement a structured boot sequence: clock init → peripheral init → self-test → main loop. Report each stage via UART. Handle init failures gracefully.",
         "acceptance_criteria": ["Ordered initialization", "Stage reporting", "Failure handling"],
         "task_type": "firmware_implementation"},
        {"title": "Bit manipulation utilities", "difficulty": "beginner", "tags": ["bitops", "utilities", "basics"],
         "description": "Implement register-safe bit manipulation macros/functions: SET_BIT, CLEAR_BIT, TOGGLE_BIT, READ_BIT, MODIFY_REG. All must be atomic on ARM (use bit-banding or LDREX/STREX).",
         "acceptance_criteria": ["Atomic operations", "All macros correct", "Register-safe"],
         "task_type": "firmware_implementation"},
        {"title": "Temperature sensor driver", "difficulty": "beginner", "tags": ["sensor", "driver", "i2c"],
         "description": "Write a driver for a temperature sensor (I2C). Read temperature in Celsius with 0.1°C resolution. Implement alert threshold configuration.",
         "acceptance_criteria": ["I2C communication works", "Temperature correct", "Alert configurable"],
         "task_type": "driver_implementation"},
        {"title": "Interrupt priority configuration", "difficulty": "beginner", "tags": ["nvic", "interrupts", "priority"],
         "description": "Configure NVIC interrupt priorities for a system with UART, Timer, and External interrupts. Demonstrate priority inversion scenario and resolution.",
         "acceptance_criteria": ["Priorities assigned correctly", "Preemption works", "No priority inversion"],
         "task_type": "firmware_implementation"},
        {"title": "RTC alarm", "difficulty": "beginner", "tags": ["rtc", "time", "alarm"],
         "description": "Configure RTC with calendar mode. Set an alarm that fires at a specific time. Handle daylight saving time transition.",
         "acceptance_criteria": ["RTC calendar working", "Alarm fires correctly", "DST handled"],
         "task_type": "firmware_implementation"},
        {"title": "Low-power sleep mode", "difficulty": "beginner", "tags": ["low_power", "sleep", "power"],
         "description": "Implement sleep mode entry and wake-up. Wake on external interrupt or RTC alarm. Measure and report current consumption difference.",
         "acceptance_criteria": ["Sleep mode entered", "Wake sources work", "Current measurement logged"],
         "task_type": "firmware_implementation"},
        {"title": "Error logging system", "difficulty": "beginner", "tags": ["logging", "error_handling", "debug"],
         "description": "Implement an error logging system that stores errors in a ring buffer in RAM. Include timestamp, error code, source file/line. Survive soft reset via no-init RAM section.",
         "acceptance_criteria": ["Ring buffer storage", "Timestamps included", "Survives soft reset"],
         "task_type": "firmware_implementation"},

        # Intermediate (20 seeds)
        {"title": "DMA-driven UART", "difficulty": "intermediate", "tags": ["dma", "uart", "performance"],
         "description": "Implement UART TX/RX using DMA with circular buffers. Handle half-transfer and transfer-complete interrupts. Support variable-length packets with idle-line detection.",
         "acceptance_criteria": ["DMA circular mode", "Idle-line detection", "Zero-copy where possible"],
         "task_type": "firmware_implementation"},
        {"title": "FreeRTOS task creation", "difficulty": "intermediate", "tags": ["rtos", "freertos", "tasks"],
         "description": "Create a FreeRTOS application with 3 tasks at different priorities. Use mutex for shared resource. Implement priority inheritance to prevent inversion.",
         "acceptance_criteria": ["3 tasks running", "Mutex protects shared data", "Priority inheritance enabled"],
         "task_type": "firmware_implementation"},
        {"title": "CAN bus driver", "difficulty": "intermediate", "tags": ["can", "automotive", "communication"],
         "description": "Implement CAN 2.0B driver with hardware filtering. Support standard and extended IDs. Handle bus-off recovery. Implement message FIFO with overflow handling.",
         "acceptance_criteria": ["Hardware filter configured", "Both ID types", "Bus-off recovery works"],
         "task_type": "driver_implementation"},
        {"title": "Bootloader with firmware update", "difficulty": "intermediate", "tags": ["bootloader", "firmware_update", "flash"],
         "description": "Implement a bootloader that receives firmware via UART (XMODEM protocol). Verify CRC before flashing. Support rollback to previous version on failed boot.",
         "acceptance_criteria": ["XMODEM receive works", "CRC verification", "Rollback mechanism"],
         "task_type": "firmware_implementation"},
        {"title": "Motor PID controller", "difficulty": "intermediate", "tags": ["pid", "control", "motor"],
         "description": "Implement a PID controller for DC motor speed control. Auto-tune PID gains using Ziegler-Nichols method. Anti-windup on integrator. Derivative filter for noise.",
         "acceptance_criteria": ["PID tuning method", "Anti-windup", "Derivative filtering"],
         "task_type": "firmware_implementation"},
        {"title": "Power management state machine", "difficulty": "intermediate", "tags": ["power", "state_machine", "low_power"],
         "description": "Implement a power management system with states: RUN, IDLE, SLEEP, DEEP_SLEEP. Transition based on activity timeout. Wake peripheral clocks only when needed.",
         "acceptance_criteria": ["All power states implemented", "Clock gating works", "Activity-based transitions"],
         "task_type": "firmware_implementation"},
        {"title": "SPI flash filesystem", "difficulty": "intermediate", "tags": ["filesystem", "spi", "flash"],
         "description": "Implement a simple filesystem on external SPI NOR flash. Support create, read, write, delete. Wear-leveling across sectors. Directory listing.",
         "acceptance_criteria": ["CRUD operations work", "Wear-leveling implemented", "Directory listing"],
         "task_type": "firmware_implementation"},
        {"title": "USB CDC virtual COM port", "difficulty": "intermediate", "tags": ["usb", "cdc", "communication"],
         "description": "Implement USB CDC ACM device (virtual COM port). Enumerate correctly on host. Handle USB suspend/resume. Support configuration descriptor with IAD.",
         "acceptance_criteria": ["USB enumeration works", "Data transfer bidirectional", "Suspend/resume handled"],
         "task_type": "driver_implementation"},
        {"title": "Sensor fusion (accelerometer + gyroscope)", "difficulty": "intermediate", "tags": ["sensor_fusion", "imu", "algorithm"],
         "description": "Implement complementary filter for IMU sensor fusion. Read accelerometer and gyroscope via SPI. Output pitch/roll/yaw with drift compensation.",
         "acceptance_criteria": ["Complementary filter correct", "Drift compensated", "Output stable"],
         "task_type": "firmware_implementation"},
        {"title": "Protocol parser (binary)", "difficulty": "intermediate", "tags": ["protocol", "parser", "communication"],
         "description": "Implement a robust binary protocol parser with: sync bytes, length field, CRC, escape characters. Handle fragmented reception. Detect and recover from sync loss.",
         "acceptance_criteria": ["Handles fragmentation", "CRC validation", "Sync recovery works"],
         "task_type": "firmware_implementation"},
        {"title": "Memory pool allocator", "difficulty": "intermediate", "tags": ["memory", "allocator", "performance"],
         "description": "Implement a fixed-block memory pool allocator for embedded use. No fragmentation. O(1) alloc and free. Thread-safe with ISR-safe variant.",
         "acceptance_criteria": ["O(1) operations", "No fragmentation", "ISR-safe version"],
         "task_type": "firmware_implementation"},
        {"title": "Multi-ADC DMA scanning", "difficulty": "intermediate", "tags": ["adc", "dma", "multichannel"],
         "description": "Implement multi-channel ADC scanning with DMA. Scan 8 channels continuously. Apply per-channel calibration offsets. Double-buffer for zero-latency access.",
         "acceptance_criteria": ["8 channels scanning", "DMA double-buffer", "Calibration applied"],
         "task_type": "firmware_implementation"},
        {"title": "Hardware abstraction layer", "difficulty": "intermediate", "tags": ["hal", "abstraction", "architecture"],
         "description": "Design a HAL for GPIO, UART, SPI that supports multiple MCU families. Use compile-time dispatch. Each peripheral has init, read, write, deinit. Include mock implementation for testing.",
         "acceptance_criteria": ["Multi-platform HAL", "Mock for testing", "Compile-time dispatch"],
         "task_type": "architecture_design"},
        {"title": "Fault handler implementation", "difficulty": "intermediate", "tags": ["fault", "debug", "cortex_m"],
         "description": "Implement HardFault, BusFault, UsageFault, and MemManage handlers for Cortex-M. Decode fault status registers. Log register dump to persistent memory. Support post-mortem debug.",
         "acceptance_criteria": ["All fault types handled", "Register dump logged", "Post-mortem data available"],
         "task_type": "firmware_implementation"},
        {"title": "Ethernet MAC driver", "difficulty": "intermediate", "tags": ["ethernet", "networking", "driver"],
         "description": "Implement Ethernet MAC driver with DMA descriptors. Support transmit and receive with scatter-gather DMA. Handle link status changes. PHY register access via MDIO.",
         "acceptance_criteria": ["DMA descriptors correct", "Link detection works", "PHY communication"],
         "task_type": "driver_implementation"},
        {"title": "Command-line interface", "difficulty": "intermediate", "tags": ["cli", "debug", "uart"],
         "description": "Implement a UART-based CLI with: command parsing, tab completion, history (up/down arrows), and help system. Support command registration with function pointers.",
         "acceptance_criteria": ["Command parsing works", "Tab completion", "History navigation"],
         "task_type": "firmware_implementation"},
        {"title": "OTA firmware update", "difficulty": "intermediate", "tags": ["ota", "firmware_update", "wireless"],
         "description": "Implement OTA firmware update over WiFi/BLE. Chunk-based transfer with resume support. Dual-bank flash for atomic swap. Cryptographic signature verification.",
         "acceptance_criteria": ["Chunk transfer with resume", "Dual-bank swap", "Signature verification"],
         "task_type": "firmware_implementation"},
        {"title": "Real-time data logger", "difficulty": "intermediate", "tags": ["logging", "sd_card", "filesystem"],
         "description": "Implement a data logger that writes sensor readings to SD card via SPI. FAT32 filesystem. Support configurable sample rate (1Hz-10kHz). Handle card removal gracefully.",
         "acceptance_criteria": ["FAT32 writing works", "Sample rate configurable", "Safe card removal"],
         "task_type": "firmware_implementation"},
        {"title": "Modbus RTU slave", "difficulty": "intermediate", "tags": ["modbus", "industrial", "protocol"],
         "description": "Implement Modbus RTU slave supporting function codes: Read Holding Registers (03), Write Single Register (06), Write Multiple Registers (16). Include CRC validation and exception responses.",
         "acceptance_criteria": ["FC 03/06/16 implemented", "CRC validation", "Exception responses"],
         "task_type": "protocol_implementation"},
        {"title": "Touch screen driver", "difficulty": "intermediate", "tags": ["touch", "display", "driver"],
         "description": "Implement resistive touch screen driver with calibration. 3-point calibration matrix calculation. Implement gesture detection: tap, long press, swipe. Noise filtering.",
         "acceptance_criteria": ["Calibration works", "Gestures detected", "Noise filtered"],
         "task_type": "driver_implementation"},

        # Advanced (15 seeds)
        {"title": "RTOS task scheduling analysis", "difficulty": "advanced", "tags": ["rtos", "scheduling", "analysis"],
         "description": "Implement rate-monotonic analysis for a set of periodic tasks. Detect schedulability violations. Propose priority assignment that meets all deadlines. Support sporadic tasks with minimum inter-arrival time.",
         "acceptance_criteria": ["RMA analysis correct", "Deadline analysis", "Sporadic task support"],
         "task_type": "analysis"},
        {"title": "Safety-critical watchdog architecture", "difficulty": "advanced", "tags": ["safety", "watchdog", "iec61508"],
         "description": "Design a dual-watchdog safety architecture per IEC 61508 SIL-2. Window watchdog for timing violations. Independent watchdog for system hang. Program flow monitoring with checkpoint validation.",
         "acceptance_criteria": ["Window + independent watchdog", "Program flow monitoring", "IEC 61508 compliant"],
         "task_type": "safety_critical"},
        {"title": "Lock-free queue", "difficulty": "advanced", "tags": ["lock_free", "concurrency", "performance"],
         "description": "Implement a lock-free SPSC (single-producer single-consumer) queue using memory barriers and atomic operations. Must work correctly on ARM with weak memory ordering. Prove ABA problem doesn't apply.",
         "acceptance_criteria": ["Lock-free verified", "Memory barriers correct", "ABA safe"],
         "task_type": "firmware_implementation"},
        {"title": "TCP/IP stack (minimal)", "difficulty": "advanced", "tags": ["tcp", "networking", "protocol"],
         "description": "Implement a minimal TCP/IP stack: ARP, IP, ICMP, TCP (3-way handshake, data transfer, connection teardown). Support one concurrent connection. Handle out-of-order packets.",
         "acceptance_criteria": ["ARP resolves", "ICMP ping works", "TCP connection lifecycle"],
         "task_type": "protocol_implementation"},
        {"title": "Cryptographic accelerator driver", "difficulty": "advanced", "tags": ["crypto", "security", "driver"],
         "description": "Implement driver for hardware crypto accelerator: AES-128/256 CBC and GCM modes. Key management with secure key storage. Side-channel attack mitigation (constant-time operations).",
         "acceptance_criteria": ["AES-CBC and GCM work", "Key storage secure", "Constant-time implementation"],
         "task_type": "driver_implementation"},
        {"title": "Motor field-oriented control", "difficulty": "advanced", "tags": ["foc", "motor", "control"],
         "description": "Implement field-oriented control (FOC) for BLDC motor. Include Clarke/Park transforms, PI current controllers, space vector PWM. Anti-cogging compensation.",
         "acceptance_criteria": ["Clarke/Park transforms correct", "SVPWM generates correct vectors", "Current loop stable"],
         "task_type": "firmware_implementation"},
        {"title": "Secure boot chain", "difficulty": "advanced", "tags": ["security", "boot", "crypto"],
         "description": "Implement a secure boot chain: ROM bootloader verifies first-stage loader (RSA-2048), which verifies application (ECDSA-P256). Chain of trust. Hardware root of trust using OTP fuses.",
         "acceptance_criteria": ["Chain of trust verified", "Both signature schemes work", "OTP fuse programming"],
         "task_type": "security_implementation"},
        {"title": "Audio codec driver with DSP", "difficulty": "advanced", "tags": ["audio", "dsp", "i2s"],
         "description": "Implement I2S audio codec driver with real-time DSP: 5-band parametric EQ, dynamic range compressor, noise gate. DMA double-buffer for glitch-free playback. 48kHz/16-bit.",
         "acceptance_criteria": ["I2S DMA working", "EQ frequency response correct", "Compressor/gate functional"],
         "task_type": "firmware_implementation"},
        {"title": "Multi-core IPC mechanism", "difficulty": "advanced", "tags": ["multicore", "ipc", "communication"],
         "description": "Implement inter-processor communication between dual Cortex-M cores. Shared memory with hardware mailbox. Lock-free message passing. Cache coherency management.",
         "acceptance_criteria": ["Mailbox notifications work", "Shared memory synchronized", "Cache coherent"],
         "task_type": "firmware_implementation"},
        {"title": "MISRA-C compliance refactor", "difficulty": "advanced", "tags": ["misra", "compliance", "code_quality"],
         "description": "Refactor a given firmware module to MISRA-C:2012 compliance. Address all mandatory and required rules. Document deviations with rationale. Static analysis must pass clean.",
         "acceptance_criteria": ["All mandatory rules met", "Required rules met", "Deviations documented"],
         "task_type": "code_review"},
        {"title": "Power profiling and optimization", "difficulty": "advanced", "tags": ["power", "optimization", "measurement"],
         "description": "Profile power consumption of a firmware system across all operating modes. Identify top 3 power consumers. Optimize to reduce average current by 30%. Document before/after measurements.",
         "acceptance_criteria": ["Power profile documented", "30% reduction achieved", "Before/after comparison"],
         "task_type": "optimization"},
        {"title": "USB mass storage device", "difficulty": "advanced", "tags": ["usb", "msc", "storage"],
         "description": "Implement USB Mass Storage Class device with SCSI transparent command set. Support read/write to external flash. Handle USB enumeration, BOT protocol, SCSI commands (INQUIRY, READ_10, WRITE_10).",
         "acceptance_criteria": ["USB MSC enumeration", "SCSI commands work", "Data transfer reliable"],
         "task_type": "driver_implementation"},
        {"title": "Functional safety monitor", "difficulty": "advanced", "tags": ["safety", "monitoring", "iec62304"],
         "description": "Implement a safety monitoring subsystem per IEC 62304 Class C. RAM test (march-C), ROM CRC check, stack overflow detection, CPU register test. All tests must run without affecting real-time performance.",
         "acceptance_criteria": ["March-C RAM test", "ROM CRC periodic check", "No real-time impact"],
         "task_type": "safety_critical"},
        {"title": "Bluetooth LE GATT server", "difficulty": "advanced", "tags": ["ble", "gatt", "wireless"],
         "description": "Implement BLE GATT server with custom service. Support notifications, indications, read/write characteristics. Connection parameter negotiation. Bond management with secure pairing.",
         "acceptance_criteria": ["GATT service discoverable", "Notifications work", "Secure pairing"],
         "task_type": "protocol_implementation"},
        {"title": "Real-time kernel from scratch", "difficulty": "advanced", "tags": ["rtos", "kernel", "scheduler"],
         "description": "Implement a minimal preemptive RTOS kernel for Cortex-M: context switch (PendSV), priority-based scheduler, semaphore, mutex with priority inheritance, message queue. No external dependencies.",
         "acceptance_criteria": ["Context switch works", "Priority scheduling", "Mutex with inheritance"],
         "task_type": "firmware_implementation"},

        # Expert (10 seeds)
        {"title": "AUTOSAR MCAL driver", "difficulty": "expert", "tags": ["autosar", "automotive", "standards"],
         "description": "Implement an AUTOSAR-compliant MCAL driver for CAN. Follow AUTOSAR layered architecture. Include Det (Default Error Tracer), configuration tool generated structures, post-build configuration.",
         "acceptance_criteria": ["AUTOSAR API compliance", "Det error reporting", "Post-build config support"],
         "task_type": "firmware_implementation"},
        {"title": "DO-178C compliant module", "difficulty": "expert", "tags": ["avionics", "do178c", "safety"],
         "description": "Implement a flight-critical software module per DO-178C DAL-A. Full MC/DC test coverage. Requirements traceability matrix. Code review checklist. Structural coverage analysis.",
         "acceptance_criteria": ["MC/DC coverage > 100%", "Requirements traced", "Review checklist complete"],
         "task_type": "safety_critical"},
        {"title": "Hardware-in-the-loop test framework", "difficulty": "expert", "tags": ["hil", "testing", "automation"],
         "description": "Implement a HIL test framework that: controls target hardware via debug probe (SWD), injects stimuli on physical interfaces, captures responses, and generates test reports. Support parallel test execution across multiple targets.",
         "acceptance_criteria": ["SWD control works", "Stimulus injection", "Parallel test execution"],
         "task_type": "test_framework"},
        {"title": "Mixed-signal firmware (analog + digital)", "difficulty": "expert", "tags": ["mixed_signal", "analog", "calibration"],
         "description": "Implement calibration and control firmware for a mixed-signal system: 16-bit DAC output with INL/DNL compensation, 24-bit ADC input with auto-zero and auto-range, closed-loop control with sub-ppm stability.",
         "acceptance_criteria": ["INL/DNL compensation", "Auto-zero/range working", "Sub-ppm loop stability"],
         "task_type": "firmware_implementation"},
        {"title": "Firmware fuzzing harness", "difficulty": "expert", "tags": ["fuzzing", "security", "testing"],
         "description": "Create a fuzzing harness for firmware protocol parser. Adapt for AFL/libFuzzer. Define seed corpus. Implement custom mutators for protocol-aware fuzzing. Coverage-guided with crash analysis.",
         "acceptance_criteria": ["AFL/libFuzzer compatible", "Custom mutators", "Coverage tracking"],
         "task_type": "security_testing"},
        {"title": "Multi-zone memory protection", "difficulty": "expert", "tags": ["mpu", "security", "isolation"],
         "description": "Implement MPU-based memory protection for task isolation on Cortex-M. Each task gets its own memory region. Privileged kernel, unprivileged tasks. SVC call interface for kernel services.",
         "acceptance_criteria": ["MPU regions per task", "Privilege separation", "SVC interface works"],
         "task_type": "firmware_implementation"},
        {"title": "Time-sensitive networking (TSN) driver", "difficulty": "expert", "tags": ["tsn", "networking", "real_time"],
         "description": "Implement IEEE 802.1 TSN driver: time-aware shaper (802.1Qbv), frame preemption (802.1Qbu), gPTP synchronization (802.1AS). Sub-microsecond time sync across network nodes.",
         "acceptance_criteria": ["gPTP sync <1µs", "Qbv scheduling works", "Frame preemption functional"],
         "task_type": "driver_implementation"},
        {"title": "Safety island architecture", "difficulty": "expert", "tags": ["safety", "architecture", "redundancy"],
         "description": "Design and implement a safety island: independent safety MCU monitors main MCU via heartbeat and output comparison. Lockstep verification. Safe state management. Diagnostic coverage >99%.",
         "acceptance_criteria": ["Independent monitor", "Lockstep verification", "DC > 99%"],
         "task_type": "architecture_design"},
        {"title": "Power-aware RTOS scheduler", "difficulty": "expert", "tags": ["rtos", "power", "scheduling"],
         "description": "Extend RTOS scheduler with power-awareness: tasks declare power budget, scheduler bins tasks into active/idle periods to minimize power state transitions, tickless idle with dynamic tick suppression.",
         "acceptance_criteria": ["Power budget enforcement", "Transition minimization", "Tickless idle working"],
         "task_type": "firmware_implementation"},
        {"title": "Firmware regression test suite", "difficulty": "expert", "tags": ["testing", "ci", "automation"],
         "description": "Build a comprehensive firmware regression suite: hardware-abstracted tests (run on host), QEMU-based integration tests, code coverage reporting, static analysis integration (cppcheck, clang-tidy). CI pipeline configuration.",
         "acceptance_criteria": ["Host-based unit tests", "QEMU integration tests", "Coverage > 80%"],
         "task_type": "test_framework"},
    ]

    # ── OpenSWE (Software Engineering) ────────────────────────────────
    catalog["openswe"] = [
        # Beginner (20 seeds)
        {"title": "REST API CRUD endpoint", "difficulty": "beginner", "tags": ["api", "rest", "crud"],
         "description": "Implement a RESTful CRUD API for a resource (e.g., 'items'). Include GET (list + detail), POST, PUT, DELETE. Input validation. Proper HTTP status codes. Error responses.",
         "acceptance_criteria": ["All CRUD operations work", "Input validation", "Correct status codes"],
         "task_type": "api_implementation"},
        {"title": "Unit test suite", "difficulty": "beginner", "tags": ["testing", "unit_test", "basics"],
         "description": "Write a comprehensive unit test suite for a given module. Cover happy path, edge cases, and error cases. Mock external dependencies. Aim for >90% branch coverage.",
         "acceptance_criteria": [">90% branch coverage", "Edge cases covered", "Mocks used properly"],
         "task_type": "test_implementation"},
        {"title": "Database migration", "difficulty": "beginner", "tags": ["database", "migration", "schema"],
         "description": "Write a database migration that adds a new table with foreign key relationships. Include up and down migrations. Handle existing data gracefully. Index frequently queried columns.",
         "acceptance_criteria": ["Up/down migrations work", "Foreign keys correct", "Indexes added"],
         "task_type": "database_implementation"},
        {"title": "Authentication middleware", "difficulty": "beginner", "tags": ["auth", "middleware", "security"],
         "description": "Implement JWT authentication middleware. Validate token signature, expiration, and claims. Return 401 for invalid tokens. Support token refresh.",
         "acceptance_criteria": ["JWT validation correct", "Expiration checked", "Refresh supported"],
         "task_type": "security_implementation"},
        {"title": "Logging middleware", "difficulty": "beginner", "tags": ["logging", "middleware", "observability"],
         "description": "Implement structured logging middleware that logs: request method, path, status code, latency, request ID. Use JSON format. Redact sensitive headers (Authorization, Cookie).",
         "acceptance_criteria": ["All fields logged", "JSON format", "Sensitive data redacted"],
         "task_type": "implementation"},
        {"title": "Rate limiter", "difficulty": "beginner", "tags": ["rate_limiting", "middleware", "security"],
         "description": "Implement token bucket rate limiter middleware. Configurable per-route limits. Return 429 with Retry-After header. Support IP-based and API-key-based limiting.",
         "acceptance_criteria": ["Token bucket algorithm", "429 with Retry-After", "Per-route configuration"],
         "task_type": "implementation"},
        {"title": "Configuration loader", "difficulty": "beginner", "tags": ["config", "environment", "basics"],
         "description": "Implement a configuration loader that reads from: environment variables, .env file, YAML config file, CLI arguments. Priority order: CLI > env > .env > YAML. Type-safe with defaults.",
         "acceptance_criteria": ["All sources supported", "Priority order correct", "Type-safe with defaults"],
         "task_type": "implementation"},
        {"title": "Pagination helper", "difficulty": "beginner", "tags": ["pagination", "api", "database"],
         "description": "Implement cursor-based pagination for a database query. Support forward/backward navigation. Return page_info with hasNextPage, hasPreviousPage, startCursor, endCursor.",
         "acceptance_criteria": ["Cursor-based pagination", "Bidirectional navigation", "Correct page_info"],
         "task_type": "implementation"},
        {"title": "Input sanitization", "difficulty": "beginner", "tags": ["security", "validation", "xss"],
         "description": "Implement input sanitization for user-provided strings. Prevent XSS, SQL injection, and command injection. Support allowlists for HTML tags. Encode output contextually.",
         "acceptance_criteria": ["XSS prevented", "SQL injection prevented", "Command injection prevented"],
         "task_type": "security_implementation"},
        {"title": "Health check endpoint", "difficulty": "beginner", "tags": ["health", "monitoring", "observability"],
         "description": "Implement /health and /ready endpoints. /health checks: process alive. /ready checks: database connected, cache reachable, required services responding. Return degraded state if partial.",
         "acceptance_criteria": ["Health/ready separated", "Dependency checks", "Degraded state support"],
         "task_type": "implementation"},
        {"title": "File upload handler", "difficulty": "beginner", "tags": ["upload", "file", "api"],
         "description": "Implement multipart file upload endpoint. Validate file type (allowlist), size limit (10MB), virus scan stub. Store with content-addressed naming. Return download URL.",
         "acceptance_criteria": ["Type validation", "Size limit enforced", "Content-addressed storage"],
         "task_type": "api_implementation"},
        {"title": "Email notification service", "difficulty": "beginner", "tags": ["email", "notification", "service"],
         "description": "Implement an email notification service with template support. HTML + plain text dual format. Queue-based sending with retry. Unsubscribe link in every email.",
         "acceptance_criteria": ["Template rendering", "Dual format", "Queue-based with retry"],
         "task_type": "implementation"},
        {"title": "CLI tool with subcommands", "difficulty": "beginner", "tags": ["cli", "tool", "ux"],
         "description": "Build a CLI tool with subcommands (init, run, status, config). Include help text, version flag, verbose mode. Config file auto-discovery. Colored output.",
         "acceptance_criteria": ["Subcommands work", "Help text comprehensive", "Config auto-discovery"],
         "task_type": "implementation"},
        {"title": "Cache layer", "difficulty": "beginner", "tags": ["cache", "performance", "redis"],
         "description": "Implement a caching layer with: set, get, delete, TTL expiration. Support cache invalidation patterns (cache-aside, write-through). Include cache hit/miss metrics.",
         "acceptance_criteria": ["TTL expiration works", "Invalidation patterns", "Hit/miss metrics"],
         "task_type": "implementation"},
        {"title": "Webhook receiver", "difficulty": "beginner", "tags": ["webhook", "api", "integration"],
         "description": "Implement a webhook receiver with: signature verification (HMAC-SHA256), idempotency (deduplicate by event ID), async processing, retry mechanism for failed processing.",
         "acceptance_criteria": ["Signature verification", "Idempotency", "Async processing"],
         "task_type": "api_implementation"},
        {"title": "Data export CSV/JSON", "difficulty": "beginner", "tags": ["export", "data", "format"],
         "description": "Implement data export in CSV and JSON formats. Support streaming for large datasets. Include column selection, filtering, and date range. Handle special characters in CSV.",
         "acceptance_criteria": ["CSV and JSON formats", "Streaming for large data", "Special chars escaped"],
         "task_type": "implementation"},
        {"title": "Background job processor", "difficulty": "beginner", "tags": ["background", "queue", "async"],
         "description": "Implement a background job processor with: job queue, retry with exponential backoff, dead letter queue, job status tracking. Support job priorities.",
         "acceptance_criteria": ["Queue processing works", "Retry with backoff", "Status tracking"],
         "task_type": "implementation"},
        {"title": "API versioning", "difficulty": "beginner", "tags": ["api", "versioning", "compatibility"],
         "description": "Implement API versioning via URL path (/v1/, /v2/). Support version deprecation headers. Maintain backward compatibility. Version-specific serializers.",
         "acceptance_criteria": ["URL-based versioning", "Deprecation headers", "Backward compatible"],
         "task_type": "api_implementation"},
        {"title": "Search endpoint", "difficulty": "beginner", "tags": ["search", "api", "query"],
         "description": "Implement a search endpoint with: full-text search, field-specific filters, sorting, faceted results. Handle query injection. Support search suggestions.",
         "acceptance_criteria": ["Full-text search works", "Filters and sorting", "Injection prevented"],
         "task_type": "api_implementation"},
        {"title": "Error handling middleware", "difficulty": "beginner", "tags": ["error", "middleware", "reliability"],
         "description": "Implement global error handling middleware. Map exceptions to HTTP status codes. Include request ID in error response. Log stack traces server-side. Never expose internal details to client.",
         "acceptance_criteria": ["Exception mapping", "Request ID included", "No internal details leaked"],
         "task_type": "implementation"},

        # Intermediate (15 seeds)
        {"title": "Event-driven architecture", "difficulty": "intermediate", "tags": ["events", "architecture", "async"],
         "description": "Implement an event-driven system with: event bus, publish/subscribe, event sourcing for one aggregate. Replay events to rebuild state. Idempotent event handlers.",
         "acceptance_criteria": ["Pub/sub works", "Event replay rebuilds state", "Idempotent handlers"],
         "task_type": "architecture_implementation"},
        {"title": "Circuit breaker pattern", "difficulty": "intermediate", "tags": ["resilience", "pattern", "reliability"],
         "description": "Implement circuit breaker for external service calls. States: CLOSED, OPEN, HALF-OPEN. Configurable failure threshold, timeout, and half-open probe count. Expose metrics.",
         "acceptance_criteria": ["All 3 states work", "Configurable thresholds", "Metrics exposed"],
         "task_type": "implementation"},
        {"title": "GraphQL API", "difficulty": "intermediate", "tags": ["graphql", "api", "query"],
         "description": "Implement a GraphQL API with: queries (with pagination), mutations, subscriptions (WebSocket). N+1 query prevention with DataLoader. Input validation. Rate limiting per query complexity.",
         "acceptance_criteria": ["Queries/mutations/subscriptions work", "DataLoader prevents N+1", "Complexity-based rate limiting"],
         "task_type": "api_implementation"},
        {"title": "Database connection pooling", "difficulty": "intermediate", "tags": ["database", "performance", "connection"],
         "description": "Implement a connection pool with: configurable min/max connections, health checking, connection timeout, idle connection reaping, automatic reconnection on failure.",
         "acceptance_criteria": ["Pool sizing works", "Health checks", "Auto-reconnect"],
         "task_type": "implementation"},
        {"title": "Multi-tenant data isolation", "difficulty": "intermediate", "tags": ["multi_tenant", "security", "database"],
         "description": "Implement multi-tenant data isolation using row-level security. Tenant context from JWT. Automatic tenant scoping on all queries. Cross-tenant access prevention. Tenant-specific migration support.",
         "acceptance_criteria": ["Row-level security", "Automatic scoping", "Cross-tenant prevention"],
         "task_type": "security_implementation"},
        {"title": "WebSocket real-time updates", "difficulty": "intermediate", "tags": ["websocket", "real_time", "communication"],
         "description": "Implement WebSocket server for real-time updates. Support channels/rooms. Handle reconnection with missed-message replay. Authentication on connect. Heartbeat/ping-pong.",
         "acceptance_criteria": ["Channels work", "Reconnection with replay", "Auth on connect"],
         "task_type": "implementation"},
        {"title": "Distributed locking", "difficulty": "intermediate", "tags": ["distributed", "locking", "concurrency"],
         "description": "Implement distributed locking with: acquire, release, auto-expiry (TTL), lock extension, deadlock detection. Support both Redis-based and DB-based backends.",
         "acceptance_criteria": ["Acquire/release works", "TTL expiry", "Deadlock detection"],
         "task_type": "implementation"},
        {"title": "Feature flag system", "difficulty": "intermediate", "tags": ["feature_flag", "deployment", "configuration"],
         "description": "Implement a feature flag system with: boolean and percentage-based rollouts, user segment targeting, A/B test assignment, real-time flag updates without restart.",
         "acceptance_criteria": ["Percentage rollouts", "User targeting", "Real-time updates"],
         "task_type": "implementation"},
        {"title": "API gateway routing", "difficulty": "intermediate", "tags": ["gateway", "routing", "microservices"],
         "description": "Implement an API gateway with: path-based routing to backend services, request/response transformation, authentication, rate limiting, request logging. Support canary routing.",
         "acceptance_criteria": ["Path routing works", "Request transformation", "Canary routing"],
         "task_type": "implementation"},
        {"title": "CQRS implementation", "difficulty": "intermediate", "tags": ["cqrs", "architecture", "pattern"],
         "description": "Implement CQRS (Command Query Responsibility Segregation) for a domain. Separate read and write models. Async projection from write to read model. Eventual consistency handling.",
         "acceptance_criteria": ["Separate models", "Async projection", "Consistency handling"],
         "task_type": "architecture_implementation"},
        {"title": "Idempotent API design", "difficulty": "intermediate", "tags": ["idempotency", "api", "reliability"],
         "description": "Implement idempotency for mutating API endpoints. Idempotency key in header. Store request/response pairs. Handle concurrent duplicate requests. Expire after 24 hours.",
         "acceptance_criteria": ["Idempotency key works", "Concurrent dupes handled", "24h expiry"],
         "task_type": "api_implementation"},
        {"title": "Database sharding", "difficulty": "intermediate", "tags": ["sharding", "database", "scale"],
         "description": "Implement horizontal database sharding with: consistent hashing for shard selection, cross-shard query support, shard rebalancing on add/remove, connection management per shard.",
         "acceptance_criteria": ["Consistent hashing", "Cross-shard queries", "Rebalancing works"],
         "task_type": "database_implementation"},
        {"title": "Audit trail system", "difficulty": "intermediate", "tags": ["audit", "compliance", "logging"],
         "description": "Implement an audit trail: capture all data mutations with who/what/when/before/after. Append-only storage. Query by entity, user, or time range. Tamper detection via hash chain.",
         "acceptance_criteria": ["All mutations captured", "Append-only", "Hash chain integrity"],
         "task_type": "implementation"},
        {"title": "OAuth2 provider", "difficulty": "intermediate", "tags": ["oauth", "auth", "security"],
         "description": "Implement OAuth2 authorization server: authorization code grant, PKCE, refresh tokens, token revocation, client registration. JWT access tokens with configurable claims.",
         "acceptance_criteria": ["Auth code + PKCE flow", "Token revocation", "PKCE enforced"],
         "task_type": "security_implementation"},
        {"title": "Service mesh sidecar", "difficulty": "intermediate", "tags": ["service_mesh", "proxy", "microservices"],
         "description": "Implement a lightweight sidecar proxy: intercept HTTP calls, add tracing headers (W3C TraceContext), circuit breaker, retry with jitter, mTLS termination.",
         "acceptance_criteria": ["Request interception", "Tracing headers added", "mTLS working"],
         "task_type": "implementation"},

        # Advanced (10 seeds)
        {"title": "Saga orchestrator", "difficulty": "advanced", "tags": ["saga", "distributed", "transactions"],
         "description": "Implement a saga orchestrator for distributed transactions. Support compensating actions on failure. Timeout handling. Idempotent step execution. Visual saga state tracking.",
         "acceptance_criteria": ["Compensating actions work", "Timeout handling", "Idempotent steps"],
         "task_type": "architecture_implementation"},
        {"title": "Zero-downtime database migration", "difficulty": "advanced", "tags": ["migration", "deployment", "database"],
         "description": "Implement zero-downtime schema migration strategy: expand-contract pattern. Support adding columns, renaming tables, changing types — all without locking. Backward compatible at every step.",
         "acceptance_criteria": ["No table locks", "Backward compatible", "Expand-contract pattern"],
         "task_type": "database_implementation"},
        {"title": "Custom query language parser", "difficulty": "advanced", "tags": ["parser", "dsl", "language"],
         "description": "Implement a parser for a domain-specific query language. Lexer, recursive descent parser, AST construction, SQL compilation. Support: AND/OR, comparisons, IN, LIKE, nested groups.",
         "acceptance_criteria": ["Lexer tokenizes correctly", "Parser handles precedence", "SQL output correct"],
         "task_type": "implementation"},
        {"title": "Distributed tracing system", "difficulty": "advanced", "tags": ["tracing", "observability", "distributed"],
         "description": "Implement distributed tracing: span creation/propagation across services, context injection/extraction, sampling strategies, trace visualization data model. OpenTelemetry-compatible spans.",
         "acceptance_criteria": ["Cross-service propagation", "Sampling works", "OTel compatible"],
         "task_type": "implementation"},
        {"title": "Blue-green deployment controller", "difficulty": "advanced", "tags": ["deployment", "devops", "zero_downtime"],
         "description": "Implement blue-green deployment controller: health check validation, traffic switching, rollback on failure, database migration coordination, smoke test execution.",
         "acceptance_criteria": ["Traffic switching works", "Auto-rollback on failure", "DB migration coordinated"],
         "task_type": "devops_implementation"},
        {"title": "Event sourcing with snapshots", "difficulty": "advanced", "tags": ["event_sourcing", "cqrs", "performance"],
         "description": "Implement event sourcing with snapshot optimization. Create snapshots every N events. Event replay from latest snapshot. Concurrent event handling. Event schema evolution (upcasting).",
         "acceptance_criteria": ["Snapshots reduce replay time", "Schema evolution works", "Concurrent safe"],
         "task_type": "architecture_implementation"},
        {"title": "Custom ORM query builder", "difficulty": "advanced", "tags": ["orm", "database", "query"],
         "description": "Implement a type-safe query builder: method chaining, join support, subqueries, window functions, CTEs. SQL injection prevention via parameterization. Dialect support (PostgreSQL, MySQL).",
         "acceptance_criteria": ["Type-safe builder", "Joins and subqueries", "Parameterized queries"],
         "task_type": "implementation"},
        {"title": "Consensus algorithm (Raft)", "difficulty": "advanced", "tags": ["consensus", "distributed", "raft"],
         "description": "Implement Raft consensus: leader election, log replication, commitment, membership changes. Handle network partitions gracefully. Implement log compaction.",
         "acceptance_criteria": ["Leader election works", "Log replication correct", "Partition tolerant"],
         "task_type": "implementation"},
        {"title": "Load testing framework", "difficulty": "advanced", "tags": ["load_test", "performance", "testing"],
         "description": "Build a load testing framework: scenario definition (DSL), virtual user simulation, ramp-up/ramp-down, percentile latency reporting (p50/p95/p99), bottleneck identification.",
         "acceptance_criteria": ["Scenario DSL works", "Percentile reporting", "Bottleneck detection"],
         "task_type": "test_framework"},
        {"title": "Multi-region data replication", "difficulty": "advanced", "tags": ["replication", "distributed", "consistency"],
         "description": "Implement multi-region data replication: conflict-free replicated data types (CRDTs), last-writer-wins for simple fields, merge functions for complex types. Eventual consistency guarantees.",
         "acceptance_criteria": ["CRDTs resolve conflicts", "LWW for simple fields", "Eventual consistency proven"],
         "task_type": "implementation"},
    ]

    # ── OpenML (Machine Learning) ─────────────────────────────────────
    catalog["openml"] = [
        {"title": "Data cleaning pipeline", "difficulty": "beginner", "tags": ["data", "cleaning", "pipeline"],
         "description": "Build a data cleaning pipeline: handle missing values (imputation strategies), detect/remove outliers (IQR and Z-score), encode categoricals, normalize numerics. Pipeline must be serializable.",
         "acceptance_criteria": ["Missing values handled", "Outlier detection", "Pipeline serializable"],
         "task_type": "pipeline_implementation"},
        {"title": "Feature engineering", "difficulty": "beginner", "tags": ["features", "engineering", "transform"],
         "description": "Implement feature engineering for tabular data: interaction features, polynomial features, target encoding, time-based features (day of week, month, lag features). Feature importance ranking.",
         "acceptance_criteria": ["Multiple feature types", "Target encoding", "Importance ranking"],
         "task_type": "pipeline_implementation"},
        {"title": "Binary classification model", "difficulty": "beginner", "tags": ["classification", "model", "evaluation"],
         "description": "Train and evaluate a binary classification model. Compare 3+ algorithms. Proper train/val/test split. Report: accuracy, precision, recall, F1, AUC-ROC. Handle class imbalance.",
         "acceptance_criteria": ["3+ models compared", "Proper splitting", "Class imbalance handled"],
         "task_type": "model_training"},
        {"title": "Cross-validation framework", "difficulty": "beginner", "tags": ["validation", "cv", "evaluation"],
         "description": "Implement k-fold cross-validation with stratification. Support time-series splitting. Report mean and std of all metrics. Detect data leakage between folds.",
         "acceptance_criteria": ["Stratified k-fold", "Time-series support", "Leakage detection"],
         "task_type": "evaluation"},
        {"title": "Hyperparameter tuning", "difficulty": "intermediate", "tags": ["tuning", "optimization", "model"],
         "description": "Implement hyperparameter tuning: grid search, random search, and Bayesian optimization. Early stopping for poor runs. Parameter space definition. Best model selection with confidence interval.",
         "acceptance_criteria": ["3 search methods", "Early stopping", "Confidence intervals"],
         "task_type": "optimization"},
        {"title": "Model serving API", "difficulty": "intermediate", "tags": ["serving", "api", "deployment"],
         "description": "Build a model serving API: load model, batch prediction, single prediction, model versioning, A/B testing between versions. Input validation. Prediction logging.",
         "acceptance_criteria": ["Batch + single prediction", "Model versioning", "A/B testing"],
         "task_type": "deployment"},
        {"title": "Time series forecasting", "difficulty": "intermediate", "tags": ["time_series", "forecasting", "model"],
         "description": "Implement time series forecasting pipeline: stationarity testing (ADF test), decomposition (trend/seasonal/residual), ARIMA + Prophet comparison, backtesting with expanding window.",
         "acceptance_criteria": ["Stationarity tested", "Multiple models compared", "Backtesting correct"],
         "task_type": "model_training"},
        {"title": "NLP text classification", "difficulty": "intermediate", "tags": ["nlp", "text", "classification"],
         "description": "Build text classification pipeline: tokenization, TF-IDF + embeddings comparison, train classifier, error analysis. Handle multi-label case. Support inference on new text.",
         "acceptance_criteria": ["TF-IDF and embeddings compared", "Multi-label support", "Error analysis"],
         "task_type": "model_training"},
        {"title": "Anomaly detection system", "difficulty": "intermediate", "tags": ["anomaly", "detection", "monitoring"],
         "description": "Implement anomaly detection: Isolation Forest + statistical methods. Streaming detection for time series. Configurable sensitivity. Alert with anomaly explanation (feature contribution).",
         "acceptance_criteria": ["Multiple methods", "Streaming support", "Explainable alerts"],
         "task_type": "model_training"},
        {"title": "Recommendation system", "difficulty": "advanced", "tags": ["recommender", "collaborative", "model"],
         "description": "Build a recommendation engine: collaborative filtering (user-based + item-based), content-based, hybrid. Handle cold-start problem. Evaluate with precision@k, nDCG, diversity.",
         "acceptance_criteria": ["Collaborative + content-based", "Cold-start handling", "Proper metrics"],
         "task_type": "model_training"},
        {"title": "ML pipeline orchestration", "difficulty": "advanced", "tags": ["pipeline", "orchestration", "mlops"],
         "description": "Build an ML pipeline: data ingestion → validation → feature engineering → training → evaluation → model registry. Support pipeline reruns. Artifact versioning. Data lineage tracking.",
         "acceptance_criteria": ["Full pipeline works", "Artifact versioning", "Data lineage"],
         "task_type": "pipeline_implementation"},
        {"title": "Model explainability dashboard", "difficulty": "advanced", "tags": ["explainability", "shap", "interpretability"],
         "description": "Implement model explainability: SHAP values, feature importance, partial dependence plots, ICE plots. Support for tree-based and linear models. Generate HTML dashboard.",
         "acceptance_criteria": ["SHAP values computed", "PDP/ICE plots", "HTML dashboard generated"],
         "task_type": "analysis"},
        {"title": "Fairness and bias audit", "difficulty": "advanced", "tags": ["fairness", "bias", "ethics"],
         "description": "Implement ML fairness audit: demographic parity, equalized odds, calibration across groups. Bias mitigation: reweighting, adversarial debiasing. Generate compliance report.",
         "acceptance_criteria": ["Multiple fairness metrics", "Bias mitigation", "Compliance report"],
         "task_type": "analysis"},
        {"title": "Online learning system", "difficulty": "advanced", "tags": ["online", "streaming", "incremental"],
         "description": "Implement online learning: incremental model updates from streaming data. Concept drift detection (ADWIN, DDM). Automatic model retraining trigger. Performance comparison vs batch.",
         "acceptance_criteria": ["Incremental updates work", "Drift detection", "Auto-retrain trigger"],
         "task_type": "model_training"},
        {"title": "AutoML pipeline", "difficulty": "expert", "tags": ["automl", "nas", "optimization"],
         "description": "Build an AutoML system: automated feature selection, model selection (from pool of 10+), hyperparameter optimization, ensemble creation. Time budget enforcement. Interpretability report.",
         "acceptance_criteria": ["10+ model candidates", "Time budget enforced", "Ensemble creation"],
         "task_type": "pipeline_implementation"},
    ]

    # ── Compact catalogs for remaining domains ────────────────────────
    # (15 seeds each — enough for training, can be expanded via variants)

    catalog["openeda"] = [
        {"title": "2-layer LED board", "difficulty": "beginner", "tags": ["pcb", "2_layer", "basics"],
         "description": "Design a 2-layer PCB for an LED driver circuit. Include: power input, voltage regulator, LED matrix (4x4), current limiting resistors. Generate BOM and Gerber files.",
         "acceptance_criteria": ["DRC clean", "BOM complete", "Gerber files valid"],
         "task_type": "pcb_design"},
        {"title": "USB-C connector footprint", "difficulty": "beginner", "tags": ["footprint", "usb", "connector"],
         "description": "Create a USB-C connector footprint with proper pad sizes, thermal relief, shield pads, and courtyard. Validate against IPC-7351B standards.",
         "acceptance_criteria": ["IPC-7351B compliant", "Thermal relief", "Shield pads correct"],
         "task_type": "pcb_design"},
        {"title": "Power supply decoupling", "difficulty": "beginner", "tags": ["power", "decoupling", "emc"],
         "description": "Design decoupling network for a microcontroller: bulk caps, local bypass caps, ferrite beads. Proper cap placement rules. Impedance vs frequency analysis.",
         "acceptance_criteria": ["Cap placement correct", "Impedance analysis", "Ferrite bead selection"],
         "task_type": "pcb_design"},
        {"title": "4-layer stackup design", "difficulty": "intermediate", "tags": ["stackup", "4_layer", "impedance"],
         "description": "Design a 4-layer PCB stackup: signal-ground-power-signal. Calculate controlled impedance for 50Ω single-ended and 100Ω differential traces. Material selection for target Dk.",
         "acceptance_criteria": ["Impedance within ±10%", "Stackup documented", "Material selected"],
         "task_type": "pcb_design"},
        {"title": "DDR3 memory routing", "difficulty": "intermediate", "tags": ["ddr3", "high_speed", "routing"],
         "description": "Route DDR3 memory interface: address/command/data groups. Length matching within groups (±25mil). Differential clock pair. Proper termination resistors.",
         "acceptance_criteria": ["Length matched", "Differential clock", "Termination correct"],
         "task_type": "pcb_design"},
        {"title": "EMC filter design", "difficulty": "intermediate", "tags": ["emc", "filter", "compliance"],
         "description": "Design EMC input filter for CE marking compliance. Pi-filter with common-mode choke. Calculate insertion loss. Simulate filter response. Layout for minimum coupling.",
         "acceptance_criteria": ["Insertion loss adequate", "Simulation matches", "Layout minimizes coupling"],
         "task_type": "pcb_design"},
        {"title": "High-current PCB design", "difficulty": "intermediate", "tags": ["power", "thermal", "current"],
         "description": "Design PCB for 20A power path: trace width calculation (IPC-2152), thermal via arrays, copper pours, kelvin connections for current sensing. Thermal simulation.",
         "acceptance_criteria": ["Trace width per IPC-2152", "Thermal vias adequate", "Temperature rise <40°C"],
         "task_type": "pcb_design"},
        {"title": "RF PCB layout", "difficulty": "advanced", "tags": ["rf", "impedance", "layout"],
         "description": "Layout an RF section (2.4GHz): 50Ω microstrip trace, RF matching network, antenna feed, ground plane management. No ground plane splits under RF traces. Via fencing.",
         "acceptance_criteria": ["50Ω impedance maintained", "No ground splits under RF", "Via fencing done"],
         "task_type": "pcb_design"},
        {"title": "Mixed-signal PCB partition", "difficulty": "advanced", "tags": ["mixed_signal", "partition", "analog"],
         "description": "Design mixed-signal PCB: analog and digital ground partition, single-point ground connection, guard rings around sensitive analog, proper ADC routing with star grounding.",
         "acceptance_criteria": ["Ground partition correct", "Single-point connection", "Guard rings placed"],
         "task_type": "pcb_design"},
        {"title": "BGA fanout strategy", "difficulty": "advanced", "tags": ["bga", "fanout", "routing"],
         "description": "Design BGA fanout for 0.8mm pitch, 256-ball package. Dog-bone via strategy for outer balls, via-in-pad for inner. Escape routing to inner layers. Layer assignment optimization.",
         "acceptance_criteria": ["All balls escaped", "Via-in-pad for inner", "Layer assignment documented"],
         "task_type": "pcb_design"},
        {"title": "Flex-rigid PCB design", "difficulty": "advanced", "tags": ["flex", "rigid_flex", "mechanical"],
         "description": "Design a rigid-flex PCB: bend radius calculation, layer stackup through flex region, impedance control in flex section, stiffener placement. Fabrication constraints documented.",
         "acceptance_criteria": ["Bend radius correct", "Flex impedance controlled", "Stiffeners placed"],
         "task_type": "pcb_design"},
        {"title": "Signal integrity simulation", "difficulty": "advanced", "tags": ["signal_integrity", "simulation", "analysis"],
         "description": "Perform signal integrity analysis on high-speed interface: eye diagram, timing margin, crosstalk (FEXT/NEXT), return loss. Propose termination scheme based on simulation results.",
         "acceptance_criteria": ["Eye diagram generated", "Timing margin adequate", "Termination scheme proposed"],
         "task_type": "analysis"},
        {"title": "Power integrity analysis", "difficulty": "expert", "tags": ["power_integrity", "pdn", "simulation"],
         "description": "Perform PDN (Power Distribution Network) analysis: DC drop analysis, AC impedance analysis, decoupling optimization. Target impedance calculation. VRM stability analysis.",
         "acceptance_criteria": ["DC drop < 3%", "AC impedance below target", "VRM stable"],
         "task_type": "analysis"},
        {"title": "DFM/DFA review", "difficulty": "expert", "tags": ["dfm", "dfa", "manufacturing"],
         "description": "Perform Design for Manufacturing review: minimum annular ring, solder paste aperture ratios, component placement clearances, panelization, testpoint access for ICT.",
         "acceptance_criteria": ["All DFM rules checked", "Aperture ratios correct", "Testpoints accessible"],
         "task_type": "review"},
        {"title": "Automotive PCB (AEC-Q)", "difficulty": "expert", "tags": ["automotive", "aec_q", "reliability"],
         "description": "Design automotive-grade PCB per AEC-Q100/200: temperature range -40°C to +125°C, vibration resistance, conformal coating provisions, IATF 16949 documentation.",
         "acceptance_criteria": ["Temperature range met", "Vibration analysis", "IATF documentation"],
         "task_type": "pcb_design"},
    ]

    catalog["opensim"] = [
        {"title": "RC circuit SPICE", "difficulty": "beginner", "tags": ["spice", "rc", "basics"],
         "description": "Simulate an RC low-pass filter in SPICE: DC analysis, AC frequency sweep, transient step response. Calculate -3dB frequency and compare with theoretical value.",
         "acceptance_criteria": ["DC/AC/transient simulations", "-3dB within 5% of theory", "Plots generated"],
         "task_type": "simulation"},
        {"title": "Op-amp inverting amplifier", "difficulty": "beginner", "tags": ["spice", "opamp", "analog"],
         "description": "Simulate inverting amplifier: gain accuracy, bandwidth, slew rate, input/output impedance. Compare ideal vs real op-amp model. Include DC offset analysis.",
         "acceptance_criteria": ["Gain within 1%", "Bandwidth measured", "DC offset analyzed"],
         "task_type": "simulation"},
        {"title": "Verilog counter module", "difficulty": "beginner", "tags": ["verilog", "counter", "digital"],
         "description": "Implement and simulate a parameterized N-bit counter in Verilog. Include synchronous reset, enable, direction control. Write testbench with assertion-based verification.",
         "acceptance_criteria": ["Parameterized width", "Testbench passes", "Assertions used"],
         "task_type": "rtl_design"},
        {"title": "SPICE power supply regulation", "difficulty": "intermediate", "tags": ["spice", "power", "regulation"],
         "description": "Simulate buck converter: steady-state ripple, load transient response, efficiency vs load curve, loop stability (Bode plot). Component sensitivity analysis.",
         "acceptance_criteria": ["Ripple <50mV", "Bode plot shows >45° phase margin", "Efficiency >85%"],
         "task_type": "simulation"},
        {"title": "Verilog UART transmitter", "difficulty": "intermediate", "tags": ["verilog", "uart", "communication"],
         "description": "Implement UART transmitter in Verilog: configurable baud rate, 8N1 format, FIFO buffer, overrun detection. Full testbench with baud rate verification.",
         "acceptance_criteria": ["Configurable baud", "FIFO works", "Baud rate accurate"],
         "task_type": "rtl_design"},
        {"title": "PLL simulation", "difficulty": "intermediate", "tags": ["spice", "pll", "clock"],
         "description": "Simulate a PLL: loop filter design, lock time, phase noise, jitter analysis. VCO tuning range. Loop bandwidth optimization for given input/output frequencies.",
         "acceptance_criteria": ["Lock time measured", "Phase noise analyzed", "Loop bandwidth optimized"],
         "task_type": "simulation"},
        {"title": "Verilog SPI controller", "difficulty": "intermediate", "tags": ["verilog", "spi", "interface"],
         "description": "Implement SPI master controller in Verilog: all 4 modes (CPOL/CPHA), configurable clock divider, chip select management, DMA-style FIFO interface. Full testbench.",
         "acceptance_criteria": ["All 4 SPI modes", "Clock divider works", "Testbench comprehensive"],
         "task_type": "rtl_design"},
        {"title": "Timing analysis", "difficulty": "advanced", "tags": ["timing", "sta", "clock"],
         "description": "Perform static timing analysis on a multi-clock domain design: setup/hold analysis, clock domain crossing identification, false path constraints, multicycle path handling.",
         "acceptance_criteria": ["Setup/hold clean", "CDC identified", "Constraints documented"],
         "task_type": "analysis"},
        {"title": "EMC pre-compliance simulation", "difficulty": "advanced", "tags": ["emc", "simulation", "compliance"],
         "description": "Simulate radiated emissions: PCB trace as antenna model, estimate emissions at 30MHz-1GHz. Identify dominant emission sources. Propose mitigation (filtering, shielding, layout changes).",
         "acceptance_criteria": ["Emission estimate generated", "Sources identified", "Mitigation proposed"],
         "task_type": "simulation"},
        {"title": "Verilog AXI4-Lite slave", "difficulty": "advanced", "tags": ["verilog", "axi", "interface"],
         "description": "Implement AXI4-Lite slave interface in SystemVerilog: read/write channels, address decoding, register map, error response for invalid addresses. Formal verification properties.",
         "acceptance_criteria": ["AXI4-Lite protocol correct", "Register map implemented", "Formal properties pass"],
         "task_type": "rtl_design"},
        {"title": "Thermal simulation", "difficulty": "advanced", "tags": ["thermal", "simulation", "power"],
         "description": "Perform thermal simulation of PCB with power components: junction-to-ambient thermal model, copper pour effectiveness, forced vs natural convection. Generate thermal map.",
         "acceptance_criteria": ["Thermal model accurate", "Hotspots identified", "Cooling solution proposed"],
         "task_type": "simulation"},
        {"title": "Monte Carlo circuit analysis", "difficulty": "expert", "tags": ["monte_carlo", "tolerance", "analysis"],
         "description": "Run Monte Carlo simulation with component tolerances: resistor ±1%, capacitor ±10%, temperature drift. 10,000 runs. Statistical analysis of circuit performance distribution. Yield prediction.",
         "acceptance_criteria": ["10,000 runs completed", "Distribution analyzed", "Yield > 99.7%"],
         "task_type": "simulation"},
    ]

    catalog["opendoc"] = [
        {"title": "API documentation", "difficulty": "beginner", "tags": ["api_docs", "openapi", "reference"],
         "description": "Write comprehensive API documentation: endpoint descriptions, request/response examples, authentication, error codes. OpenAPI 3.0 spec. Include getting started guide.",
         "acceptance_criteria": ["All endpoints documented", "Examples for each", "OpenAPI spec valid"],
         "task_type": "documentation"},
        {"title": "User guide", "difficulty": "beginner", "tags": ["user_guide", "tutorial", "onboarding"],
         "description": "Write a user guide with: getting started tutorial, feature walkthrough, FAQ, troubleshooting. Include screenshots/diagrams. Audience: non-technical users.",
         "acceptance_criteria": ["Getting started works", "Screenshots included", "Non-technical language"],
         "task_type": "documentation"},
        {"title": "Architecture decision record", "difficulty": "intermediate", "tags": ["adr", "architecture", "decision"],
         "description": "Write an ADR for a significant technical decision. Include: context, decision drivers, considered options, decision outcome, consequences, compliance implications.",
         "acceptance_criteria": ["All ADR sections", "Options evaluated", "Consequences documented"],
         "task_type": "documentation"},
        {"title": "IEC 62304 SRS", "difficulty": "intermediate", "tags": ["iec62304", "srs", "medical"],
         "description": "Write a Software Requirements Specification per IEC 62304. Include: system requirements, software requirements, risk controls, traceability matrix. Class C software safety classification.",
         "acceptance_criteria": ["IEC 62304 structure", "Traceability matrix", "Risk controls linked"],
         "task_type": "regulatory_documentation"},
        {"title": "Release notes", "difficulty": "beginner", "tags": ["release", "changelog", "communication"],
         "description": "Write release notes for a major version: new features, improvements, bug fixes, breaking changes, migration guide. Audience: developers and end users (separate sections).",
         "acceptance_criteria": ["New features listed", "Breaking changes highlighted", "Migration guide included"],
         "task_type": "documentation"},
        {"title": "FDA 510(k) summary", "difficulty": "advanced", "tags": ["fda", "510k", "regulatory"],
         "description": "Draft a 510(k) premarket notification summary: device description, intended use, substantial equivalence comparison, performance data summary, cybersecurity considerations.",
         "acceptance_criteria": ["All FDA sections", "SE comparison complete", "Cybersecurity addressed"],
         "task_type": "regulatory_documentation"},
        {"title": "Design History File", "difficulty": "advanced", "tags": ["dhf", "design_control", "medical"],
         "description": "Create a Design History File index: design inputs, design outputs, verification results, validation plan, design review records, risk management file reference. ISO 13485 compliant.",
         "acceptance_criteria": ["ISO 13485 structure", "All design phases", "Cross-references complete"],
         "task_type": "regulatory_documentation"},
        {"title": "Runbook", "difficulty": "intermediate", "tags": ["runbook", "operations", "incident"],
         "description": "Write an operational runbook: common alerts and responses, escalation procedures, rollback steps, health check procedures, disaster recovery checklist. Include decision trees.",
         "acceptance_criteria": ["Alert responses documented", "Escalation paths clear", "Decision trees included"],
         "task_type": "documentation"},
        {"title": "Compliance matrix", "difficulty": "advanced", "tags": ["compliance", "matrix", "audit"],
         "description": "Build a compliance traceability matrix mapping requirements → design → implementation → test → evidence. Support multiple standards simultaneously (ISO 13485, IEC 62304, ISO 14971).",
         "acceptance_criteria": ["Full traceability chain", "Multi-standard support", "Gap analysis included"],
         "task_type": "regulatory_documentation"},
        {"title": "Technical specification", "difficulty": "intermediate", "tags": ["spec", "technical", "design"],
         "description": "Write a technical specification for a new system component: functional requirements, non-functional requirements, interface definitions, data model, sequence diagrams.",
         "acceptance_criteria": ["Functional + non-functional reqs", "Interface definitions", "Diagrams included"],
         "task_type": "documentation"},
    ]

    catalog["opendesign"] = [
        {"title": "Login form", "difficulty": "beginner", "tags": ["form", "auth", "accessibility"],
         "description": "Design an accessible login form: email/password fields, error states, loading state, forgot password link. WCAG 2.1 AA compliant. Support password managers. Keyboard navigable.",
         "acceptance_criteria": ["WCAG 2.1 AA", "Error states clear", "Keyboard navigable"],
         "task_type": "ui_design"},
        {"title": "Dashboard layout", "difficulty": "beginner", "tags": ["dashboard", "layout", "responsive"],
         "description": "Design a responsive dashboard: KPI cards, chart area, table, sidebar navigation. Breakpoints for mobile/tablet/desktop. Dark mode support. Design tokens defined.",
         "acceptance_criteria": ["Responsive breakpoints", "Dark mode", "Design tokens documented"],
         "task_type": "ui_design"},
        {"title": "Design system foundation", "difficulty": "intermediate", "tags": ["design_system", "tokens", "components"],
         "description": "Create a design system foundation: color palette (semantic tokens), typography scale, spacing scale, border radius, shadow elevation. Component spec for Button, Input, Card, Modal.",
         "acceptance_criteria": ["Semantic color tokens", "Typography scale", "4 component specs"],
         "task_type": "design_system"},
        {"title": "Error page UX", "difficulty": "beginner", "tags": ["error", "ux", "recovery"],
         "description": "Design error pages (404, 500, 403, offline) with: clear explanation, recovery actions, maintain navigation context, humor/brand personality. Accessible to screen readers.",
         "acceptance_criteria": ["All error types covered", "Recovery actions clear", "Screen reader friendly"],
         "task_type": "ui_design"},
        {"title": "Onboarding flow", "difficulty": "intermediate", "tags": ["onboarding", "wizard", "flow"],
         "description": "Design a multi-step onboarding flow: progress indicator, step validation, save and resume, skip option. Handle validation errors inline. Support back navigation without data loss.",
         "acceptance_criteria": ["Progress indicator", "Save and resume", "Back navigation safe"],
         "task_type": "ux_design"},
        {"title": "Data table with actions", "difficulty": "intermediate", "tags": ["table", "data", "interaction"],
         "description": "Design a data table: sortable columns, column resizing, row selection (single/multi), inline editing, bulk actions toolbar, pagination/infinite scroll toggle, export actions.",
         "acceptance_criteria": ["Sort/filter/resize", "Inline editing", "Bulk actions work"],
         "task_type": "ui_design"},
        {"title": "Notification system UX", "difficulty": "intermediate", "tags": ["notification", "toast", "inbox"],
         "description": "Design notification UX: toast notifications (stacking, auto-dismiss, actions), notification inbox (read/unread, categories, bulk actions), push notification permission flow.",
         "acceptance_criteria": ["Toast stacking", "Inbox with categories", "Permission flow"],
         "task_type": "ux_design"},
        {"title": "Accessibility audit", "difficulty": "advanced", "tags": ["accessibility", "wcag", "audit"],
         "description": "Perform WCAG 2.1 AA accessibility audit: color contrast ratios, keyboard navigation, screen reader compatibility, focus management, ARIA labels, reduced motion support.",
         "acceptance_criteria": ["Contrast ratios pass", "Keyboard fully navigable", "Screen reader tested"],
         "task_type": "audit"},
        {"title": "Design token architecture", "difficulty": "advanced", "tags": ["tokens", "architecture", "system"],
         "description": "Architect a multi-brand design token system: primitive tokens → semantic tokens → component tokens. Support light/dark/high-contrast themes. Token naming convention. Export to CSS/JSON/iOS/Android.",
         "acceptance_criteria": ["3-tier token hierarchy", "Multi-theme support", "Multi-platform export"],
         "task_type": "design_system"},
        {"title": "Complex form design", "difficulty": "advanced", "tags": ["form", "complex", "validation"],
         "description": "Design a complex form: conditional sections, repeatable groups, file attachments, autosave draft, multi-page with summary, real-time validation, accessibility for all states.",
         "acceptance_criteria": ["Conditional sections", "Autosave works", "All states accessible"],
         "task_type": "ux_design"},
    ]

    catalog["openstrategy"] = [
        {"title": "Product requirements document", "difficulty": "beginner", "tags": ["prd", "requirements", "product"],
         "description": "Write a PRD for a new feature: problem statement, user stories, acceptance criteria, success metrics, technical constraints, launch plan. Include stakeholder sign-off section.",
         "acceptance_criteria": ["Problem clearly stated", "User stories complete", "Metrics defined"],
         "task_type": "product_document"},
        {"title": "Competitive analysis", "difficulty": "beginner", "tags": ["competition", "analysis", "market"],
         "description": "Conduct competitive analysis: identify 5+ competitors, feature comparison matrix, pricing comparison, SWOT analysis, positioning map. Identify underserved market segments.",
         "acceptance_criteria": ["5+ competitors analyzed", "Feature matrix", "Positioning map"],
         "task_type": "market_analysis"},
        {"title": "Go-to-market plan", "difficulty": "intermediate", "tags": ["gtm", "launch", "marketing"],
         "description": "Create GTM plan: target customer profile, value proposition, channel strategy, pricing model, launch timeline, success metrics (MQLs, pipeline, revenue targets). Sales enablement materials outline.",
         "acceptance_criteria": ["Customer profile defined", "Channel strategy", "Revenue targets set"],
         "task_type": "strategy_document"},
        {"title": "Product roadmap", "difficulty": "intermediate", "tags": ["roadmap", "planning", "strategy"],
         "description": "Build a 12-month product roadmap: themes by quarter, feature prioritization (RICE framework), dependency mapping, resource requirements, risk assessment per initiative.",
         "acceptance_criteria": ["Quarterly themes", "RICE scoring", "Dependencies mapped"],
         "task_type": "planning_document"},
        {"title": "TAM-SAM-SOM analysis", "difficulty": "intermediate", "tags": ["market_sizing", "tam", "analysis"],
         "description": "Perform market sizing: Total Addressable Market (top-down), Serviceable Addressable Market (bottom-up), Serviceable Obtainable Market (realistic capture). Source all assumptions.",
         "acceptance_criteria": ["TAM/SAM/SOM calculated", "Top-down and bottom-up", "Assumptions sourced"],
         "task_type": "market_analysis"},
        {"title": "Pricing strategy", "difficulty": "intermediate", "tags": ["pricing", "monetization", "strategy"],
         "description": "Develop pricing strategy: cost analysis, competitive pricing benchmark, value-based pricing model, pricing tiers (free/pro/enterprise), sensitivity analysis, cannibalization risk.",
         "acceptance_criteria": ["3 pricing tiers", "Value-based rationale", "Sensitivity analysis"],
         "task_type": "strategy_document"},
        {"title": "OKR framework", "difficulty": "intermediate", "tags": ["okr", "goals", "metrics"],
         "description": "Design OKR framework for a product team: 3 Objectives with 3 Key Results each. Scoring rubric (0-1.0). Alignment cascade from company → team → individual. Quarterly review cadence.",
         "acceptance_criteria": ["3 Os with 3 KRs each", "Scoring rubric", "Alignment cascade"],
         "task_type": "planning_document"},
        {"title": "User research plan", "difficulty": "advanced", "tags": ["research", "users", "methodology"],
         "description": "Create user research plan: research questions, methodology mix (interviews, surveys, usability tests), participant recruitment criteria, analysis framework, deliverable format.",
         "acceptance_criteria": ["Research questions clear", "Mixed methodology", "Analysis framework"],
         "task_type": "research_plan"},
        {"title": "Business case", "difficulty": "advanced", "tags": ["business_case", "roi", "investment"],
         "description": "Build a business case for a product investment: market opportunity, financial projections (3-year P&L), ROI analysis, break-even timeline, risk-adjusted NPV, sensitivity scenarios.",
         "acceptance_criteria": ["3-year P&L", "ROI calculated", "Sensitivity scenarios"],
         "task_type": "strategy_document"},
        {"title": "Platform strategy", "difficulty": "expert", "tags": ["platform", "ecosystem", "strategy"],
         "description": "Design a platform strategy: core value proposition, network effects analysis, developer ecosystem plan, API monetization, governance model, chicken-and-egg launch strategy.",
         "acceptance_criteria": ["Network effects analyzed", "Developer ecosystem plan", "Launch strategy"],
         "task_type": "strategy_document"},
    ]

    return catalog


# ---------------------------------------------------------------------------
# Exercise Catalog
# ---------------------------------------------------------------------------

class ExerciseCatalog:
    """
    Scalable exercise catalog for Agent Gym.

    Manages seed exercises, generates variants, tracks prerequisites,
    and auto-calibrates difficulty based on agent success rates.
    """

    def __init__(self, db_path: str = ""):
        self.logger = logging.getLogger("ExerciseCatalog")
        if not db_path:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                ".gym_catalog.db",
            )
        self.db_path = db_path
        self._lock = threading.Lock()
        self._exercises: dict[str, Exercise] = {}  # id → Exercise
        self._domain_index: dict[str, list[str]] = {}  # domain → [exercise_ids]
        self._difficulty_index: dict[str, dict[str, list[str]]] = {}  # domain → difficulty → [ids]
        self._prerequisites: dict[str, list[str]] = {}  # exercise_id → [prereq_ids]

        self._init_db()
        self._load_seed_catalog()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS exercises (
                        id TEXT PRIMARY KEY,
                        domain TEXT NOT NULL,
                        skill TEXT DEFAULT '',
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        difficulty TEXT DEFAULT 'intermediate',
                        tags_json TEXT DEFAULT '[]',
                        acceptance_json TEXT DEFAULT '[]',
                        context TEXT DEFAULT '',
                        task_type TEXT DEFAULT '',
                        time_limit INTEGER DEFAULT 300,
                        prerequisites_json TEXT DEFAULT '[]',
                        seed_id TEXT DEFAULT '',
                        variant_axis TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_ex_domain ON exercises(domain);
                    CREATE INDEX IF NOT EXISTS idx_ex_difficulty ON exercises(difficulty);
                    CREATE INDEX IF NOT EXISTS idx_ex_seed ON exercises(seed_id);
                """)
                conn.commit()
            finally:
                conn.close()

    def _load_seed_catalog(self):
        """Load seed exercises into memory and DB."""
        catalog = _generate_seed_catalog()
        loaded = 0

        for domain, seeds in catalog.items():
            for seed in seeds:
                ex_id = self._make_id(domain, seed["title"])
                exercise = Exercise(
                    id=ex_id,
                    domain=domain,
                    skill=f"{domain}_skill",
                    title=seed["title"],
                    description=seed["description"],
                    difficulty=seed["difficulty"],
                    tags=seed.get("tags", []),
                    acceptance_criteria=seed.get("acceptance_criteria", []),
                    task_type=seed.get("task_type", ""),
                    time_limit=seed.get("time_limit", 300),
                    prerequisites=seed.get("prerequisites", []),
                )
                self._register(exercise)
                loaded += 1

        self.logger.info("Loaded %d seed exercises across %d domains", loaded, len(catalog))

    def _make_id(self, domain: str, title: str) -> str:
        """Generate deterministic exercise ID from domain + title."""
        slug = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
        short_hash = hashlib.md5(f"{domain}:{title}".encode()).hexdigest()[:6]
        return f"{domain}_{slug}_{short_hash}"

    def _register(self, exercise: Exercise) -> None:
        """Register an exercise in memory indexes."""
        self._exercises[exercise.id] = exercise

        if exercise.domain not in self._domain_index:
            self._domain_index[exercise.domain] = []
        if exercise.id not in self._domain_index[exercise.domain]:
            self._domain_index[exercise.domain].append(exercise.id)

        if exercise.domain not in self._difficulty_index:
            self._difficulty_index[exercise.domain] = {}
        if exercise.difficulty not in self._difficulty_index[exercise.domain]:
            self._difficulty_index[exercise.domain][exercise.difficulty] = []
        if exercise.id not in self._difficulty_index[exercise.domain][exercise.difficulty]:
            self._difficulty_index[exercise.domain][exercise.difficulty].append(exercise.id)

        if exercise.prerequisites:
            self._prerequisites[exercise.id] = exercise.prerequisites

    # ── Query ────────────────────────────────────────────────────────

    def get(self, exercise_id: str) -> Optional[Exercise]:
        return self._exercises.get(exercise_id)

    def get_for_domain(self, domain: str, difficulty: str = "") -> list[Exercise]:
        """Get exercises for a domain, optionally filtered by difficulty."""
        if difficulty and domain in self._difficulty_index:
            ids = self._difficulty_index.get(domain, {}).get(difficulty, [])
        else:
            ids = self._domain_index.get(domain, [])
        return [self._exercises[eid] for eid in ids if eid in self._exercises]

    def get_for_tags(self, tags: list[str], domain: str = "") -> list[Exercise]:
        """Get exercises matching any of the given tags."""
        tag_set = set(tags)
        results = []
        source = self._exercises.values()
        if domain:
            source_ids = self._domain_index.get(domain, [])
            source = [self._exercises[eid] for eid in source_ids if eid in self._exercises]
        for ex in source:
            if tag_set & set(ex.tags):
                results.append(ex)
        return results

    def check_prerequisites(self, exercise_id: str, mastered_ids: set[str]) -> bool:
        """Check if all prerequisites for an exercise are mastered."""
        prereqs = self._prerequisites.get(exercise_id, [])
        return all(p in mastered_ids for p in prereqs)

    def count(self, domain: str = "") -> dict:
        """Count exercises by domain and difficulty."""
        if domain:
            exercises = self.get_for_domain(domain)
            by_diff = {}
            for ex in exercises:
                by_diff[ex.difficulty] = by_diff.get(ex.difficulty, 0) + 1
            return {"domain": domain, "total": len(exercises), "by_difficulty": by_diff}

        total = 0
        by_domain = {}
        for d, ids in self._domain_index.items():
            by_domain[d] = len(ids)
            total += len(ids)
        return {"total": total, "by_domain": by_domain}

    # ── Variant generation ───────────────────────────────────────────

    def generate_variants(
        self,
        domain: str,
        count: int = 10,
        difficulty: str = "",
        axis: str = "",
    ) -> list[Exercise]:
        """
        Generate exercise variants from seed exercises using LLM.

        Args:
            domain: Which domain to generate for
            count: Number of variants to generate
            difficulty: Optional difficulty filter for seeds
            axis: Optional variant axis (e.g., "platform", "scale")

        Returns:
            List of generated Exercise objects (also registered in catalog)
        """
        seeds = self.get_for_domain(domain, difficulty)
        if not seeds:
            return []

        # Pick seeds that aren't already variants
        original_seeds = [s for s in seeds if not s.seed_id]
        if not original_seeds:
            original_seeds = seeds[:5]

        axes = VARIANT_AXES.get(domain, ["complexity", "scale", "constraint"])
        if axis:
            axes = [axis]

        generated = []
        try:
            from src.core.llm_gateway import llm_gateway

            # Generate in batches
            batch_size = min(count, 10)
            seed_sample = original_seeds[:min(5, len(original_seeds))]

            for batch_start in range(0, count, batch_size):
                remaining = min(batch_size, count - batch_start)
                seed = seed_sample[batch_start % len(seed_sample)]
                target_axis = axes[batch_start % len(axes)]

                prompt = (
                    f"Generate {remaining} exercise variants for a {domain} training gym.\n\n"
                    f"Base exercise:\n"
                    f"  Title: {seed.title}\n"
                    f"  Description: {seed.description}\n"
                    f"  Difficulty: {seed.difficulty}\n"
                    f"  Tags: {seed.tags}\n\n"
                    f"Variation axis: {target_axis}\n"
                    f"Generate variants that explore the '{target_axis}' dimension.\n"
                    f"Each variant should be progressively harder or test a different aspect.\n\n"
                    f"Return JSON array: [\n"
                    f'  {{"title": "...", "description": "...", "difficulty": "beginner|intermediate|advanced|expert", '
                    f'"tags": [...], "acceptance_criteria": [...], "task_type": "{seed.task_type}"}}\n'
                    f"]\n\n"
                    f"Make descriptions detailed and specific. Include concrete technical requirements."
                )

                response = llm_gateway.generate(
                    prompt,
                    f"You are an expert {domain} trainer creating practice exercises. "
                    f"Generate realistic, verifiable exercises that test real skills.",
                    trace_name=f"exercise_catalog.generate.{domain}",
                )

                # Parse response
                response = response.replace("```json", "").replace("```", "").strip()
                match = re.search(r'\[[\s\S]*\]', response)
                if match:
                    variants = json.loads(match.group(0))
                    for v in variants[:remaining]:
                        ex = Exercise(
                            id=self._make_id(domain, v.get("title", f"variant_{len(generated)}")),
                            domain=domain,
                            skill=seed.skill,
                            title=v.get("title", "Generated variant"),
                            description=v.get("description", ""),
                            difficulty=v.get("difficulty", seed.difficulty),
                            tags=v.get("tags", seed.tags),
                            acceptance_criteria=v.get("acceptance_criteria", []),
                            task_type=v.get("task_type", seed.task_type),
                            seed_id=seed.id,
                            variant_axis=target_axis,
                        )
                        self._register(ex)
                        self._save_exercise(ex)
                        generated.append(ex)

        except Exception as exc:
            self.logger.error("Variant generation failed: %s", exc)

        self.logger.info("Generated %d variants for %s", len(generated), domain)
        return generated

    def _save_exercise(self, ex: Exercise) -> None:
        """Persist a generated exercise to SQLite."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO exercises
                    (id, domain, skill, title, description, difficulty, tags_json,
                     acceptance_json, context, task_type, time_limit,
                     prerequisites_json, seed_id, variant_axis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ex.id, ex.domain, ex.skill, ex.title, ex.description,
                    ex.difficulty, json.dumps(ex.tags), json.dumps(ex.acceptance_criteria),
                    ex.context, ex.task_type, ex.time_limit,
                    json.dumps(ex.prerequisites), ex.seed_id, ex.variant_axis,
                ))
                conn.commit()
            finally:
                conn.close()

    def load_generated(self) -> int:
        """Load previously generated exercises from SQLite."""
        loaded = 0
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT * FROM exercises WHERE seed_id != ''"
                ).fetchall()
                for row in rows:
                    ex = Exercise(
                        id=row["id"],
                        domain=row["domain"],
                        skill=row["skill"],
                        title=row["title"],
                        description=row["description"],
                        difficulty=row["difficulty"],
                        tags=json.loads(row["tags_json"]),
                        acceptance_criteria=json.loads(row["acceptance_json"]),
                        context=row["context"],
                        task_type=row["task_type"],
                        time_limit=row["time_limit"],
                        prerequisites=json.loads(row["prerequisites_json"]),
                        seed_id=row["seed_id"],
                        variant_axis=row["variant_axis"],
                    )
                    self._register(ex)
                    loaded += 1
            finally:
                conn.close()

        if loaded:
            self.logger.info("Restored %d generated exercises from SQLite", loaded)
        return loaded

    # ── Stats ────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Catalog statistics."""
        total = len(self._exercises)
        seeds = sum(1 for ex in self._exercises.values() if not ex.seed_id)
        variants = total - seeds
        domains = {}
        for domain, ids in self._domain_index.items():
            difficulties = {}
            for eid in ids:
                ex = self._exercises.get(eid)
                if ex:
                    difficulties[ex.difficulty] = difficulties.get(ex.difficulty, 0) + 1
            domains[domain] = {"total": len(ids), "by_difficulty": difficulties}

        return {
            "total_exercises": total,
            "seed_exercises": seeds,
            "generated_variants": variants,
            "domains": domains,
            "variant_axes": {d: len(axes) for d, axes in VARIANT_AXES.items()},
        }


# Module-level singleton
exercise_catalog = ExerciseCatalog()
