# finance-management-app
# 📊 Finance Management App (Smart Personal Finance Assistant)

A mobile-first **personal finance management app** (inspired by Axio app) that helps users analyze and manage their UPI/SMS transactions with AI-powered features.

---

## ✨ Features

- 📩 **SMS & UPI Transaction Parsing** → Extracts debit/credit transactions from SMS & UPI logs.  
- 🏷️ **Smart Categorization** → AI model automatically categorizes transactions into Food, Shopping, Bills, etc.  
- 🎯 **Behavioral Analysis** → Detects spending habits & patterns using clustering (KMeans, DBSCAN).  
- 🚨 **Fraud & Gambling Detection** → Flags suspicious transactions (gambling, fraud sites, unknown merchants).  
- 🤖 **AI Chatbot** → Conversational assistant for queries like:
  - *"How much did I spend on food last month?"*  
  - *"Show me my biggest transactions this week."*  
- 📊 **Dashboard & Insights** → Visual reports of spending trends, savings, and alerts.  
- ☁️ **Cloud Sync** → Supabase backend for storing & syncing user data securely.

---

## 🛠️ Tech Stack

### 🔹 Mobile App (Frontend)
- **React Native (Expo)** → Cross-platform mobile development  
- **UI Design** → Figma for mockups, Tailwind (via NativeWind) for styling  

### 🔹 Backend
- **Supabase** → Database + authentication + storage  
- **FastAPI** → AI & ML model inference APIs  

### 🔹 AI/ML
- Transaction categorization (Rule-based + ML model)  
- Clustering (KMeans + DBSCAN) for spending behavior  
- NLP (lemmatization, keyword detection) for fraud/gambling detection  
- AI chatbot → powered by LLM (OpenAI API or fine-tuned model)

---

## 📂 Project Structure
