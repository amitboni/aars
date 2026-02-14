# Agent Activation & Retention System — Domain Foundation

## Document Purpose

This document is the source of truth for building an Agent Activation & Retention System for life insurance companies in India. It captures the domain reality (Phase 1) and the precise domain model (Phase 2) that all technical design must reference.

Every assumption is marked with `[ASSUMPTION]` for validation. Every number is marked with `[VALIDATE]` where it needs insurer-specific confirmation.

---

# PHASE 1: DOMAIN TRUTH

## 1.1 The Problem in Numbers

Indian life insurance operates on an agency distribution model where individual agents (licensed by IRDAI) sell policies on behalf of insurers.

- Total licensed agents across the industry: ~28 lakh (2.8 million) `[VALIDATE]`
- Active agent ratio (industry average): 2%–4%
- This means: for every 100 onboarded agents, 96–98 produce zero business in any given period
- Cost of onboarding one agent: ₹3,000–₹8,000 (training, exam fees, licensing, admin) `[VALIDATE]`
- Cost of maintaining an inactive agent on books: ₹200–₹500/year (compliance, communication, system costs) `[VALIDATE]`
- A mid-size insurer with 2 lakh agents and 4% active rate has 1,92,000 inactive agents costing ₹3.8–9.6 crore/year in maintenance alone — producing nothing
- If the system reactivates even 2% of dormant agents (3,840 agents), at an average premium of ₹15,000/policy and 1.5 policies/year, that's ₹8.6 crore in new premium `[VALIDATE: premium and policy assumptions]`

The economics are clear: even a modest improvement in activation/retention has massive ROI.

---

## 1.2 The People

### 1.2.1 THE AGENT

**Who they are:**

There is no single "agent persona." The agent population is deeply heterogeneous, and the system must handle this diversity. Here are the real archetypes:

**Archetype A: The Reluctant Recruit**
- Age: 22–30
- Profile: Recently graduated, couldn't find a job, someone told them "insurance mein paisa hai"
- Recruited by: ADM who had a recruitment target to meet
- Passed IRDAI exam: Barely, maybe on second attempt
- First 30 days: Sold one LIC-style endowment to a family member, couldn't close anyone else
- Current state: Dormant within 60 days of onboarding
- Phone: Android smartphone, uses WhatsApp and YouTube daily, comfortable with Hindi text
- Likelihood of reactivation: Low unless given structured hand-holding and early success
- What would bring them back: A guided first-sale experience — someone telling them exactly who to approach, what to say, how to fill the form
- `[ASSUMPTION: This is the largest archetype, ~40% of inactive pool]`

**Archetype B: The Multi-Insurer Agent**
- Age: 28–45
- Profile: Experienced in selling, licensed with 2–4 insurers simultaneously
- Active with: Whichever insurer pays better commissions this quarter or has easier products
- Current state with YOUR insurer: Inactive, but actively selling for a competitor
- Phone: Smartphone, uses multiple WhatsApp Business accounts, tech-comfortable
- Likelihood of reactivation: High IF you give them a reason (better commission, simpler product, faster issuance)
- What would bring them back: Commission comparison data, fast-track product training, streamlined proposal process
- `[ASSUMPTION: ~25% of inactive pool]`

**Archetype C: The Part-Timer**
- Age: 30–50
- Profile: Has a primary job (shopkeeper, teacher, government employee), does insurance on the side
- Sells: To their natural market (neighbors, relatives, colleagues) — maybe 2–5 policies/year
- Current state: Episodic — active during certain months (tax season, bonus time), dormant otherwise
- Phone: Smartphone, moderate WhatsApp user, prefers voice calls to reading
- Likelihood of reactivation: Medium — they come back naturally but could be nudged to sell more consistently
- What would bring them back: Timely reminders during buying seasons, ready-made pitches for their audience, low-effort renewal follow-ups
- `[ASSUMPTION: ~20% of inactive pool]`

**Archetype D: The Disillusioned Professional**
- Age: 35–55
- Profile: Was once a productive agent, sold 20–50 policies/year
- Why they stopped: Commission structure changed, claim got rejected and they lost face, ADM changed and new one doesn't engage, company launched complex products they don't understand
- Current state: Dormant but bitter — they have opinions about why the system failed them
- Phone: Smartphone, prefers calls, doesn't read long WhatsApp messages
- Likelihood of reactivation: High IF their specific grievance is addressed
- What would bring them back: Acknowledgment of the problem, specific resolution (training on new products, connection to responsive ADM, commission clarity)
- `[ASSUMPTION: ~10% of inactive pool, but highest value if reactivated]`

**Archetype E: The Gone-for-Good**
- Age: Any
- Profile: Moved cities, changed career completely, health issues, passed away, license expired and no interest in renewal
- Current state: Permanently inactive
- Likelihood of reactivation: Near zero
- System should: Identify them quickly and stop wasting outreach resources on them
- `[ASSUMPTION: ~5% of inactive pool, but important to classify correctly to avoid wasting effort]`

**Cross-cutting Agent Realities:**

- **Language**: Agents operate in their local language. A Tamil Nadu agent thinks in Tamil, sells in Tamil, and should be engaged in Tamil. Hindi is NOT universal — it works in the Hindi belt (UP, MP, Bihar, Rajasthan, Delhi NCR, Jharkhand, Chhattisgarh, Uttarakhand) but not in South or East India. Marathi in Maharashtra, Bangla in West Bengal, Kannada in Karnataka. The system MUST support at minimum: Hindi, English, Tamil, Telugu, Kannada, Marathi, Bangla, Malayalam, Gujarati. `[VALIDATE: priority languages based on insurer's geographic footprint]`

- **Literacy & Communication Preference**: Not all agents read comfortably. Many are comfortable with voice but not text. Some are comfortable with short WhatsApp text but not long documents. The system must profile each agent's actual communication preference, not assume it.

- **Time Availability**: Agents who have other jobs are available at specific times — evenings, weekends, lunch breaks. Agents who are full-time available during business hours. The system must learn each agent's reachable time window from actual interaction data, not from assumptions.

- **Trust**: Agents don't trust "the company." They trust their ADM (if the ADM has earned it), or they trust a specific person who recruited them. An AI voice calling from "the company" starts with negative trust. The system must build trust through consistency, relevance, and follow-through — if the system promises to send a training video, it must send it. If it says "your ADM will call," the ADM must call.

- **Smartphone Reality**: Most agents have entry-level Android phones (₹8,000–₹15,000 range). Storage is limited. They won't install new apps. WhatsApp works because it's already there. Video should be short (<3 min) and compressed. PDFs often don't render well. Images and short text work best. `[VALIDATE: phone demographics from insurer data]`


### 1.2.2 THE ADM (Agency Development Manager)

**Who they are:**

The ADM is the most critical person in this system and the most underserved by current technology.

**Reality of an ADM's day:**
- Wakes up at 7am. Checks WhatsApp — there are 40+ messages across various groups (company groups, team groups, personal)
- Plans the day: 2–3 agent meetings, maybe a joint call with a promising agent, maybe a recruitment drive
- Travels: Mostly by two-wheeler or local transport. In semi-urban/rural areas, an ADM might travel 30–80 km in a day between agent locations `[VALIDATE: travel patterns]`
- Meetings: Each agent meeting is 30–60 minutes. The ADM is coaching, motivating, sometimes helping fill proposals
- Phone calls: Makes 10–20 calls/day to agents — follow-ups, reminders, check-ins
- Reporting: Expected to update company CRM/LMS at end of day. Most ADMs either don't do this or do it perfunctorily because they're exhausted
- Evening: May have a team meeting or training session

**ADM Archetypes:**

**The High-Performer ADM**
- Manages: 150–250 agents
- Active agents: 15–30 (10–15% — well above average)
- Secret: They have a system. They know which agents to focus on. They follow up. They're essentially doing what our system should do, but manually and with limited bandwidth.
- What they need: Scale. Help them apply their instincts to more agents. Handle the routine engagement so they can focus on high-value personal interactions.
- `[ASSUMPTION: ~15% of ADMs]`

**The Average ADM**
- Manages: 150–250 agents
- Active agents: 5–10 (3–5%)
- Reality: Overwhelmed. Doesn't know where to start. Focuses on the 5 agents who are already active because that's where immediate commission comes from. Ignores the 200+ dormant agents because engaging them feels futile.
- What they need: Prioritized action list. "These 5 agents showed signals this week — call them first." Remove decision fatigue.
- `[ASSUMPTION: ~60% of ADMs]`

**The Struggling ADM**
- Manages: 100–200 agents
- Active agents: 0–3
- Reality: May be close to being terminated themselves. Either new to the role, wrong fit, or demoralized. 
- What they need: More hand-holding than they can give. The system may need to compensate for their absence — engaging agents directly and escalating to Regional Manager when ADM is unresponsive.
- `[ASSUMPTION: ~25% of ADMs]`

**ADM Technology Reality:**
- Phone: Android smartphone, usually mid-range (₹12,000–₹20,000)
- Primary tool: WhatsApp. Not email. Not a web portal. WhatsApp.
- They ARE in company WhatsApp groups but these are noisy and mostly ignored
- They check company apps only when forced (e.g., to submit attendance or download commission statement)
- They are NOT going to log into a dashboard. Ever. Unless their manager asks them to show a specific number during a review meeting.
- They will respond to WhatsApp messages that are short, actionable, and relevant
- They will listen to voice notes (WhatsApp voice notes are a natural format for them)

**What the system must understand about ADMs:**
The ADM is not a "user of a portal." The ADM is a field professional whose attention is the scarcest resource in the system. Every interaction the system has with an ADM must pass this test: "Is this worth interrupting their day for?" If the answer is no, don't send it.


### 1.2.3 THE REGIONAL / ZONAL MANAGER

- Manages: 8–15 ADMs, covering a geographic zone `[VALIDATE: span of control]`
- Focuses on: Numbers — activation rate, premium collection, recruitment, persistency
- Technology: Has a laptop. Will use a dashboard if it's simple and shows what they need
- Meetings: Weekly review with ADMs, monthly review with HQ
- Key need: Which ADMs need help? Which regions are underperforming? What's the trend?
- Decision power: Can approve campaigns, reallocate agents between ADMs, recommend ADM training
- They're the bridge between ground reality and HQ strategy


### 1.2.4 INSURER HQ

Multiple teams care about this system's output:

**Distribution Team:**
- Cares about: Activation rates, agent productivity, ADM effectiveness, channel performance
- Needs: Aggregate dashboards, trend analysis, regional comparisons
- Decision power: Commission structures, recruitment policies, ADM targets

**Product Team:**
- Cares about: Which products agents can and can't sell, where product knowledge gaps exist
- Needs: Product-wise confidence scores from agent interactions, training completion by product
- Decision power: Product simplification, training content creation, product launch strategy

**Training Team:**
- Cares about: Training effectiveness — does training lead to sales?
- Needs: Training completion rates, score distributions, correlation between training and first-sale
- Decision power: Training content, delivery format, certification requirements

**Compliance Team:**
- Cares about: Regulatory compliance, consent management, data privacy
- Needs: Audit trails, consent records, communication logs
- Decision power: Communication policies, data retention, opt-out enforcement

---

## 1.3 Current State: What Happens Today

### 1.3.1 Agent Onboarding (Current)

```
Day 0:    Recruited by ADM (often at a "career seminar" or personal referral)
Day 1-15: IRDAI pre-licensing training (classroom or online, 25-50 hours)
Day 16-20: IRDAI exam (multiple choice, ~60% pass rate on first attempt)
Day 21-30: License issued, agent code generated in insurer's system
Day 30-45: "Induction training" by insurer — product basics, how to use the app
Day 45+:  Agent is expected to start selling

REALITY: By day 45, most agents have already lost momentum. The gap between 
exam and first meaningful customer interaction is too long. The induction 
training is generic. No one helps them identify their first prospect or 
practice their first pitch.
```
`[VALIDATE: onboarding timeline with specific insurer]`

### 1.3.2 Agent Engagement (Current)

```
What SHOULD happen:
- ADM meets agent weekly
- Regular product training updates
- Performance tracking and feedback
- Joint customer calls for struggling agents

What ACTUALLY happens:
- ADM focuses on top 5-10 agents who are already producing
- Dormant agents get: occasional SMS blasts, quarterly "reactivation drives" 
  that are actually just mass calling with no personalization
- Training is classroom-based, infrequent, and in the wrong language
- Agent has no idea where they stand or what to do next
- Company communication is broadcast, not personalized
```

### 1.3.3 The Dormancy Spiral (Current)

```
Week 1-4 post-onboarding: Agent tries to sell, fails 3-4 times → confidence drops
Week 5-8:   Agent stops trying, ADM doesn't notice (too many agents to track)
Week 9-12:  Agent's number goes into "dormant" bucket in system reports
Month 4-6:  Company sends generic "reactivation" SMS → agent ignores
Month 7-12: Agent is forgotten. Maybe gets a mass WhatsApp during festival season.
Year 2:     License renewal comes up → agent doesn't renew → permanently gone

THE MISSED WINDOW: The most recoverable moment is Week 4-8, when the agent 
has tried and failed but hasn't given up yet. Currently, no one intervenes 
during this window because no one knows it's happening.
```

### 1.3.4 Data Landscape (Current)

| System | What It Holds | State of Data | Accessibility |
|--------|---------------|---------------|---------------|
| PAS (Policy Admin System) | Policy data, premium, agent-policy linkage | Structured, reliable | API available (usually legacy SOAP/REST) |
| LMS (License Management) | Agent license status, renewal dates | Structured | Often batch export only |
| Commission System | Commission calculations, payouts | Structured | Monthly batch files |
| CRM (if exists) | Agent contact info, activity logs | Often stale, poorly maintained | Varies widely |
| Training Platform (if exists) | Course completion, exam scores | Partial — many trainings are offline | Limited API |
| ADM Reports | Agent meeting logs, activity reports | Mostly manual, unreliable | Paper/Excel |
| WhatsApp Groups | Informal communication, announcements | Unstructured, noisy | Not captured |

`[VALIDATE: specific systems and their APIs for target insurer]`

**Key data gaps today:**
- No record of WHY an agent is inactive (no dormancy reason captured)
- No record of agent-ADM interaction quality or frequency
- No measurement of agent product knowledge or confidence
- No unified timeline of all interactions with an agent across channels
- No real-time signal of agent engagement (everything is batch, delayed by days/weeks)

---

## 1.4 Regulatory & Compliance Reality

### IRDAI (Insurance Regulatory Authority)
- Agent must hold valid IRDAI license (renewed every 3 years `[VALIDATE]`)
- Minimum training hours required for license renewal (25 hours `[VALIDATE]`)
- Agent can represent only one life insurer at a time (but can hold licenses for life + general + health separately)
- Mis-selling regulations: agent must explain product suitability
- `[ASSUMPTION: IRDAI doesn't currently regulate AI-based agent communication specifically, but this may change]`

### TRAI (Telecom Regulatory Authority)
- Calling hours: 9:00 AM – 9:00 PM only (for commercial/promotional calls)
- DND (Do Not Disturb) registry: Must scrub against NCPR before calling
- Transactional calls (appointment reminders, service follow-ups) have different rules than promotional calls
- `[ASSUMPTION: Agent engagement calls classify as "service" not "promotional" — needs legal validation]`

### DPDP Act (Digital Personal Data Protection)
- Explicit consent required for data processing
- Purpose limitation: data collected for one purpose can't be used for another without consent
- Right to erasure: agent can request deletion of their data
- Data localization requirements: personal data of Indian residents must be stored in India
- `[VALIDATE: specific DPDP requirements as rules are still being finalized as of 2025]`

### WhatsApp Business API Compliance
- Message templates must be pre-approved by Meta
- 24-hour window: after agent sends a message, you have 24 hours to respond freely; outside this window, only pre-approved templates
- Opt-in required before sending messages
- Business verification required for each WhatsApp Business Account

---

## 1.5 Technology Constraints on the Ground

**Network reality:**
- Tier-1 cities: Reliable 4G/5G, consistent connectivity
- Tier-2 cities: Mostly reliable 4G, occasional drops
- Semi-urban/rural: Patchy connectivity, 3G/4G mix, calls may drop
- Implication: Voice AI calls must handle poor network gracefully. WhatsApp works well even on poor networks (messages queue and deliver when connectivity returns).

**Device reality:**
- Entry-level Android phones: 2-3 GB RAM, 32 GB storage (often nearly full)
- No app installs: Agents won't install a new app. Period. The 3-4 who would are already active.
- WhatsApp is universal: 95%+ smartphone users have it `[VALIDATE]`
- Voice calls: Universal. Even feature phone users can receive voice calls.
- SMS: Universal but largely ignored (high spam, low engagement)

**Language technology reality:**
- Hindi ASR (Automatic Speech Recognition): Good quality available (Sarvam, Bhashini, Google)
- South Indian language ASR: Improving but less accurate than Hindi
- Code-switching: Agents frequently mix Hindi/English or regional language/English. ASR must handle this.
- TTS (Text-to-Speech): Hindi quality is good. South Indian languages are serviceable but not natural-sounding yet.
- `[VALIDATE: current quality of ASR/TTS for target languages with chosen providers]`

---

---

# PHASE 2: DOMAIN MODEL

## 2.1 Entity Map

```
                        ┌──────────────┐
                        │   INSURER    │
                        │  (Tenant)    │
                        └──────┬───────┘
                               │ has many
                    ┌──────────┼──────────┐
                    │          │          │
              ┌─────▼───┐ ┌───▼────┐ ┌───▼─────┐
              │ REGION  │ │PRODUCT │ │TRAINING │
              │HIERARCHY│ │CATALOG │ │ CONTENT │
              └─────┬───┘ └───┬────┘ └────┬────┘
                    │         │           │
              ┌─────▼────┐    │     ┌─────▼──────┐
              │   ADM    │    │     │  LEARNING  │
              │ (User)   │    │     │  PATHWAY   │
              └─────┬────┘    │     └─────┬──────┘
                    │ manages  │           │ assigned to
              ┌─────▼────┐    │     ┌─────▼──────┐
              │  AGENT   │◄───┘     │  TRAINING  │
              │          │──────────│ PROGRESS   │
              └─────┬────┘ sells    └────────────┘
                    │
         ┌──────────┼──────────────┐
         │          │              │
   ┌─────▼───┐ ┌───▼─────┐ ┌─────▼──────┐
   │ SIGNAL  │ │CONVERSA-│ │  AGENT     │
   │ STREAM  │ │  TION   │ │UNDERSTANDING│
   └─────┬───┘ └───┬─────┘ └─────┬──────┘
         │         │              │
         │    ┌────▼────┐        │
         └───►│LIFECYCLE│◄───────┘
              │  STATE  │
              └────┬────┘
                   │ informs
              ┌────▼──────┐
              │ DECISION  │
              │  ENGINE   │
              └────┬──────┘
                   │ produces
         ┌─────────┼─────────┐
         │         │         │
   ┌─────▼──┐ ┌───▼────┐ ┌──▼──────┐
   │PLAYBOOK│ │  ADM   │ │FEEDBACK │
   │EXECUTION│ │ NUDGE  │ │TO HQ    │
   └────────┘ └────────┘ └─────────┘
```

**Key relationships:**
- An Insurer (Tenant) contains everything — all data is tenant-scoped
- A Region Hierarchy defines the geographic org structure: Zone → Region → Branch → Area
- An ADM belongs to one or more Areas and manages Agents in those Areas
- An Agent has one primary ADM (but this can change)
- An Agent accumulates Signals over time from all channels
- Signals flow into a unified Signal Stream (append-only event log)
- The Agent Understanding is a derived, continuously-updated profile built from Signals
- Lifecycle State is computed from Signals and Agent Understanding (not manually set)
- The Decision Engine reads Lifecycle State + Agent Understanding to determine next action
- Actions manifest as Playbook Executions (engagement sequences), ADM Nudges, or HQ Feedback

---

## 2.2 Semantic Type Registry

These are the domain-specific types that every field in the system maps to. These are NOT database column types — they carry meaning, validation, and behavior.

### 2.2.1 Identity Types

```yaml
TenantId:
  base: UUIDv4
  immutable: true  # never changes after creation
  description: "Uniquely identifies an insurer on the platform"

AgentId:
  base: UUIDv4
  immutable: true
  description: "System-generated unique identifier for an agent"

AgentCode:
  base: String
  format: "Tenant-defined pattern (e.g., 'AG' + 8 digits)"
  scope: "Unique within tenant, NOT globally unique"
  source: "Imported from insurer's PAS"
  description: "The agent's code as known in the insurer's systems"
  validation: "Pattern varies by insurer — stored in tenant config"

ADMId:
  base: UUIDv4
  immutable: true
  description: "Identifies an ADM user"

UserId:
  base: UUIDv4
  immutable: true
  description: "Identifies any user of the platform (ADM, Regional Mgr, HQ user)"

RegionNodeId:
  base: UUIDv4
  description: "Identifies a node in the region hierarchy (zone, region, branch, area)"

TrainingModuleId:
  base: UUIDv4
  immutable: true
  description: "Identifies a training module"

PlaybookExecutionId:
  base: UUIDv4
  immutable: true
  description: "Identifies a specific execution instance of a playbook"

SignalId:
  base: UUIDv4
  immutable: true
  description: "Identifies a single signal event in the signal stream"

ConversationId:
  base: UUIDv4
  immutable: true
  description: "Identifies a conversation thread with an agent"

PlaybookId:
  base: UUIDv4
  immutable: true
  description: "Identifies a playbook definition"
```

### 2.2.2 Personal Information Types

```yaml
PersonName:
  base: String
  max_length: 200
  description: "Full name as recorded in insurer systems"
  note: "May be in any script — Devanagari, Tamil, etc."
  pii: true

IndianMobileNumber:
  base: String
  format: "+91XXXXXXXXXX" (E.164, always 10 digits after country code)
  regex: '^\+91[6-9]\d{9}$'
  validation: "Must start with 6, 7, 8, or 9 after +91"
  pii: true
  description: "Indian mobile number — primary contact for agents and ADMs"

EmailAddress:
  base: String
  format: RFC5322
  normalization: lowercase
  pii: true
  optional: true  # Many agents don't have email or don't check it

IndianPAN:
  base: String
  format: "[A-Z]{5}[0-9]{4}[A-Z]"
  regex: '^[A-Z]{5}\d{4}[A-Z]$'
  pii: true
  sensitivity: HIGH  # encrypted at rest, field-level access control
  description: "Permanent Account Number — tax identity"

AadhaarNumber:
  base: String
  format: "12 digits with Verhoeff checksum"
  regex: '^\d{12}$'
  pii: true
  sensitivity: HIGH  # encrypted at rest, NEVER displayed in full
  display_format: "XXXX-XXXX-{last4}"
  description: "Aadhaar — biometric identity"

IrdaiLicenseNumber:
  base: String
  format: "Insurer-prefixed alphanumeric"
  pii: false  # public registry
  description: "IRDAI license number for the agent"
```

### 2.2.3 Temporal Types

```yaml
Timestamp:
  base: ISO8601
  timezone: "Always stored as UTC"
  display: "Converted to tenant timezone for display"
  description: "Point in time — all system events recorded in UTC"

CalendarDate:
  base: ISO8601 date (YYYY-MM-DD)
  description: "Date without time — used for policy dates, license expiry, etc."

TimeOfDay:
  base: "HH:MM in 24-hour format"
  timezone: "Always in agent's local timezone"
  description: "Used for reachability patterns, contact preferences"

TimeWindow:
  base: "{start: TimeOfDay, end: TimeOfDay, timezone: IANATimezone}"
  description: "A window of time — used for TRAI-compliant calling hours, agent availability"
  example: "{start: '10:00', end: '13:00', timezone: 'Asia/Kolkata'}"

DurationSeconds:
  base: Integer (positive)
  description: "Duration in seconds — used for call duration, training video length"

DaysSince:
  base: Integer (non-negative)
  computed: true
  description: "Derived field — number of days since a reference event (last sale, last contact, etc.)"
```

### 2.2.4 Domain-Specific Types

```yaml
Language:
  base: ISO 639-1 code
  allowed_values: [hi, en, ta, te, kn, mr, bn, ml, gu, pa, or, as]
  description: "Language for communication"
  note: "Agent may have multiple — detected language may differ from registered language"

LanguagePreference:
  base: "{registered: Language, detected: Language[], preferred: Language}"
  description: "Captures the gap between what's on file and what the agent actually speaks"

AgentLifecycleState:
  base: Enum
  values:
    - ONBOARDED        # Recruited, pre-exam
    - LICENSED         # Passed exam, has IRDAI license, hasn't sold
    - FIRST_SALE       # Made first policy sale
    - ACTIVE           # Regular selling activity (definition: tenant-configurable)
    - PRODUCTIVE       # Consistently exceeding targets
    - AT_RISK          # Showing declining signals
    - DORMANT          # No activity for X days (tenant-configurable threshold)
    - LAPSED           # License expired or surrendered
    - TERMINATED       # Removed by insurer (compliance, fraud, etc.)
  computed: true  # Derived from signals, never manually set
  description: "The agent's current position in their lifecycle"

DormancyReasonCode:
  base: Enum (hierarchical — see Section 2.5)
  source: "Derived from Voice AI conversations, WhatsApp interactions, and system signals"
  description: "Structured reason for why an agent is inactive"
  note: "An agent may have multiple contributing reasons"

EngagementScore:
  base: Float (0.0 to 100.0)
  computed: true
  description: "Composite score reflecting agent's engagement level"
  components: "call_answer_rate, whatsapp_response_rate, training_completion, recency_of_interaction"
  decay: "Score decays over time without new positive signals"

ReactivationProbability:
  base: Float (0.0 to 1.0)
  computed: true
  model: "ML model trained on historical reactivation data"
  description: "Predicted probability that this agent will become active in the next 90 days"

ProductConfidenceScore:
  base: Float (0.0 to 100.0)
  per_product: true
  computed: true
  description: "How confident/knowledgeable the agent is about a specific product"
  sources: "Training quiz scores, conversation analysis, sales history"

Money:
  base: "{amount: Decimal(12,2), currency: 'INR'}"
  description: "Monetary amount — always in INR for Indian market"
  note: "Currency field exists for future multi-market expansion but defaults to INR"

CommissionAmount:
  base: Money
  description: "Commission earned or projected"
  context: "Always scoped to a time period and product"

Premium:
  base: Money
  description: "Insurance premium amount"
  variants: "annualized, modal (monthly/quarterly/half-yearly/annual)"

ContactOutcome:
  base: Enum
  values:
    - ANSWERED           # Agent picked up / responded
    - NOT_ANSWERED       # Call not picked up / message not read
    - BUSY               # Agent busy, asked to call back
    - SWITCHED_OFF       # Phone switched off
    - WRONG_NUMBER       # Number no longer belongs to agent
    - DND_BLOCKED        # Blocked by DND/NCPR registry
    - OPTED_OUT          # Agent explicitly opted out
    - COMPLETED          # Conversation completed successfully
    - PARTIAL            # Conversation started but cut short
    - FAILED_TECHNICAL   # Technical failure (network, API error)
  description: "Outcome of any contact attempt"

SentimentLabel:
  base: Enum
  values: [POSITIVE, NEUTRAL, NEGATIVE, FRUSTRATED, INTERESTED, CONFUSED]
  computed: true
  source: "NLU analysis of conversation"
  description: "Detected emotional tone — more nuanced than positive/negative"

ChannelType:
  base: Enum
  values:
    - VOICE_AI          # Automated voice call
    - WHATSAPP_BOT      # WhatsApp automated message
    - WHATSAPP_ADM      # WhatsApp message from/attributed to ADM
    - ADM_CALL          # ADM made a personal phone call (logged by system)
    - ADM_VISIT         # ADM visited in person (logged by ADM)
    - SMS               # SMS message
    - EMAIL             # Email
    - SELF_SERVICE      # Agent accessed training/portal themselves
  description: "Communication channel used"

ConsentStatus:
  base: Enum
  values:
    - NOT_ASKED         # Consent not yet requested
    - GRANTED           # Agent gave explicit consent
    - DENIED            # Agent explicitly refused
    - REVOKED           # Agent had granted but later revoked
    - EXPIRED           # Consent expired (time-bound)
  per_channel: true     # Separate consent per channel
  description: "Agent's consent status for communication on a specific channel"
```

### 2.2.5 Region & Organization Types

```yaml
RegionHierarchyLevel:
  base: Enum
  values: [ZONE, REGION, BRANCH, AREA]
  description: "Levels in the geographic org structure"
  note: "Exact hierarchy may vary by insurer — some have 3 levels, some have 5"

RegionNode:
  base: "{id: RegionNodeId, name: String, level: RegionHierarchyLevel, parent: RegionNodeId?, tenant: TenantId}"
  description: "A node in the insurer's geographic org tree"

SubscriptionTier:
  base: Enum
  values: [TRIAL, STARTER, PROFESSIONAL, ENTERPRISE]
  description: "Insurer's subscription level — controls feature access and quotas"
```

---

## 2.3 Agent Lifecycle State Machine

This is the most important model in the entire system. Every other component references it.

### 2.3.1 State Definitions

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT LIFECYCLE                                 │
│                                                                         │
│  ┌──────────┐    exam     ┌──────────┐   1st sale  ┌───────────┐       │
│  │ONBOARDED │───passed───►│ LICENSED │────────────►│FIRST_SALE │       │
│  └──────────┘             └──────────┘             └─────┬─────┘       │
│       │                        │                         │              │
│       │                        │ no sale in              │ consistent   │
│       │ didn't                 │ X days                  │ activity     │
│       │ attempt exam           │                         ▼              │
│       │                        │                   ┌──────────┐        │
│       │                        │                   │  ACTIVE  │        │
│       │                        ▼                   └────┬─────┘        │
│       │                   ┌──────────┐                  │              │
│       │                   │          │    declining      │ exceeds     │
│       │                   │          │◄───signals───────┤ targets     │
│       │                   │ AT_RISK  │                  │              │
│       │                   │          │                  ▼              │
│       │                   │          │           ┌────────────┐        │
│       │                   └────┬─────┘           │PRODUCTIVE │        │
│       │                        │                  └──────┬─────┘       │
│       │                        │ no activity             │             │
│       │                        │ for Y days              │ declining   │
│       │                        ▼                         │             │
│       │              ┌─────────────┐                     │             │
│       └─────────────►│   DORMANT   │◄────────────────────┘             │
│                      └──────┬──────┘                                    │
│                             │                                           │
│                    ┌────────┼────────┐                                  │
│                    │        │        │                                  │
│                    ▼        │        ▼                                  │
│              re-engages     │   ┌──────────┐                           │
│              (→ back to     │   │  LAPSED  │  (license expired)        │
│               appropriate   │   └──────────┘                           │
│               state)        │                                          │
│                             ▼                                           │
│                      ┌─────────────┐                                    │
│                      │ TERMINATED  │  (removed by insurer)              │
│                      └─────────────┘                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3.2 State Transition Rules

```yaml
ONBOARDED_to_LICENSED:
  trigger: "IRDAI exam passed and license number received"
  signal: exam_passed
  automatic: true  # System detects from LMS integration
  time_expectation: "Within 30 days of onboarding"
  if_not_triggered: "After 90 days, flag for ADM review"

ONBOARDED_to_DORMANT:
  trigger: "No exam attempt within 90 days of onboarding [VALIDATE: threshold]"
  signal: absence_of(exam_attempted, 90_days)
  automatic: true
  dormancy_reason: TRAINING_GAP.EXAM_NOT_ATTEMPTED

LICENSED_to_FIRST_SALE:
  trigger: "First policy sale recorded in PAS"
  signal: policy_sold (where agent.total_policies == 1)
  automatic: true
  side_effects:
    - "Send congratulations message to agent"
    - "Notify ADM"
    - "Update agent understanding: first_product_sold"

LICENSED_to_AT_RISK:
  trigger: "Licensed but no sale within 60 days [VALIDATE: threshold]"
  signal: absence_of(policy_sold, 60_days since LICENSED)
  automatic: true
  side_effects:
    - "Increase engagement frequency"
    - "Notify ADM: agent hasn't made first sale"

LICENSED_to_DORMANT:
  trigger: "Licensed but no sale and no engagement signals for 120 days [VALIDATE]"
  signal: absence_of(any_positive_signal, 120_days since LICENSED)
  automatic: true
  dormancy_reason: "Classified from last known signals"

FIRST_SALE_to_ACTIVE:
  trigger: "Agent meets 'active' threshold defined by tenant"
  signal: policy_sold (where rolling_policies_in_period >= tenant.active_threshold)
  automatic: true
  note: "Tenant-configurable: some define active as 1 policy/month, others as 2"

ACTIVE_to_PRODUCTIVE:
  trigger: "Agent exceeds productivity target for 3 consecutive months [VALIDATE]"
  signal: monthly_production >= tenant.productive_threshold for 3 months
  automatic: true

ACTIVE_to_AT_RISK:
  trigger: "Engagement score drops below threshold OR sales declining for 2 months"
  signal: engagement_score < 40 OR (month_over_month_sales_decline for 2 months)
  automatic: true
  side_effects:
    - "Notify ADM with specific concern"
    - "Initiate retention playbook"

PRODUCTIVE_to_AT_RISK:
  trigger: "Production drops below active threshold for 1 month"
  signal: monthly_production < tenant.active_threshold
  automatic: true
  urgency: HIGH  # Losing a productive agent is expensive

AT_RISK_to_ACTIVE:
  trigger: "Agent resumes activity — makes a sale or shows strong engagement"
  signal: policy_sold OR (engagement_score > 60 for 14 consecutive days)
  automatic: true
  side_effects:
    - "ADM notification: agent recovered"
    - "Analyze what intervention worked (for playbook refinement)"

AT_RISK_to_DORMANT:
  trigger: "No positive signals for X days after entering AT_RISK [VALIDATE: X = 60?]"
  signal: absence_of(any_positive_signal, 60_days since AT_RISK)
  automatic: true
  dormancy_reason: "Classified from signals during AT_RISK period"

DORMANT_to_ACTIVE:
  trigger: "Dormant agent makes a sale"
  signal: policy_sold (while in DORMANT state)
  automatic: true
  side_effects:
    - "Celebrate: reactivation success"
    - "Tag the playbook/intervention that preceded reactivation"
    - "Notify ADM"

DORMANT_to_LICENSED:
  trigger: "Dormant agent re-engages (responds to outreach, completes training) but hasn't sold yet"
  signal: positive_engagement_signal (while in DORMANT state)
  automatic: true
  note: "Goes back to LICENSED, not ACTIVE — they need to sell again"

ANY_to_LAPSED:
  trigger: "IRDAI license expired and not renewed"
  signal: license_expired
  automatic: true
  side_effects:
    - "Stop all outreach"
    - "Notify ADM and Regional Manager"
    - "Archive agent data per retention policy"

ANY_to_TERMINATED:
  trigger: "Insurer removes agent (fraud, compliance violation, voluntary termination)"
  signal: agent_terminated (manual action by authorized user)
  automatic: false  # Requires human action
  side_effects:
    - "Immediately stop all outreach"
    - "Audit log"
    - "Retain data per compliance requirements"
```

### 2.3.3 Tenant-Configurable Thresholds

```yaml
# Each insurer defines these based on their business model
TenantLifecycleConfig:
  active_agent_definition:
    min_policies_per_period: Integer  # e.g., 1
    period_days: Integer              # e.g., 30 (monthly)
    
  productive_agent_definition:
    min_policies_per_period: Integer  # e.g., 5
    period_days: Integer              # e.g., 30
    consecutive_periods: Integer      # e.g., 3
    
  dormancy_thresholds:
    licensed_no_sale_days: Integer    # e.g., 120
    active_no_activity_days: Integer  # e.g., 90
    at_risk_to_dormant_days: Integer  # e.g., 60
    
  at_risk_triggers:
    engagement_score_threshold: Float   # e.g., 40.0
    sales_decline_months: Integer       # e.g., 2
    
  contact_rules:
    min_days_between_voice_calls: Integer  # e.g., 7
    min_days_between_whatsapp: Integer     # e.g., 3
    max_contact_attempts_per_month: Integer # e.g., 8
    calling_hours: TimeWindow              # e.g., 09:00-21:00 IST
    dnd_scrub_required: Boolean            # e.g., true
```

---

## 2.4 Signal Taxonomy

A **Signal** is the fundamental unit of information in the system. Everything that happens produces signals. Signals are immutable, append-only, and form the single source of truth from which all state is derived.

### 2.4.0 Positive Signal Classification

The lifecycle engine uses the concept of "positive signals" throughout — e.g., "no positive signals for X days → dormant." This section defines exactly what counts as positive.

```yaml
PositiveSignal:
  definition: "A signal indicating the agent is actively engaged or progressing"
  
  always_positive:
    - POLICY_SOLD                         # Strongest positive signal
    - WHATSAPP_AGENT_REPLIED              # Any reply from agent
    - TRAINING_COMPLETED_EXTERNAL         # Agent completed external training
    - ADM_AGENT_VISIT_LOGGED              # Any in-person visit happened

  conditionally_positive:
    - VOICE_CALL_OUTCOME:
        when: "outcome IN [ANSWERED, COMPLETED]"
        not_when: "outcome IN [NOT_ANSWERED, BUSY, SWITCHED_OFF, etc.]"
    - WHATSAPP_TRAINING_INTERACTION:
        when: "completion_percentage > 50% OR interaction_type == QUIZ_COMPLETED"
        not_when: "opened but immediately closed (completion < 10%)"
    - ADM_AGENT_CALL_LOGGED:
        when: "outcome IN [CONNECTED, DETAILED_DISCUSSION]"
        not_when: "outcome == NOT_ANSWERED or BRIEF_CHAT"
    - WHATSAPP_MESSAGE_READ:
        when: "Agent was DORMANT 30+ days AND read within 24 hours of delivery"
        note: "Read-only from a long-dormant agent is a re-engagement signal"
  
  never_positive:
    - WHATSAPP_MESSAGE_SENT              # System sending is not agent engagement
    - WHATSAPP_MESSAGE_DELIVERED         # Delivery without read/reply is not engagement
    - ADM_NUDGE_RECEIVED                 # ADM getting a nudge is not agent activity
    - LIFECYCLE_STATE_CHANGED            # System event, not agent action
    - PLAYBOOK_STARTED                   # System event
    - Any system-generated signal        # Only agent actions count
```

### 2.4.0b Signal Source Types

```yaml
SignalSource:
  description: "What system or actor generated this signal"
  values:
    - VOICE_AI          # Generated by voice AI provider/analysis
    - WHATSAPP_BOT      # Generated by WhatsApp bot
    - ADM_REPORT        # Logged by ADM (via WhatsApp reply or manual)
    - PAS_SYNC          # From Policy Admin System integration
    - LMS_SYNC          # From License Management System integration
    - COMMISSION_SYNC   # From commission system integration
    - SYSTEM            # Generated internally (lifecycle transitions, playbook events)
    - MANUAL            # Manually created by admin/support user
    - BATCH_IMPORT      # From batch file upload (CSV/Excel)
```

### 2.4.1 Signal Envelope (Common to all signals)

```yaml
SignalSource:
  base: Enum
  values:
    - VOICE_AI          # Generated by Voice AI calls
    - WHATSAPP_BOT      # Generated by WhatsApp bot interactions
    - ADM_REPORT        # Logged by ADM via WhatsApp action logging
    - PAS_SYNC          # Imported from Policy Admin System
    - LMS_SYNC          # Imported from License Management System
    - COMMISSION_SYNC   # Imported from Commission System
    - SYSTEM            # Generated by internal system processes
    - MANUAL            # Manually created by admin/support
    - BATCH_IMPORT      # From CSV/Excel bulk import
  description: "What system or process generated this signal"

SignalEnvelope:
  signal_id: UUIDv4                 # Unique, immutable
  tenant_id: TenantId              # Always present — tenant isolation
  signal_type: SignalType          # From taxonomy below
  source: SignalSource             # What generated this signal (see 2.4.0b)
  agent_id: AgentId                # Which agent this is about (nullable for system signals)
  adm_id: ADMId?                   # Which ADM was involved (if applicable)
  timestamp: Timestamp             # When this happened (UTC)
  channel: ChannelType?            # Which channel (if applicable)
  conversation_id: ConversationId? # Part of which conversation (if applicable)
  payload: JSON                    # Signal-specific data (typed per signal_type)
  idempotency_key: String?         # Prevents duplicate signals from external systems
                                   # Format: "{source}:{external_id}:{event_type}"
                                   # Example: "pas:POL-2024-001234:policy_sold"
                                   # Unique within tenant when present
  metadata:
    correlation_id: UUIDv4?        # Links related signals (e.g., a call generates multiple)
    campaign_id: UUIDv4?           # If triggered by a playbook/campaign
    playbook_id: UUIDv4?           # If part of a playbook execution
    source_system: String?         # External system that originated this (PAS, LMS, etc.)
    idempotency_key: String?       # Optional. Prevents duplicate signals from external systems.
                                   # Format: "{source}:{external_id}:{event_type}"
                                   # Example: "pas_sync:POL-2024-001234:policy_sold"
                                   # If set, system rejects duplicates with same key within tenant.
```

### 2.4.2 Signal Types — Voice AI

```yaml
VOICE_CALL_INITIATED:
  payload:
    caller_id: IndianMobileNumber
    agent_phone: IndianMobileNumber
    language_intended: Language
    call_purpose: Enum[CHECK_IN, TRAINING, REACTIVATION, CONGRATULATION, SURVEY]
    playbook_step: String?

VOICE_CALL_OUTCOME:
  payload:
    outcome: ContactOutcome
    duration_seconds: DurationSeconds
    language_detected: Language
    language_switches: Language[]    # If agent switched languages during call
    
VOICE_CONVERSATION_ANALYZED:
  payload:
    transcript_summary: String       # NOT full transcript — structured summary
    sentiment: SentimentLabel
    dormancy_reasons_detected: DormancyReasonCode[]
    product_interests_mentioned: ProductCode[]
    product_confusion_detected: ProductCode[]
    training_needs_identified: TrainingTopic[]
    competitor_mentions: String[]    # "LIC", "HDFC Life", etc.
    commission_concerns: Boolean
    adm_relationship_signals:
      mentioned_adm: Boolean
      adm_sentiment: SentimentLabel?
    action_items_detected: String[]  # "wants to know about term plans", "asked about commission"
    reachability_preference:
      preferred_time: TimeOfDay?
      preferred_channel: ChannelType?
      callback_requested: Boolean
    key_quotes: String[]             # 2-3 verbatim quotes that capture essence (for ADM context)
    
VOICE_CALL_RECORDING_STORED:
  payload:
    recording_url: String            # S3 URL
    recording_duration_seconds: DurationSeconds
    file_size_bytes: Integer
    encryption: String               # Encryption method used
```

### 2.4.3 Signal Types — WhatsApp

```yaml
WHATSAPP_MESSAGE_SENT:
  payload:
    message_type: Enum[TEMPLATE, TEXT, MEDIA, INTERACTIVE]
    template_id: String?
    content_summary: String          # What was sent (not full content for media)
    purpose: Enum[TRAINING, NUDGE, REMINDER, INFO, CONGRATULATION]

WHATSAPP_MESSAGE_DELIVERED:
  payload:
    message_id: UUIDv4
    delivered_at: Timestamp

WHATSAPP_MESSAGE_READ:
  payload:
    message_id: UUIDv4
    read_at: Timestamp

WHATSAPP_AGENT_REPLIED:
  payload:
    reply_to_message_id: UUIDv4?
    reply_type: Enum[TEXT, BUTTON_CLICK, LIST_SELECTION, MEDIA, VOICE_NOTE]
    reply_content: String
    sentiment: SentimentLabel
    intent_detected: String?
    
WHATSAPP_TRAINING_INTERACTION:
  payload:
    module_id: TrainingModuleId
    interaction_type: Enum[VIDEO_WATCHED, QUIZ_ATTEMPTED, QUIZ_COMPLETED, DOCUMENT_OPENED]
    completion_percentage: Float?    # For video: how much they watched
    quiz_score: Float?               # For quiz: score achieved
    quiz_max_score: Float?
    time_spent_seconds: DurationSeconds?
```

### 2.4.4 Signal Types — ADM Activity

```yaml
ADM_AGENT_CALL_LOGGED:
  payload:
    call_duration_seconds: DurationSeconds?
    outcome: Enum[CONNECTED, NOT_ANSWERED, BRIEF_CHAT, DETAILED_DISCUSSION]
    notes: String?                   # ADM's notes (optional, via WhatsApp prompt)

ADM_AGENT_VISIT_LOGGED:
  payload:
    visit_purpose: Enum[COACHING, JOINT_CALL, TRAINING, RECRUITMENT_FOLLOWUP]
    outcome: String?
    location: String?

ADM_NUDGE_RECEIVED:
  payload:
    nudge_type: Enum[AGENT_ALERT, MORNING_BRIEFING, WEEKLY_SUMMARY, ESCALATION]
    content_summary: String

ADM_NUDGE_ACTED_ON:
  payload:
    nudge_id: UUIDv4
    action_taken: Enum[CALLED_AGENT, VISITED_AGENT, ACKNOWLEDGED, IGNORED, FORWARDED_CONTENT]
    time_to_action_minutes: Integer?

ADM_BRIEFING_OPENED:
  payload:
    briefing_type: Enum[MORNING, WEEKLY, MONTHLY]
    items_viewed: Integer
    time_spent_seconds: DurationSeconds?
```

### 2.4.5 Signal Types — Business Events (from Insurer Systems)

```yaml
POLICY_SOLD:
  payload:
    policy_number: String
    product_code: ProductCode
    product_name: String
    premium: Premium
    premium_mode: Enum[MONTHLY, QUARTERLY, HALF_YEARLY, ANNUAL, SINGLE]
    sum_assured: Money
    proposal_date: CalendarDate
    issuance_date: CalendarDate
    customer_age: Integer?           # Anonymized — for product analytics only
    is_first_sale: Boolean           # Agent's first ever sale

COMMISSION_CREDITED:
  payload:
    amount: CommissionAmount
    for_policy: String?              # Policy number
    commission_type: Enum[FIRST_YEAR, RENEWAL, BONUS]
    credit_date: CalendarDate

LICENSE_STATUS_CHANGED:
  payload:
    new_status: Enum[ACTIVE, EXPIRED, SUSPENDED, SURRENDERED]
    expiry_date: CalendarDate?
    renewal_due_date: CalendarDate?

AGENT_DATA_UPDATED:
  payload:
    fields_changed: String[]         # Which fields changed
    source: String                   # Which system triggered the update

TRAINING_COMPLETED_EXTERNAL:
  payload:
    training_name: String
    training_type: Enum[IRDAI_MANDATORY, PRODUCT_TRAINING, SKILLS_TRAINING]
    completion_date: CalendarDate
    score: Float?
    hours: Float                     # Training hours (for IRDAI compliance tracking)
```

### 2.4.6 Signal Types — System Events

```yaml
LIFECYCLE_STATE_CHANGED:
  payload:
    previous_state: AgentLifecycleState
    new_state: AgentLifecycleState
    trigger_signal_id: UUIDv4        # Which signal caused this transition
    reason: String                   # Human-readable explanation

PLAYBOOK_STARTED:
  payload:
    playbook_id: PlaybookId
    playbook_name: String
    trigger_reason: String
    estimated_duration_days: Integer
    steps_count: Integer

PLAYBOOK_STEP_EXECUTED:
  payload:
    playbook_id: PlaybookId
    step_number: Integer
    step_action: String              # What was done
    outcome: String?                 # Result if immediate

PLAYBOOK_COMPLETED:
  payload:
    playbook_id: PlaybookId
    outcome: Enum[AGENT_REACTIVATED, AGENT_ENGAGED, NO_RESPONSE, OPTED_OUT, EXPIRED]
    duration_days: Integer
    steps_executed: Integer
    steps_skipped: Integer

ESCALATION_CREATED:
  payload:
    escalation_type: Enum[AGENT_UNREACHABLE, AGENT_COMPLAINT, ADM_UNRESPONSIVE, COMPLIANCE_ISSUE, LICENSE_EXPIRING]
    priority: Enum[LOW, MEDIUM, HIGH, CRITICAL]
    assigned_to: UserId
    description: String
    
CONSENT_CHANGED:
  payload:
    channel: ChannelType
    previous_status: ConsentStatus
    new_status: ConsentStatus
    method: Enum[VOICE_RESPONSE, WHATSAPP_REPLY, SELF_SERVICE, ADM_REPORTED, SYSTEM_EXPIRY]
```

### 2.4.7 Positive Signal Classification

The lifecycle engine and engagement score use the concept of "positive signals" — signals that indicate the agent is engaged or progressing. This is the formal definition:

```yaml
PositiveSignals:
  description: "Signals that indicate agent engagement. Used by lifecycle engine and engagement scoring."

  ALWAYS_POSITIVE:
    - POLICY_SOLD                        # Strongest signal — agent is selling
    - WHATSAPP_AGENT_REPLIED             # Agent responded to any message
    - TRAINING_COMPLETED_EXTERNAL        # Agent completed external training
    - ADM_AGENT_VISIT_LOGGED             # ADM visited agent in person (any visit)

  POSITIVE_IF_CONDITION_MET:
    - VOICE_CALL_OUTCOME:
        condition: "payload.outcome IN [ANSWERED, COMPLETED]"
        note: "NOT_ANSWERED is not positive"
    - WHATSAPP_TRAINING_INTERACTION:
        condition: "payload.completion_percentage > 50 OR payload.interaction_type == QUIZ_COMPLETED"
        note: "Partial video views <50% don't count"
    - ADM_AGENT_CALL_LOGGED:
        condition: "payload.outcome == DETAILED_DISCUSSION"
        note: "Brief chats are not strong enough signals"

  NOT_POSITIVE:
    - WHATSAPP_MESSAGE_DELIVERED         # Delivery alone is not engagement
    - WHATSAPP_MESSAGE_READ              # Read-without-reply is WEAK — tracked separately but not positive
    - VOICE_CALL_OUTCOME where outcome == NOT_ANSWERED
    - All system-generated signals (LIFECYCLE_STATE_CHANGED, PLAYBOOK_*, ESCALATION_*, CONSENT_*)
    
  note: |
    An agent may have "read" a WhatsApp message but not replied. This is tracked as
    whatsapp_read_rate_30d in the Agent Understanding but does NOT reset the 
    "days since last positive signal" counter used for dormancy transitions.
```

---

## 2.5 Dormancy Reason Taxonomy

This taxonomy is populated primarily from Voice AI conversation analysis and WhatsApp interactions. An agent may have multiple contributing reasons. The system tracks PRIMARY reason and CONTRIBUTING reasons.

```yaml
DormancyReasons:
  TRAINING_GAP:
    description: "Agent lacks knowledge or skills needed to sell"
    sub_reasons:
      PRODUCT_KNOWLEDGE_INSUFFICIENT:
        description: "Doesn't understand products well enough to explain to customers"
        detection: "Voice AI: agent expresses confusion about product features, says 'mujhe samajh nahi aata'"
        intervention: "Product-specific micro-training via WhatsApp"
      SALES_SKILLS_LACKING:
        description: "Understands product but can't close sales"
        detection: "Voice AI: agent says 'log mante nahi hain', 'kaise samjhaaun'"
        intervention: "Sales technique training, role-play exercises, joint call with ADM"
      EXAM_NOT_ATTEMPTED:
        description: "Never attempted IRDAI exam after recruitment"
        detection: "System signal: 90 days since onboarding, no exam record"
        intervention: "Exam preparation support, study material, mock tests"
      EXAM_FAILED:
        description: "Failed IRDAI exam, hasn't reattempted"
        detection: "LMS signal: exam_failed, no subsequent exam_attempted"
        intervention: "Targeted preparation for weak areas, encouragement"
      PROCESS_UNCLEAR:
        description: "Doesn't know how to fill proposals, use the app, submit business"
        detection: "Voice AI: agent asks about process, says 'form kaise bharna hai'"
        intervention: "Step-by-step process training, screen recording walkthroughs"

  ENGAGEMENT_GAP:
    description: "Agent feels disconnected from the insurer / ADM"
    sub_reasons:
      ADM_NEVER_CONTACTED:
        description: "After onboarding, ADM never followed up"
        detection: "System: no ADM_AGENT_CALL_LOGGED or ADM_AGENT_VISIT for this agent"
        intervention: "Immediate ADM alert, system compensates with direct engagement"
      ADM_CONTACTED_NO_FOLLOWTHROUGH:
        description: "ADM met once but never came back"
        detection: "Signal pattern: one ADM interaction, then silence"
        intervention: "ADM accountability nudge, system continues engagement"
      FEELS_UNSUPPORTED:
        description: "Agent tried but felt no one helped when they struggled"
        detection: "Voice AI: 'koi help nahi karta', 'akele kar raha tha'"
        intervention: "Assign mentor (senior agent or ADM), increase touch frequency"
      NO_RECOGNITION:
        description: "Agent did work but felt unrecognized"
        detection: "Voice AI: 'kisi ne notice nahi kiya', mentions efforts without acknowledgment"
        intervention: "Recognition program, milestone celebrations, ADM prompted to acknowledge"

  ECONOMIC:
    description: "Financial incentives aren't compelling enough"
    sub_reasons:
      COMMISSION_TOO_LOW:
        description: "Perceives commission rates as inadequate"
        detection: "Voice AI: mentions commission amount, compares to effort"
        intervention: "Clarify actual commission structure, highlight bonuses, show earning potential"
      COMPETITOR_BETTER_COMMISSION:
        description: "Explicitly mentions other insurer pays more"
        detection: "Voice AI: names competitor, compares rates"
        intervention: "Flag to HQ product/distribution team, highlight non-commission benefits"
      IRREGULAR_PAYMENTS:
        description: "Commission payments are delayed or incorrect"
        detection: "Voice AI: 'paisa nahi aaya', 'commission late hai'"
        intervention: "Escalate to operations, verify payment status, resolve"
      INSUFFICIENT_INCOME:
        description: "Insurance selling doesn't generate enough to be worth the time"
        detection: "Voice AI: 'itna time lagta hai', 'kuch khaas milta nahi'"
        intervention: "Productivity training, show path to higher earnings, time management"

  OPERATIONAL:
    description: "Insurer's systems or processes create friction"
    sub_reasons:
      PROPOSAL_PROCESS_COMPLEX:
        description: "Filling proposals is too hard or error-prone"
        detection: "Voice AI: 'form bahut mushkil hai', 'reject ho jata hai'"
        intervention: "Process simplification training, common errors guide, proposal filling assistance"
      TECHNOLOGY_BARRIERS:
        description: "Can't use the insurer's app or digital tools"
        detection: "Voice AI: 'app kaam nahi karta', 'samajh nahi aata app'"
        intervention: "App training (short video), helpdesk connection, alternative manual process"
      CLAIM_EXPERIENCE_BAD:
        description: "A customer's claim was rejected and agent lost trust/credibility"
        detection: "Voice AI: mentions claim rejection, customer complaint, loss of face"
        intervention: "Claim process explanation, talking points for customers, escalate specific case"
      SLOW_ISSUANCE:
        description: "Policies take too long to issue after proposal submission"
        detection: "Voice AI: 'bahut time lagta hai policy aane mein'"
        intervention: "Flag to operations, set realistic expectations, provide tracking"
      KYC_ISSUES:
        description: "KYC/documentation requirements are burdensome"
        detection: "Voice AI: 'bahut documents chahiye', 'customer ke paas nahi hota'"
        intervention: "Simplified documentation guide, digital KYC alternatives"

  PERSONAL:
    description: "Agent's personal circumstances changed"
    sub_reasons:
      HEALTH_ISSUES:
        description: "Agent or family member unwell"
        detection: "Voice AI: mentions health, illness, hospital"
        intervention: "Express empathy, pause engagement, check in after stated recovery time"
      RELOCATED:
        description: "Agent moved to a different area"
        detection: "Voice AI: 'main shift ho gaya', phone number area code changed"
        intervention: "Reassign to new area's ADM, update region, re-engage"
      FAMILY_OBLIGATIONS:
        description: "Family commitments consuming time"
        detection: "Voice AI: 'ghar mein problem hai', 'time nahi mil raha'"
        intervention: "Reduce engagement frequency, offer flexible re-entry path"
      LOST_INTEREST:
        description: "Simply doesn't want to sell insurance anymore"
        detection: "Voice AI: 'interest nahi hai', 'nahi karna hai ab'"
        intervention: "Respectful acknowledgment, leave door open, reduce to minimal annual check-in"
      OTHER_EMPLOYMENT:
        description: "Found a full-time job that conflicts"
        detection: "Voice AI: 'job lag gayi', 'aur kaam kar raha hoon'"
        intervention: "Explore part-time possibility, otherwise graceful dormancy"

  REGULATORY:
    description: "Licensing or compliance issues"
    sub_reasons:
      LICENSE_EXPIRED:
        description: "IRDAI license expired, agent didn't renew"
        detection: "LMS signal: license_expired"
        intervention: "License renewal assistance, training hours completion support"
      LICENSE_EXPIRING_SOON:
        description: "License expiring within 90 days, no renewal initiated"
        detection: "System: license_expiry_date - today < 90 days"
        intervention: "Urgent reminder, help complete required training hours"
      COMPLIANCE_ISSUE:
        description: "Agent has a pending compliance matter"
        detection: "System flag from compliance team"
        intervention: "Route to compliance team, pause outreach until resolved"

  UNKNOWN:
    description: "Reason not yet determined"
    note: "This is the default state for newly dormant agents until Voice AI conversation classifies them"
    intervention: "Schedule Voice AI check-in call to determine reason"
```

---

## 2.6 Agent Understanding Model

The Agent Understanding is a continuously-updated profile that accumulates everything the system knows about an agent. It is derived entirely from the Signal Stream — never manually edited (except for corrections).

```yaml
AgentUnderstanding:
  # Identity (from insurer data)
  agent_id: AgentId
  tenant_id: TenantId
  agent_code: AgentCode
  name: PersonName
  registered_phone: IndianMobileNumber
  registered_email: EmailAddress?
  
  # Lifecycle (computed from signals)
  current_lifecycle_state: AgentLifecycleState
  state_since: Timestamp
  previous_states: [{state: AgentLifecycleState, from: Timestamp, to: Timestamp}]
  days_in_current_state: DaysSince
  
  # Organization
  assigned_adm: ADMId
  region_path: RegionNodeId[]        # [zone_id, region_id, branch_id, area_id]
  adm_assignment_date: CalendarDate
  previous_adms: [{adm_id: ADMId, from: CalendarDate, to: CalendarDate}]
  
  # Engagement Profile (learned from interactions)
  engagement:
    score: EngagementScore           # Current composite score
    score_trend: Enum[RISING, STABLE, DECLINING]
    last_positive_signal: Timestamp?
    last_contact_attempt: Timestamp?
    last_successful_contact: Timestamp?
    preferred_channel: ChannelType?  # Learned from response patterns
    preferred_language: Language      # Detected, not registered
    preferred_time_window: TimeWindow? # When they typically respond/answer
    call_answer_rate_30d: Float      # % of calls answered in last 30 days
    whatsapp_read_rate_30d: Float    # % of WhatsApp messages read
    whatsapp_response_rate_30d: Float # % of WhatsApp messages responded to
    average_response_time_minutes: Float? # How quickly they respond on WhatsApp
  
  # Dormancy Analysis (populated when state is DORMANT or AT_RISK)
  dormancy:
    primary_reason: DormancyReasonCode?
    contributing_reasons: DormancyReasonCode[]
    dormancy_onset_date: CalendarDate?
    last_known_activity: Timestamp?
    reactivation_probability: ReactivationProbability
    reactivation_attempts: Integer    # How many playbooks have been run
    last_playbook_outcome: Enum[SUCCESS, NO_RESPONSE, OPTED_OUT, IN_PROGRESS]?
  
  # Capability Profile (learned from training + conversations)
  capability:
    product_confidence: {ProductCode: ProductConfidenceScore}  # Per product
    training_modules_completed: [{module_id, completed_at, score}]
    training_modules_in_progress: [{module_id, started_at, progress_pct}]
    identified_training_needs: TrainingTopic[]
    irdai_training_hours_completed: Float  # For license renewal tracking
    irdai_training_hours_required: Float
    license_expiry_date: CalendarDate?
  
  # Sales Profile (from PAS integration)
  sales:
    total_policies_sold: Integer
    policies_sold_last_12m: Integer
    total_premium_generated: Money
    premium_last_12m: Money
    products_sold: ProductCode[]     # Which products they've sold
    average_premium: Money?
    last_sale_date: CalendarDate?
    commission_earned_ytd: CommissionAmount
    commission_earned_last_12m: CommissionAmount
    
  # Relationship with ADM (observed, not self-reported)
  adm_relationship:
    adm_contact_frequency_30d: Integer  # How many times ADM contacted in last 30 days
    agent_initiated_contact_30d: Integer # How many times agent reached out to ADM
    last_adm_interaction: Timestamp?
    adm_relationship_quality: Enum[STRONG, MODERATE, WEAK, ABSENT]  # Computed
    
  # Consent
  consent:
    voice_ai: ConsentStatus
    whatsapp: ConsentStatus
    sms: ConsentStatus
    email: ConsentStatus
    consent_last_updated: Timestamp
    
  # DND (Do Not Disturb) Registry Status
  dnd:
    dnd_registered: Boolean          # Is the phone number on NCPR DND registry?
    dnd_checked_at: Timestamp?       # When was the last DND check performed?
    note: "Re-check if dnd_checked_at > 30 days ago before making voice calls"
    
  # DND / Regulatory
  dnd:
    dnd_registered: Boolean            # Is agent on NCPR DND registry?
    dnd_checked_at: Timestamp?         # When was DND status last verified?
    note: "Re-check every 30 days. If DND registered, voice calls must be classified as transactional (existing business relationship), not promotional."
    
  # Contact History Summary (not full history — summary for quick access)
  contact_summary:
    total_voice_calls: Integer
    total_whatsapp_messages_sent: Integer
    total_whatsapp_messages_received: Integer  # From agent
    total_training_interactions: Integer
    total_adm_interactions: Integer
```

---

## 2.7 Conversation Model

A Conversation is a unified, cross-channel thread of interactions with a single agent over a period. It provides continuity — when the Voice AI calls an agent, it knows what happened in the last WhatsApp exchange.

```yaml
Conversation:
  conversation_id: UUIDv4
  tenant_id: TenantId
  agent_id: AgentId
  
  # Lifecycle
  status: Enum[ACTIVE, PAUSED, CLOSED, ARCHIVED]
  opened_at: Timestamp
  last_activity_at: Timestamp
  closed_at: Timestamp?
  close_reason: Enum[COMPLETED, OPTED_OUT, NO_RESPONSE_TIMEOUT, AGENT_REACTIVATED, MANUAL]?
  
  # Context carried forward
  context:
    purpose: Enum[ONBOARDING, TRAINING, REACTIVATION, RETENTION, CHECK_IN, ESCALATION_FOLLOWUP]
    playbook_id: PlaybookId?
    dormancy_reason_being_addressed: DormancyReasonCode?
    topics_discussed: String[]       # Running list of topics covered
    commitments_made: String[]       # Promises the system made ("will send training video")
    commitments_fulfilled: String[]  # Which promises were kept
    open_questions: String[]         # Things the agent asked that haven't been answered
    adm_involvement: Boolean         # Whether ADM has been brought into this conversation
    
  # Interactions (ordered by time, across channels)
  interactions: [ConversationInteraction]
  
ConversationInteraction:
  interaction_id: UUIDv4
  timestamp: Timestamp
  channel: ChannelType
  direction: Enum[OUTBOUND, INBOUND]  # System→Agent or Agent→System
  content_type: Enum[VOICE_CALL, TEXT_MESSAGE, MEDIA, QUIZ, BUTTON_RESPONSE]
  content_summary: String             # Brief summary (not full transcript)
  signal_ids: UUIDv4[]               # Links to the Signal Stream entries
  outcome: ContactOutcome?
  sentiment: SentimentLabel?
  
  # Voice-specific
  voice_call_duration: DurationSeconds?
  voice_language_used: Language?
  
  # WhatsApp-specific
  whatsapp_message_status: Enum[SENT, DELIVERED, READ, REPLIED]?
  whatsapp_template_used: String?
```

---

## 2.8 Reactivation Playbook Model

A Playbook is a structured sequence of interventions designed to address a specific dormancy reason or lifecycle situation. Playbooks are not rigid scripts — they're adaptive frameworks that adjust based on agent response.

```yaml
Playbook:
  playbook_id: PlaybookId
  tenant_id: TenantId
  name: String
  description: String
  
  # When to trigger
  trigger_conditions:
    lifecycle_states: AgentLifecycleState[]       # Which states trigger this
    dormancy_reasons: DormancyReasonCode[]?        # Specific to which reasons
    time_in_state_days_min: Integer?               # Only after X days in state
    reactivation_attempts_max: Integer?            # Don't run if already tried N times
    engagement_score_range: {min: Float, max: Float}?
    
  # The steps
  steps: [PlaybookStep]
  
  # Completion criteria
  success_criteria: 
    agent_state_becomes: AgentLifecycleState[]?    # e.g., [ACTIVE, FIRST_SALE]
    engagement_score_above: Float?
    specific_signal_received: SignalType?           # e.g., POLICY_SOLD
    
  max_duration_days: Integer         # Auto-close after this many days
  
  # Performance tracking
  metrics:
    times_executed: Integer
    success_rate: Float              # % that met success criteria
    average_duration_days: Float
    average_steps_to_success: Float

PlaybookStep:
  step_number: Integer
  name: String
  
  # What to do
  action:
    type: Enum[VOICE_CALL, WHATSAPP_MESSAGE, WHATSAPP_TRAINING, ADM_NUDGE, WAIT, ESCALATE]
    
    # Voice call specifics
    voice_call_config:
      purpose: String
      language: Language              # Or "agent_preferred" to auto-select
      conversation_guide: String      # High-level guide for AI, not rigid script
      max_duration_seconds: DurationSeconds
      
    # WhatsApp specifics
    whatsapp_config:
      message_template: String
      media_attachment: String?       # Training video URL, document, etc.
      interactive_elements: Boolean   # Buttons, quick replies
      
    # ADM nudge specifics
    adm_nudge_config:
      nudge_message_template: String  # What to tell the ADM
      action_requested: String        # What we want the ADM to do
      follow_up_if_no_action_days: Integer  # Remind ADM if they don't act
      
  # When to do it
  scheduling:
    delay_after_previous_step_days: Integer  # Wait N days after previous step
    preferred_time: TimeOfDay?        # Or "agent_preferred" to auto-select
    day_of_week_preference: Enum[WEEKDAY, WEEKEND, ANY]?
    
  # Branching logic
  next_step_rules:
    - condition: "outcome == ANSWERED AND sentiment == POSITIVE"
      go_to_step: Integer
    - condition: "outcome == ANSWERED AND dormancy_reason == COMMISSION_TOO_LOW"
      go_to_step: Integer
    - condition: "outcome == NOT_ANSWERED AND attempts >= 3"
      go_to_step: Integer             # Maybe escalate to ADM
    - condition: "outcome == OPTED_OUT"
      action: CLOSE_PLAYBOOK
    - condition: "default"
      go_to_step: Integer             # Next sequential step
```

### Example Playbook: Training Gap — Product Knowledge

```yaml
playbook_example:
  name: "Reactivation: Product Knowledge Gap"
  trigger_conditions:
    lifecycle_states: [DORMANT, AT_RISK]
    dormancy_reasons: [TRAINING_GAP.PRODUCT_KNOWLEDGE_INSUFFICIENT]
    
  steps:
    - step: 1
      name: "WhatsApp: Identify specific product gap"
      action:
        type: WHATSAPP_MESSAGE
        message: "Hi {agent_name}, we have some short training videos on our products. Which would you like to learn about? [Term Life] [Endowment] [ULIP] [Health]"
      next_step_rules:
        - condition: "agent_replied with product selection"
          go_to_step: 2
        - condition: "no_reply in 3 days"
          go_to_step: 5  # Try voice call instead
          
    - step: 2
      name: "WhatsApp: Send product micro-training"
      action:
        type: WHATSAPP_TRAINING
        training_module: "product_{selected_product}_basics"  # 3-min video
      next_step_rules:
        - condition: "video_watched > 80%"
          go_to_step: 3
        - condition: "video_not_watched in 2 days"
          go_to_step: 2b  # Resend with encouragement
          
    - step: 3
      name: "WhatsApp: Quick quiz"
      action:
        type: WHATSAPP_TRAINING
        training_module: "product_{selected_product}_quiz"  # 5 questions
      next_step_rules:
        - condition: "quiz_score >= 60%"
          go_to_step: 4
        - condition: "quiz_score < 60%"
          go_to_step: 2  # Resend training with focus on weak areas
          
    - step: 4
      name: "ADM Nudge: Agent is ready for guided sale"
      action:
        type: ADM_NUDGE
        message: "{agent_name} just completed {product} training (scored {score}%). Good time to call them and help with their first {product} sale."
      next_step_rules:
        - condition: "adm_acted within 7 days"
          go_to_step: 6  # Monitor for sale
        - condition: "adm_no_action in 7 days"
          go_to_step: 7  # Voice AI follow-up directly
          
    - step: 5
      name: "Voice AI: Check-in call"
      action:
        type: VOICE_CALL
        purpose: "Understand what product topics confuse the agent, offer training"
      next_step_rules:
        - condition: "answered AND identified specific product"
          go_to_step: 2  # Send that product's training
        - condition: "not_answered after 3 attempts"
          action: CLOSE_PLAYBOOK
```

---

## 2.9 ADM Effectiveness Model

The system tracks ADM performance not to punish but to help — and to compensate when ADM engagement is low.

```yaml
ADMProfile:
  adm_id: ADMId
  tenant_id: TenantId
  name: PersonName
  phone: IndianMobileNumber
  
  # Portfolio
  portfolio:
    total_agents: Integer
    agents_by_state: {AgentLifecycleState: Integer}  # Distribution
    activation_rate: Float           # Active / Total
    portfolio_health_score: Float    # Composite
    
  # Engagement behavior
  engagement:
    agents_contacted_last_30d: Integer
    average_contacts_per_agent_per_month: Float
    nudges_received_last_30d: Integer
    nudges_acted_on_last_30d: Integer
    nudge_response_rate: Float
    average_time_to_act_on_nudge_hours: Float
    
  # Effectiveness
  effectiveness:
    reactivations_last_90d: Integer  # How many dormant agents came back
    first_sales_facilitated_last_90d: Integer
    agent_satisfaction_score: Float?  # Derived from agent conversation sentiment about ADM
    
  # ADM classification (derived)
  classification: Enum[HIGH_PERFORMER, AVERAGE, STRUGGLING, UNRESPONSIVE]
  classification_reason: String
  
  # Communication preferences
  preferred_language: Language
  preferred_briefing_time: TimeOfDay?
  whatsapp_active: Boolean           # Do they read/respond to system messages?
```

---

## 2.10 Training Content Model

```yaml
TrainingModule:
  module_id: UUIDv4
  tenant_id: TenantId
  
  # Content
  title: String
  description: String
  topic: TrainingTopic               # From taxonomy
  product_codes: ProductCode[]?      # If product-specific
  
  # Delivery
  format: Enum[VIDEO, QUIZ, INFOGRAPHIC, AUDIO, TEXT, INTERACTIVE]
  delivery_channel: Enum[WHATSAPP, SELF_SERVICE, BOTH]
  duration_minutes: Float            # Expected time to complete
  
  # Language
  available_languages: Language[]
  content_by_language: {Language: TrainingContent}
  
  # Difficulty & Prerequisites
  difficulty: Enum[BEGINNER, INTERMEDIATE, ADVANCED]
  prerequisites: UUIDv4[]?           # Other modules that should be completed first
  
  # For IRDAI tracking
  irdai_training_hours: Float?       # Hours this counts towards license renewal
  irdai_category: String?            # IRDAI training category
  
  # Performance
  metrics:
    completion_rate: Float
    average_score: Float?
    correlation_with_first_sale: Float?  # Does completing this module predict sales?

TrainingContent:
  language: Language
  content_url: String                # S3 URL for video/audio/document
  content_size_bytes: Integer
  thumbnail_url: String?
  quiz_questions: [QuizQuestion]?
  
QuizQuestion:
  question_text: String
  question_type: Enum[MULTIPLE_CHOICE, TRUE_FALSE]
  options: String[]
  correct_answer_index: Integer
  explanation: String                # Shown after answering

TrainingTopic:
  base: Enum
  values:
    - PRODUCT_TERM_LIFE
    - PRODUCT_ENDOWMENT
    - PRODUCT_ULIP
    - PRODUCT_HEALTH
    - PRODUCT_PENSION
    - SALES_PROSPECTING
    - SALES_PITCH
    - SALES_OBJECTION_HANDLING
    - SALES_CLOSING
    - PROCESS_PROPOSAL_FILLING
    - PROCESS_KYC
    - PROCESS_DIGITAL_TOOLS
    - COMPLIANCE_BASICS
    - COMPLIANCE_MIS_SELLING
    - SOFT_SKILLS_COMMUNICATION
    - SOFT_SKILLS_TRUST_BUILDING
```

---

## 2.11 Decision Engine Inputs & Outputs

The Decision Engine answers one question per agent: **"What should we do next for this agent, and when?"**

```yaml
DecisionInput:
  agent_understanding: AgentUnderstanding    # Full profile
  active_conversation: Conversation?          # If one exists
  active_playbook: PlaybookExecution?         # If one is running
  recent_signals: Signal[]                    # Last 30 days of signals
  tenant_config: TenantLifecycleConfig       # Tenant's rules
  adm_profile: ADMProfile                    # ADM's current state
  current_datetime: Timestamp
  
DecisionOutput:
  action: Enum[
    DO_NOTHING,              # Agent is in good state, no intervention needed
    START_PLAYBOOK,          # Begin a new playbook
    CONTINUE_PLAYBOOK,       # Execute next step in current playbook
    SEND_NUDGE_TO_ADM,       # Alert ADM about this agent
    SCHEDULE_VOICE_CALL,     # Direct Voice AI outreach
    SEND_WHATSAPP,           # Direct WhatsApp message
    SEND_TRAINING,           # Training content delivery
    ESCALATE,                # Escalate to Regional Manager
    CELEBRATE,               # Agent achieved something — acknowledge
    PAUSE_OUTREACH,          # Agent requested space / opted out temporarily
    CLOSE_AND_ARCHIVE        # Agent is gone-for-good, stop spending resources
  ]
  
  # Action details
  playbook_id: PlaybookId?            # If START_PLAYBOOK
  scheduled_time: Timestamp           # When to execute
  channel: ChannelType                # Which channel to use
  language: Language                  # Which language
  content: String?                    # Specific message/template
  priority: Enum[LOW, MEDIUM, HIGH, URGENT]
  
  # Reasoning (for transparency and debugging)
  reasoning: String                   # "Agent dormant 45 days, reason: training gap, 
                                      #  playbook 'product_knowledge' not yet tried, 
                                      #  ADM engagement weak — starting system-led playbook"

DecisionConstraints:
  # Hard constraints that override everything
  - "NEVER make voice calls outside TRAI calling hours (09:00-21:00 IST). WhatsApp is NOT restricted by TRAI hours."
  - "NEVER contact on ANY channel if consent is DENIED or REVOKED for that channel"
  - "NEVER contact if agent is TERMINATED or LAPSED"
  - "Respect min_days_between_voice_calls from tenant config"
  - "Respect max_contact_attempts_per_month from tenant config"
  - "If DND registered: voice calls must be classified as transactional (existing business relationship), not promotional. If legal team has NOT confirmed transactional classification, DO NOT CALL."
  - "If agent said 'don't call me' in last conversation, PAUSE_OUTREACH for 30 days"
  
  # Soft constraints (preferences, can be overridden by priority)
  - "Prefer agent's learned preferred_time_window"
  - "Prefer agent's detected preferred_channel"
  - "Prefer agent's detected preferred_language"
  - "If ADM is HIGH_PERFORMER, prefer ADM_NUDGE over direct outreach"
  - "If ADM is UNRESPONSIVE, prefer direct system outreach"
```

---

## 2.12 Product & Commission Model

```yaml
InsuranceProduct:
  product_code: ProductCode
  tenant_id: TenantId
  product_name: String
  product_category: Enum[TERM_LIFE, ENDOWMENT, ULIP, WHOLE_LIFE, PENSION, HEALTH, GROUP]
  status: Enum[ACTIVE, DISCONTINUED, COMING_SOON]
  min_premium: Money
  max_premium: Money?
  min_sum_assured: Money
  max_sum_assured: Money?
  min_entry_age: Integer
  max_entry_age: Integer
  policy_term_options: Integer[]     # [10, 15, 20, 30] years
  premium_mode_options: Enum[MONTHLY, QUARTERLY, HALF_YEARLY, ANNUAL, SINGLE][]
  
  # Selling context
  target_customer_profile: String    # Brief description for agent training
  common_objections: String[]        # What customers typically say
  key_selling_points: String[]       # What agents should highlight
  
  # Commission
  commission_structure:
    first_year_rate: Float           # % of first year premium
    renewal_rate: Float              # % of renewal premium
    bonus_criteria: String?          # Additional commission triggers
  
  # Training linkage
  required_training_modules: UUIDv4[] # Modules agent should complete before selling this

ProductCode:
  base: String
  format: "Insurer-specific product code"
  source: "Imported from insurer's product master"
```

---

## 2.13 Open Questions for Validation

These must be resolved with the specific insurer before technical design begins:

```
[V1]  What are the exact IRDAI training hour requirements for license renewal?
[V2]  Can agents represent multiple life insurers, or only one? (Changed recently?)
[V3]  What is the insurer's existing PAS API capability? REST? SOAP? Batch files?
[V4]  Does the insurer have a training platform? Can it integrate?
[V5]  What is the commission payment cycle? Monthly? Quarterly?
[V6]  What is the ADM:Agent ratio at this insurer? How does the hierarchy work?
[V7]  Are there existing WhatsApp groups? Can we integrate or must we create new?
[V8]  What is the insurer's agent data quality like? How complete are phone numbers?
[V9]  What languages does the insurer need on day 1? (Start with 2-3, expand later)
[V10] What is the insurer's legal interpretation of TRAI rules for agent calls?
[V11] Does the insurer have any existing AI/ML capabilities or data science team?
[V12] What is the insurer's appetite for AI-generated voice calls to agents?
[V13] What is the budget/timeline? (Affects build vs. buy decisions)
[V14] What is the insurer's cloud preference? (AWS/Azure/GCP affects architecture)
[V15] Data residency requirements — must everything be in India?
```

---

## Next Step: Phase 3 (System Behavior Design)

With Phase 1 and Phase 2 complete, Phase 3 designs the actual experience for each person: concrete conversation flows for Voice AI, exact WhatsApp message templates, ADM morning briefing format, decision engine rules, and integration behavior with insurer systems. Phase 3 turns this domain model into something a developer can build.
