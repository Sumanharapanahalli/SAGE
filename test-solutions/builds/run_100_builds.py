"""
SAGE Framework — 100-Solution Scale Deployment via Web API
===========================================================
Submits all 100 product ideas to the SAGE Build Orchestrator REST API,
then approves plans and generates full solution folders with regulations.

Each solution gets:
  - Numbered folder (001-100)
  - project.yaml — domain config, compliance standards, active modules
  - prompts.yaml — agent role definitions + system prompts
  - tasks.yaml  — task types the domain needs
  - build_plan.json — decomposed task plan from the orchestrator
  - regulations.md — applicable compliance standards and requirements

Usage:
  cd /home/shetty/sandbox/SAGE
  .venv/bin/python test-solutions/builds/run_100_builds.py

  # Or run a subset:
  .venv/bin/python test-solutions/builds/run_100_builds.py --start 1 --end 10
  .venv/bin/python test-solutions/builds/run_100_builds.py --domain medtech
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
import yaml
from datetime import datetime

BASE_URL = "http://localhost:8000"
BUILDS_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 100 Solutions — same as test_100_solutions.py
# ---------------------------------------------------------------------------
SOLUTIONS = [
    # ── MEDTECH (001-010) ──
    {"id": "001", "domain": "medtech", "name": "elder_fall_detection",
     "description": "IoT wearable device for elderly fall detection with real-time caregiver alerts, GPS tracking, and automatic emergency dispatch. Must comply with FDA Class II and IEC 62304 for medical device software.",
     "compliance": ["FDA Class II", "IEC 62304", "ISO 14971", "ISO 13485"]},
    {"id": "002", "domain": "medtech", "name": "insulin_pump_controller",
     "description": "Closed-loop insulin pump controller with continuous glucose monitoring integration, predictive dosing algorithm, and mobile app for patient monitoring. FDA Class III, ISO 13485, IEC 62304.",
     "compliance": ["FDA Class III", "ISO 13485", "IEC 62304", "ISO 14971"]},
    {"id": "003", "domain": "medtech", "name": "telehealth_platform",
     "description": "HIPAA-compliant telehealth platform with video consultations, e-prescriptions, electronic health records integration, and AI-powered symptom checker.",
     "compliance": ["HIPAA", "HITECH", "HL7 FHIR", "SOC 2"]},
    {"id": "004", "domain": "medtech", "name": "surgical_robot_ui",
     "description": "Surgeon console interface for a minimally invasive surgical robot with 3D visualization, haptic feedback controls, and real-time instrument tracking. ISO 13485 and IEC 62304 SIL 3.",
     "compliance": ["ISO 13485", "IEC 62304", "IEC 61508 SIL 3", "ISO 14971"]},
    {"id": "005", "domain": "medtech", "name": "patient_monitoring_dashboard",
     "description": "ICU patient monitoring dashboard aggregating data from ventilators, infusion pumps, and vital sign monitors. Real-time alerting with nurse station integration. HL7 FHIR compliant.",
     "compliance": ["IEC 62304", "ISO 13485", "HL7 FHIR", "ISO 14971"]},
    {"id": "006", "domain": "medtech", "name": "clinical_trial_manager",
     "description": "Clinical trial management system for tracking patient enrollment, randomization, adverse events, and regulatory submissions. 21 CFR Part 11 compliant electronic signatures.",
     "compliance": ["21 CFR Part 11", "ICH GCP", "HIPAA", "GDPR"]},
    {"id": "007", "domain": "medtech", "name": "rehab_exercise_tracker",
     "description": "Physical rehabilitation exercise tracking app using smartphone camera for pose estimation, progress tracking, and therapist reporting. FDA Class I wellness device.",
     "compliance": ["FDA Class I", "HIPAA", "IEC 62304"]},
    {"id": "008", "domain": "medtech", "name": "medical_imaging_ai",
     "description": "AI-powered medical imaging analysis for chest X-rays detecting pneumonia, tuberculosis, and lung nodules. DICOM integration, FDA 510(k) pathway, De Novo classification for ML/AI SaMD.",
     "compliance": ["FDA 510(k)", "IEC 62304", "ISO 13485", "ISO 14971", "DICOM"]},
    {"id": "009", "domain": "medtech", "name": "ehr_interop_gateway",
     "description": "Healthcare interoperability gateway for converting between HL7 v2, FHIR R4, and CDA formats. Supports Epic, Cerner, and Allscripts EHR systems. ONC certification required.",
     "compliance": ["ONC Certification", "HL7 FHIR", "HIPAA", "HITECH"]},
    {"id": "010", "domain": "medtech", "name": "mental_health_chatbot",
     "description": "AI mental health companion chatbot providing CBT exercises, mood tracking, crisis detection with emergency hotline routing. Not a medical device but wellness category with safety considerations.",
     "compliance": ["HIPAA", "SOC 2", "WCAG 2.1"]},

    # ── FINTECH (011-020) ──
    {"id": "011", "domain": "fintech", "name": "neobank_mobile_app",
     "description": "Mobile-first neobank app with checking/savings accounts, P2P transfers, virtual debit cards, spending insights, and round-up investing. PCI DSS, KYC/AML compliance.",
     "compliance": ["PCI DSS", "KYC/AML", "SOC 2", "GDPR"]},
    {"id": "012", "domain": "fintech", "name": "crypto_trading_platform",
     "description": "Cryptocurrency trading platform with real-time orderbook, limit/market/stop orders, portfolio tracking, tax reporting, and institutional custody. FinCEN MSB registration.",
     "compliance": ["FinCEN MSB", "SOC 2", "PCI DSS", "GDPR"]},
    {"id": "013", "domain": "fintech", "name": "invoice_factoring_marketplace",
     "description": "B2B invoice factoring marketplace connecting SMBs with institutional investors. Credit scoring, fraud detection, automated KYB verification, and escrow management.",
     "compliance": ["KYC/AML", "SOC 2", "PCI DSS"]},
    {"id": "014", "domain": "fintech", "name": "robo_advisor",
     "description": "Automated investment advisory platform with risk profiling, portfolio construction using Modern Portfolio Theory, tax-loss harvesting, and rebalancing. SEC RIA registration.",
     "compliance": ["SEC RIA", "SOC 2", "FINRA", "Reg BI"]},
    {"id": "015", "domain": "fintech", "name": "expense_management",
     "description": "Corporate expense management with receipt OCR, policy enforcement, approval workflows, accounting integration (QuickBooks, Xero, NetSuite), and corporate card program.",
     "compliance": ["PCI DSS", "SOC 2", "SOX"]},
    {"id": "016", "domain": "fintech", "name": "insurance_claims_ai",
     "description": "AI-powered insurance claims processing with damage photo analysis, fraud detection, automated liability assessment, and settlement recommendation engine.",
     "compliance": ["SOC 2", "State Insurance Regulations", "NAIC Model Laws"]},
    {"id": "017", "domain": "fintech", "name": "cross_border_payments",
     "description": "Cross-border payment platform with multi-currency wallets, FX rate engine, SWIFT/SEPA integration, sanctions screening, and remittance tracking. PSD2 and FATF compliance.",
     "compliance": ["PSD2", "FATF", "PCI DSS", "KYC/AML", "SWIFT"]},
    {"id": "018", "domain": "fintech", "name": "micro_lending_platform",
     "description": "Micro-lending platform for emerging markets with alternative credit scoring (mobile data, utility payments), automated disbursement, and collection management.",
     "compliance": ["KYC/AML", "Consumer Lending Regulations", "Data Protection"]},
    {"id": "019", "domain": "fintech", "name": "accounting_automation",
     "description": "AI accounting automation that categorizes transactions, reconciles bank statements, generates financial reports, and prepares tax filings for small businesses.",
     "compliance": ["SOC 2", "GAAP", "SOX"]},
    {"id": "020", "domain": "fintech", "name": "payment_gateway",
     "description": "Multi-PSP payment gateway with card processing, digital wallets (Apple Pay, Google Pay), BNPL integration, subscription billing, and PCI DSS Level 1 certification.",
     "compliance": ["PCI DSS Level 1", "PSD2", "SOC 2", "3DS2"]},

    # ── AUTOMOTIVE (021-030) ──
    {"id": "021", "domain": "automotive", "name": "adas_perception",
     "description": "Advanced Driver Assistance System (ADAS) perception module with camera, LiDAR, and radar sensor fusion for object detection, lane keeping, and adaptive cruise control. ASIL D, ISO 26262.",
     "compliance": ["ISO 26262 ASIL D", "AUTOSAR", "UNECE R79"]},
    {"id": "022", "domain": "automotive", "name": "ev_battery_management",
     "description": "Electric vehicle battery management system (BMS) with cell balancing, state-of-charge estimation, thermal management, and degradation prediction. ISO 26262 ASIL C.",
     "compliance": ["ISO 26262 ASIL C", "IEC 62619", "UN ECE R100"]},
    {"id": "023", "domain": "automotive", "name": "infotainment_system",
     "description": "In-vehicle infotainment system with Android Automotive integration, voice assistant, navigation, media streaming, and OTA update capability. ISO 26262 QM.",
     "compliance": ["ISO 26262 QM", "ISO 15005", "UNECE R155/R156"]},
    {"id": "024", "domain": "automotive", "name": "fleet_telematics",
     "description": "Fleet management telematics platform with GPS tracking, driver behavior scoring, fuel optimization, predictive maintenance, and ELD compliance.",
     "compliance": ["ELD Mandate", "FMCSA", "GDPR", "SOC 2"]},
    {"id": "025", "domain": "automotive", "name": "v2x_communication",
     "description": "Vehicle-to-Everything (V2X) communication stack implementing DSRC and C-V2X for intersection collision warning, emergency vehicle preemption, and platooning. SAE J2735/J3161.",
     "compliance": ["SAE J2735", "SAE J3161", "IEEE 802.11p", "ETSI ITS"]},
    {"id": "026", "domain": "automotive", "name": "obd_diagnostics_app",
     "description": "OBD-II vehicle diagnostics mobile app with DTC code reading, live sensor data, maintenance scheduling, and mechanic marketplace integration.",
     "compliance": ["OBD-II Standard", "SAE J1979", "ISO 15031"]},
    {"id": "027", "domain": "automotive", "name": "ev_charging_network",
     "description": "EV charging station network management with OCPP 2.0.1, dynamic pricing, load balancing, payment processing, and fleet charging optimization.",
     "compliance": ["OCPP 2.0.1", "IEC 61851", "ISO 15118", "PCI DSS"]},
    {"id": "028", "domain": "automotive", "name": "autonomous_parking",
     "description": "Automated valet parking system with ultrasonic sensor mapping, path planning, low-speed maneuver control, and mobile app for remote parking/retrieval. ISO 26262 ASIL B.",
     "compliance": ["ISO 26262 ASIL B", "SAE J3016", "UNECE R79"]},
    {"id": "029", "domain": "automotive", "name": "connected_car_platform",
     "description": "Connected car cloud platform with remote vehicle control, OTA firmware updates, usage-based insurance data, and dealer service integration.",
     "compliance": ["UNECE R155/R156", "ISO 21434", "GDPR", "SOC 2"]},
    {"id": "030", "domain": "automotive", "name": "hmi_design_system",
     "description": "Automotive HMI design system with instrument cluster renderer, head-up display overlay, multi-modal input (touch, voice, gesture), and distraction-minimizing UX. ISO 15005.",
     "compliance": ["ISO 15005", "ISO 15008", "NHTSA Distraction Guidelines"]},

    # ── SAAS (031-040) ──
    {"id": "031", "domain": "saas", "name": "project_management",
     "description": "Project management SaaS with Kanban boards, Gantt charts, time tracking, resource allocation, sprint planning, and Slack/Jira integration.",
     "compliance": ["SOC 2", "GDPR", "ISO 27001"]},
    {"id": "032", "domain": "saas", "name": "crm_platform",
     "description": "CRM platform with contact management, sales pipeline, email automation, lead scoring, reporting dashboards, and Salesforce migration tools.",
     "compliance": ["SOC 2", "GDPR", "CCPA"]},
    {"id": "033", "domain": "saas", "name": "helpdesk_platform",
     "description": "Customer support helpdesk with ticket management, knowledge base, live chat, AI auto-response, SLA tracking, and multi-channel inbox (email, social, WhatsApp).",
     "compliance": ["SOC 2", "GDPR", "ISO 27001"]},
    {"id": "034", "domain": "saas", "name": "hr_management",
     "description": "HR management system with employee onboarding, PTO tracking, performance reviews, payroll integration, org chart, and compliance reporting.",
     "compliance": ["SOC 2", "GDPR", "Employment Law", "ADA"]},
    {"id": "035", "domain": "saas", "name": "document_collaboration",
     "description": "Real-time document collaboration platform with rich text editor, version history, commenting, permissions, templates, and AI writing assistant.",
     "compliance": ["SOC 2", "GDPR", "ISO 27001"]},
    {"id": "036", "domain": "saas", "name": "analytics_dashboard",
     "description": "Business analytics dashboard builder with data source connectors (PostgreSQL, BigQuery, Snowflake), drag-and-drop chart builder, scheduled reports, and embedding SDK.",
     "compliance": ["SOC 2", "GDPR", "ISO 27001"]},
    {"id": "037", "domain": "saas", "name": "form_builder",
     "description": "No-code form builder with conditional logic, file uploads, payment collection, webhook integrations, analytics, and embeddable widgets.",
     "compliance": ["SOC 2", "GDPR", "PCI DSS"]},
    {"id": "038", "domain": "saas", "name": "scheduling_app",
     "description": "Appointment scheduling SaaS with calendar sync, booking pages, team scheduling, payment collection, reminders, and CRM integration.",
     "compliance": ["SOC 2", "GDPR", "PCI DSS"]},
    {"id": "039", "domain": "saas", "name": "email_marketing",
     "description": "Email marketing platform with drag-and-drop template builder, audience segmentation, A/B testing, automation workflows, deliverability monitoring, and GDPR consent management.",
     "compliance": ["GDPR", "CAN-SPAM", "CCPA", "SOC 2"]},
    {"id": "040", "domain": "saas", "name": "api_gateway",
     "description": "API management platform with gateway proxy, rate limiting, API key management, developer portal, OpenAPI documentation, and usage analytics.",
     "compliance": ["SOC 2", "ISO 27001", "OAuth 2.0/OIDC"]},

    # ── ECOMMERCE (041-050) ──
    {"id": "041", "domain": "ecommerce", "name": "marketplace_platform",
     "description": "Multi-vendor ecommerce marketplace with seller onboarding, product listings, order management, payment splitting, reviews, and dispute resolution.",
     "compliance": ["PCI DSS", "GDPR", "Consumer Protection", "SOC 2"]},
    {"id": "042", "domain": "ecommerce", "name": "headless_storefront",
     "description": "Headless ecommerce storefront with React frontend, Shopify/Medusa backend, product search (Algolia), cart management, checkout, and SSR for SEO.",
     "compliance": ["PCI DSS", "GDPR", "WCAG 2.1"]},
    {"id": "043", "domain": "ecommerce", "name": "subscription_box",
     "description": "Subscription box ecommerce with product curation, recurring billing, skip/pause/cancel flow, referral program, and inventory management.",
     "compliance": ["PCI DSS", "GDPR", "FTC Auto-Renewal Rules"]},
    {"id": "044", "domain": "ecommerce", "name": "dropshipping_automation",
     "description": "Dropshipping automation platform with AliExpress/1688 product import, automated order forwarding, tracking sync, margin calculator, and multi-store management.",
     "compliance": ["Consumer Protection", "GDPR", "FTC Guidelines"]},
    {"id": "045", "domain": "ecommerce", "name": "grocery_delivery",
     "description": "Grocery delivery platform with real-time inventory, route optimization, shopper app, customer app, substitution logic, and slot-based delivery scheduling.",
     "compliance": ["PCI DSS", "GDPR", "Food Safety Regulations", "WCAG 2.1"]},
    {"id": "046", "domain": "ecommerce", "name": "product_recommendation",
     "description": "AI product recommendation engine with collaborative filtering, content-based filtering, real-time personalization, A/B testing, and Shopify/WooCommerce plugins.",
     "compliance": ["GDPR", "SOC 2", "ePrivacy Directive"]},
    {"id": "047", "domain": "ecommerce", "name": "inventory_management",
     "description": "Multi-channel inventory management with warehouse management, barcode scanning, stock forecasting, purchase order automation, and marketplace sync (Amazon, eBay, Shopify).",
     "compliance": ["SOC 2", "GDPR"]},
    {"id": "048", "domain": "ecommerce", "name": "loyalty_rewards",
     "description": "Customer loyalty and rewards platform with point earning/redemption, tier levels, referral tracking, birthday rewards, and POS integration.",
     "compliance": ["PCI DSS", "GDPR", "CCPA"]},
    {"id": "049", "domain": "ecommerce", "name": "price_optimization",
     "description": "Dynamic pricing optimization engine with competitor price monitoring, demand forecasting, price elasticity modeling, and automated repricing rules.",
     "compliance": ["Antitrust/Competition Law", "GDPR", "SOC 2"]},
    {"id": "050", "domain": "ecommerce", "name": "returns_management",
     "description": "Returns and exchange management platform with self-service portal, return label generation, warehouse receiving, refund automation, and analytics dashboard.",
     "compliance": ["Consumer Protection", "GDPR", "PCI DSS"]},

    # ── IOT (051-060) ──
    {"id": "051", "domain": "iot", "name": "smart_home_hub",
     "description": "Smart home hub platform with Zigbee/Z-Wave/Matter protocol support, device pairing, automation rules engine, voice assistant integration, and energy monitoring.",
     "compliance": ["IEC 62443", "Matter Standard", "FCC Part 15", "GDPR"]},
    {"id": "052", "domain": "iot", "name": "industrial_iot_platform",
     "description": "Industrial IoT platform for factory monitoring with MQTT/OPC-UA ingestion, real-time dashboards, predictive maintenance ML, alert management, and SCADA integration.",
     "compliance": ["IEC 62443", "ISO 27001", "NIST Cybersecurity Framework"]},
    {"id": "053", "domain": "iot", "name": "agriculture_monitoring",
     "description": "Smart agriculture IoT system with soil moisture sensors, weather station, irrigation automation, crop health imaging (NDVI), and yield prediction.",
     "compliance": ["IEC 62443", "FCC Part 15", "EPA Water Standards"]},
    {"id": "054", "domain": "iot", "name": "asset_tracking",
     "description": "IoT asset tracking with BLE beacons, GPS trackers, geofencing, real-time location system (RTLS), and supply chain visibility dashboard.",
     "compliance": ["IEC 62443", "FCC Part 15", "GDPR"]},
    {"id": "055", "domain": "iot", "name": "energy_management",
     "description": "Building energy management system with smart meter integration, HVAC optimization, solar panel monitoring, demand response, and carbon footprint tracking.",
     "compliance": ["IEC 62443", "ISO 50001", "ENERGY STAR"]},
    {"id": "056", "domain": "iot", "name": "water_quality_monitor",
     "description": "Water quality monitoring IoT system with pH, turbidity, dissolved oxygen, and conductivity sensors. Real-time alerting, trend analysis, and EPA compliance reporting.",
     "compliance": ["EPA Standards", "IEC 62443", "ISO 17025"]},
    {"id": "057", "domain": "iot", "name": "wearable_fitness",
     "description": "Fitness wearable platform with heart rate, SpO2, step counting, sleep tracking, workout detection, and health insights. BLE sync with mobile app.",
     "compliance": ["FCC Part 15", "CE Mark", "GDPR", "HIPAA"]},
    {"id": "058", "domain": "iot", "name": "cold_chain_monitor",
     "description": "Cold chain monitoring for pharmaceuticals with temperature/humidity sensors, GPS tracking, excursion alerting, audit trail, and GDP compliance.",
     "compliance": ["GDP", "WHO Technical Report", "21 CFR Part 211", "IEC 62443"]},
    {"id": "059", "domain": "iot", "name": "smart_parking",
     "description": "Smart parking IoT system with occupancy sensors, mobile app guidance, payment integration, reservation system, and city parking analytics.",
     "compliance": ["IEC 62443", "PCI DSS", "ADA Compliance", "FCC Part 15"]},
    {"id": "060", "domain": "iot", "name": "noise_monitoring",
     "description": "Environmental noise monitoring IoT network with decibel sensors, frequency analysis, source identification, compliance reporting, and citizen complaint correlation.",
     "compliance": ["EPA Noise Standards", "WHO Guidelines", "IEC 61672", "IEC 62443"]},

    # ── ML/AI (061-070) ──
    {"id": "061", "domain": "ml_ai", "name": "document_extraction",
     "description": "AI document extraction pipeline for invoices, receipts, and contracts with OCR, NER, table extraction, and structured JSON output. REST API with batch processing.",
     "compliance": ["SOC 2", "GDPR", "ISO 27001"]},
    {"id": "062", "domain": "ml_ai", "name": "voice_assistant",
     "description": "Custom voice assistant with wake word detection, ASR (speech-to-text), NLU intent classification, dialog management, and TTS response generation.",
     "compliance": ["GDPR", "CCPA", "Biometric Privacy Laws"]},
    {"id": "063", "domain": "ml_ai", "name": "content_moderation",
     "description": "AI content moderation system for UGC platforms with text toxicity detection, image NSFW classification, video analysis, appeal workflow, and human review queue.",
     "compliance": ["DSA (Digital Services Act)", "GDPR", "COPPA", "Section 230"]},
    {"id": "064", "domain": "ml_ai", "name": "recommendation_engine",
     "description": "Real-time ML recommendation engine with collaborative filtering, contextual bandits for exploration, feature store, A/B testing framework, and sub-100ms serving latency.",
     "compliance": ["GDPR", "ePrivacy Directive", "SOC 2"]},
    {"id": "065", "domain": "ml_ai", "name": "fraud_detection",
     "description": "Real-time fraud detection ML pipeline with transaction feature engineering, ensemble models (XGBoost + neural), explainability (SHAP), and case management dashboard.",
     "compliance": ["PCI DSS", "SOC 2", "GDPR", "Fair Lending Laws"]},
    {"id": "066", "domain": "ml_ai", "name": "chatbot_builder",
     "description": "No-code chatbot builder with RAG pipeline, custom knowledge base, multi-LLM support (GPT, Claude, Gemini), conversation analytics, and embeddable widget.",
     "compliance": ["SOC 2", "GDPR", "ISO 27001"]},
    {"id": "067", "domain": "ml_ai", "name": "image_generation",
     "description": "AI image generation service with Stable Diffusion backend, prompt engineering UI, style transfer, inpainting, upscaling, and asset library management.",
     "compliance": ["Copyright Law", "GDPR", "Content Safety Guidelines"]},
    {"id": "068", "domain": "ml_ai", "name": "anomaly_detection",
     "description": "Time-series anomaly detection platform for infrastructure monitoring with unsupervised ML, seasonality handling, alert deduplication, and root cause correlation.",
     "compliance": ["SOC 2", "ISO 27001"]},
    {"id": "069", "domain": "ml_ai", "name": "search_engine",
     "description": "Semantic search engine with vector embeddings, hybrid search (BM25 + vector), query understanding, auto-complete, faceted filtering, and relevance tuning console.",
     "compliance": ["GDPR", "SOC 2", "Accessibility Standards"]},
    {"id": "070", "domain": "ml_ai", "name": "translation_service",
     "description": "Neural machine translation service with 50+ language pairs, domain adaptation, terminology management, translation memory, and quality estimation scoring.",
     "compliance": ["GDPR", "SOC 2", "ISO 17100"]},

    # ── EDTECH (071-080) ──
    {"id": "071", "domain": "edtech", "name": "lms_platform",
     "description": "Learning management system with course builder, video hosting, quizzes, progress tracking, certificates, SCORM/xAPI compliance, and LTI integration.",
     "compliance": ["FERPA", "COPPA", "WCAG 2.1", "SCORM/xAPI"]},
    {"id": "072", "domain": "edtech", "name": "ai_tutor",
     "description": "AI-powered personal tutor with adaptive learning paths, Socratic questioning, multi-subject support, progress analytics, and parent dashboard.",
     "compliance": ["FERPA", "COPPA", "GDPR", "WCAG 2.1"]},
    {"id": "073", "domain": "edtech", "name": "coding_bootcamp",
     "description": "Interactive coding bootcamp platform with browser-based IDE, auto-grading, code review bot, project-based curriculum, and job placement tracking.",
     "compliance": ["FERPA", "SOC 2", "WCAG 2.1"]},
    {"id": "074", "domain": "edtech", "name": "language_learning",
     "description": "Language learning app with spaced repetition, speech recognition for pronunciation, conversational AI practice, gamification, and offline mode.",
     "compliance": ["GDPR", "COPPA", "WCAG 2.1"]},
    {"id": "075", "domain": "edtech", "name": "exam_proctoring",
     "description": "Online exam proctoring platform with webcam monitoring, screen recording, AI cheating detection, identity verification, and exam analytics.",
     "compliance": ["FERPA", "GDPR", "Biometric Privacy Laws", "ADA"]},
    {"id": "076", "domain": "edtech", "name": "school_erp",
     "description": "School ERP system with student enrollment, attendance tracking, grade management, timetable scheduling, parent communication, and fee collection.",
     "compliance": ["FERPA", "COPPA", "PCI DSS", "GDPR"]},
    {"id": "077", "domain": "edtech", "name": "flashcard_app",
     "description": "Collaborative flashcard app with spaced repetition algorithm, image/audio support, shared decks, study statistics, and cross-platform sync.",
     "compliance": ["GDPR", "COPPA", "WCAG 2.1"]},
    {"id": "078", "domain": "edtech", "name": "virtual_lab",
     "description": "Virtual science laboratory with 3D simulations for physics, chemistry, and biology experiments. Student collaboration, lab reports, and curriculum alignment.",
     "compliance": ["FERPA", "WCAG 2.1", "NGSS Alignment"]},
    {"id": "079", "domain": "edtech", "name": "skill_assessment",
     "description": "Skill assessment platform for hiring with adaptive testing, coding challenges, video interviews, anti-cheating measures, and candidate ranking with bias detection.",
     "compliance": ["EEOC Guidelines", "GDPR", "SOC 2", "Adverse Impact Analysis"]},
    {"id": "080", "domain": "edtech", "name": "course_marketplace",
     "description": "Course marketplace connecting instructors with learners. Instructor analytics, revenue sharing, review system, affiliate program, and corporate training licenses.",
     "compliance": ["SOC 2", "GDPR", "PCI DSS", "Tax Compliance"]},

    # ── CONSUMER APP (081-090) ──
    {"id": "081", "domain": "consumer_app", "name": "social_fitness",
     "description": "Social fitness app with workout sharing, challenges, leaderboards, trainer marketplace, nutrition tracking, and Apple Health/Google Fit integration.",
     "compliance": ["GDPR", "CCPA", "Apple/Google Health Data Policies"]},
    {"id": "082", "domain": "consumer_app", "name": "food_delivery",
     "description": "Food delivery app with restaurant discovery, menu browsing, cart management, real-time order tracking, driver assignment, and rating system.",
     "compliance": ["PCI DSS", "GDPR", "Food Safety Regulations", "Labor Law"]},
    {"id": "083", "domain": "consumer_app", "name": "dating_app",
     "description": "Dating app with profile creation, photo verification, matching algorithm, chat with video calls, safety features (block/report), and premium subscription.",
     "compliance": ["GDPR", "CCPA", "Age Verification Laws", "SOC 2"]},
    {"id": "084", "domain": "consumer_app", "name": "travel_planner",
     "description": "AI travel planner with itinerary generation, flight/hotel booking integration, budget tracking, group trip planning, and offline maps.",
     "compliance": ["PCI DSS", "GDPR", "Package Travel Directive", "SOC 2"]},
    {"id": "085", "domain": "consumer_app", "name": "meditation_app",
     "description": "Meditation and mindfulness app with guided sessions, sleep stories, breathing exercises, mood tracking, streak system, and Apple Watch companion.",
     "compliance": ["GDPR", "CCPA", "Health Data Privacy"]},
    {"id": "086", "domain": "consumer_app", "name": "recipe_app",
     "description": "Recipe and meal planning app with ingredient-based search, nutritional info, grocery list generation, step-by-step cooking mode, and social sharing.",
     "compliance": ["GDPR", "FDA Nutritional Label Guidelines"]},
    {"id": "087", "domain": "consumer_app", "name": "pet_care",
     "description": "Pet care app with vet appointment booking, vaccination reminders, pet health records, pet sitter marketplace, lost pet alerts, and community forums.",
     "compliance": ["GDPR", "CCPA", "PCI DSS", "SOC 2"]},
    {"id": "088", "domain": "consumer_app", "name": "event_platform",
     "description": "Event discovery and ticketing platform with event creation, ticket sales, seating charts, check-in app, and post-event analytics.",
     "compliance": ["PCI DSS", "GDPR", "Consumer Protection", "ADA"]},
    {"id": "089", "domain": "consumer_app", "name": "habit_tracker",
     "description": "Habit tracking app with streak management, reminders, statistics, social accountability groups, and integration with Apple Health and Google Fit.",
     "compliance": ["GDPR", "CCPA", "Apple/Google Health Policies"]},
    {"id": "090", "domain": "consumer_app", "name": "podcast_platform",
     "description": "Podcast hosting and listening platform with RSS import, analytics, monetization (ads, subscriptions), transcription, clip sharing, and discovery algorithm.",
     "compliance": ["GDPR", "CCPA", "DMCA", "SOC 2"]},

    # ── ENTERPRISE (091-100) ──
    {"id": "091", "domain": "enterprise", "name": "identity_platform",
     "description": "Enterprise identity and access management (IAM) with SSO (SAML, OIDC), MFA, RBAC, SCIM provisioning, audit logging, and compliance reporting.",
     "compliance": ["SOC 2", "ISO 27001", "NIST 800-63", "GDPR"]},
    {"id": "092", "domain": "enterprise", "name": "data_warehouse",
     "description": "Cloud data warehouse with ETL pipeline builder, SQL query engine, data catalog, lineage tracking, access control, and BI tool integration.",
     "compliance": ["SOC 2", "ISO 27001", "GDPR", "CCPA"]},
    {"id": "093", "domain": "enterprise", "name": "workflow_automation",
     "description": "Enterprise workflow automation platform with visual flow builder, 200+ app connectors, conditional logic, error handling, and execution monitoring.",
     "compliance": ["SOC 2", "ISO 27001", "GDPR"]},
    {"id": "094", "domain": "enterprise", "name": "contract_management",
     "description": "Contract lifecycle management with template library, clause extraction, redline comparison, e-signature, obligation tracking, and renewal alerting.",
     "compliance": ["eIDAS", "ESIGN Act", "SOC 2", "GDPR"]},
    {"id": "095", "domain": "enterprise", "name": "compliance_platform",
     "description": "GRC (Governance, Risk, Compliance) platform with control framework mapping (SOC 2, ISO 27001, GDPR), evidence collection, risk register, and audit management.",
     "compliance": ["SOC 2", "ISO 27001", "GDPR", "NIST CSF"]},
    {"id": "096", "domain": "enterprise", "name": "internal_comms",
     "description": "Enterprise internal communications platform with channels, threads, file sharing, video conferencing, employee directory, and IT admin controls.",
     "compliance": ["SOC 2", "ISO 27001", "GDPR", "Data Retention Policies"]},
    {"id": "097", "domain": "enterprise", "name": "procurement_system",
     "description": "Enterprise procurement system with purchase requisitions, vendor management, RFQ process, PO generation, invoice matching, and spend analytics.",
     "compliance": ["SOC 2", "SOX", "ISO 27001", "GDPR"]},
    {"id": "098", "domain": "enterprise", "name": "knowledge_management",
     "description": "Enterprise knowledge management with wiki, FAQ, decision tree, AI-powered search, content freshness scoring, and expertise directory.",
     "compliance": ["SOC 2", "ISO 27001", "GDPR"]},
    {"id": "099", "domain": "enterprise", "name": "visitor_management",
     "description": "Enterprise visitor management with pre-registration, kiosk check-in, badge printing, NDA signing, host notification, and evacuation list.",
     "compliance": ["GDPR", "SOC 2", "Physical Security Standards"]},
    {"id": "100", "domain": "enterprise", "name": "it_asset_management",
     "description": "IT asset management with device inventory, software license tracking, automated provisioning, lifecycle management, and security compliance scanning.",
     "compliance": ["SOC 2", "ISO 27001", "NIST 800-53", "SAM (ISO 19770)"]},
]


# ---------------------------------------------------------------------------
# YAML generators — create domain-appropriate solution files
# ---------------------------------------------------------------------------

def _generate_project_yaml(sol: dict, detected_domains: list, plan: list) -> dict:
    """Generate project.yaml for a solution."""
    task_types = sorted(set(t.get("task_type", "BACKEND") for t in plan))
    agent_roles = sorted(set(t.get("agent_role", "developer") for t in plan))

    return {
        "project_name": sol["name"],
        "display_name": sol["name"].replace("_", " ").title(),
        "version": "1.0.0",
        "domain": sol["domain"],
        "description": sol["description"],
        "detected_domains": detected_domains,
        "compliance_standards": sol["compliance"],
        "task_types": task_types,
        "agent_roles": agent_roles,
        "active_modules": [
            "dashboard", "analyst", "developer", "monitor",
            "approvals", "queue", "audit", "knowledge",
        ],
        "build": {
            "critic_threshold": 70,
            "hitl_level": "strict" if any(
                d in ["medtech", "automotive", "avionics"]
                for d in [sol["domain"]]
            ) else "standard",
            "max_critic_iterations": 3,
        },
        "integrations": ["github"],
        "theme": {
            "sidebar_bg": "#f0fdf4",
            "sidebar_text": "#166534",
            "badge_bg": "#dcfce7",
            "badge_text": "#15803d",
        },
    }


def _generate_prompts_yaml(sol: dict, plan: list) -> dict:
    """Generate prompts.yaml with role definitions for the solution's agents."""
    roles = {}
    agent_roles = sorted(set(t.get("agent_role", "developer") for t in plan))

    role_templates = {
        "developer": {
            "name": "Software Developer",
            "system_prompt": f"You are a senior software developer building {sol['name'].replace('_', ' ')}. "
                           f"Domain: {sol['domain']}. Compliance: {', '.join(sol['compliance'])}. "
                           f"Write clean, tested, production-ready code. Follow all applicable standards.",
        },
        "analyst": {
            "name": "Technical Analyst",
            "system_prompt": f"You are a technical analyst for {sol['name'].replace('_', ' ')}. "
                           f"Analyze logs, errors, and system behavior. Provide root cause analysis. "
                           f"Compliance context: {', '.join(sol['compliance'])}.",
        },
        "qa_engineer": {
            "name": "QA Engineer",
            "system_prompt": f"You are a QA engineer for {sol['name'].replace('_', ' ')}. "
                           f"Design test plans, write test cases, ensure coverage. "
                           f"Compliance testing for: {', '.join(sol['compliance'])}.",
        },
        "safety_engineer": {
            "name": "Safety Engineer",
            "system_prompt": f"You are a safety engineer for {sol['name'].replace('_', ' ')}. "
                           f"Perform FMEA, fault tree analysis, hazard assessment. "
                           f"Standards: {', '.join(sol['compliance'])}.",
        },
        "regulatory_specialist": {
            "name": "Regulatory Specialist",
            "system_prompt": f"You are a regulatory specialist for {sol['name'].replace('_', ' ')}. "
                           f"Ensure compliance with: {', '.join(sol['compliance'])}. "
                           f"Prepare documentation for regulatory submissions.",
        },
        "business_analyst": {
            "name": "Business Analyst",
            "system_prompt": f"You are a business analyst for {sol['name'].replace('_', ' ')}. "
                           f"Define requirements, user stories, and acceptance criteria. "
                           f"Domain: {sol['domain']}.",
        },
        "data_scientist": {
            "name": "Data Scientist",
            "system_prompt": f"You are a data scientist for {sol['name'].replace('_', ' ')}. "
                           f"Build ML models, data pipelines, and evaluation frameworks. "
                           f"Domain: {sol['domain']}.",
        },
        "ux_designer": {
            "name": "UX Designer",
            "system_prompt": f"You are a UX designer for {sol['name'].replace('_', ' ')}. "
                           f"Create wireframes, user flows, and accessibility-compliant interfaces.",
        },
        "devops_engineer": {
            "name": "DevOps Engineer",
            "system_prompt": f"You are a DevOps engineer for {sol['name'].replace('_', ' ')}. "
                           f"Build CI/CD pipelines, monitoring, and infrastructure.",
        },
        "product_manager": {
            "name": "Product Manager",
            "system_prompt": f"You are a product manager for {sol['name'].replace('_', ' ')}. "
                           f"Define roadmap, prioritize features, track success metrics.",
        },
        "technical_writer": {
            "name": "Technical Writer",
            "system_prompt": f"You are a technical writer for {sol['name'].replace('_', ' ')}. "
                           f"Create user guides, API docs, and training materials. "
                           f"Compliance documentation for: {', '.join(sol['compliance'])}.",
        },
        "marketing_strategist": {
            "name": "Marketing Strategist",
            "system_prompt": f"You are a marketing strategist for {sol['name'].replace('_', ' ')}. "
                           f"Market analysis, positioning, GTM strategy. Domain: {sol['domain']}.",
        },
        "financial_analyst": {
            "name": "Financial Analyst",
            "system_prompt": f"You are a financial analyst for {sol['name'].replace('_', ' ')}. "
                           f"Financial modeling, pricing strategy, unit economics.",
        },
        "legal_advisor": {
            "name": "Legal Advisor",
            "system_prompt": f"You are a legal advisor for {sol['name'].replace('_', ' ')}. "
                           f"Review contracts, draft policies, ensure compliance with: {', '.join(sol['compliance'])}.",
        },
        "operations_manager": {
            "name": "Operations Manager",
            "system_prompt": f"You are an operations manager for {sol['name'].replace('_', ' ')}. "
                           f"Create runbooks, define SLAs, plan capacity and incident response.",
        },
        "system_tester": {
            "name": "System Tester",
            "system_prompt": f"You are a system tester for {sol['name'].replace('_', ' ')}. "
                           f"E2E testing, performance testing, security scanning. "
                           f"Compliance validation for: {', '.join(sol['compliance'])}.",
        },
        "localization_engineer": {
            "name": "Localization Engineer",
            "system_prompt": f"You are a localization engineer for {sol['name'].replace('_', ' ')}. "
                           f"i18n setup, translation management, locale testing.",
        },
    }

    for role in agent_roles:
        if role in role_templates:
            roles[role] = role_templates[role]
        else:
            roles[role] = {
                "name": role.replace("_", " ").title(),
                "system_prompt": f"You are a {role.replace('_', ' ')} for {sol['name'].replace('_', ' ')}. "
                               f"Domain: {sol['domain']}. Compliance: {', '.join(sol['compliance'])}.",
            }

    return {"roles": roles}


def _generate_tasks_yaml(sol: dict, plan: list) -> dict:
    """Generate tasks.yaml with task type definitions."""
    task_types = {}
    for task in plan:
        tt = task.get("task_type", "BACKEND")
        if tt not in task_types:
            task_types[tt] = {
                "description": task.get("description", f"{tt} task"),
                "agent_role": task.get("agent_role", "developer"),
                "acceptance_criteria": task.get("acceptance_criteria", []),
                "depends_on": task.get("depends_on", []),
            }

    return {"task_types": task_types}


def _generate_regulations_md(sol: dict, detected_domains: list, plan: list) -> str:
    """Generate regulations.md with compliance requirements and plan evidence."""
    lines = [
        f"# Regulatory Compliance — {sol['name'].replace('_', ' ').title()}",
        f"",
        f"**Domain:** {sol['domain']}",
        f"**Solution ID:** {sol['id']}",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**HITL Level:** {'strict' if sol['domain'] in ('medtech', 'automotive', 'avionics') else 'standard'}",
        f"",
        f"---",
        f"",
        f"## 1. Applicable Standards",
        f"",
    ]
    for std in sol["compliance"]:
        lines.append(f"- **{std}**")

    lines.append("")
    lines.append("## 2. Domain Detection Results")
    lines.append("")
    if detected_domains:
        for d in detected_domains:
            name = d.get("domain", d) if isinstance(d, dict) else d
            lines.append(f"- {name}")
    else:
        lines.append(f"- {sol['domain']} (from solution definition)")

    lines.append("")
    lines.append("## 3. Compliance Task Coverage")
    lines.append("")
    lines.append("Tasks in the build plan that address compliance requirements:")
    lines.append("")
    lines.append("| Task | Type | Description | Compliance Relevance |")
    lines.append("|------|------|-------------|---------------------|")

    compliance_types = {"SAFETY", "COMPLIANCE", "REGULATORY", "SECURITY", "LEGAL",
                        "QA", "SYSTEM_TEST", "EMBEDDED_TEST"}
    compliance_tasks = [t for t in plan if t.get("task_type", "") in compliance_types]
    other_tasks = [t for t in plan if t.get("task_type", "") not in compliance_types]

    for task in compliance_tasks:
        desc = task.get("description", "")[:80]
        tt = task.get("task_type", "")
        step = task.get("step", "?")
        relevance = {
            "SAFETY": "Risk management, FMEA, hazard analysis",
            "COMPLIANCE": "Standards mapping, DHF, traceability",
            "REGULATORY": "Submission preparation, audit readiness",
            "SECURITY": "Threat modeling, penetration testing",
            "LEGAL": "Privacy, licensing, contracts",
            "QA": "Verification & validation",
            "SYSTEM_TEST": "End-to-end validation, performance",
            "EMBEDDED_TEST": "Hardware-in-the-loop verification",
        }.get(tt, "Quality assurance")
        lines.append(f"| Step {step} | {tt} | {desc} | {relevance} |")

    if not compliance_tasks:
        lines.append(f"| — | — | No compliance-specific tasks in plan | — |")

    lines.append("")
    lines.append(f"**Total tasks:** {len(plan)} | **Compliance tasks:** {len(compliance_tasks)} | "
                 f"**Coverage:** {len(compliance_tasks)/max(len(plan),1)*100:.0f}%")

    lines.append("")
    lines.append("## 4. Compliance Checklist")
    lines.append("")
    lines.append("| # | Requirement | Status | Evidence | Responsible Agent |")
    lines.append("|---|------------|--------|----------|-------------------|")
    for i, std in enumerate(sol["compliance"], 1):
        # Map standard to responsible agent
        agent = "regulatory_specialist"
        if "PCI" in std:
            agent = "safety_engineer"
        elif "HIPAA" in std or "GDPR" in std:
            agent = "legal_advisor"
        elif "ISO 26262" in std or "ASIL" in std:
            agent = "safety_engineer"
        elif "SOC" in std or "ISO 27001" in std:
            agent = "devops_engineer"
        lines.append(f"| {i} | {std} compliance verified | PENDING | Build plan includes relevant tasks | {agent} |")

    lines.append("")
    lines.append("## 5. Risk Assessment Summary")
    lines.append("")
    if sol["domain"] in ("medtech", "automotive", "avionics"):
        lines.append("**Risk Level:** HIGH — Safety-critical domain requiring strict HITL gates")
        lines.append("")
        lines.append("| Risk Category | Mitigation in Plan |")
        lines.append("|--------------|-------------------|")
        lines.append("| Patient/User Safety | SAFETY tasks with FMEA and hazard analysis |")
        lines.append("| Data Integrity | DATABASE tasks with audit trail requirements |")
        lines.append("| Cybersecurity | SECURITY tasks with threat modeling |")
        lines.append("| Regulatory Non-compliance | REGULATORY + COMPLIANCE tasks |")
        lines.append("| Software Defects | QA + SYSTEM_TEST + EMBEDDED_TEST tasks |")
    elif sol["domain"] in ("fintech",):
        lines.append("**Risk Level:** HIGH — Financial data and transactions require strict controls")
        lines.append("")
        lines.append("| Risk Category | Mitigation in Plan |")
        lines.append("|--------------|-------------------|")
        lines.append("| Financial Loss | SECURITY tasks with fraud detection |")
        lines.append("| Data Breach | SECURITY + COMPLIANCE tasks |")
        lines.append("| Regulatory Fine | REGULATORY + LEGAL tasks |")
        lines.append("| Service Disruption | DEVOPS + SYSTEM_TEST tasks |")
    else:
        lines.append("**Risk Level:** STANDARD — Compliance focus on data protection and quality")
        lines.append("")
        lines.append("| Risk Category | Mitigation in Plan |")
        lines.append("|--------------|-------------------|")
        lines.append("| Data Privacy | SECURITY + LEGAL tasks |")
        lines.append("| Service Quality | QA + SYSTEM_TEST tasks |")
        lines.append("| Compliance Gap | REGULATORY tasks (if applicable) |")

    lines.append("")
    lines.append("## 6. Agent Team Assignment")
    lines.append("")
    agent_counts = {}
    for task in plan:
        agent = task.get("agent_role", "developer")
        agent_counts[agent] = agent_counts.get(agent, 0) + 1
    lines.append("| Agent Role | Tasks Assigned | Team |")
    lines.append("|-----------|---------------|------|")
    team_map = {
        "developer": "Engineering", "qa_engineer": "Engineering",
        "system_tester": "Engineering", "devops_engineer": "Engineering",
        "analyst": "Analysis", "business_analyst": "Analysis",
        "financial_analyst": "Analysis", "data_scientist": "Analysis",
        "ux_designer": "Design", "product_manager": "Design",
        "regulatory_specialist": "Compliance", "legal_advisor": "Compliance",
        "safety_engineer": "Compliance",
        "operations_manager": "Operations", "technical_writer": "Operations",
        "marketing_strategist": "Operations",
    }
    for agent, count in sorted(agent_counts.items(), key=lambda x: -x[1]):
        team = team_map.get(agent, "Engineering")
        lines.append(f"| {agent} | {count} | {team} |")

    lines.append("")
    lines.append("## 7. Audit Trail")
    lines.append("")
    lines.append(f"- **Generated by:** SAGE Build Orchestrator v2.0")
    lines.append(f"- **Timestamp:** {datetime.now().isoformat()}")
    lines.append(f"- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize")
    lines.append(f"- **Approval gates:** All build artifacts subject to HITL approval")
    lines.append(f"- **Critic threshold:** 70/100 (actor-critic review required before human approval)")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_post(path: str, data: dict) -> dict:
    """POST to SAGE API."""
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def api_get(path: str) -> dict:
    """GET from SAGE API."""
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def build_solution(sol: dict, idx: int, total: int) -> dict:
    """Submit one solution to the Build Orchestrator and create its folder."""
    folder = os.path.join(BUILDS_DIR, sol["id"])
    os.makedirs(folder, exist_ok=True)

    print(f"\n[{idx}/{total}] {sol['id']} — {sol['domain']}/{sol['name']}")
    print(f"  Description: {sol['description'][:80]}...")

    # Step 1: Submit to Build Orchestrator via API
    print(f"  → POST /build/start ...", end=" ", flush=True)
    result = api_post("/build/start", {
        "product_description": sol["description"],
        "solution_name": sol["name"],
    })

    if result.get("error"):
        print(f"ERROR: {result['error'][:100]}")
        # Write error to folder
        with open(os.path.join(folder, "ERROR.txt"), "w") as f:
            f.write(f"Build start failed:\n{json.dumps(result, indent=2)}\n")
        return {"id": sol["id"], "status": "error", "error": result["error"]}

    run_id = result.get("run_id", "")
    print(f"run_id={run_id[:8]}...")

    # Step 2: Get full status (includes plan, domain detection, etc.)
    print(f"  → GET /build/status/{run_id[:8]}... ...", end=" ", flush=True)
    status = api_get(f"/build/status/{run_id}")
    plan = status.get("plan", [])
    print(f"{len(plan)} tasks")

    # Step 3: Get detected domains from status
    detected_domains = status.get("detected_domains", [])

    # Step 4: Generate solution files
    print(f"  → Generating YAML files ...", end=" ", flush=True)

    # project.yaml
    project_yaml = _generate_project_yaml(sol, detected_domains, plan)
    with open(os.path.join(folder, "project.yaml"), "w") as f:
        yaml.dump(project_yaml, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # prompts.yaml
    prompts_yaml = _generate_prompts_yaml(sol, plan)
    with open(os.path.join(folder, "prompts.yaml"), "w") as f:
        yaml.dump(prompts_yaml, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # tasks.yaml
    tasks_yaml = _generate_tasks_yaml(sol, plan)
    with open(os.path.join(folder, "tasks.yaml"), "w") as f:
        yaml.dump(tasks_yaml, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # build_plan.json
    with open(os.path.join(folder, "build_plan.json"), "w") as f:
        json.dump({"run_id": run_id, "status": status}, f, indent=2, default=str)

    # regulations.md
    with open(os.path.join(folder, "regulations.md"), "w") as f:
        f.write(_generate_regulations_md(sol, detected_domains, plan))

    print("done")

    # Step 5: Save final status (plan generated, awaiting human approval via web UI)
    with open(os.path.join(folder, "build_status.json"), "w") as f:
        json.dump(status, f, indent=2, default=str)

    return {
        "id": sol["id"],
        "domain": sol["domain"],
        "name": sol["name"],
        "run_id": run_id,
        "tasks": len(plan),
        "state": status.get("state", "awaiting_plan"),
        "compliance": sol["compliance"],
        "status": "ok",
    }


def main():
    parser = argparse.ArgumentParser(description="SAGE 100-Solution Scale Deployment")
    parser.add_argument("--start", type=int, default=1, help="Start solution number (1-100)")
    parser.add_argument("--end", type=int, default=100, help="End solution number (1-100)")
    parser.add_argument("--domain", type=str, help="Only build solutions for this domain")
    args = parser.parse_args()

    # Filter solutions
    solutions = SOLUTIONS
    if args.domain:
        solutions = [s for s in solutions if s["domain"] == args.domain]
    else:
        solutions = [s for s in solutions if args.start <= int(s["id"]) <= args.end]

    if not solutions:
        print("No solutions match the filter.")
        sys.exit(1)

    # Check backend health
    print("=" * 70)
    print("SAGE Framework — 100-Solution Scale Deployment")
    print("=" * 70)
    health = api_get("/health")
    if health.get("error"):
        print(f"ERROR: Backend not reachable at {BASE_URL}")
        print(f"  Start it with: make run PROJECT=starter")
        sys.exit(1)
    print(f"Backend: {health.get('status')} | LLM: {health.get('llm_provider')}")
    print(f"Building {len(solutions)} solutions ({solutions[0]['id']}–{solutions[-1]['id']})")
    print("=" * 70)

    start_time = time.time()
    results = []

    for i, sol in enumerate(solutions, 1):
        result = build_solution(sol, i, len(solutions))
        results.append(result)

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "=" * 70)
    print("DEPLOYMENT SUMMARY")
    print("=" * 70)
    ok = sum(1 for r in results if r["status"] == "ok")
    err = sum(1 for r in results if r["status"] == "error")
    print(f"Total: {len(results)} | Success: {ok} | Failed: {err}")
    print(f"Time: {elapsed:.1f}s ({elapsed/len(results):.1f}s/solution)")

    # Domain breakdown
    domains = {}
    for r in results:
        d = r.get("domain", "unknown")
        domains.setdefault(d, {"ok": 0, "err": 0})
        if r["status"] == "ok":
            domains[d]["ok"] += 1
        else:
            domains[d]["err"] += 1

    print(f"\nPer-domain results:")
    for d, counts in sorted(domains.items()):
        print(f"  {d:20s}: {counts['ok']} ok, {counts['err']} failed")

    # Save master report
    report_path = os.path.join(BUILDS_DIR, "deployment_report.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "success": ok,
            "failed": err,
            "elapsed_seconds": round(elapsed, 1),
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nFull report: {report_path}")

    # List folder structure
    print(f"\nFolder structure:")
    for sol in solutions[:5]:
        folder = os.path.join(BUILDS_DIR, sol["id"])
        files = os.listdir(folder) if os.path.exists(folder) else []
        print(f"  {sol['id']}/ ({sol['domain']}/{sol['name']}): {', '.join(sorted(files))}")
    if len(solutions) > 5:
        print(f"  ... and {len(solutions) - 5} more")


if __name__ == "__main__":
    main()
