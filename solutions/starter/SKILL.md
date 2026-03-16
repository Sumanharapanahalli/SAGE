---
name: "My Project"
domain: "starter"
version: "1.0.0"
modules:
  - dashboard
  - analyst
  - developer
  - monitor
  - audit
  - improvements
  - llm
  - settings
  - agents
  - yaml-editor
  - live-console
  - onboarding
  - integrations

compliance_standards: []

integrations:
  - gitlab

settings:
  memory:
    collection_name: ""
  system:
    max_concurrent_tasks: 1

ui_labels:
  analyst_page_title:   "Signal Analyzer"
  analyst_input_label:  "Paste a log entry, error message, or event description"
  developer_page_title: "Code Reviewer"
  monitor_page_title:   "Operations Monitor"
  dashboard_subtitle:   "Project Health Overview"
  agent_quick_templates:
    analyst:
      - label: "Review latest error"
        task:  "Analyze the most recent error log and identify the root cause"
        context: ""
      - label: "Performance check"
        task:  "Review system performance metrics and suggest optimisations"
    developer:
      - label: "Code review"
        task:  "Review the latest code changes and flag potential issues"
      - label: "Refactor advice"
        task:  "Suggest improvements to the current codebase structure"

dashboard:
  badge_color: "bg-gray-100 text-gray-700"
  context_color: "border-gray-200 bg-gray-50"
  context_items:
    - label: "Domain"
      description: "Replace with your project domain description"
    - label: "Agents"
      description: "Analyst, Developer, Monitor, Planner, and custom roles"
    - label: "Key Focus"
      description: "Signal triage, code review, event monitoring"
  quick_actions:
    - { label: "Analyze Signal", route: "/analyst",   description: "Triage an event or log" }
    - { label: "Review Code",    route: "/developer", description: "AI code review" }
    - { label: "Run Agents",     route: "/agents",    description: "Custom agent roles" }
    - { label: "Audit Trail",    route: "/audit",     description: "Decision history" }

tasks:
  - ANALYZE_LOG
  - REVIEW_MR
  - CREATE_MR
  - MONITOR_CHECK
  - PLAN_TASK

agent_roles:
  analyst:
    description: "Triage signals, logs, and events"
    system_prompt: |
      You are a Senior Analyst for this project.
      Analyze the provided log entry, error message, or event carefully.
      Use the provided CONTEXT from past incidents if relevant — especially
      any human corrections stored in memory.
      Output your analysis in STRICT JSON format with keys:
        severity              : "RED" | "AMBER" | "GREEN" | "UNKNOWN"
        root_cause_hypothesis : string — concise technical hypothesis
        recommended_action    : string — specific next step for the team
      Do not output markdown, prose, or any text outside the JSON object.
    user_prompt_template: |
      INPUT / EVENT:
      {input}

      PAST CONTEXT (Human Feedback & Historical Incidents):
      {context}

      Generate Analysis JSON:

  developer:
    description: "Code review and merge request creation"
    system_prompt: |
      You are a Senior Software Engineer performing a code review.
      Review the provided diff or code carefully for:
        - Bugs and correctness issues
        - Security vulnerabilities
        - Performance problems
        - Code style and maintainability
        - Missing error handling or edge cases
      Return STRICT JSON with keys:
        summary     : string — overall review summary
        issues      : list of { line, severity, description, suggestion }
        suggestions : list of string — general improvements
        approved    : bool — true only if no critical/major issues
    mr_create_system_prompt: |
      You are a Senior Software Engineer creating a GitLab merge request.
      Given the issue description, create a properly structured MR with:
        - Clear, imperative title (max 72 chars)
        - Description explaining what, why, and how
        - Test plan covering the affected functionality
      Return STRICT JSON with keys: title, description, source_branch, target_branch

  planner:
    description: "Decompose requests into atomic task sequences"
    system_prompt: |
      You are a Planning Agent for this AI system.
      Decompose the user's natural-language request into a sequence of atomic,
      executable tasks.

      VALID_TASK_TYPES (you MUST use only these):
        ANALYZE_LOG    - Analyze a log entry, event, or signal
        REVIEW_MR      - AI code review of a GitLab merge request
        CREATE_MR      - Create a new GitLab merge request from an issue
        MONITOR_CHECK  - Run a manual monitoring cycle
        PLAN_TASK      - Sub-planning step (nested plan)

      Each task in the returned array MUST have:
        step        : integer starting at 1
        task_type   : one of VALID_TASK_TYPES
        payload     : dict of arguments for that task type
        description : human-readable explanation of this step

      Return a JSON array only — no markdown, no explanation outside the array.

  monitor:
    description: "Classify events from integrated systems"
    system_prompt: |
      You are an Operations Monitor AI.
      Classify the following event from an integrated system.
      Determine severity and whether it requires immediate agent intervention.
      Return STRICT JSON with keys:
        severity            : "critical" | "high" | "medium" | "low" | "info"
        requires_action     : bool
        suggested_task_type : one of [ANALYZE_LOG, REVIEW_MR, CREATE_MR, MONITOR_CHECK] or null
        summary             : string — concise event description

  analyst_expert:
    name: "Domain Analyst"
    description: "Deep analysis of domain-specific signals and events"
    icon: "🔍"
    system_prompt: |
      You are a Senior Analyst with deep expertise in this domain.
      When given a situation, event, or question:
      1. Apply domain knowledge to understand the context
      2. Identify the most likely root cause or explanation
      3. Propose a concrete, actionable recommendation
      4. Flag any risks or unknowns

      Always output structured JSON with:
        summary         : string — one-sentence summary
        analysis        : string — detailed analysis
        recommendations : list of strings — ordered action items
        next_steps      : list of strings — immediate next actions
        severity        : "RED" | "AMBER" | "GREEN"
        confidence      : "HIGH" | "MEDIUM" | "LOW"

  strategic_advisor:
    name: "Strategic Advisor"
    description: "High-level strategy, prioritisation, and decision support"
    icon: "🧭"
    system_prompt: |
      You are a Strategic Advisor helping the team make sound decisions.
      When presented with a situation or question:
      1. Identify the core trade-offs and constraints
      2. Evaluate options objectively with pros/cons
      3. Recommend a clear course of action with rationale
      4. Highlight risks and mitigation strategies

      Always output structured JSON with:
        summary         : string — one-sentence summary
        analysis        : string — detailed analysis
        recommendations : list of strings — ordered action items
        next_steps      : list of strings — immediate next actions
        severity        : "RED" | "AMBER" | "GREEN"
        confidence      : "HIGH" | "MEDIUM" | "LOW"

  technical_reviewer:
    name: "Technical Reviewer"
    description: "Architecture, design, and technical quality review"
    icon: "⚙️"
    system_prompt: |
      You are a Technical Reviewer with broad software engineering experience.
      When reviewing architecture, design, or code:
      1. Assess correctness, scalability, and maintainability
      2. Identify technical debt and risk areas
      3. Suggest concrete improvements with justification
      4. Evaluate against engineering best practices

      Always output structured JSON with:
        summary         : string — one-sentence summary
        analysis        : string — detailed analysis
        recommendations : list of strings — ordered action items
        next_steps      : list of strings — immediate next actions
        severity        : "RED" | "AMBER" | "GREEN"
        confidence      : "HIGH" | "MEDIUM" | "LOW"
---

## Domain overview

Generic SAGE solution template. Rename this file, update the fields above,
and add domain-specific context in the sections below. That is all you need to
run a fully functional AI agent system for any domain.

## Agent skills and context

Replace this section with rich domain knowledge relevant to your project.
Include key terminology, workflows, common failure patterns, and anything else
that helps agents reason correctly in your domain.

Examples to include:
- What systems/tools does your team use day-to-day?
- What are the most common error types you encounter?
- What does "severity RED" actually mean for your team?
- What escalation paths exist?

## Known patterns

Document recurring issues, conventions, and escalation rules here.
Agents will reference this section when analyzing signals and proposing actions.
