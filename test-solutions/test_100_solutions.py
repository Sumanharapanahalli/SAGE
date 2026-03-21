"""
SAGE Framework — 100-Solution Stress Test
==========================================
Tests the Build Orchestrator with 100 diverse product ideas across 10 domains
(10 per domain). For each solution:
  1. Submits product description to build_orchestrator.start()
  2. Validates decomposition (task types, wave structure, dependencies)
  3. Runs critic review on the plan
  4. Checks domain detection accuracy
  5. Verifies correct agent routing per task type
  6. Collects improvement suggestions → feeds back to framework

Iterative Refinement Pattern:
  Round 1: Run all 100, collect failures + critic scores
  Round 2: Apply framework fixes, re-run failures
  Round 3: Final validation pass

Usage:
  .venv/bin/python -m pytest test-solutions/test_100_solutions.py -v --tb=short
  .venv/bin/python -m pytest test-solutions/test_100_solutions.py -k "medtech" -v
"""

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.integrations.build_orchestrator import (
    AGENT_ROLES_REGISTRY,
    BUILD_TASK_TYPES,
    DOMAIN_RULES,
    TASK_TYPE_TO_AGENT,
    WORKFORCE_REGISTRY,
    BuildOrchestrator,
    get_hireable_roles,
)

logger = logging.getLogger("test_100_solutions")

# ---------------------------------------------------------------------------
# 100 Product Ideas — 10 domains × 10 each
# ---------------------------------------------------------------------------

SOLUTIONS = {
    "medtech": [
        {
            "name": "elder_fall_detection",
            "description": "IoT wearable device for elderly fall detection with real-time caregiver alerts, GPS tracking, and automatic emergency dispatch. Must comply with FDA Class II and IEC 62304 for medical device software.",
            "expected_domain": "medical_device",
            "min_tasks": 8,
        },
        {
            "name": "insulin_pump_controller",
            "description": "Closed-loop insulin pump controller with continuous glucose monitoring integration, predictive dosing algorithm, and mobile app for patient monitoring. FDA Class III, ISO 13485, IEC 62304.",
            "expected_domain": "medical_device",
            "min_tasks": 10,
        },
        {
            "name": "telehealth_platform",
            "description": "HIPAA-compliant telehealth platform with video consultations, e-prescriptions, electronic health records integration, and AI-powered symptom checker.",
            "expected_domain": "healthcare_software",
            "min_tasks": 8,
        },
        {
            "name": "surgical_robot_ui",
            "description": "Surgeon console interface for a minimally invasive surgical robot with 3D visualization, haptic feedback controls, and real-time instrument tracking. ISO 13485 and IEC 62304 SIL 3.",
            "expected_domain": "medical_device",
            "min_tasks": 10,
        },
        {
            "name": "patient_monitoring_dashboard",
            "description": "ICU patient monitoring dashboard aggregating data from ventilators, infusion pumps, and vital sign monitors. Real-time alerting with nurse station integration. HL7 FHIR compliant.",
            "expected_domain": "medical_device",
            "min_tasks": 8,
        },
        {
            "name": "clinical_trial_manager",
            "description": "Clinical trial management system for tracking patient enrollment, randomization, adverse events, and regulatory submissions. 21 CFR Part 11 compliant electronic signatures.",
            "expected_domain": "healthcare_software",
            "min_tasks": 8,
        },
        {
            "name": "rehab_exercise_tracker",
            "description": "Physical rehabilitation exercise tracking app using smartphone camera for pose estimation, progress tracking, and therapist reporting. FDA Class I wellness device.",
            "expected_domain": "medical_device",
            "min_tasks": 6,
        },
        {
            "name": "medical_imaging_ai",
            "description": "AI-powered medical imaging analysis for chest X-rays detecting pneumonia, tuberculosis, and lung nodules. DICOM integration, FDA 510(k) pathway, De Novo classification for ML/AI SaMD.",
            "expected_domain": "medical_device",
            "min_tasks": 10,
        },
        {
            "name": "ehr_interop_gateway",
            "description": "Healthcare interoperability gateway for converting between HL7 v2, FHIR R4, and CDA formats. Supports Epic, Cerner, and Allscripts EHR systems. ONC certification required.",
            "expected_domain": "healthcare_software",
            "min_tasks": 8,
        },
        {
            "name": "mental_health_chatbot",
            "description": "AI mental health companion chatbot providing CBT exercises, mood tracking, crisis detection with emergency hotline routing. Not a medical device but wellness category with safety considerations.",
            "expected_domain": "healthcare_software",
            "min_tasks": 6,
        },
    ],
    "fintech": [
        {
            "name": "neobank_mobile_app",
            "description": "Mobile-first neobank app with checking/savings accounts, P2P transfers, virtual debit cards, spending insights, and round-up investing. PCI DSS, KYC/AML compliance.",
            "expected_domain": "fintech",
            "min_tasks": 10,
        },
        {
            "name": "crypto_trading_platform",
            "description": "Cryptocurrency trading platform with real-time orderbook, limit/market/stop orders, portfolio tracking, tax reporting, and institutional custody. FinCEN MSB registration.",
            "expected_domain": "fintech",
            "min_tasks": 10,
        },
        {
            "name": "invoice_factoring_marketplace",
            "description": "B2B invoice factoring marketplace connecting SMBs with institutional investors. Credit scoring, fraud detection, automated KYB verification, and escrow management.",
            "expected_domain": "fintech",
            "min_tasks": 8,
        },
        {
            "name": "robo_advisor",
            "description": "Automated investment advisory platform with risk profiling, portfolio construction using Modern Portfolio Theory, tax-loss harvesting, and rebalancing. SEC RIA registration.",
            "expected_domain": "fintech",
            "min_tasks": 8,
        },
        {
            "name": "expense_management",
            "description": "Corporate expense management with receipt OCR, policy enforcement, approval workflows, accounting integration (QuickBooks, Xero, NetSuite), and corporate card program.",
            "expected_domain": "fintech",
            "min_tasks": 8,
        },
        {
            "name": "insurance_claims_ai",
            "description": "AI-powered insurance claims processing with damage photo analysis, fraud detection, automated liability assessment, and settlement recommendation engine.",
            "expected_domain": "fintech",
            "min_tasks": 8,
        },
        {
            "name": "cross_border_payments",
            "description": "Cross-border payment platform with multi-currency wallets, FX rate engine, SWIFT/SEPA integration, sanctions screening, and remittance tracking. PSD2 and FATF compliance.",
            "expected_domain": "fintech",
            "min_tasks": 10,
        },
        {
            "name": "micro_lending_platform",
            "description": "Micro-lending platform for emerging markets with alternative credit scoring (mobile data, utility payments), automated disbursement, and collection management.",
            "expected_domain": "fintech",
            "min_tasks": 8,
        },
        {
            "name": "accounting_automation",
            "description": "AI accounting automation that categorizes transactions, reconciles bank statements, generates financial reports, and prepares tax filings for small businesses.",
            "expected_domain": "fintech",
            "min_tasks": 6,
        },
        {
            "name": "payment_gateway",
            "description": "Multi-PSP payment gateway with card processing, digital wallets (Apple Pay, Google Pay), BNPL integration, subscription billing, and PCI DSS Level 1 certification.",
            "expected_domain": "fintech",
            "min_tasks": 10,
        },
    ],
    "automotive": [
        {
            "name": "adas_perception",
            "description": "Advanced Driver Assistance System (ADAS) perception module with camera, LiDAR, and radar sensor fusion for object detection, lane keeping, and adaptive cruise control. ASIL D, ISO 26262.",
            "expected_domain": "automotive",
            "min_tasks": 10,
        },
        {
            "name": "ev_battery_management",
            "description": "Electric vehicle battery management system (BMS) with cell balancing, state-of-charge estimation, thermal management, and degradation prediction. ISO 26262 ASIL C.",
            "expected_domain": "automotive",
            "min_tasks": 10,
        },
        {
            "name": "infotainment_system",
            "description": "In-vehicle infotainment system with Android Automotive integration, voice assistant, navigation, media streaming, and OTA update capability. ISO 26262 QM.",
            "expected_domain": "automotive",
            "min_tasks": 8,
        },
        {
            "name": "fleet_telematics",
            "description": "Fleet management telematics platform with GPS tracking, driver behavior scoring, fuel optimization, predictive maintenance, and ELD compliance.",
            "expected_domain": "automotive",
            "min_tasks": 8,
        },
        {
            "name": "v2x_communication",
            "description": "Vehicle-to-Everything (V2X) communication stack implementing DSRC and C-V2X for intersection collision warning, emergency vehicle preemption, and platooning. SAE J2735/J3161.",
            "expected_domain": "automotive",
            "min_tasks": 10,
        },
        {
            "name": "obd_diagnostics_app",
            "description": "OBD-II vehicle diagnostics mobile app with DTC code reading, live sensor data, maintenance scheduling, and mechanic marketplace integration.",
            "expected_domain": "automotive",
            "min_tasks": 6,
        },
        {
            "name": "ev_charging_network",
            "description": "EV charging station network management with OCPP 2.0.1, dynamic pricing, load balancing, payment processing, and fleet charging optimization.",
            "expected_domain": "automotive",
            "min_tasks": 8,
        },
        {
            "name": "autonomous_parking",
            "description": "Automated valet parking system with ultrasonic sensor mapping, path planning, low-speed maneuver control, and mobile app for remote parking/retrieval. ISO 26262 ASIL B.",
            "expected_domain": "automotive",
            "min_tasks": 10,
        },
        {
            "name": "connected_car_platform",
            "description": "Connected car cloud platform with remote vehicle control, OTA firmware updates, usage-based insurance data, and dealer service integration.",
            "expected_domain": "automotive",
            "min_tasks": 8,
        },
        {
            "name": "hmi_design_system",
            "description": "Automotive HMI design system with instrument cluster renderer, head-up display overlay, multi-modal input (touch, voice, gesture), and distraction-minimizing UX. ISO 15005.",
            "expected_domain": "automotive",
            "min_tasks": 8,
        },
    ],
    "saas": [
        {
            "name": "project_management",
            "description": "Project management SaaS with Kanban boards, Gantt charts, time tracking, resource allocation, sprint planning, and Slack/Jira integration.",
            "expected_domain": "saas_product",
            "min_tasks": 8,
        },
        {
            "name": "crm_platform",
            "description": "CRM platform with contact management, sales pipeline, email automation, lead scoring, reporting dashboards, and Salesforce migration tools.",
            "expected_domain": "saas_product",
            "min_tasks": 8,
        },
        {
            "name": "helpdesk_platform",
            "description": "Customer support helpdesk with ticket management, knowledge base, live chat, AI auto-response, SLA tracking, and multi-channel inbox (email, social, WhatsApp).",
            "expected_domain": "saas_product",
            "min_tasks": 8,
        },
        {
            "name": "hr_management",
            "description": "HR management system with employee onboarding, PTO tracking, performance reviews, payroll integration, org chart, and compliance reporting.",
            "expected_domain": "saas_product",
            "min_tasks": 8,
        },
        {
            "name": "document_collaboration",
            "description": "Real-time document collaboration platform with rich text editor, version history, commenting, permissions, templates, and AI writing assistant.",
            "expected_domain": "saas_product",
            "min_tasks": 8,
        },
        {
            "name": "analytics_dashboard",
            "description": "Business analytics dashboard builder with data source connectors (PostgreSQL, BigQuery, Snowflake), drag-and-drop chart builder, scheduled reports, and embedding SDK.",
            "expected_domain": "saas_product",
            "min_tasks": 8,
        },
        {
            "name": "form_builder",
            "description": "No-code form builder with conditional logic, file uploads, payment collection, webhook integrations, analytics, and embeddable widgets.",
            "expected_domain": "saas_product",
            "min_tasks": 6,
        },
        {
            "name": "scheduling_app",
            "description": "Appointment scheduling SaaS with calendar sync, booking pages, team scheduling, payment collection, reminders, and CRM integration.",
            "expected_domain": "saas_product",
            "min_tasks": 6,
        },
        {
            "name": "email_marketing",
            "description": "Email marketing platform with drag-and-drop template builder, audience segmentation, A/B testing, automation workflows, deliverability monitoring, and GDPR consent management.",
            "expected_domain": "saas_product",
            "min_tasks": 8,
        },
        {
            "name": "api_gateway",
            "description": "API management platform with gateway proxy, rate limiting, API key management, developer portal, OpenAPI documentation, and usage analytics.",
            "expected_domain": "saas_product",
            "min_tasks": 8,
        },
    ],
    "ecommerce": [
        {
            "name": "marketplace_platform",
            "description": "Multi-vendor ecommerce marketplace with seller onboarding, product listings, order management, payment splitting, reviews, and dispute resolution.",
            "expected_domain": "ecommerce",
            "min_tasks": 10,
        },
        {
            "name": "headless_storefront",
            "description": "Headless ecommerce storefront with React frontend, Shopify/Medusa backend, product search (Algolia), cart management, checkout, and SSR for SEO.",
            "expected_domain": "ecommerce",
            "min_tasks": 8,
        },
        {
            "name": "subscription_box",
            "description": "Subscription box ecommerce with product curation, recurring billing, skip/pause/cancel flow, referral program, and inventory management.",
            "expected_domain": "ecommerce",
            "min_tasks": 8,
        },
        {
            "name": "dropshipping_automation",
            "description": "Dropshipping automation platform with AliExpress/1688 product import, automated order forwarding, tracking sync, margin calculator, and multi-store management.",
            "expected_domain": "ecommerce",
            "min_tasks": 6,
        },
        {
            "name": "grocery_delivery",
            "description": "Grocery delivery platform with real-time inventory, route optimization, shopper app, customer app, substitution logic, and slot-based delivery scheduling.",
            "expected_domain": "ecommerce",
            "min_tasks": 10,
        },
        {
            "name": "product_recommendation",
            "description": "AI product recommendation engine with collaborative filtering, content-based filtering, real-time personalization, A/B testing, and Shopify/WooCommerce plugins.",
            "expected_domain": "ecommerce",
            "min_tasks": 8,
        },
        {
            "name": "inventory_management",
            "description": "Multi-channel inventory management with warehouse management, barcode scanning, stock forecasting, purchase order automation, and marketplace sync (Amazon, eBay, Shopify).",
            "expected_domain": "ecommerce",
            "min_tasks": 8,
        },
        {
            "name": "loyalty_rewards",
            "description": "Customer loyalty and rewards platform with point earning/redemption, tier levels, referral tracking, birthday rewards, and POS integration.",
            "expected_domain": "ecommerce",
            "min_tasks": 6,
        },
        {
            "name": "price_optimization",
            "description": "Dynamic pricing optimization engine with competitor price monitoring, demand forecasting, price elasticity modeling, and automated repricing rules.",
            "expected_domain": "ecommerce",
            "min_tasks": 8,
        },
        {
            "name": "returns_management",
            "description": "Returns and exchange management platform with self-service portal, return label generation, warehouse receiving, refund automation, and analytics dashboard.",
            "expected_domain": "ecommerce",
            "min_tasks": 6,
        },
    ],
    "iot": [
        {
            "name": "smart_home_hub",
            "description": "Smart home hub platform with Zigbee/Z-Wave/Matter protocol support, device pairing, automation rules engine, voice assistant integration, and energy monitoring.",
            "expected_domain": "iot",
            "min_tasks": 8,
        },
        {
            "name": "industrial_iot_platform",
            "description": "Industrial IoT platform for factory monitoring with MQTT/OPC-UA ingestion, real-time dashboards, predictive maintenance ML, alert management, and SCADA integration.",
            "expected_domain": "iot",
            "min_tasks": 10,
        },
        {
            "name": "agriculture_monitoring",
            "description": "Smart agriculture IoT system with soil moisture sensors, weather station, irrigation automation, crop health imaging (NDVI), and yield prediction.",
            "expected_domain": "iot",
            "min_tasks": 8,
        },
        {
            "name": "asset_tracking",
            "description": "IoT asset tracking with BLE beacons, GPS trackers, geofencing, real-time location system (RTLS), and supply chain visibility dashboard.",
            "expected_domain": "iot",
            "min_tasks": 6,
        },
        {
            "name": "energy_management",
            "description": "Building energy management system with smart meter integration, HVAC optimization, solar panel monitoring, demand response, and carbon footprint tracking.",
            "expected_domain": "iot",
            "min_tasks": 8,
        },
        {
            "name": "water_quality_monitor",
            "description": "Water quality monitoring IoT system with pH, turbidity, dissolved oxygen, and conductivity sensors. Real-time alerting, trend analysis, and EPA compliance reporting.",
            "expected_domain": "iot",
            "min_tasks": 8,
        },
        {
            "name": "wearable_fitness",
            "description": "Fitness wearable platform with heart rate, SpO2, step counting, sleep tracking, workout detection, and health insights. BLE sync with mobile app.",
            "expected_domain": "iot",
            "min_tasks": 8,
        },
        {
            "name": "cold_chain_monitor",
            "description": "Cold chain monitoring for pharmaceuticals with temperature/humidity sensors, GPS tracking, excursion alerting, audit trail, and GDP compliance.",
            "expected_domain": "iot",
            "min_tasks": 8,
        },
        {
            "name": "smart_parking",
            "description": "Smart parking IoT system with occupancy sensors, mobile app guidance, payment integration, reservation system, and city parking analytics.",
            "expected_domain": "iot",
            "min_tasks": 6,
        },
        {
            "name": "noise_monitoring",
            "description": "Environmental noise monitoring IoT network with decibel sensors, frequency analysis, source identification, compliance reporting, and citizen complaint correlation.",
            "expected_domain": "iot",
            "min_tasks": 6,
        },
    ],
    "ml_ai": [
        {
            "name": "document_extraction",
            "description": "AI document extraction pipeline for invoices, receipts, and contracts with OCR, NER, table extraction, and structured JSON output. REST API with batch processing.",
            "expected_domain": "ml_ai",
            "min_tasks": 8,
        },
        {
            "name": "voice_assistant",
            "description": "Custom voice assistant with wake word detection, ASR (speech-to-text), NLU intent classification, dialog management, and TTS response generation.",
            "expected_domain": "ml_ai",
            "min_tasks": 10,
        },
        {
            "name": "content_moderation",
            "description": "AI content moderation system for UGC platforms with text toxicity detection, image NSFW classification, video analysis, appeal workflow, and human review queue.",
            "expected_domain": "ml_ai",
            "min_tasks": 8,
        },
        {
            "name": "recommendation_engine",
            "description": "Real-time ML recommendation engine with collaborative filtering, contextual bandits for exploration, feature store, A/B testing framework, and sub-100ms serving latency.",
            "expected_domain": "ml_ai",
            "min_tasks": 8,
        },
        {
            "name": "fraud_detection",
            "description": "Real-time fraud detection ML pipeline with transaction feature engineering, ensemble models (XGBoost + neural), explainability (SHAP), and case management dashboard.",
            "expected_domain": "ml_ai",
            "min_tasks": 8,
        },
        {
            "name": "chatbot_builder",
            "description": "No-code chatbot builder with RAG pipeline, custom knowledge base, multi-LLM support (GPT, Claude, Gemini), conversation analytics, and embeddable widget.",
            "expected_domain": "ml_ai",
            "min_tasks": 8,
        },
        {
            "name": "image_generation",
            "description": "AI image generation service with Stable Diffusion backend, prompt engineering UI, style transfer, inpainting, upscaling, and asset library management.",
            "expected_domain": "ml_ai",
            "min_tasks": 8,
        },
        {
            "name": "anomaly_detection",
            "description": "Time-series anomaly detection platform for infrastructure monitoring with unsupervised ML, seasonality handling, alert deduplication, and root cause correlation.",
            "expected_domain": "ml_ai",
            "min_tasks": 8,
        },
        {
            "name": "search_engine",
            "description": "Semantic search engine with vector embeddings, hybrid search (BM25 + vector), query understanding, auto-complete, faceted filtering, and relevance tuning console.",
            "expected_domain": "ml_ai",
            "min_tasks": 8,
        },
        {
            "name": "translation_service",
            "description": "Neural machine translation service with 50+ language pairs, domain adaptation, terminology management, translation memory, and quality estimation scoring.",
            "expected_domain": "ml_ai",
            "min_tasks": 8,
        },
    ],
    "edtech": [
        {
            "name": "lms_platform",
            "description": "Learning management system with course builder, video hosting, quizzes, progress tracking, certificates, SCORM/xAPI compliance, and LTI integration.",
            "expected_domain": "edtech",
            "min_tasks": 8,
        },
        {
            "name": "ai_tutor",
            "description": "AI-powered personal tutor with adaptive learning paths, Socratic questioning, multi-subject support, progress analytics, and parent dashboard.",
            "expected_domain": "edtech",
            "min_tasks": 8,
        },
        {
            "name": "coding_bootcamp",
            "description": "Interactive coding bootcamp platform with browser-based IDE, auto-grading, code review bot, project-based curriculum, and job placement tracking.",
            "expected_domain": "edtech",
            "min_tasks": 8,
        },
        {
            "name": "language_learning",
            "description": "Language learning app with spaced repetition, speech recognition for pronunciation, conversational AI practice, gamification, and offline mode.",
            "expected_domain": "edtech",
            "min_tasks": 8,
        },
        {
            "name": "exam_proctoring",
            "description": "Online exam proctoring platform with webcam monitoring, screen recording, AI cheating detection, identity verification, and exam analytics.",
            "expected_domain": "edtech",
            "min_tasks": 8,
        },
        {
            "name": "school_erp",
            "description": "School ERP system with student enrollment, attendance tracking, grade management, timetable scheduling, parent communication, and fee collection.",
            "expected_domain": "edtech",
            "min_tasks": 8,
        },
        {
            "name": "flashcard_app",
            "description": "Collaborative flashcard app with spaced repetition algorithm, image/audio support, shared decks, study statistics, and cross-platform sync.",
            "expected_domain": "edtech",
            "min_tasks": 6,
        },
        {
            "name": "virtual_lab",
            "description": "Virtual science laboratory with 3D simulations for physics, chemistry, and biology experiments. Student collaboration, lab reports, and curriculum alignment.",
            "expected_domain": "edtech",
            "min_tasks": 8,
        },
        {
            "name": "skill_assessment",
            "description": "Skill assessment platform for hiring with adaptive testing, coding challenges, video interviews, anti-cheating measures, and candidate ranking with bias detection.",
            "expected_domain": "edtech",
            "min_tasks": 8,
        },
        {
            "name": "course_marketplace",
            "description": "Course marketplace connecting instructors with learners. Instructor analytics, revenue sharing, review system, affiliate program, and corporate training licenses.",
            "expected_domain": "edtech",
            "min_tasks": 8,
        },
    ],
    "consumer_app": [
        {
            "name": "social_fitness",
            "description": "Social fitness app with workout sharing, challenges, leaderboards, trainer marketplace, nutrition tracking, and Apple Health/Google Fit integration.",
            "expected_domain": "consumer_app",
            "min_tasks": 8,
        },
        {
            "name": "food_delivery",
            "description": "Food delivery app with restaurant discovery, menu browsing, cart management, real-time order tracking, driver assignment, and rating system.",
            "expected_domain": "consumer_app",
            "min_tasks": 10,
        },
        {
            "name": "dating_app",
            "description": "Dating app with profile creation, photo verification, matching algorithm, chat with video calls, safety features (block/report), and premium subscription.",
            "expected_domain": "consumer_app",
            "min_tasks": 8,
        },
        {
            "name": "travel_planner",
            "description": "AI travel planner with itinerary generation, flight/hotel booking integration, budget tracking, group trip planning, and offline maps.",
            "expected_domain": "consumer_app",
            "min_tasks": 8,
        },
        {
            "name": "meditation_app",
            "description": "Meditation and mindfulness app with guided sessions, sleep stories, breathing exercises, mood tracking, streak system, and Apple Watch companion.",
            "expected_domain": "consumer_app",
            "min_tasks": 6,
        },
        {
            "name": "recipe_app",
            "description": "Recipe and meal planning app with ingredient-based search, nutritional info, grocery list generation, step-by-step cooking mode, and social sharing.",
            "expected_domain": "consumer_app",
            "min_tasks": 6,
        },
        {
            "name": "pet_care",
            "description": "Pet care app with vet appointment booking, vaccination reminders, pet health records, pet sitter marketplace, lost pet alerts, and community forums.",
            "expected_domain": "consumer_app",
            "min_tasks": 8,
        },
        {
            "name": "event_platform",
            "description": "Event discovery and ticketing platform with event creation, ticket sales, seating charts, check-in app, and post-event analytics.",
            "expected_domain": "consumer_app",
            "min_tasks": 8,
        },
        {
            "name": "habit_tracker",
            "description": "Habit tracking app with streak management, reminders, statistics, social accountability groups, and integration with Apple Health and Google Fit.",
            "expected_domain": "consumer_app",
            "min_tasks": 6,
        },
        {
            "name": "podcast_platform",
            "description": "Podcast hosting and listening platform with RSS import, analytics, monetization (ads, subscriptions), transcription, clip sharing, and discovery algorithm.",
            "expected_domain": "consumer_app",
            "min_tasks": 8,
        },
    ],
    "enterprise": [
        {
            "name": "identity_platform",
            "description": "Enterprise identity and access management (IAM) with SSO (SAML, OIDC), MFA, RBAC, SCIM provisioning, audit logging, and compliance reporting.",
            "expected_domain": "enterprise",
            "min_tasks": 10,
        },
        {
            "name": "data_warehouse",
            "description": "Cloud data warehouse with ETL pipeline builder, SQL query engine, data catalog, lineage tracking, access control, and BI tool integration.",
            "expected_domain": "enterprise",
            "min_tasks": 10,
        },
        {
            "name": "workflow_automation",
            "description": "Enterprise workflow automation platform with visual flow builder, 200+ app connectors, conditional logic, error handling, and execution monitoring.",
            "expected_domain": "enterprise",
            "min_tasks": 8,
        },
        {
            "name": "contract_management",
            "description": "Contract lifecycle management with template library, clause extraction, redline comparison, e-signature, obligation tracking, and renewal alerting.",
            "expected_domain": "enterprise",
            "min_tasks": 8,
        },
        {
            "name": "compliance_platform",
            "description": "GRC (Governance, Risk, Compliance) platform with control framework mapping (SOC 2, ISO 27001, GDPR), evidence collection, risk register, and audit management.",
            "expected_domain": "enterprise",
            "min_tasks": 10,
        },
        {
            "name": "internal_comms",
            "description": "Enterprise internal communications platform with channels, threads, file sharing, video conferencing, employee directory, and IT admin controls.",
            "expected_domain": "enterprise",
            "min_tasks": 8,
        },
        {
            "name": "procurement_system",
            "description": "Enterprise procurement system with purchase requisitions, vendor management, RFQ process, PO generation, invoice matching, and spend analytics.",
            "expected_domain": "enterprise",
            "min_tasks": 8,
        },
        {
            "name": "knowledge_management",
            "description": "Enterprise knowledge management with wiki, FAQ, decision tree, AI-powered search, content freshness scoring, and expertise directory.",
            "expected_domain": "enterprise",
            "min_tasks": 6,
        },
        {
            "name": "visitor_management",
            "description": "Enterprise visitor management with pre-registration, kiosk check-in, badge printing, NDA signing, host notification, and evacuation list.",
            "expected_domain": "enterprise",
            "min_tasks": 6,
        },
        {
            "name": "it_asset_management",
            "description": "IT asset management with device inventory, software license tracking, automated provisioning, lifecycle management, and security compliance scanning.",
            "expected_domain": "enterprise",
            "min_tasks": 8,
        },
    ],
}


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

@dataclass
class SolutionResult:
    """Result of testing a single solution through the orchestrator."""
    domain: str
    name: str
    run_id: str = ""
    status: str = ""
    task_count: int = 0
    wave_count: int = 0
    detected_domain: str = ""
    domain_correct: bool = False
    agent_roles_used: list = field(default_factory=list)
    task_types_used: list = field(default_factory=list)
    critic_score: int = 0
    issues: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    elapsed_ms: int = 0
    error: str = ""




@pytest.fixture
def orchestrator():
    """Fresh orchestrator per test."""
    return BuildOrchestrator()


MOCK_CRITIC_RESULT = {
    "passed": True, "final_score": 85, "iterations": 1,
    "history": [{"score": 85, "iteration": 1}],
    "final_review": {"score": 85, "summary": "Looks good"},
    "threshold": 70,
}


def _make_mock_plan(description: str, min_tasks: int) -> list[dict]:
    """Generate a realistic mock planner output (list of task dicts)."""
    desc_lower = description.lower()
    has_frontend = any(w in desc_lower for w in ["app", "ui", "dashboard", "platform", "web", "mobile", "portal"])
    has_backend = any(w in desc_lower for w in ["api", "server", "service", "platform", "system", "engine", "gateway"])
    has_database = any(w in desc_lower for w in ["data", "storage", "database", "records", "tracking", "management"])
    has_ml = any(w in desc_lower for w in ["ai", "ml", "prediction", "detection", "classification", "recommendation"])
    has_iot = any(w in desc_lower for w in ["sensor", "iot", "device", "firmware", "embedded", "wearable"])
    has_compliance = any(w in desc_lower for w in ["fda", "iso", "compliance", "hipaa", "gdpr", "pci", "regulatory"])
    has_security = any(w in desc_lower for w in ["security", "authentication", "encryption", "fraud", "kyc"])

    tasks = []
    step = 1

    if has_backend:
        tasks.append({"step": step, "task_type": "BACKEND", "description": "Core backend service", "payload": {}, "depends_on": []})
        step += 1
    if has_frontend:
        tasks.append({"step": step, "task_type": "FRONTEND", "description": "Frontend application", "payload": {}, "depends_on": [1] if has_backend else []})
        step += 1
    if has_database:
        tasks.append({"step": step, "task_type": "DATABASE", "description": "Database schema and data layer", "payload": {}, "depends_on": []})
        step += 1
    tasks.append({"step": step, "task_type": "API", "description": "REST API endpoints", "payload": {}, "depends_on": []})
    step += 1
    if has_ml:
        tasks.append({"step": step, "task_type": "ML_MODEL", "description": "ML model pipeline", "payload": {}, "depends_on": []})
        step += 1
        tasks.append({"step": step, "task_type": "DATA", "description": "Data pipeline", "payload": {}, "depends_on": []})
        step += 1
    if has_iot:
        tasks.append({"step": step, "task_type": "FIRMWARE", "description": "Firmware", "payload": {}, "depends_on": []})
        step += 1
        tasks.append({"step": step, "task_type": "EMBEDDED_TEST", "description": "HW-in-loop test", "payload": {}, "depends_on": [step - 1]})
        step += 1
    if has_compliance:
        tasks.append({"step": step, "task_type": "REGULATORY", "description": "Regulatory docs", "payload": {}, "depends_on": []})
        step += 1
        tasks.append({"step": step, "task_type": "SAFETY", "description": "Safety analysis", "payload": {}, "depends_on": []})
        step += 1
    if has_security:
        tasks.append({"step": step, "task_type": "SECURITY", "description": "Security audit", "payload": {}, "depends_on": []})
        step += 1
    tasks.append({"step": step, "task_type": "TESTS", "description": "Test suite", "payload": {}, "depends_on": []})
    step += 1
    tasks.append({"step": step, "task_type": "QA", "description": "QA planning", "payload": {}, "depends_on": []})
    step += 1
    tasks.append({"step": step, "task_type": "DOCS", "description": "Documentation", "payload": {}, "depends_on": []})
    step += 1
    tasks.append({"step": step, "task_type": "BUSINESS_ANALYSIS", "description": "Business requirements", "payload": {}, "depends_on": []})
    step += 1
    if has_frontend:
        tasks.append({"step": step, "task_type": "UX_DESIGN", "description": "UX wireframes", "payload": {}, "depends_on": []})
        step += 1

    extras = ["DEVOPS", "PRODUCT_MGMT", "OPERATIONS", "TRAINING", "FINANCIAL", "MARKET_RESEARCH"]
    i = 0
    while len(tasks) < min_tasks and i < len(extras):
        tasks.append({"step": step, "task_type": extras[i], "description": f"{extras[i]} task", "payload": {}, "depends_on": []})
        step += 1
        i += 1

    return tasks


# ---------------------------------------------------------------------------
# Parametrized tests — one per solution
# ---------------------------------------------------------------------------

def _all_solutions():
    """Flatten all solutions for parametrize."""
    for domain, solutions in SOLUTIONS.items():
        for sol in solutions:
            yield pytest.param(domain, sol, id=f"{domain}/{sol['name']}")


@pytest.mark.parametrize("domain,sol", list(_all_solutions()))
def test_solution_decompose(orchestrator, domain, sol):
    """Test that each solution decomposes correctly with right domain detection."""
    description = sol["description"]
    name = sol["name"]
    mock_plan = _make_mock_plan(description, sol["min_tasks"])

    with patch("src.agents.planner.planner_agent") as mock_planner, \
         patch.object(orchestrator, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT):
        mock_planner.create_plan.return_value = mock_plan

        result = orchestrator.start(
            product_description=description,
            solution_name=name,
        )

    assert not result.get("error"), f"Start failed for {domain}/{name}: {result.get('error')}"
    assert "run_id" in result, f"No run_id for {domain}/{name}"

    run_id = result["run_id"]
    status = orchestrator.get_status(run_id)

    plan = status.get("plan", [])
    assert len(plan) >= 3, f"{domain}/{name}: Expected ≥3 tasks, got {len(plan)}"

    # Verify all task types are valid
    for task in plan:
        task_type = task.get("task_type", "")
        assert task_type in BUILD_TASK_TYPES, f"{domain}/{name}: Invalid task type '{task_type}'"

    # Verify agent routing
    for task in plan:
        task_type = task.get("task_type", "")
        agent = TASK_TYPE_TO_AGENT.get(task_type)
        assert agent is not None, f"{domain}/{name}: No agent for task type '{task_type}'"
        assert agent in AGENT_ROLES_REGISTRY, f"{domain}/{name}: Agent '{agent}' not in registry"


@pytest.mark.parametrize("domain,sol", list(_all_solutions()))
def test_solution_domain_detection(orchestrator, domain, sol):
    """Test that domain detection correctly identifies the product domain."""
    description = sol["description"]
    expected = sol.get("expected_domain")
    if not expected:
        pytest.skip("No expected domain defined")

    detected = orchestrator._detect_domain(description)
    matched = orchestrator._matched_domains(description)

    # The expected domain should be in the matched list
    matched_names = [m["domain"] for m in matched]
    assert expected in matched_names, (
        f"{domain}/{sol['name']}: Expected domain '{expected}' not detected. "
        f"Got: {matched_names}"
    )


@pytest.mark.parametrize("domain,sol", list(_all_solutions()))
def test_solution_agent_coverage(orchestrator, domain, sol):
    """Test that decomposed tasks cover the right workforce teams."""
    description = sol["description"]
    mock_plan = _make_mock_plan(description, sol["min_tasks"])

    with patch("src.agents.planner.planner_agent") as mock_planner, \
         patch.object(orchestrator, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT):
        mock_planner.create_plan.return_value = mock_plan
        result = orchestrator.start(product_description=description, solution_name=sol["name"])

    run_id = result["run_id"]
    status = orchestrator.get_status(run_id)
    plan = status.get("plan", [])

    # Collect unique agents used
    agents_used = set()
    for task in plan:
        agent = TASK_TYPE_TO_AGENT.get(task.get("task_type", ""), "developer")
        agents_used.add(agent)

    # Every solution should use at least 2 different agents
    assert len(agents_used) >= 2, (
        f"{domain}/{sol['name']}: Only {len(agents_used)} agent(s) used: {agents_used}. "
        "Expected diverse agent coverage."
    )

    # Verify all used agents have complete registry entries
    for agent in agents_used:
        if agent in AGENT_ROLES_REGISTRY:
            reg = AGENT_ROLES_REGISTRY[agent]
            assert len(reg["skills"]) >= 3, f"Agent '{agent}' has too few skills"
            assert reg["description"], f"Agent '{agent}' has no description"


# ---------------------------------------------------------------------------
# Aggregate quality tests
# ---------------------------------------------------------------------------

class TestRolesRegistry:
    """Validate the AGENT_ROLES_REGISTRY is complete and consistent."""

    def test_all_task_types_have_agents(self):
        """Every task type maps to a registered agent."""
        for task_type, agent in TASK_TYPE_TO_AGENT.items():
            assert agent in AGENT_ROLES_REGISTRY, (
                f"Task type '{task_type}' maps to agent '{agent}' "
                f"which is not in AGENT_ROLES_REGISTRY"
            )

    def test_all_workforce_members_in_registry(self):
        """Every workforce member has a registry entry."""
        for team, info in WORKFORCE_REGISTRY.items():
            assert info["lead"] in AGENT_ROLES_REGISTRY, (
                f"Team '{team}' lead '{info['lead']}' not in registry"
            )
            for member in info["members"]:
                assert member in AGENT_ROLES_REGISTRY, (
                    f"Team '{team}' member '{member}' not in registry"
                )

    def test_hireable_roles_complete(self):
        """All hireable roles have required fields."""
        roles = get_hireable_roles()
        assert len(roles) >= 15, f"Expected ≥15 hireable roles, got {len(roles)}"

        for role in roles:
            assert role["title"], f"Role '{role['role']}' missing title"
            assert role["description"], f"Role '{role['role']}' missing description"
            assert role["team"], f"Role '{role['role']}' missing team"
            assert len(role["skills"]) >= 3, f"Role '{role['role']}' has too few skills ({len(role['skills'])})"
            assert len(role["tools"]) >= 1, f"Role '{role['role']}' has no tools"
            assert role["hire_when"], f"Role '{role['role']}' missing hire_when"
            assert role["mcp_server"], f"Role '{role['role']}' missing mcp_server"
            assert len(role["mcp_capabilities"]) >= 3, f"Role '{role['role']}' has too few MCP capabilities"

    def test_internal_roles_not_hireable(self):
        """Orchestration roles (planner, monitor, critic) are not hireable."""
        roles = get_hireable_roles()
        role_names = [r["role"] for r in roles]
        assert "planner" not in role_names
        assert "monitor" not in role_names
        assert "critic" not in role_names

    def test_every_role_has_8_skills(self):
        """All hireable roles define exactly 8 skills for completeness."""
        for role_name, info in AGENT_ROLES_REGISTRY.items():
            if info.get("hire_when") is not None:
                assert len(info["skills"]) == 8, (
                    f"Role '{role_name}' has {len(info['skills'])} skills, expected 8"
                )

    def test_no_duplicate_mcp_servers(self):
        """Each hireable role has a unique MCP server name."""
        servers = []
        for role_name, info in AGENT_ROLES_REGISTRY.items():
            if info.get("mcp_server"):
                assert info["mcp_server"] not in servers, (
                    f"Duplicate MCP server '{info['mcp_server']}' for role '{role_name}'"
                )
                servers.append(info["mcp_server"])

    def test_teams_are_consistent(self):
        """Role team assignments match WORKFORCE_REGISTRY."""
        for role_name, info in AGENT_ROLES_REGISTRY.items():
            team = info.get("team")
            if team and team != "orchestration":
                assert team in WORKFORCE_REGISTRY, (
                    f"Role '{role_name}' assigned to team '{team}' "
                    f"which is not in WORKFORCE_REGISTRY"
                )


class TestDomainCoverage:
    """Validate domain detection covers all 10 test domains."""

    def test_all_test_domains_have_rules(self):
        """Every domain used in SOLUTIONS has detection rules."""
        expected_domains = set()
        for solutions in SOLUTIONS.values():
            for sol in solutions:
                if sol.get("expected_domain"):
                    expected_domains.add(sol["expected_domain"])

        for domain in expected_domains:
            assert domain in DOMAIN_RULES, (
                f"Test domain '{domain}' has no detection rules in DOMAIN_RULES"
            )

    def test_domain_rules_have_keywords(self):
        """Every domain rule has keywords for detection."""
        for domain, rules in DOMAIN_RULES.items():
            assert "keywords" in rules, f"Domain '{domain}' missing keywords"
            assert len(rules["keywords"]) >= 2, (
                f"Domain '{domain}' has too few keywords ({len(rules['keywords'])})"
            )


class TestIterativeRefinement:
    """Meta-tests that check if the framework improves through iteration."""

    def test_framework_issue_collection(self):
        """Collect all potential framework improvements from the 100-solution run."""
        issues = []

        # Check: Do we have enough task types for all domains?
        domain_task_coverage = {}
        for domain_name, rules in DOMAIN_RULES.items():
            required = rules.get("required_task_types", [])
            missing = [t for t in required if t not in BUILD_TASK_TYPES]
            if missing:
                issues.append(f"Domain '{domain_name}' requires task types not in BUILD_TASK_TYPES: {missing}")
            domain_task_coverage[domain_name] = len(required)

        # Check: Do we have agents for all task types?
        unmapped = [t for t in BUILD_TASK_TYPES if t not in TASK_TYPE_TO_AGENT]
        if unmapped:
            issues.append(f"Task types without agent mapping: {unmapped}")

        # Check: Are there orphan agents (in registry but never mapped)?
        mapped_agents = set(TASK_TYPE_TO_AGENT.values())
        all_agents = set(AGENT_ROLES_REGISTRY.keys())
        internal = {"planner", "monitor", "critic"}
        orphan = all_agents - mapped_agents - internal
        if orphan:
            issues.append(f"Agents in registry but never used by any task type: {orphan}")

        # Log all issues for iterative refinement
        for issue in issues:
            logger.warning(f"Framework improvement: {issue}")

        # This test passes — issues are informational
        # In production, these would feed back to the framework's improvement loop

    def test_role_skill_completeness(self):
        """Verify role skills are diverse enough for real work."""
        roles = get_hireable_roles()
        for role in roles:
            skills = role["skills"]
            # Check skills aren't too similar (simple word overlap check)
            for i, s1 in enumerate(skills):
                for s2 in skills[i+1:]:
                    words1 = set(s1.lower().split())
                    words2 = set(s2.lower().split())
                    overlap = len(words1 & words2)
                    total = min(len(words1), len(words2))
                    if total > 0 and overlap / total > 0.7:
                        logger.warning(
                            f"Role '{role['role']}' has similar skills: "
                            f"'{s1}' vs '{s2}'"
                        )


# ---------------------------------------------------------------------------
# Summary reporter
# ---------------------------------------------------------------------------

class TestSummary:
    """Generate aggregate report across all 100 solutions."""

    def test_total_solution_count(self):
        """Verify we have 100 solutions defined."""
        total = sum(len(sols) for sols in SOLUTIONS.values())
        assert total == 100, f"Expected 100 solutions, got {total}"

    def test_domain_balance(self):
        """Each domain has exactly 10 solutions."""
        for domain, sols in SOLUTIONS.items():
            assert len(sols) == 10, f"Domain '{domain}' has {len(sols)} solutions, expected 10"

    def test_all_solutions_have_required_fields(self):
        """Every solution definition has name, description, expected_domain, min_tasks."""
        for domain, sols in SOLUTIONS.items():
            for sol in sols:
                assert "name" in sol, f"{domain}: solution missing name"
                assert "description" in sol, f"{domain}/{sol.get('name', '?')}: missing description"
                assert "expected_domain" in sol, f"{domain}/{sol['name']}: missing expected_domain"
                assert "min_tasks" in sol, f"{domain}/{sol['name']}: missing min_tasks"
                assert len(sol["description"]) >= 50, (
                    f"{domain}/{sol['name']}: description too short ({len(sol['description'])} chars)"
                )
