# SAGE FallGuard Wearable — Caregiver Training Module
**Document ID:** TRN-CG-001 v1.0
**Device:** SAGE FallGuard Wearable v1.0
**Applicable Standards:** ISO 13485:2016 §7.3, IEC 62133, 21 CFR Part 820
**Classification:** Clinical Training Material — Controlled Document
**Estimated Training Time:** 45 minutes

> **⚠️ CLINICAL SPECIALIST REVIEW REQUIRED**
> This document must be reviewed and signed off by a qualified clinical specialist (RN or higher credential) before distribution to care staff. Review status: **PENDING — [Clinical Specialist Name / Date]**

---

## Pre-Training Checklist

Before starting this module, confirm you have:
- [ ] A powered SAGE FallGuard device (or training unit)
- [ ] Access to the FallGuard Care Dashboard (URL provided by your administrator)
- [ ] Your staff login credentials
- [ ] A quiet environment with no interruptions for 45 minutes

---

## ⚠️ ALERT RESPONSE PROTOCOL — START HERE (Minutes 0–5)

> **SAFETY CRITICAL — This section is first because every second counts during a fall event.**

### What an Alert Looks Like

When the FallGuard device detects a fall, you will receive **simultaneous notifications** through:

| Channel | Appearance | Action Required |
|---|---|---|
| **Care Dashboard** | Red banner + alarm sound | Acknowledge within 60 seconds |
| **Mobile app** | Push notification + vibration | Tap "Respond" |
| **Email** (if configured) | Subject: "FALL ALERT — [Patient Name]" | Secondary backup only |

### Alert Response — 4-Step Protocol (Complete within 3 minutes of alert)

**Step 1 — Acknowledge (0:00–0:30)**
Open the Care Dashboard or mobile app. Tap **"Acknowledge Alert"**. This stops the alarm and timestamps your response. *Do not skip acknowledgement — it creates the required audit record.*

**Step 2 — Assess (0:30–1:30)**
Review the alert detail screen:
- Patient name and room/location
- Fall confidence score (0–100%): scores ≥70% indicate a confirmed fall event
- GPS coordinates (for home-monitoring patients)
- Last vital signs if biometric sensor is active

**Step 3 — Respond (1:30–2:30)**
- **Score ≥70% or patient non-responsive:** Go to patient immediately. Bring emergency response kit.
- **Score 40–69%:** Call the patient by intercom or phone. If no answer within 60 seconds, proceed as confirmed fall.
- **Score <40%:** Log as reviewed and mark "False positive — verified safe."

**Step 4 — Document (2:30–3:00)**
After reaching and assessing the patient, return to the dashboard and complete the **Incident Report**:
- Select outcome: `Patient Safe` / `Minor Injury` / `Serious Injury` / `No Fall Confirmed`
- Enter brief description (2–3 sentences)
- If injury occurred: tap **"Escalate to Clinical"** — this triggers the escalation protocol (see Section 4)

> **⏱ Target:** Alert acknowledged within 60 seconds. Patient assessed within 3 minutes. Incident report completed within 15 minutes.

---

## Module Overview

This module certifies caregivers to:
1. Set up and configure a FallGuard wearable on a patient
2. Respond to fall alerts following the 4-step protocol
3. Execute the emergency escalation procedure
4. Perform daily device checks and maintenance

**Upon successful completion** (competency quiz score ≥80%), your training record is automatically updated in the Care Dashboard and a digital certificate is issued.

---

## Learning Objectives

By the end of this module, you will be able to:

- **LO-1:** Apply the 4-step alert response protocol within the 3-minute target window
- **LO-2:** Correctly fit and initialize the FallGuard wearable on a patient
- **LO-3:** Interpret alert confidence scores and select the appropriate response tier
- **LO-4:** Execute the emergency escalation procedure including 911 coordination
- **LO-5:** Perform daily device checks using the Device Status Dashboard
- **LO-6:** Document all fall events accurately in the incident report system

---

## Section 1: Device Setup and Patient Initialization (Minutes 5–18)

### 1.1 Device Components

| Component | Description |
|---|---|
| FallGuard Wearable Unit | Worn on wrist or clipped to waistband |
| Charging Dock | USB-C, charges in 90 minutes |
| Quick-Start Card | Laminated — keep in patient room |
| Replacement Band | Hypoallergenic silicone, 3 sizes: S/M/L |

### 1.2 Fitting the Device

**IMPORTANT:** Never force the band — it should sit snug but allow one finger to slide underneath.

1. Select the appropriate band size (check patient chart or measure wrist)
2. Clean the patient's wrist with a dry cloth
3. Slide the wearable over the wrist, sensor side facing the inner wrist (pulse point)
4. Secure the band — you should hear one click
5. Ask the patient: "Does this feel comfortable?" — adjust if needed
6. Check skin integrity underneath the device **every 8 hours** for patients with fragile skin

### 1.3 Pairing to the System

1. Power on the device (hold side button 3 seconds — LED flashes blue)
2. Open Care Dashboard → **Devices → Add New Device**
3. Enter the 6-digit Device ID printed on the back of the unit
4. Select the patient from the dropdown
5. Tap **"Pair"** — the wearable LED turns solid green when connected (up to 90 seconds)
6. Verify the device appears as **"Active"** in the patient's profile

**Troubleshooting pairing failures:**

| Issue | Resolution |
|---|---|
| LED stays red | Device battery <15% — dock and charge 10 minutes, retry |
| Device not found | Ensure Bluetooth and WiFi are enabled on the tablet; move within 3 metres of device |
| Patient already assigned | Contact administrator to release previous assignment |

### 1.4 Configuring Alert Thresholds

Navigate to patient profile → **Alert Settings**:

- **Sensitivity:** Set per physician order. Default: Medium (70% confidence threshold)
- **Alert Recipients:** Add at least 2 caregivers + 1 supervisor as recipients
- **Quiet Hours:** Configure for patient's nighttime hours to suppress low-confidence alerts (do NOT suppress high-confidence alerts)
- **Emergency Contacts:** Add patient's next-of-kin phone number

> **Clinical Note:** Sensitivity adjustments require a physician or nurse practitioner order. Do not change sensitivity settings without written authorization in the patient record.

### 1.5 First-Use Calibration

After pairing, perform a supervised calibration walk:
1. Ask the patient to walk 5–10 steps normally while wearing the device
2. Tap **"Calibrate Gait"** in the dashboard — takes 30 seconds
3. Confirm the status shows **"Calibrated"** before leaving the patient

---

## Section 2: Daily Device Checks (Minutes 18–28)

Perform the following checks at the **start of every shift**:

### 2.1 Physical Inspection (at bedside)

- [ ] Device is present on patient — not left on nightstand
- [ ] Band is secure and positioned correctly (sensor on pulse point)
- [ ] No redness, rash, or skin breakdown under the device
- [ ] LED is solid green (connected) or slow-pulse green (sleep mode)
- [ ] Battery indicator is ≥30%

**If battery <30%:** Dock the device while patient is stationary (e.g., during a meal). The device continues monitoring while docked.

### 2.2 Dashboard Status Check

Open Care Dashboard → **Device Fleet**:
- All assigned devices should show **"Connected"** status
- Any device showing **"Offline"** for >15 minutes requires immediate investigation
- Review the shift's alert log — confirm all alerts have a completed incident report

### 2.3 Handoff Documentation

At shift end, document in the handoff notes:
- Device status (connected/offline)
- Battery level
- Any alerts during the shift and outcomes
- Skin condition at device site

---

## Section 3: Common Scenarios and Decisions (Minutes 28–38)

### Scenario A: Patient Removes the Device

**What happens:** Device goes offline → dashboard shows "Device Removed" alert
**What to do:**
1. Acknowledge the alert in the dashboard
2. Go to patient — explain the device's purpose kindly
3. Re-fit the device (repeat Section 1.3 fit steps)
4. If patient refuses: escalate to charge nurse; do NOT forcibly apply the device
5. Document refusal in patient chart with time and reason

### Scenario B: Patient in the Shower / Bathing

The FallGuard Wearable is **IP67 water-resistant** — it can be worn during bathing and showers.
- Do NOT remove the device during personal hygiene activities
- After water exposure, check that the LED status is still green
- If LED is red after water exposure: dock the device and replace with a dry unit from supplies

### Scenario C: Low Battery During Active Patient Care

If battery drops to 10% during your shift:
1. Dashboard shows amber "Low Battery" warning
2. Bring a spare charged device from the supply cabinet
3. Swap devices: pair new device to patient, remove old device, place old device on charging dock
4. Total swap time should not exceed 5 minutes — patient is unmonitored during this window
5. Document the device swap with timestamps in the incident log

### Scenario D: False Alert

A fall alert was received but the patient is safe (e.g., patient sat down suddenly, bumped arm).
1. Acknowledge the alert
2. Assess the patient (always go to patient first)
3. Confirm patient is safe
4. Mark outcome: **"No Fall Confirmed — False Positive"**
5. Note the activity that triggered the alert (e.g., "Patient sat heavily in chair")
6. If same patient generates >3 false positives in 24 hours: notify charge nurse to review sensitivity settings

---

## Section 4: Emergency Escalation Procedure (Minutes 38–43)

### When to Escalate Immediately

Escalate to emergency services (911) AND charge nurse simultaneously if:
- Patient is **found on the floor** following an alert
- Patient is **unconscious or unresponsive**
- Patient has **visible injury** (bleeding, suspected fracture, head trauma)
- Patient reports **severe pain** (pain score ≥7/10)

### Escalation Steps

**Immediate actions (perform in order):**

1. **Call 911** — state: "Medical emergency, fall with injury at [facility name and address]. Patient is [conscious/unconscious]."
2. **Tap "Escalate to Clinical"** in the dashboard — this pages the charge nurse and on-call physician simultaneously
3. **Stay with patient** — do not move a patient with suspected spinal injury unless in immediate danger
4. **Send a colleague** to meet emergency services at the entrance
5. **Document your arrival time** and patient assessment findings

**While waiting for emergency services:**
- Maintain airway if patient is unconscious (recovery position if no spinal injury suspected)
- Apply direct pressure to any bleeding wounds
- Keep patient warm with a blanket
- Speak calmly and reassuringly to a conscious patient

**After emergency services arrive:**
- Provide the FallGuard alert timestamp and confidence score to the paramedic team
- Hand off the patient and follow facility handoff protocol
- Complete the incident report within 1 hour (mark as "Serious Injury — EMS Activated")

### Post-Escalation Documentation Requirements

The charge nurse or administrator must complete the **FDA MDR Pre-Screen Form** within 24 hours for any serious injury event. This is a regulatory requirement. You are responsible for providing accurate timestamps and observations to support this process.

---

## Section 5: Competency Check Reminders

Before taking the quiz, confirm you can answer:
- What are the 4 steps of the alert response protocol?
- What confidence score threshold triggers an immediate in-person response?
- When do you call 911 vs. notify the charge nurse?
- How do you document a false positive alert?
- What is the maximum time to complete an incident report after a fall event?

**Proceed to the Competency Assessment Quiz** (TRN-QUIZ-001) in the Care Dashboard → Training → My Assessments. You must score **≥80% to receive certification.**

---

## Document Control

| Field | Value |
|---|---|
| Author | SAGE OpenDoc Agent (AI-assisted draft) |
| Clinical Reviewer | [Clinical Specialist — SIGNATURE PENDING] |
| Version | 1.0 |
| Effective Date | Pending clinical review sign-off |
| Review Cycle | Annual or upon device firmware update |
| Next Review Due | 2027-03-27 |
| Related Documents | TRN-ADM-001, TRN-ONB-001, TRN-QUIZ-001 |
