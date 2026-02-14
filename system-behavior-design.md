# Agent Activation & Retention System — Phase 3: System Behavior Design

## Relationship to Earlier Phases

Phase 1 (Domain Truth) captures who the people are and what happens today.
Phase 2 (Domain Model) defines the concepts, types, and state machines.
Phase 3 (this document) defines **what the system actually does** — the concrete behaviors that each person experiences. This is the last document before technical design and code.

---

## 3.0 The Configurability Principle

**Nothing in this system is hardcoded for a single insurer.**

Every value that might differ between insurers — thresholds, taxonomies, playbooks, message templates, scoring weights, archetype definitions, org hierarchy levels, even the dormancy reason tree — is a **tenant-configurable parameter** with a **platform default**.

This means the system has three layers:

```
┌─────────────────────────────────────────────────┐
│  PLATFORM DEFAULTS                               │
│  Sensible starting values. Work out of the box.  │
│  Informed by Phase 1 & 2 research.               │
│  Example: dormancy_threshold = 90 days           │
├─────────────────────────────────────────────────┤
│  TENANT CONFIGURATION                            │
│  Insurer overrides platform defaults.             │
│  Set during onboarding, adjustable anytime.       │
│  Example: Insurer A sets dormancy = 60 days      │
├─────────────────────────────────────────────────┤
│  LEARNED ADJUSTMENTS                             │
│  System learns from data and suggests changes.    │
│  Example: "For your agent base, 75 days seems    │
│  to be the actual inflection point, not 60."     │
│  Requires tenant approval to apply.               │
└─────────────────────────────────────────────────┘
```

### What's Configurable (Complete List)

```yaml
TenantConfiguration:
  # ─── IDENTITY & BRANDING ───
  branding:
    company_name: String
    logo_url: String
    primary_color: HexColor
    voice_ai_persona_name: String        # "Priya from XYZ Insurance"
    whatsapp_display_name: String
    
  # ─── ORGANIZATION STRUCTURE ───
  org_structure:
    hierarchy_levels: String[]           # ["Zone", "Region", "Branch", "Area"] or ["Region", "District"]
    hierarchy_depth: Integer             # 3, 4, or 5 levels
    adm_role_title: String              # "ADM", "Agency Manager", "Development Officer"
    agent_role_title: String            # "Agent", "Advisor", "Insurance Consultant"
    
  # ─── LIFECYCLE THRESHOLDS ───
  lifecycle:
    exam_attempt_window_days: Integer    # Default: 90
    licensed_to_at_risk_days: Integer    # Default: 60
    licensed_to_dormant_days: Integer    # Default: 120
    active_definition:
      min_policies: Integer              # Default: 1
      period_days: Integer               # Default: 30
    productive_definition:
      min_policies: Integer              # Default: 5
      period_days: Integer               # Default: 30
      consecutive_periods: Integer       # Default: 3
    at_risk_engagement_threshold: Float  # Default: 40.0
    at_risk_sales_decline_months: Integer # Default: 2
    at_risk_to_dormant_days: Integer     # Default: 60
    
  # ─── ENGAGEMENT RULES ───
  engagement:
    calling_hours: TimeWindow            # Default: 09:00-21:00 IST (TRAI requirement, applies to VOICE CALLS only)
    min_days_between_voice_calls: Integer # Default: 7
    min_days_between_whatsapp: Integer   # Default: 3
    max_contacts_per_month: Integer      # Default: 8
    dnd_scrub_required: Boolean          # Default: true
    consent_required_before_first_contact: Boolean  # Default: true
    
  # ─── LANGUAGES ───
  languages:
    supported: Language[]                # Minimum: [hi, en]
    default: Language                    # Default: hi
    voice_ai_languages: Language[]       # Subset that Voice AI supports
    training_content_languages: Language[]
    
  # ─── AGENT ARCHETYPES ───
  # Tenant can define their own archetypes or use platform defaults
  archetypes:
    custom_archetypes_enabled: Boolean   # Default: false (use platform defaults)
    archetypes: [
      {
        name: String,
        description: String,
        identification_rules: JSON,      # How to detect this archetype from signals
        default_playbook: PlaybookId?,   # Default engagement playbook
        proportion_estimate: Float       # Expected % of agent base
      }
    ]
    
  # ─── DORMANCY REASONS ───
  # Base taxonomy from platform, tenant can add custom sub-reasons
  dormancy_taxonomy:
    use_platform_default: Boolean        # Default: true
    custom_reasons: [                    # Additional reasons specific to this insurer
      {
        code: String,
        parent_code: String,             # Which platform category it falls under
        name: String,
        detection_hints: String[],       # Keywords/phrases that indicate this reason
        intervention_playbook: PlaybookId?
      }
    ]
    
  # ─── SCORING WEIGHTS ───
  scoring:
    engagement_score_weights:
      call_answer_rate: Float            # Default: 0.25
      whatsapp_response_rate: Float      # Default: 0.25
      training_completion: Float         # Default: 0.20
      recency_of_interaction: Float      # Default: 0.30
    engagement_score_decay_rate: Float   # Default: 0.02 per day without signal
    reactivation_model:
      use_platform_model: Boolean        # Default: true (until enough tenant data)
      custom_model_endpoint: String?     # Tenant can bring their own ML model
      
  # ─── PLAYBOOKS ───
  playbooks:
    use_platform_defaults: Boolean       # Default: true
    custom_playbooks: [Playbook]         # Tenant-defined playbooks (structure from Phase 2)
    playbook_overrides: {PlaybookId: JSON}  # Override specific steps in platform playbooks
    
  # ─── ADM EXPERIENCE ───
  adm_experience:
    morning_briefing_time: TimeOfDay     # Default: 08:00
    morning_briefing_enabled: Boolean    # Default: true
    weekly_summary_day: Enum[MON..SUN]   # Default: MON
    weekly_summary_enabled: Boolean      # Default: true
    max_agents_in_briefing: Integer      # Default: 5 (top priority agents)
    escalation_auto_route: Boolean       # Default: true
    
  # ─── INTEGRATIONS ───
  integrations:
    pas:                                 # Policy Admin System
      type: Enum[API_REST, API_SOAP, BATCH_FILE, MANUAL]
      endpoint: String?
      auth: JSON?                        # Encrypted credentials
      sync_frequency: Enum[REALTIME, HOURLY, DAILY]
      field_mapping: JSON                # Maps insurer fields to platform fields
    lms:                                 # License Management
      type: Enum[API, BATCH, MANUAL]
      # ... similar structure
    commission_system:
      type: Enum[API, BATCH, MANUAL]
      # ... similar structure
    existing_crm:
      type: Enum[SALESFORCE, ZOHO, CUSTOM, NONE]
      # ... similar structure
      
  # ─── QUOTAS & BILLING ───
  quotas:
    max_agents: Integer
    max_voice_calls_per_month: Integer
    max_whatsapp_messages_per_month: Integer
    max_adm_users: Integer
    max_concurrent_voice_calls: Integer
```

### The Configuration Lifecycle

```
Tenant Signs Up
       │
       ▼
Platform Defaults Applied
(system works immediately with reasonable behavior)
       │
       ▼
Onboarding Configuration
(tenant sets: branding, org structure, languages, integration endpoints)
       │
       ▼
System Starts Operating
(uses platform default playbooks, thresholds, scoring)
       │
       ▼
Data Accumulates (30-90 days)
       │
       ▼
System Suggests Adjustments
("Your agents go dormant faster than average — consider 
reducing at_risk threshold from 60 to 45 days")
       │
       ▼
Tenant Reviews & Approves Changes
       │
       ▼
Continuous Refinement
(system keeps learning, keeps suggesting, tenant keeps deciding)
```

This means Day 1 deployment requires ONLY: branding, org structure, languages, and integration credentials. Everything else works with intelligent defaults. The system gets smarter over time, per tenant.

---

## 3.1 The Five Feedback Loops (System Behavior Overview)

Before detailing each experience, here's how the system operates as a whole. Five loops running continuously:

```
LOOP 1: LISTEN ──────────────────────────────────────────────────────┐
│ Voice AI calls agents. WhatsApp messages agents. Training quizzes.  │
│ Every interaction produces SIGNALS into the Signal Stream.          │
│ External systems (PAS, LMS) also feed signals.                      │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ signals
                                   ▼
LOOP 2: UNDERSTAND ──────────────────────────────────────────────────┐
│ Signal Processor reads the stream. Updates Agent Understanding.     │
│ Computes lifecycle state. Detects dormancy reasons. Scores agents.  │
│ Identifies training gaps. Flags anomalies.                          │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ updated understanding
                                   ▼
LOOP 3: DECIDE ──────────────────────────────────────────────────────┐
│ Decision Engine evaluates each agent: What should we do next?       │
│ Selects playbook. Chooses channel, language, timing.                │
│ Respects constraints (consent, DND, frequency caps, TRAI hours).   │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ decisions
                          ┌────────┼────────┐
                          ▼        ▼        ▼
LOOP 4: ACT ─────────────────────────────────────────────────────────┐
│ Execute decisions:                                                   │
│ • Voice AI makes calls to agents                                    │
│ • WhatsApp bot sends messages, training, nudges                     │
│ • ADM gets briefings, alerts, action requests via WhatsApp          │
│ • Escalations routed to Regional Manager                            │
│ All actions produce NEW SIGNALS → back to Loop 1                    │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ aggregated data
                                   ▼
LOOP 5: LEARN ───────────────────────────────────────────────────────┐
│ Aggregate signals across all agents.                                │
│ Which playbooks actually work? Which dormancy reasons are growing?   │
│ Which products are agents confused about? Which ADMs are effective?  │
│ Feed insights to HQ dashboards.                                     │
│ Suggest configuration adjustments to tenant.                        │
│ Retrain ML models on accumulated data.                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3.2 Voice AI: Conversation Design

The Voice AI is not a robocaller. It's a conversational agent that has a specific purpose for each call, carries context from previous interactions, and produces structured signals from unstructured conversation.

### 3.2.1 Voice AI Persona

```yaml
VoicePersona:
  # Configurable per tenant
  name: String                       # "Priya", "Anita", "Neha" — a human name
  introduction: String               # "Hi, main {name} bol rahi hoon, {company} se"
  gender: Enum[FEMALE, MALE]         # Configurable; default: FEMALE (research shows 
                                     # higher answer rates for female voices in India)
  tone: "Warm, respectful, not corporate. Like a helpful colleague, not a call center."
  formality: "Uses 'aap' not 'tum'. Respectful but not stiff."
  
  # Behavior rules
  rules:
    - "NEVER sound scripted. Use natural conversation patterns."
    - "ALWAYS introduce yourself and state purpose within first 10 seconds."
    - "If agent sounds busy or irritated, offer to call back at a better time."
    - "If agent asks who gave you this number, explain: 'Aapka number aapki company ke records mein hai.'"
    - "If agent uses a different language than expected, SWITCH to that language if supported."
    - "NEVER pressure. The goal is understanding, not selling."
    - "Maximum call duration: 5 minutes for check-ins, 8 minutes for training/reactivation."
    - "End every call with a clear next step: 'Main aapko WhatsApp par ek training video bhejungi.'"
    - "If call quality is poor, acknowledge it: 'Network thoda kharab lag raha hai, kya aap sun pa rahe hain?'"
```

### 3.2.2 Conversation Flows

Each flow below defines the PURPOSE, OPENING, KEY BRANCHES, SIGNAL EXTRACTION, and CLOSING. These are not rigid scripts — they're guides for the AI. The actual conversation will vary.

**Flow A: First-Contact Call (Newly Onboarded Agent, Day 3–5)**

```yaml
purpose: "Welcome, set expectations, assess readiness, begin relationship"
trigger: "Agent entered LICENSED state within last 5 days"
language: "Agent's registered language, with fallback to Hindi"
max_duration: 300 seconds (5 minutes)

opening: |
  "Namaste {agent_name} ji, main {persona_name} bol rahi hoon {company_name} se. 
  Aapne recently {company_name} ke saath associate kiya hai, toh main aapka 
  swagat karne ke liye call kar rahi hoon. Kya aap 2-3 minute baat kar sakte hain?"

branches:
  agent_says_busy:
    response: "Koi baat nahi. Kab call karun toh convenient hoga aapke liye?"
    signal: {type: REACHABILITY_PREFERENCE, preferred_time: extracted_time}
    action: "Schedule callback at stated time"
    
  agent_says_yes:
    flow: |
      1. "Bahut accha. Aapke ADM {adm_name} ji hain, unse aapki baat hui hai?"
         → Captures: ADM engagement signal
         
      2. "Aapne koi product training complete kiya hai abhi tak?"
         → Captures: Training status awareness
         
      3. "Kya aapko kisi bhi product ke baare mein aur jaankari chahiye? 
          Term insurance, endowment, ya koi aur?"
         → Captures: Product interest, training need
         
      4. "Aapke area mein customers se baat karne mein koi dikkat aa rahi hai?"
         → Captures: Sales readiness, barriers
         
  agent_says_not_interested:
    response: |
      "Samajh sakti hoon. Kya main jaana sakti hoon ki koi specific wajah hai? 
      Hum aapki madad karna chahte hain."
    signal: {type: EARLY_DISENGAGEMENT, reason: extracted_if_stated}
    
  agent_says_wrong_number:
    response: "Maafi chahti hoon. Kya aap {agent_name} nahi hain?"
    signal: {type: CONTACT_INFO_INVALID, phone: agent_phone}
    action: "Flag for data correction"

closing: |
  "Dhanyavaad {agent_name} ji. Main aapko WhatsApp par ek chota sa video 
  bhejungi {identified_topic} ke baare mein. Aap dekh lijiye, aur agar koi 
  sawaal ho toh seedha reply kar dijiye. {adm_name} ji bhi aapko jaldi 
  contact karenge."

signals_produced:
  - VOICE_CALL_INITIATED
  - VOICE_CALL_OUTCOME
  - VOICE_CONVERSATION_ANALYZED (with: readiness_assessment, adm_contact_status,
    product_interests, barriers_identified, language_detected, sentiment)
  
follow_up_actions:
  - "Send WhatsApp training content based on identified interest/gap"
  - "Nudge ADM: 'New agent {name} is ready for your first meeting. 
    They're interested in {topic}.'"
```

**Flow B: Dormant Agent Check-In (90+ Days Inactive)**

```yaml
purpose: "Understand why agent stopped, classify dormancy reason, explore reactivation"
trigger: "Agent in DORMANT state, no successful contact in 30+ days"
language: "Agent's detected preferred language (from past interactions) or registered"
max_duration: 480 seconds (8 minutes)
context_loaded: "Last known interaction, last sale date, dormancy duration, previous dormancy reasons if any"

opening: |
  "Namaste {agent_name} ji, main {persona_name}, {company_name} se. 
  Humein laga ki kaafi samay ho gaya aapse baat kiye, toh socha check 
  kar lein ki sab theek hai. Kya 2-3 minute baat ho sakti hai?"

branches:
  agent_says_why_calling:
    response: |
      "Ji, aap {company_name} ke saath associate hain, aur humein laga 
      ki aapko kisi cheez mein madad chahiye ho toh hum help kar sakein."
    # Normalize the situation, don't make them feel tracked
    
  agent_shares_reason_unprompted:
    # Many agents will volunteer why they stopped if asked warmly
    action: "Listen, empathize, classify into dormancy taxonomy"
    signal: {type: DORMANCY_REASON_DETECTED, reason: classified_reason}
    
  agent_needs_prompting:
    flow: |
      1. "Aapki last sale {months_ago} mahine pehle thi. Kya uske baad 
          koi dikkat aayi selling mein?"
         → Captures: Sales barriers
         
      2. If no clear answer: "Kya products samajhne mein koi problem hai? 
          Ya customers mil nahi rahe?"
         → Captures: Training vs. prospecting issue
         
      3. If mentions competition: "Kya kisi aur company ke saath bhi 
          kaam kar rahe hain?"
         → Captures: Multi-insurer status, commission comparison
         
      4. If mentions ADM: "Kya {adm_name} ji se aapki regularly baat 
          hoti hai?"
         → Captures: ADM relationship quality
         
      5. If personal reason: "Samajh sakti hoon. Aap jab ready hon, 
          hum yahaan hain."
         → Captures: Personal reason, don't push
         
  agent_interested_in_restarting:
    response: |
      "Bahut accha! Main aapke liye ek plan banati hoon. Pehle ek 
      chota sa training {identified_product} ke baare mein, phir 
      {adm_name} ji se baat, aur phir pehli sale ki tayyari."
    signal: {type: REACTIVATION_INTEREST, products: mentioned_products}
    action: "Start appropriate reactivation playbook"
    
  agent_firmly_not_interested:
    response: |
      "Bilkul samajhti hoon. Kya aap chahte hain ki hum aapko aur 
      call na karein?"
    # CRITICAL: Respect opt-out, but ask clearly
    if_opts_out:
      signal: {type: CONSENT_CHANGED, new_status: REVOKED, channel: VOICE_AI}
      response: "Theek hai, hum aapko call nahi karenge. Agar kabhi 
                 interest ho toh aap {helpline_number} par call kar sakte hain."
    if_doesnt_opt_out:
      response: "Theek hai. Main 2-3 mahine baad ek baar check karungi. 
                 Tab tak WhatsApp par kuch useful information bhejti rahungi."
      signal: {type: CONTACT_PREFERENCE, frequency: LOW}

closing: |
  Always end with ONE specific next step, not vague promises.
  Good: "Kal subah 10 baje aapko WhatsApp par term insurance ka 
         ek 2-minute video bhejungi."
  Bad:  "Hum aapko support karte rahenge."

signals_produced:
  - VOICE_CALL_INITIATED
  - VOICE_CALL_OUTCOME
  - VOICE_CONVERSATION_ANALYZED (with: dormancy_reasons[], sentiment, 
    reactivation_interest, competitor_mentions[], adm_relationship_quality,
    product_interests[], training_needs[], preferred_language, 
    preferred_callback_time, key_quotes[])
    
nlu_extraction_requirements:
  # The NLU layer must extract these from the conversation:
  dormancy_reason_classification:
    - Map to DormancyReasonCode taxonomy
    - Confidence score for each detected reason
    - Support for multiple co-occurring reasons
    - Key phrases that triggered classification (for audit)
    
  sentiment_throughout_call:
    - Not just one sentiment for the whole call
    - Track sentiment shifts: "Started negative, became interested when 
      training was mentioned"
    - Final sentiment is what matters most for next action
    
  competitor_intelligence:
    - Which competitors mentioned by name
    - What specifically is better (commission, products, process)
    - This feeds into HQ strategic intelligence
    
  action_items:
    - Commitments the system made ("will send video")
    - Things the agent asked for ("explain ULIP charges")
    - Requests for ADM contact
    - These MUST be fulfilled — broken promises destroy trust
```

**Flow C: Congratulations Call (Agent Made a Sale)**

```yaml
purpose: "Celebrate success, reinforce positive behavior, identify next opportunity"
trigger: "POLICY_SOLD signal received for this agent"
timing: "Within 24 hours of sale confirmation"
max_duration: 180 seconds (3 minutes)
tone: "Genuinely happy. This might be their first sale ever."

opening: |
  "{agent_name} ji, badhai ho! Aapki {product_name} policy issue ho gayi hai! 
  Main {persona_name}, {company_name} se, aapko congratulate karne ke liye 
  call kar rahi hoon."

flow: |
  1. Celebrate: "Ye bahut acchi baat hai. {if first_sale: 'Ye aapki pehli 
     sale hai, ye toh aur bhi special hai!'}"
     
  2. Acknowledge effort: "Customer ko convince karna aasan nahi hota, 
     aapne accha kaam kiya."
     
  3. Gentle next step: "Kya aapke paas aur koi customer hai jise 
     {same_product} ya koi aur plan mein interest ho? Main aapko ek 
     accha approach bhej sakti hoon WhatsApp par."
     
  4. Reinforce ADM connection: "{adm_name} ji ko bhi bataya hai, 
     woh bhi khush honge."

signals_produced:
  - VOICE_CONVERSATION_ANALYZED (sentiment: POSITIVE, next_opportunity_identified,
    agent_confidence_level)
    
why_this_matters: |
  Most insurers NEVER call agents to say congratulations. They only call 
  to push targets. This builds trust and positive association with the 
  system. The agent thinks "these people actually care about my success."
```

**Flow D: License Expiry Reminder (60 Days Before Expiry)**

```yaml
purpose: "Alert agent about expiring license, help them complete requirements"
trigger: "LICENSE_EXPIRING_SOON signal, 60 days before expiry"
urgency: HIGH
max_duration: 300 seconds

opening: |
  "{agent_name} ji, main {persona_name}, {company_name} se. Ek important 
  information deni thi — aapka IRDAI license {expiry_date} ko expire ho 
  raha hai. Renewal ke liye kuch steps complete karne hain."

flow: |
  1. State the situation clearly:
     "Aapko renewal ke liye {remaining_hours} ghante training complete 
     karni hai. Abhi tak {completed_hours} ghante ho chuke hain."
     
  2. Offer help:
     "Main aapko WhatsApp par training modules bhej sakti hoon jo aap 
     phone pe complete kar sakte hain. Har module 30-45 minute ka hai."
     
  3. Create urgency without panic:
     "Agar license expire ho gaya toh dubara exam dena padega, toh 
     pehle se kar lein toh accha hai."
     
  4. If agent unaware of requirement:
     "Koi baat nahi, main abhi WhatsApp par poori process bhej deti hoon."

follow_up: "Trigger license renewal training pathway via WhatsApp"
```

### 3.2.3 Voice AI Technical Requirements

```yaml
voice_ai_requirements:
  # Speech Recognition
  asr:
    languages_required: "Tenant-configured, minimum Hindi + English"
    code_switching: "MUST handle Hindi-English mixing within same sentence"
    accuracy_target: "> 85% word accuracy for supported languages"
    noise_handling: "Must work with background noise (agent may be outdoors, in market)"
    dialect_tolerance: "Hindi has significant regional variation — system must handle"
    
  # Natural Language Understanding
  nlu:
    intent_detection: "Map conversation to structured intents from taxonomy"
    entity_extraction: "Product names, competitor names, time references, amounts"
    sentiment_analysis: "Per-utterance, with shift tracking"
    dormancy_reason_classification: "Map to DormancyReasonCode with confidence score"
    language_detection: "Real-time, to switch TTS language if needed"
    
  # Text to Speech
  tts:
    naturalness: "Must not sound robotic — agents will hang up on robotic voices"
    language_switching: "Can switch language mid-conversation if agent switches"
    voice_consistency: "Same voice persona across all calls to build recognition"
    speed_control: "Slightly slower than normal conversation — agents may be in noisy environments"
    
  # Call Management
  call_infra:
    concurrent_calls: "Tenant-configured quota"
    retry_logic: "If not answered, retry up to 2 more times on different days/times"
    call_recording: "All calls recorded, stored in tenant-isolated storage"
    fallback: "If AI can't understand or conversation goes off-rails, gracefully end with 'Main samajh nahi paayi, aapka ADM aapko call karenge'"
    dtmf_support: "For simple menu selections if voice isn't working well"
    
  # Quality & Safety
  safety:
    pii_in_calls: "NEVER read out full PAN, Aadhaar, or policy numbers on call"
    recording_consent: "Announce at start: 'Ye call quality ke liye record ho sakti hai'"
    no_financial_advice: "System MUST NOT give specific financial advice or guarantee returns"
    escalation_trigger: "If agent mentions self-harm, distress, or threats → immediate flag to human"
```

---

## 3.3 WhatsApp Bot: Interaction Design

WhatsApp is the primary channel for ongoing engagement because it's asynchronous (agent responds when convenient), rich (supports media, buttons, lists), and universal (already installed on every agent's phone).

### 3.3.1 Message Types & Templates

WhatsApp Business API requires pre-approved templates for outbound messages (outside the 24-hour reply window). The system needs these template categories:

```yaml
whatsapp_templates:
  
  # ─── WELCOME & ONBOARDING ───
  welcome_new_agent:
    category: UTILITY
    languages: [hi, en, ta, te, kn, mr, bn, ml, gu]  # All supported
    template_hi: |
      🎉 स्वागत है {agent_name} जी!
      
      आप {company_name} परिवार का हिस्सा बन गए हैं। 
      आपके ADM {adm_name} जी हैं — वो जल्द आपसे मिलेंगे।
      
      शुरू करने के लिए, यह 2 मिनट का video देखें:
      [Training Video Link]
      
      कोई सवाल हो तो यहीं पूछें! 👇
    buttons: ["▶️ Video देखें", "📞 ADM से बात करें"]
    
  # ─── TRAINING ───
  training_nudge:
    category: UTILITY
    template_hi: |
      {agent_name} जी, आपके लिए एक नया lesson तैयार है:
      
      📚 {module_name}
      ⏱️ {duration} मिनट
      
      {module_description}
    buttons: ["शुरू करें", "बाद में"]
    
  training_quiz:
    category: UTILITY
    template_hi: |
      चलिए देखते हैं कितना याद रहा! 
      
      सवाल {question_number}/{total_questions}:
      {question_text}
    buttons: ["{option_1}", "{option_2}", "{option_3}"]  # Dynamic
    # Note: WhatsApp allows max 3 buttons or a list of up to 10 items
    
  training_result:
    category: UTILITY
    template_hi: |
      {if score >= 80}
      🌟 शानदार! आपने {score}% score किया!
      {module_name} complete हो गया।
      {/if}
      
      {if score >= 50 && score < 80}
      👍 अच्छा प्रयास! {score}% score। 
      {weak_topic} पर एक और बार देखें तो और अच्छा होगा।
      {/if}
      
      {if score < 50}
      कोई बात नहीं, {score}% score आया। 
      चलिए {weak_topic} फिर से देखते हैं — यह बहुत 
      ज़रूरी topic है selling के लिए।
      {/if}
    # Note: WhatsApp templates don't support conditionals — 
    # system sends appropriate variant based on score
    
  # ─── ENGAGEMENT & CHECK-IN ───
  gentle_checkin:
    category: UTILITY
    template_hi: |
      {agent_name} जी, कैसे हैं आप?
      
      {contextual_message}
      
      क्या कोई चीज़ है जिसमें हम मदद कर सकें?
    buttons: ["Training चाहिए", "ADM से बात करनी है", "सब ठीक है"]
    
  # ─── CELEBRATION ───
  sale_congratulation:
    category: UTILITY
    template_hi: |
      🎊 बधाई हो {agent_name} जी!
      
      आपकी {product_name} policy issue हो गई! 
      {if first_sale}यह आपकी पहली sale है — शानदार शुरुआत!{/if}
      
      Commission: ₹{estimated_commission} (estimate)
      
      आगे और भी sales आएंगी! 💪
    
  # ─── REMINDERS ───
  license_expiry_reminder:
    category: UTILITY
    template_hi: |
      ⚠️ {agent_name} जी, आपका IRDAI license {expiry_date} 
      को expire हो रहा है।
      
      Renewal के लिए {remaining_hours} घंटे training 
      बाकी है। 
      
      अभी शुरू करें — सब WhatsApp पर ही हो जाएगा।
    buttons: ["Training शुरू करें", "Details चाहिए"]
    
  # ─── ADM-ATTRIBUTED MESSAGES ───
  # These appear to come FROM the ADM (with ADM's knowledge/approval)
  adm_personalized:
    category: UTILITY
    template_hi: |
      {agent_name} जी, मैं {adm_name}।
      
      {personalized_message}
      
      कोई सवाल हो तो बताइए।
    note: "These messages are GENERATED by the system but ATTRIBUTED to the ADM. 
           The ADM is notified that this message was sent on their behalf. 
           ADM can opt out of this feature."
```

### 3.3.2 Conversational WhatsApp Flows

Beyond templates, when an agent replies (opening the 24-hour free-form window), the bot can have a natural conversation:

```yaml
whatsapp_conversation_flows:

  agent_asks_question:
    description: "Agent sends a free-text question"
    handling: |
      1. NLU classifies the question:
         - Product question → Answer from product knowledge base, suggest training module
         - Process question → Answer with step-by-step guide
         - Commission question → Provide relevant commission info (NO specific amounts 
           for other agents — only THEIR commission data)
         - Complaint → Log as signal, escalate to ADM
         - Personal/off-topic → Gentle redirect: "Main insurance se related 
           sawaalon mein madad kar sakti hoon"
      
      2. If system can't answer confidently:
         "Ye accha sawaal hai. Main {adm_name} ji ko batati hoon, 
         woh aapko jaldi answer denge."
         → Creates ADM nudge with agent's question
         
      3. Always end with: "Aur kuch poochna hai?"
      
  agent_sends_voice_note:
    description: "Agent sends a WhatsApp voice note instead of typing"
    handling: |
      1. Transcribe voice note using ASR
      2. Process as if it were a text message
      3. Respond in text (most agents can read short responses even 
         if they prefer to send voice)
      4. If response is complex, option to send back a voice note 
         (TTS of the response)
    note: "Voice notes are VERY common with agents who are more comfortable 
          speaking than typing. The system MUST handle them."
          
  agent_shares_image:
    description: "Agent sends a photo (maybe of a proposal form, document, etc.)"
    handling: |
      1. OCR + image analysis to understand what it is
      2. If it's a filled proposal form: 
         "Ye form dikhta hai complete. Kya aapko submit karne mein madad chahiye?"
      3. If it's an error screenshot: 
         "Lag raha hai koi error aa raha hai. Main {adm_name} ji ko bhejti hoon."
      4. If unclear: 
         "Ye kya hai, thoda batayenge?"
```

### 3.3.3 Training Delivery via WhatsApp

```yaml
whatsapp_training:
  
  micro_module_flow:
    description: "A single learning unit delivered entirely via WhatsApp"
    structure:
      step_1_intro: 
        type: TEXT
        content: "Brief intro: what you'll learn and why it matters (2-3 lines)"
        
      step_2_content:
        type: VIDEO or INFOGRAPHIC
        constraints:
          video_max_duration: 180 seconds  # 3 minutes
          video_format: MP4, compressed for mobile
          video_size_max: 16 MB  # WhatsApp limit
          infographic_format: JPEG or PNG
          infographic_max_size: 5 MB
        content_rules:
          - "Use the agent's language — not English technical jargon"
          - "Show real scenarios, not theoretical concepts"
          - "For product training: show how to explain to a CUSTOMER, 
             not how the product works internally"
          - "For sales training: show actual conversation examples"
          
      step_3_quiz:
        type: INTERACTIVE (buttons or list)
        questions: 3-5 multiple choice
        immediate_feedback: true  # Tell them right/wrong after each question
        
      step_4_result:
        type: TEXT
        content: "Score, encouragement, and clear next step"
        
      step_5_practice_prompt:
        type: TEXT
        content: "Optional: 'Try explaining {concept} to a family member 
                  today and tell me how it went'"
        # This is powerful — it bridges training to real practice
        
  training_pathway:
    description: "A sequence of micro-modules building toward a capability"
    example_pathway_term_life:
      - module: "What is term life insurance? (Customer perspective)"
        day: 1
      - module: "Who needs term life? (Identifying prospects)"
        day: 3
      - module: "How to explain term life simply (Conversation script)"
        day: 5
      - module: "Common objections and how to handle them"
        day: 7
      - module: "How to fill the proposal form (Step by step)"
        day: 10
      - module: "Practice quiz: Full term life scenario"
        day: 12
      # After completion → ADM nudge: "Agent is ready for first term life sale"
```

---

## 3.4 ADM Experience: WhatsApp-Native Management

The ADM never opens a portal. Everything reaches them on WhatsApp. The system acts as their intelligent assistant.

### 3.4.1 Morning Briefing

```yaml
adm_morning_briefing:
  delivery_time: "Tenant-configurable, default 08:00 local time"
  channel: WhatsApp
  format: "Single message, scannable in 30 seconds"
  
  template: |
    🌅 Good morning {adm_name} ji
    
    📊 आज का snapshot:
    • Active agents: {active_count}  
    • At-risk: {at_risk_count} ({at_risk_change})
    • Dormant: {dormant_count}
    
    🔔 Today's priorities:
    
    {priority_1_emoji} {agent_name_1}: {one_line_context}
    → {suggested_action_1}
    
    {priority_2_emoji} {agent_name_2}: {one_line_context}
    → {suggested_action_2}
    
    {priority_3_emoji} {agent_name_3}: {one_line_context}
    → {suggested_action_3}
    
    {if any_celebration}
    🎉 {celebrating_agent}: {achievement}!
    {/if}
    
    Reply with agent name for details, or "all" for full list.
    
  example_instance: |
    🌅 Good morning Sunita ji
    
    📊 आज का snapshot:
    • Active agents: 12  
    • At-risk: 3 (↑1 since last week)
    • Dormant: 185
    
    🔔 Today's priorities:
    
    🟢 Priya Sharma: Training complete (8/10), ready for first sale
    → Call her today, help with first customer approach
    
    🟡 Rajan Kumar: Answered our call yesterday, interested in term plans
    → He wants to restart — schedule a meeting
    
    🔴 Amit Patel: 3 months no activity, license expiring in 45 days
    → Urgent: help him complete training hours
    
    🎉 Meena Devi: First sale yesterday! ₹24,000 premium!
    
    Reply with agent name for details, or "all" for full list.
    
  priority_selection_logic: |
    System selects 3-5 agents based on:
    1. URGENT items first (license expiring, compliance issue)
    2. HIGH-VALUE opportunities (agent showing reactivation signals)
    3. CELEBRATIONS (keep positive — not all doom and gloom)
    4. Rotate agents — don't show same ones daily unless urgent
    
    NEVER show more than 5 agents in morning briefing. 
    ADM is overwhelmed with 200 agents. 
    The system's job is to REDUCE cognitive load, not add to it.
```

### 3.4.2 ADM Agent Detail (On-Demand)

```yaml
adm_agent_detail:
  trigger: "ADM replies with agent name or taps on agent from briefing"
  
  response_template: |
    📋 {agent_name}
    Status: {lifecycle_state} ({days_in_state} days)
    Last contact: {last_contact_date} via {channel}
    
    📈 Recent activity:
    {recent_signals_summary}
    
    🎯 Recommendation:
    {system_recommendation}
    
    📞 Quick actions:
    1 — Mark "I called this agent"
    2 — Mark "I visited this agent"  
    3 — Send them a training module
    4 — Escalate to Regional Manager
    
  example_instance: |
    📋 Rajan Kumar
    Status: Dormant (94 days)
    Last contact: Yesterday via Voice AI
    
    📈 Recent activity:
    • Yesterday: Answered Voice AI call (4 min). Said he's interested 
      in selling term plans but doesn't understand the proposal process. 
      Also mentioned commission is lower than [Competitor].
    • Last week: Read WhatsApp training message but didn't respond
    • 3 months ago: Last sale (endowment, ₹15,000 premium)
    
    🎯 Recommendation:
    High reactivation potential. Call him today. Focus on:
    1. Walk through proposal process (his main barrier)
    2. Clarify commission structure for term plans
    
    📞 Quick actions:
    1 — Mark "I called this agent"
    2 — Mark "I visited this agent"
    3 — Send term plan proposal training video
    4 — Escalate to Regional Manager
    
  why_this_works: |
    The ADM gets CONTEXT they never had before. Previously, calling a 
    dormant agent was shooting in the dark. Now the ADM knows:
    - Agent is interested (Voice AI confirmed yesterday)
    - Specific barrier (proposal process)
    - Competitive threat (commission comparison)
    - Suggested talking points
    
    The ADM's call becomes 10x more effective.
```

### 3.4.3 ADM Alert (Real-Time)

```yaml
adm_alerts:
  description: "Time-sensitive notifications that shouldn't wait for morning briefing"
  
  alert_types:
    agent_reengagement_signal:
      trigger: "Dormant agent responds to WhatsApp or answers Voice AI call positively"
      urgency: HIGH
      message: |
        🟢 {agent_name} just responded!
        
        {brief_context}
        
        This is a good time to reach out personally.
        Reply 1 to see full details.
      why: "Reactivation window is narrow. If ADM calls while agent is still warm, 
            conversion is much higher."
            
    agent_completed_training:
      trigger: "Agent completes a training pathway"
      urgency: MEDIUM
      message: |
        📚 {agent_name} completed {training_name} (Score: {score}%)
        
        They may be ready for their first {product} sale.
        Can you schedule a joint customer call?
        
    agent_opted_out:
      trigger: "Agent opted out of a channel"
      urgency: MEDIUM
      message: |
        ⚠️ {agent_name} ने {channel} से opt out किया है।
        
        Reason (if stated): {reason}
        
        Personal outreach might help. Reply 1 for details.
        
    license_expiring:
      trigger: "Agent's license expiring in 30 days and training hours incomplete"
      urgency: HIGH
      message: |
        🔴 URGENT: {agent_name} का license {days_remaining} दिन में 
        expire हो रहा है। Training hours: {completed}/{required}
        
        Please help them complete the requirement.
        Reply 1 to send them training reminders.
        
    escalation_from_system:
      trigger: "System can't resolve something without human intervention"
      urgency: VARIES
      message: |
        📌 {agent_name}: {issue_description}
        
        System tried: {what_system_tried}
        Result: {outcome}
        
        Your input needed. Reply 1 for options.
```

### 3.4.4 ADM Weekly Summary

```yaml
adm_weekly_summary:
  delivery: "Monday morning (configurable), before morning briefing"
  channel: WhatsApp
  
  template: |
    📊 Weekly Report: {week_date_range}
    
    Your portfolio: {total_agents} agents
    
    ✅ Wins this week:
    {wins_list}
    
    📈 Movement:
    • New active: {newly_active_count}
    • Became at-risk: {newly_at_risk_count}
    • Re-engaged (from dormant): {reengaged_count}
    
    📊 Your numbers:
    • Agents you contacted: {adm_contacted_count}
    • System-assisted contacts: {system_contacted_count}
    • Training completions: {training_completions}
    
    🎯 Focus for next week:
    {top_3_focus_areas}
    
    Reply "detail" for full breakdown.
    
  example_instance: |
    📊 Weekly Report: 3-9 Feb 2026
    
    Your portfolio: 187 agents
    
    ✅ Wins this week:
    • Meena Devi: First sale! 🎉 (Term Life, ₹24,000)
    • Priya Sharma: Completed full product training (8/10)
    • Rajan Kumar: Re-engaged after 3 months dormancy
    
    📈 Movement:
    • New active: 1 (Meena Devi)
    • Became at-risk: 2 (Suresh Gupta, Anita Verma)
    • Re-engaged: 3 (Rajan, Deepak, Pooja)
    
    📊 Your numbers:
    • Agents you contacted: 8
    • System-assisted contacts: 23
    • Training completions: 5
    
    🎯 Focus for next week:
    1. Rajan Kumar: Ready for first sale, needs proposal help
    2. Suresh Gupta: Newly at-risk, find out why
    3. 4 agents with licenses expiring in March
    
    Reply "detail" for full breakdown.
```

### 3.4.5 ADM Action Logging

```yaml
adm_action_logging:
  description: "How the ADM tells the system they did something"
  
  design_principle: |
    Logging must be EFFORTLESS. If it takes more than 10 seconds, 
    ADMs won't do it. The system should make it as easy as replying 
    to a WhatsApp message.
  
  methods:
    reply_to_nudge:
      description: "ADM replies to an agent alert/nudge"
      example: 
        system: "🟢 Priya Sharma responded! Good time to call."
        adm_reply: "1"  # Marks "I called this agent"
        system: "Logged: You called Priya. How did it go? (Reply briefly or skip)"
        adm_reply: "Accha raha, meeting fix ki next week"
        system: "Great, noted! I'll check in with Priya after your meeting."
        
    quick_log:
      description: "ADM proactively logs an interaction"
      example:
        adm: "Met Rajan today"
        system: |
          Logged: Visit with Rajan Kumar.
          How did it go?
          1 — Very positive (likely to sell soon)
          2 — Okay (needs more support)
          3 — Not great (concerns)
          4 — Skip
        adm: "1"
        system: "Great! I'll prepare Rajan for his first sale."
        
    voice_note_log:
      description: "ADM sends a voice note about an agent interaction"
      handling: |
        1. Transcribe voice note
        2. Extract: which agent, what happened, what was discussed
        3. Store as ADM_AGENT_VISIT or ADM_AGENT_CALL signal
        4. Confirm: "Logged: You met Priya Sharma. She's interested 
           in term plans. Noted for follow-up."
```

---

## 3.5 Decision Engine: Behavior Specification

### 3.5.1 Decision Cadence

```yaml
decision_cadence:
  description: "How often the Decision Engine evaluates each agent"
  
  # Not all agents need evaluation at the same frequency
  frequency_by_state:
    ONBOARDED: "Daily — critical window, every day matters"
    LICENSED: "Every 2 days — waiting for first sale signals"
    FIRST_SALE: "Every 3 days — momentum building"
    ACTIVE: "Weekly — low touch, monitor for decline"
    PRODUCTIVE: "Bi-weekly — very low touch, watch for problems"
    AT_RISK: "Daily — intervention window"
    DORMANT: "Weekly for first 6 months, then monthly"
    LAPSED: "Never — no action possible"
    TERMINATED: "Never"
    
  # Decision engine runs in batches per tenant
  execution: |
    Daily processing order (dependencies require this sequence):
    1. Sync external data (midnight) — get latest policy/commission/license data
    2. Decision engine batch (06:00-07:00 local) — evaluate all agents due
    3. Generate morning briefings (08:00 local) — incorporates today's decisions
    
    IMPORTANT: Briefings MUST run AFTER the decision engine, not before.
    Briefings include "recommended next actions" which come from decision output.
    
    Within decision engine:
    a. Evaluate all agents due for evaluation
    b. Generate action queue sorted by priority
    c. Execute actions throughout the day per scheduling rules
    d. Respect all constraints (calling hours, frequency caps, consent)
```

### 3.5.2 Decision Rules (Priority Order)

```yaml
decision_rules:
  description: |
    Rules evaluated in order. First matching rule wins. 
    These are PLATFORM DEFAULTS — tenants can modify, reorder, add, or remove rules.
    
  rules:
    # ─── HARD CONSTRAINTS (Never override) ───
    - id: CONSTRAINT_001
      name: "No contact without consent"
      condition: "agent.consent.{channel} != GRANTED"
      action: DO_NOTHING
      note: "Immutable — cannot be overridden by tenant config"
      
    - id: CONSTRAINT_002
      name: "Respect opt-out"
      condition: "agent.consent.{any_channel} == REVOKED within last 30 days"
      action: DO_NOTHING for that channel
      
    - id: CONSTRAINT_003
      name: "No voice calls outside TRAI hours"
      condition: "action.channel == VOICE_AI AND current_time NOT IN tenant.engagement.calling_hours"
      action: "Defer voice call to next valid window"
      note: "TRAI 09:00-21:00 restriction applies to phone calls only. WhatsApp messages are NOT restricted by TRAI calling hours and can be sent anytime (though prefer agent's learned preferred_time_window for engagement quality)."
      
    - id: CONSTRAINT_004
      name: "Respect frequency caps"
      condition: "contacts_this_month >= tenant.engagement.max_contacts_per_month"
      action: DO_NOTHING
      
    - id: CONSTRAINT_005
      name: "No contact for terminated/lapsed"
      condition: "agent.lifecycle_state IN [TERMINATED, LAPSED]"
      action: DO_NOTHING
      
    # ─── URGENT ACTIONS ───
    - id: URGENT_001
      name: "License expiring — no training started"
      condition: "license_expiry < 60 days AND training_hours_remaining > 10"
      action: START_PLAYBOOK(license_renewal_urgent)
      priority: CRITICAL
      
    - id: URGENT_002
      name: "Productive agent suddenly at-risk"
      condition: "state == AT_RISK AND previous_state == PRODUCTIVE AND days_in_state < 14"
      action: SEND_NUDGE_TO_ADM(urgent_productive_agent_declining)
      priority: CRITICAL
      note: "Losing a productive agent is very expensive — immediate ADM intervention"
      
    # ─── OPPORTUNITY ACTIONS ───
    - id: OPP_001
      name: "Dormant agent re-engaged"
      condition: "state == DORMANT AND positive_signal_in_last_7_days"
      action: |
        1. SEND_NUDGE_TO_ADM(agent_reengagement_opportunity)
        2. CONTINUE_PLAYBOOK or START_PLAYBOOK based on dormancy reason
      priority: HIGH
      note: "Re-engagement window is narrow — act fast"
      
    - id: OPP_002
      name: "Agent completed training, ready for sale"
      condition: "training_pathway_completed AND no_sale_for_product"
      action: |
        1. SEND_NUDGE_TO_ADM(agent_ready_for_sale)
        2. SEND_WHATSAPP(practice_scenario for product)
      priority: HIGH
      
    - id: OPP_003
      name: "Agent's first sale"
      condition: "signal: POLICY_SOLD AND agent.total_policies == 1"
      action: |
        1. CELEBRATE(voice_call_congratulation)
        2. SEND_WHATSAPP(sale_congratulation)
        3. SEND_NUDGE_TO_ADM(first_sale_celebration)
      priority: HIGH
      
    # ─── PROACTIVE ENGAGEMENT ───
    - id: PROACTIVE_001
      name: "Newly licensed, no ADM contact"
      condition: "state == LICENSED AND days_in_state > 3 AND adm_contact_count == 0"
      action: |
        1. SCHEDULE_VOICE_CALL(first_contact_welcome)
        2. SEND_NUDGE_TO_ADM(new_agent_needs_contact)
      priority: MEDIUM
      
    - id: PROACTIVE_002
      name: "Active agent, no training in 30 days"
      condition: "state == ACTIVE AND days_since_last_training > 30"
      action: SEND_TRAINING(next_relevant_module)
      priority: LOW
      
    - id: PROACTIVE_003
      name: "Dormant agent, no contact attempt in 30 days"
      condition: "state == DORMANT AND days_since_last_contact > 30 AND reactivation_attempts < 3"
      action: START_PLAYBOOK(based_on_dormancy_reason)
      priority: MEDIUM
      
    - id: PROACTIVE_004
      name: "Dormant agent, 3+ failed reactivation attempts"
      condition: "state == DORMANT AND reactivation_attempts >= 3"
      action: |
        1. Reduce to quarterly check-in only
        2. If reactivation_probability < 0.1: CLOSE_AND_ARCHIVE
      priority: LOW
      note: "Don't waste resources on agents who've been tried repeatedly. 
             But don't fully give up either — one check-in per quarter."
             
    # ─── ADM COMPENSATION ───
    - id: ADM_COMP_001
      name: "ADM is unresponsive, agent needs help"
      condition: "adm.nudge_response_rate < 0.2 AND agent needs intervention"
      action: |
        1. System engages agent directly (don't wait for ADM)
        2. ESCALATE to Regional Manager: ADM not engaging
      priority: HIGH
      note: "The system compensates for weak ADMs. Agent shouldn't suffer 
             because their ADM is disengaged."
```

---

## 3.6 Integration Behavior

How the system connects with existing insurer systems. Designed for flexibility — each insurer has different systems.

### 3.6.1 Integration Adapter Pattern

```yaml
integration_architecture:
  principle: |
    The system doesn't know or care what specific PAS, LMS, or CRM the 
    insurer uses. It defines WHAT data it needs (the signal contract) and 
    the ADAPTER handles the how.
    
  adapter_types:
    REALTIME_API:
      description: "REST/SOAP API that pushes or pulls data in real-time"
      use_when: "Insurer has modern APIs"
      latency: "Seconds to minutes"
      
    BATCH_FILE:
      description: "CSV/Excel/XML files exchanged on schedule (SFTP, S3, email)"
      use_when: "Legacy systems that only export batch files"
      latency: "Hours to 1 day"
      
    WEBHOOK:
      description: "Insurer's system calls our API when events happen"
      use_when: "Insurer can configure outbound webhooks"
      latency: "Seconds"
      
    MANUAL_UPLOAD:
      description: "Insurer uploads files through a web interface"
      use_when: "No technical integration possible initially"
      latency: "Manual, 1-7 days"
      
    DATABASE_SYNC:
      description: "Direct database connection (read-only) with CDC"
      use_when: "Insurer provides direct DB access"
      latency: "Minutes"

  # What the adapters produce — regardless of source
  adapter_output:
    description: "All adapters transform insurer data into platform Signals"
    examples:
      - "PAS adapter receives policy issuance → emits POLICY_SOLD signal"
      - "LMS adapter receives exam result → emits exam_passed/exam_failed signal"
      - "Commission adapter receives payout file → emits COMMISSION_CREDITED signals"
      - "CRM adapter receives agent update → emits AGENT_DATA_UPDATED signal"
```

### 3.6.2 Data Flow: What We Need from Insurer

```yaml
required_data:
  # MUST HAVE (system can't function without these)
  critical:
    agent_master:
      fields: [agent_code, name, phone, email, status, adm_assignment, region, license_number, license_expiry, onboarding_date]
      frequency: "Daily sync minimum, real-time preferred"
      source: "PAS or HR system"
      
    policy_transactions:
      fields: [policy_number, agent_code, product_code, premium, sum_assured, issuance_date, status]
      frequency: "Daily sync minimum"
      source: "PAS"
      
    agent_hierarchy:
      fields: [agent_code, adm_code, branch, region, zone]
      frequency: "Weekly sync (changes less frequently)"
      source: "HR/Distribution system"
      
  # SHOULD HAVE (system works without but with reduced capability)
  important:
    commission_data:
      fields: [agent_code, commission_amount, commission_type, credit_date, policy_number]
      frequency: "Monthly minimum"
      impact_if_missing: "Can't show agents their earnings, can't detect commission concerns"
      
    training_history:
      fields: [agent_code, training_name, completion_date, score, hours]
      frequency: "After each training event"
      impact_if_missing: "System manages its own training but can't account for external training"
      
    license_management:
      fields: [agent_code, license_status, expiry_date, training_hours_completed]
      frequency: "Monthly"
      impact_if_missing: "Can't alert on expiring licenses"
      
  # NICE TO HAVE (enriches intelligence)
  enriching:
    product_catalog:
      fields: [product_code, product_name, category, premium_range, commission_rates]
      frequency: "On change"
      impact_if_missing: "System uses generic product references instead of insurer-specific"
      
    customer_complaints:
      fields: [agent_code, complaint_type, complaint_date, resolution_status]
      frequency: "Real-time or daily"
      impact_if_missing: "Can't detect operational dormancy reasons (claim rejections, etc.)"
```

### 3.6.3 DND Registry Check Flow

```yaml
dnd_check:
  description: |
    Before making voice calls, the system must verify the agent's phone number 
    against the NCPR (National Consumer Preference Register) DND registry.
    
  when_to_check:
    - "During agent import: batch check all phone numbers"
    - "Before each voice call: if last check > 30 days ago, re-check"
    - "Never required for WhatsApp messages (WhatsApp has its own consent)"
    
  result_storage:
    location: "agent_understanding.dnd.dnd_registered (Boolean)"
    timestamp: "agent_understanding.dnd.dnd_checked_at (Timestamp)"
    
  call_classification:
    description: |
      TRAI distinguishes "transactional" from "promotional" calls.
      Agent engagement calls are "service" calls (existing business relationship
      between insurer and agent), NOT promotional. This classification allows
      calls to DND-registered numbers.
      
    requirement: |
      Each tenant's legal team must confirm this classification.
      Stored as: tenant.config.engagement.dnd_call_classification = "transactional"
      If NOT confirmed: system will NOT make voice calls to DND-registered agents.
      Default: NOT confirmed (conservative).
      
  provider: |
    Configurable per tenant. Options:
    - NCPR API (government registry)
    - Third-party DND scrub service (e.g., ValueFirst)
    - Manual upload (for initial launch)
    Implementation: modules/integration/dnd_checker.py
```

---

## 3.7 HQ Feedback: Strategic Intelligence

The data flowing back to insurer HQ is one of the most valuable outputs of the system. No insurer today has structured data on WHY agents are inactive.

### 3.7.1 Dashboards (For Regional Manager and HQ)

```yaml
dashboards:
  # These are the ONLY interfaces that are web-based.
  # ADMs and agents NEVER use these.
  
  executive_dashboard:
    audience: "Distribution Head, CEO, Board"
    refresh: "Daily"
    metrics:
      - headline: "Agent Activation Rate"
        current: "{active_agents / total_agents}%"
        trend: "↑↓ vs last month, vs last quarter"
        benchmark: "vs industry average"
        
      - headline: "Reactivation Success"
        current: "{agents_reactivated_this_month}"
        detail: "From dormant → active in last 30 days"
        attribution: "By intervention type (Voice AI, WhatsApp, ADM, combined)"
        
      - headline: "Dormancy Reason Distribution"
        visualization: "Pie/bar chart of primary dormancy reasons"
        insight: "Top growing reason, top shrinking reason"
        action: "Click through to see specific agents per reason"
        
      - headline: "Training Impact"
        current: "Agents who completed training → sold within 30 days: {x}%"
        by_module: "Which training modules have highest training-to-sale conversion"
        
      - headline: "ADM Effectiveness"
        current: "Portfolio health distribution across ADMs"
        highlight: "Top 5 ADMs, Bottom 5 ADMs (by activation rate)"
        
      - headline: "Competitive Intelligence"
        current: "Competitors mentioned in agent conversations this month"
        detail: "What specifically agents say about competitors"
        source: "Aggregated from Voice AI conversations (anonymized)"
        
      - headline: "System ROI"
        current: "New premium from reactivated agents: ₹{amount}"
        cost: "System cost this month: ₹{amount}"
        roi: "{premium / cost}x return"
  
  regional_manager_dashboard:
    audience: "Regional/Zonal Manager"
    refresh: "Daily"
    scope: "Their regions only"
    metrics:
      - "ADM-wise performance comparison"
      - "Agent lifecycle state distribution by area"
      - "Reactivation funnel: contacted → engaged → trained → sold"
      - "Escalations pending their action"
      - "Weekly trend: which areas improving, which declining"
```

### 3.7.2 Strategic Reports (Periodic)

```yaml
strategic_reports:
  
  dormancy_intelligence_report:
    frequency: "Monthly"
    audience: "Distribution + Product + Training teams"
    content:
      - "Dormancy reason breakdown with month-over-month trend"
      - "Top 3 reasons driving dormancy growth"
      - "Regional variations in dormancy reasons"
      - "Correlation: dormancy reasons vs. agent tenure, age, product mix"
      - "Specific product-level insights: 'Agents with only ULIP training 
         have 2x dormancy rate vs. agents with term + endowment training'"
      - "Competitor intelligence summary"
      - "Recommended actions for Product team, Training team, Distribution team"
      
  training_effectiveness_report:
    frequency: "Monthly"
    audience: "Training team"
    content:
      - "Training completion rates by module, by language"
      - "Quiz score distributions"
      - "Training-to-sale conversion by module"
      - "Modules with highest drop-off"
      - "Agent-requested training topics (from conversations)"
      - "Recommended new content areas"
      
  adm_performance_report:
    frequency: "Monthly"
    audience: "Distribution Head, Regional Managers"
    content:
      - "ADM ranking by portfolio health"
      - "ADM engagement patterns (who contacts agents, who doesn't)"
      - "ADM response to system nudges"
      - "Correlation: ADM engagement → agent activation"
      - "ADMs who need support vs. ADMs who need accountability"
```

---

## 3.8 Consent & Compliance Behavior

### 3.8.1 Consent Collection Flow

```yaml
consent_flow:
  description: |
    Before the system contacts any agent, consent must be obtained.
    The insurer collects initial consent during agent onboarding (physical 
    or digital form). The system then confirms consent digitally.
    
  initial_consent:
    method: "During agent onboarding, insurer's existing process"
    what_they_consent_to: |
      "I consent to receive communications from {company_name} via 
      phone calls (including automated calls), WhatsApp messages, and SMS 
      for purposes of training, support, and business development."
    stored_as: "GRANTED for all channels"
    
  digital_confirmation:
    timing: "First WhatsApp message to agent"
    message: |
      Welcome to {company_name} support!
      
      We'll send you:
      📚 Training content
      📊 Your performance updates  
      📞 Occasional check-in calls
      
      You can opt out anytime by replying STOP.
      
      Reply OK to continue.
    if_no_reply: "Send one reminder after 3 days. If still no reply, mark as NOT_CONFIRMED"
    if_stop: "Mark consent as DENIED for WhatsApp"
    
  ongoing_opt_out:
    whatsapp: "Agent can reply STOP at any time → immediate opt-out"
    voice_ai: "Agent can say 'don't call me again' during any call → immediate opt-out"
    system_behavior: |
      On opt-out:
      1. Immediately stop all outreach on that channel
      2. Log CONSENT_CHANGED signal
      3. Notify ADM: "{agent_name} opted out of {channel}"
      4. Try alternate channel if available and consented
      5. If opted out of ALL channels, mark for ADM-only engagement
```

---

## 3.9 System Bootstrapping: Day 1 to Day 90

How the system comes to life for a new tenant:

```yaml
bootstrapping:
  
  day_0_to_7:
    name: "Setup & Data Load"
    actions:
      - "Tenant configuration: branding, org structure, languages"
      - "Integration setup: connect to PAS, load agent master data"
      - "WhatsApp Business Account provisioning + template approval"
      - "Voice AI persona configuration + language testing"
      - "Load initial agent data → all agents enter system with UNKNOWN state"
      - "System computes initial lifecycle states from historical data:
         • Has active policies in last 90 days? → ACTIVE
         • Has policies but none in last 90 days? → AT_RISK or DORMANT
         • Licensed but never sold? → LICENSED
         • License expired? → LAPSED"
    outcome: "System has complete agent base with computed lifecycle states"
    
  day_7_to_30:
    name: "Pilot Phase"
    scope: "Start with ONE region, 2-3 ADMs, ~500 agents"
    actions:
      - "Send welcome WhatsApp to all pilot agents"
      - "Begin morning briefings for pilot ADMs"
      - "Start Voice AI calls to dormant agents (20-30/day initially)"
      - "Monitor: call pickup rates, WhatsApp read rates, ADM engagement"
      - "Collect dormancy reasons from Voice AI conversations"
      - "Adjust Voice AI scripts based on actual conversation patterns"
      - "Tune NLU models on real data"
    outcome: |
      "Validated: agents pick up calls, respond to WhatsApp, ADMs find 
      briefings useful. Initial dormancy reason distribution captured."
    success_criteria:
      - "Voice AI call answer rate > 30%"
      - "WhatsApp message read rate > 50%"
      - "ADM morning briefing read rate > 70%"
      - "At least 50 dormancy reasons classified"
      
  day_30_to_60:
    name: "Expand & Optimize"
    scope: "Expand to 3-5 regions, 10-15 ADMs"
    actions:
      - "Activate training pathways via WhatsApp"
      - "Start reactivation playbooks for dormant agents"
      - "Begin tracking training-to-sale correlation"
      - "Activate HQ dashboards"
      - "First dormancy intelligence report"
      - "Adjust thresholds based on tenant-specific data"
    outcome: "System operating at meaningful scale, first reactivation successes"
    success_criteria:
      - "At least 5 agents reactivated (dormant → first sale)"
      - "At least 20 agents re-engaged (dormant → responding)"
      - "ADM reporting value from briefings"
      
  day_60_to_90:
    name: "Full Deployment"
    scope: "All regions, all ADMs, all agents"
    actions:
      - "Full rollout"
      - "ML model training on 60 days of tenant data"
      - "Playbook optimization based on what's working"
      - "First ROI report"
      - "Configuration refinement suggestions from system"
    outcome: "System fully operational, measurable business impact"
```

---

## 3.10 What Phase 4 (Technical Design) Must Address

Phase 3 defines WHAT the system does. Phase 4 defines HOW to build it. Based on everything above, Phase 4 must cover:

```yaml
phase_4_scope:
  - "Signal Store architecture (append-only event log — Kafka + PostgreSQL/TimescaleDB)"
  - "Agent Understanding service (real-time materialized view from signal stream)"
  - "Lifecycle State Machine engine (evaluates signals, computes state transitions)"
  - "Decision Engine service (batch + real-time evaluation, rule engine)"
  - "Voice AI integration layer (provider abstraction, conversation management, NLU pipeline)"
  - "WhatsApp Bot service (Business API integration, conversation state, template management)"
  - "Training content management (storage, delivery, progress tracking)"
  - "ADM notification service (WhatsApp-based, formatting, action tracking)"
  - "Integration adapter framework (pluggable adapters per insurer system)"
  - "Dashboard & reporting (web-based, for Regional Manager and HQ only)"
  - "Tenant configuration service (the full TenantConfiguration model)"
  - "Multi-tenancy layer (RLS, tenant context propagation, data isolation)"
  - "RBAC layer (permission model — simplified from original doc, most users are on WhatsApp not portal)"
  - "Audit & compliance logging"
  - "ML pipeline (reactivation prediction, engagement scoring, NLU model training)"
  - "Infrastructure (cloud, databases, queues, storage, monitoring)"
  - "API design (internal services + external integration endpoints)"
```

This is the complete Phase 3. Combined with Phase 1 and Phase 2, you now have enough to start technical design.
