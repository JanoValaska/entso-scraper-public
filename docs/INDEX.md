# ENTSO-E Data Scraper — Documentation Index

**Project:** ENTSO-E Data Collection System on AWS
**Owner:** Jan Valaska
**Last updated:** 2026-02-09

---

## Project Summary

AWS Lambda-based data collection system that scrapes electricity market data from the ENTSO-E Transparency Platform. The system uses EventBridge for scheduling, stores data as CSV in S3, and is fully config-driven (no code changes needed to add new data sources). All infrastructure is provisioned via Terraform with VPC networking and fck-nat for cost-effective internet egress.

---

## Documentation Structure

### Read Order (Start Here)

1. **INDEX.md** ← You are here
2. **source/BUSINESS_CASE_2025-02-06.md** — Original assignment requirements (immutable)
3. **PRD.md** — Product Requirements (WHAT and WHY)
4. **SPEC.md** — Engineering Specification (HOW to build)
5. **ARCHITECTURE.md** — System design and infrastructure
6. **DECISIONS.md** — Design decisions and rationale

---

## Document Descriptions

### docs/source/BUSINESS_CASE_2025-02-06.md
**Purpose:** Original assignment text (immutable)
**Contents:** Verbatim copy of the home assignment requirements
**Status:** Immutable — never edit, add new dated files if requirements change

---

### docs/PRD.md
**Purpose:** Product Requirements Document (WHAT/WHY)
**Contents:**
- Project goals and non-goals
- Functional requirements (FR1-FR6)
- Non-functional requirements (reliability, security, cost)
- User personas and use cases
- Acceptance criteria

**When to read:** To understand project scope, requirements, and success criteria

---

### docs/SPEC.md
**Purpose:** Engineering Specification (HOW)
**Contents:**
- Implementation details for each functional requirement
- Data contracts (CSV format, S3 structure)
- EventBridge event schema
- Testing strategy
- Lambda handler pseudocode
- Error scenarios

**When to read:** When implementing features or understanding technical behavior

---

### docs/ARCHITECTURE.md
**Purpose:** System architecture and infrastructure
**Contents:**
- AWS component overview
- VPC networking design (2 AZs, public/private subnets)
- fck-nat configuration
- Security architecture (IAM, SSM, S3)
- Terraform resources and variables
- Data flow diagrams
- Deployment architecture

**When to read:** When provisioning infrastructure or understanding system design

---

### docs/DECISIONS.md
**Purpose:** Design decision log
**Contents:**
- 29 key decisions with context, options, rationale, consequences
- Topics: language choice, configuration approach, security, networking, testing
- Traceable decision-making process

**When to read:** When understanding why specific approaches were chosen

---

## Key Technical Details

### Technology Stack
- **Language:** Python 3.11+
- **AWS Services:** Lambda, S3, EventBridge, SSM Parameter Store, VPC, CloudWatch
- **Infrastructure:** Terraform
- **Data Library:** entsoe-py (REST client for ENTSO-E API)
- **Networking:** fck-nat for cost-effective NAT

### Key Features
- **Config-driven:** Add new data sources via EventBridge rules (no code changes)
- **Flexible time parsing:** Supports relative (`-1d`, `+7d`) and absolute dates
- **Generic processing:** Works with any EntsoePandasClient method starting with `query_`
- **Production-ready patterns:** Remote Terraform state, SSM secrets, structured logging

---

## Quick Links

- **Original Assignment:** [source/BUSINESS_CASE_2025-02-06.md](source/BUSINESS_CASE_2025-02-06.md)
- **Requirements:** [PRD.md](PRD.md)
- **Technical Spec:** [SPEC.md](SPEC.md)
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Decisions:** [DECISIONS.md](DECISIONS.md)

---

## For New Contributors / AI Assistants

**Start by reading in this order:**
1. This INDEX.md (overview)
2. source/BUSINESS_CASE_2025-02-06.md (requirements)
3. PRD.md (what to build)
4. SPEC.md (how to build)
5. ARCHITECTURE.md (system design)
6. DECISIONS.md (why decisions were made)

**Important Rules (from .clinerules):**
- Never edit source/*.md files (they are immutable inputs)
- Ask questions when requirements are unclear
- All design decisions must be documented in DECISIONS.md
- Use requirement IDs (FR1, FR2, etc.) for traceability

---

**End of INDEX**
