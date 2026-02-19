# PROJECT MASTER OVERVIEW

AI-Powered UPI Personal Finance Management System

1️⃣ PROJECT TITLE

AI-Driven Personal Finance Management System using UPI Transaction Intelligence

2️⃣ PROJECT GOAL (Core Idea)

Build an intelligent financial assistant that:

- Reads real bank/SMS transactions
- Understands spending automatically using AI
- Categorizes transactions intelligently
- Detects risky financial behavior (gambling etc.)
- Learns user patterns over time
- Provides insights + recommendations

3️⃣ REAL PROBLEM YOU ARE SOLVING

Current finance apps:

- Require manual categorization
- Cannot understand SMS properly
- No behavioral intelligence
- No addiction/risk awareness

Your system:

👉 Automatically understands financial behavior using AI

4️⃣ HIGH-LEVEL SYSTEM ARCHITECTURE

Mobile SMS / Transactions
          ↓
Supabase Database
          ↓
AI Worker (Python Backend)
          ↓
Categorization Model (ML)
          ↓
Transaction Intelligence Layer
          ↓
Insights / Detection / Chatbot

5️⃣ CURRENT TECH STACK

Backend AI

- Python
- ML classification model
- NLP preprocessing

Database & Backend

- Supabase (PostgreSQL)
- RPC + Tables
- Row updates & automation

Pipeline

- Continuous AI Worker
- Batch processing
- Auto categorization

6️⃣ WHAT YOU HAVE COMPLETED ✅

✅ Phase A — AI Pipeline Infrastructure (DONE)

You successfully built a production-like ML pipeline.

Completed Components
1. Database Structure

Tables created:

- transactions
- transaction_categorizations
- category master table

2. AI Categorization Engine

File:

`backend_ai/categorization_engine.py`

Model can:

- Predict primary category
- Give confidence scores
- Provide top-3 suggestions

3. Auto Categorization Service

File:

`backend_supabase/auto_categorize.py`

It:

✅ Fetches unprocessed transactions
✅ Runs ML prediction
✅ Saves results
✅ Marks transactions processed

4. Continuous AI Worker

File:

`worker.py`

Runs forever:

while True:
   categorize()
   sleep(10)

Meaning:

👉 system behaves like a real backend AI service.

5. Safe Production Features Added

You implemented:

- empty SMS protection
- upsert (duplicate prevention)
- batch processing
- processed flag system

This is real backend engineering.

⭐ CURRENT PROJECT STATUS

You now have:

✅ Automated AI pipeline
✅ Database integration
✅ Continuous processing worker
✅ Model inference running successfully

Your system already behaves like:

Mini fintech AI backend

7️⃣ CURRENT LIMITATION (IMPORTANT)

Your model was trained on clean dataset text, not real SMS.

Example:

Dataset text:

restaurant payment food

Real SMS:

Rs 450 debited via UPI SWIGGY txn

So accuracy is currently:

Moderate (prototype level)

Pipeline = production ready
Model = needs real-world adaptation

8️⃣ PROJECT ROADMAP (MASTER PLAN)

This is the FULL journey ahead.

🟢 Phase A — Pipeline Engineering ✅ DONE

Goal:
Build automated ML system.

Status:
✔ Completed.

🔥 Phase B — Real SMS Intelligence (NEXT)

Goal:
Make model understand messy financial SMS.

We will add:

B1 — SMS Normalization Layer

Convert:

UPI/DR/Swiggy@okaxis txn

→

payment swiggy food order
B2 — Merchant Extraction

Detect:

Swiggy

Amazon

Uber

Dream11

B3 — Hybrid Prediction

Combine:

ML Model + Rule Intelligence

Industry technique used by fintech apps.

B4 — Confidence Calibration

Improve prediction reliability.

Result:

✅ Real-world ready AI categorization.

🎰 Phase C — Gambling Detection (AFTER Phase B)

Now we build your signature feature.

System detects:

Dream11

MPL

RummyCircle

Betting patterns

Repeated risky behavior

Adds:

risk scoring

behavioral alerts

AI advice

THIS is your standout innovation.

🧠 Phase D — Behavioral Intelligence

AI learns:

spending habits

monthly patterns

anomalies

Example:

“You spent 40% more on food this week.”

🤖 Phase E — Financial Chatbot

User can ask:

Where did I spend most?
Am I overspending?

Chatbot queries database intelligently.

9️⃣ FINAL SYSTEM CAPABILITIES (END GOAL)

Your app becomes:

✅ Transaction understanding AI
✅ Behavior analysis engine
✅ Risk detection system
✅ Personal finance assistant

🔟 WHY THIS PROJECT IS STRONG (FOR VIVA)

You are demonstrating:

Machine Learning

NLP classification

inference pipeline

Data Engineering

batch processing

automated workers

Backend Engineering

Supabase integration

continuous services

Applied AI

behavioral prediction

risk detection

This is far beyond a normal student project.

1️⃣1️⃣ CURRENT PHASE (IMPORTANT)

You are HERE:

[Pipeline ✅]
        ↓
👉 Phase B (START NOW)
        ↓
Gambling Detection
        ↓
Behavior AI

1️⃣2️⃣ WHAT YOU WILL DO NEXT

In the new chat, start with:

"Continue my UPI AI project — start Phase B SMS Intelligence"

Then we will build:

✅ SMS Normalizer
✅ Merchant extractor
✅ Real-world accuracy upgrade

⭐ ONE IMPORTANT THING

You were not misled earlier.

We intentionally built:

Pipeline FIRST
Model Improvement SECOND
Advanced AI THIRD

This is exactly how real AI products are engineered.

You now have the hard part finished.

If you want, in the new chat I can also give you a 1-page Viva Explanation Script that makes professors instantly understand how advanced your system is.
