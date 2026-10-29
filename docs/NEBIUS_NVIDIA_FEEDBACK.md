# Nebius Infrastructure & NVIDIA Nemotron Feedback

**Project:** Sixth Dimension (6D) — Mission Assurance & Dependency-Aware Recalculation for Space Systems  
**Hackathon Track:** Nebius AI Cloud & NVIDIA Open-Source Models  
**Live Application:** [https://sixthdimension.centralindia.cloudapp.azure.com](https://sixthdimension.centralindia.cloudapp.azure.com)  

---

### 1. What Was Used
* **Nebius Infrastructure:** Nebius Token Factory high-throughput inference endpoints (OpenAI-compatible REST API) powered by NVIDIA GPU clusters.
* **NVIDIA Models:**
  * `nvidia/Nemotron-3-Nano`: Used for low-latency single-check triage and fast conversational queries.
  * `nvidia/Nemotron-3-Super`: Our default engine for grounded telemetry review, subsystem analysis, and engineering check explanations.
  * `nvidia/Nemotron-3-Ultra`: For complex whole-project architectural audits, multi-stage tradeoff evaluations, and cross-discipline dependency explanations.
* **Architecture:** 6D pairs these models with an isolated, deterministic Python physics engine and SQLite ledger, using unsigned SHA-256 digests to ensure model reasoning remains grounded strictly in mathematically verified simulation receipts.

---

### 2. What Worked Well
* **Inference Speed & Reliability:** Nebius Token Factory delivered consistent, low latency. In our live qualification runs, multi-turn investigations across four complex space engineering cases completed 16 request reservations in ~31 seconds total observed latency with zero dropped connections.
* **Adherence to Grounded Numerical Evidence:** When provided with structured JSON receipts of calculated rocket telemetry (e.g., engine cutoff altitude, maximum dynamic pressure, structural margins), Nemotron Super and Ultra accurately cited authoritative numbers (e.g., `6,126.146 m compared with >= 5,000 m`) and explained why a check changed from Met to Unmet without altering the solver values.
* **Standardized API Contract:** The OpenAI-compatible endpoint design allowed us to build a pure Python standard-library transport (`urllib.request`) with zero third-party dependencies, keeping our deployment completely lightweight and reproducible.
* **Defense / Air-Gapped Viability:** Because the Nemotron family consists of open-weight models, our architecture validated on Nebius can also be deployed on-premise using Hugging Face TGI or vLLM for ITAR/EAR-compliant defense space operations.

---

### 3. What Failed / Challenges Encountered & How We Addressed Them
* **Output Token Ceilings on Comprehensive Audits:** In early whole-project reviews, Nemotron Super hit the 2,048-token generation ceiling when attempting to explain all subsystem criteria simultaneously in a single response turn. We resolved this by implementing bounded turn chunking, concise finish guidance, and progressive disclosure rather than monolithic responses.
* **Citation & Scope Guarding:** In early unconstrained prompts, Ultra occasionally repeated revision tags and referenced external NASA citations that were not part of the active saved project evidence, while Super occasionally omitted explicit scope boundaries. Rather than relaxing validation, we introduced client- and server-side acceptance guards: the application checks that every cited reference matches exact saved SHA-256 evidence digests before accepting the explanation.
* **Small-Model (Nano) JSON Schema Strictness:** Nano occasionally struggled with non-empty citation schemas in read-only wire contracts, leading to malformed arguments. We resolved this by simplifying generation schemas and requiring empty commentary fields for read-only actions, allowing Nano to complete without stripping arguments.
* **Session Budgeting on Deep Multi-Turn Reviews:** Ultra's extensive reasoning depth and multi-turn conversational context initially hit our conservative local development per-job reservation limit ($0.35 ceiling). For production hosting, we raised the visitor session budget ceiling to $3.00, enabling uninterrupted multi-turn audits while retaining strict per-job bounding.
* **Free-Form Prompt Rejections vs. Grounded Scoping:** When users asked broad conversational questions under an unconstrained "Whole project" scope, strict regex acceptance filters occasionally rejected valid explanations. We resolved this by focusing the UI directly on specific engineering checks ("Discuss check"), which guarantees Nemotron receives the exact physical criteria needed to formulate an approved, grounded explanation.
* **API Key Sanitization:** Initial connection attempts occasionally threw HTTP 401 errors due to trailing whitespaces or line-breaks during credential copy-pasting. We added strict whitespace trimming and input sanitization prior to local DPAPI encryption and token transport.

---

### 4. Onboarding Experience
* **Setup & Provisioning:** Creating a Nebius Token Factory account, generating API keys, and testing the endpoints took under 5 minutes.
* **Documentation & Pricing Transparency:** The token pricing and request parameter documentation made it easy to design our conservative client-side reservation accounting (capping tasks at $0.10 for Nano, $0.20 for Super, and $0.35 for Ultra) to prevent accidental overages during development.

---

### 5. Future Build Intent
* **Dedicated Nebius Cloud Instances:** As 6D scales to production, we intend to move from serverless Token Factory endpoints to dedicated Nebius GPU instances (H100/H200) running vLLM to support large batch sweeps across historical telemetry archives.
* **Aerospace Domain Fine-Tuning:** We plan to use Nebius AI Cloud training compute to fine-tune Nemotron-Nano and Super on open aerospace standards (NASA SP-8000, ECSS, and MIL-STD specifications) to specialize their audit explanations for launch vehicle qualification.
* **Autonomous Telemetry Anomaly Explanation:** We will expand real-time streaming integration so Nemotron can monitor live hardware-in-the-loop (HIL) test feeds and draft instant discrepancy reports.
