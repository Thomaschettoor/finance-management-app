# Kotlin Client Configuration Guide

This document explains how to integrate the Finance Management API with your Kotlin frontend application.

---

## 📄 Generated Files

1. **`openapi.json`** - Compact OpenAPI 3.1.0 specification
2. **`openapi-formatted.json`** - Human-readable formatted version (use this for review)

---

## 🚀 Server Configuration

### Local Development
- **Base URL**: `http://localhost:8000`
- **API Prefix**: `/api/v1`
- **Docs**: `http://localhost:8000/docs` (Swagger UI)

### Production Setup
When deploying, update the base URL to your production server:
```
https://your-domain.com
```

---

## 🔐 Authentication

All API endpoints (except `/health`) require authentication via **Supabase JWT**.

### Headers Required:
```
Authorization: Bearer <SUPABASE_JWT_TOKEN>
Content-Type: application/json
```

### Getting the Token:
1. User authenticates with Supabase
2. Retrieve the session token: `supabase.auth.session()?.access_token`
3. Include it in all API requests

---

## 📱 Kotlin/Android Integration Options

### Option 1: Auto-Generate Client with OpenAPI Generator

Install OpenAPI Generator:
```bash
# Using Homebrew (macOS)
brew install openapi-generator

# Or download JAR
wget https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/7.3.0/openapi-generator-cli-7.3.0.jar -O openapi-generator-cli.jar
```

Generate Kotlin client:
```bash
openapi-generator generate \
  -i openapi.json \
  -g kotlin \
  -o ./kotlin-client \
  --additional-properties=dateLibrary=java8,serializationLibrary=gson
```

Or for Android with Retrofit:
```bash
openapi-generator generate \
  -i openapi.json \
  -g kotlin \
  -o ./kotlin-client \
  --library jvm-retrofit2 \
  --additional-properties=dateLibrary=java8,serializationLibrary=gson
```

### Option 2: Manual Retrofit Setup

Add dependencies to `build.gradle.kts`:
```kotlin
dependencies {
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
}
```

Create API service interface:
```kotlin
interface FinanceApiService {
    
    @GET("api/v1/dashboard/summary")
    suspend fun getDashboardSummary(): Response<DashboardSummary>
    
    @GET("api/v1/transactions/")
    suspend fun getTransactions(
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
        @Query("category") category: String? = null,
        @Query("search") search: String? = null,
        @Query("sort") sort: String? = "recent"
    ): Response<TransactionListResponse>
    
    @POST("api/v1/transactions/")
    suspend fun createTransaction(
        @Body request: CreateTransactionRequest
    ): Response<CreateTransactionResponse>
    
    @GET("api/v1/analytics/risk_score")
    suspend fun getRiskScore(): Response<RiskScoreResponse>
    
    @POST("api/v1/chat/query")
    suspend fun chatQuery(
        @Body request: ChatQueryRequest
    ): Response<ChatQueryResponse>
}
```

Setup Retrofit client with authentication:
```kotlin
object ApiClient {
    private const val BASE_URL = "http://10.0.2.2:8000/" // Android emulator
    // Or use "http://YOUR_LOCAL_IP:8000/" for physical device
    
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }
    
    private val authInterceptor = Interceptor { chain ->
        val token = getSupabaseToken() // Your token retrieval logic
        val request = chain.request().newBuilder()
            .addHeader("Authorization", "Bearer $token")
            .build()
        chain.proceed(request)
    }
    
    private val client = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(loggingInterceptor)
        .build()
    
    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(client)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
    
    val apiService: FinanceApiService = retrofit.create(FinanceApiService::class.java)
}
```

### Option 3: Ktor Client

Add dependencies:
```kotlin
dependencies {
    implementation("io.ktor:ktor-client-android:2.3.7")
    implementation("io.ktor:ktor-client-content-negotiation:2.3.7")
    implementation("io.ktor:ktor-serialization-gson:2.3.7")
    implementation("io.ktor:ktor-client-auth:2.3.7")
    implementation("io.ktor:ktor-client-logging:2.3.7")
}
```

Setup Ktor client:
```kotlin
val client = HttpClient(Android) {
    install(ContentNegotiation) {
        gson()
    }
    install(Auth) {
        bearer {
            loadTokens {
                BearerTokens(getSupabaseToken(), "")
            }
        }
    }
    install(Logging) {
        level = LogLevel.ALL
    }
}

// Usage
suspend fun getDashboardSummary(): DashboardSummary {
    return client.get("http://10.0.2.2:8000/api/v1/dashboard/summary").body()
}
```

---

## 🔄 Network Configuration for Android

### Android Emulator
Use `http://10.0.2.2:8000` to access `localhost` on your development machine.

### Physical Device
1. Ensure your device and computer are on the same WiFi network
2. Find your computer's local IP: `ifconfig | grep "inet "` (macOS/Linux)
3. Use `http://YOUR_LOCAL_IP:8000` as base URL
4. Add network security config to allow cleartext HTTP during development:

Create `res/xml/network_security_config.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">10.0.2.2</domain>
        <domain includeSubdomains="true">YOUR_LOCAL_IP</domain>
    </domain-config>
</network-security-config>
```

Add to `AndroidManifest.xml`:
```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ...>
```

---

## 📋 Key API Endpoints

### 🏠 Dashboard
- `GET /api/v1/dashboard/summary` - User greeting, monthly totals and transaction_count for the current month
- `GET /api/v1/dashboard/recent_transactions?limit=5` - Recent transactions (newest first)

### 💳 Transactions
- `GET /api/v1/transactions/` - List with filters (page, limit, search, sort, date range or month/year for a specific calendar month)
- `POST /api/v1/transactions/` - Create new transaction
- `GET /api/v1/transactions/{id}` - Transaction details
- `GET /api/v1/transactions/merchants?q=search` - Merchant autocomplete

### 📊 Analytics
- `GET /api/v1/analytics/risk_score` - Financial risk assessment
- `GET /api/v1/analytics/spending_summary` - Current month spending
- `GET /api/v1/analytics/category_breakdown` - Spending by category
- `GET /api/v1/analytics/monthly_forecast` - Spending prediction
- `GET /api/v1/analytics/alerts` - Spending alerts
- `GET /api/v1/analytics/recommendations` - Financial recommendations

### 🤖 AI Chat
- `POST /api/v1/chat/query` - Chat with AI assistant
- `GET /api/v1/chat/suggestions` - Suggested questions
- `GET /api/v1/chat/context` - Chat context data
- `GET /api/v1/chat/history` - Chat history (last 20)

### 📂 Categories
- `GET /api/v1/categories` - List all categories

### 👤 User
- `GET /api/v1/user/profile` - User profile info

### ❤️ Health
- `GET /health` or `GET /api/v1/health` - Server health check

---

## 📦 Sample Data Models (Kotlin)

```kotlin
// Dashboard
data class DashboardSummary(
    val user_name: String,
    val total_credit: Double,
    val total_debit: Double,
    val currency: String
)

// Transactions
data class Transaction(
    val transaction_id: String,
    val merchant: String,
    val category: String?,
    val amount: Double,
    val type: String, // "credit" or "debit"
    val date: String
)

data class TransactionListResponse(
    val page: Int,
    val limit: Int,
    val total: Int,
    val transactions: List<Transaction>
)

data class CreateTransactionRequest(
    val merchant: String,
    val amount: Double,
    val category_id: String? = null,
    val date: String? = null,
    val notes: String? = null
)

// Analytics
data class RiskScoreResponse(
    val risk_score: Int,
    val risk_level: String, // "LOW", "MODERATE", "HIGH"
    val message: String
)

data class CategoryBreakdown(
    val category_id: String,
    val amount: Double,
    val percentage: Double
)

// Chat
data class ChatQueryRequest(
    val query: String
)

data class ChatQueryResponse(
    val response: String,
    val context_used: Map<String, Any>
)
```

---

## 🧪 Testing

Test the API with your browser or curl:
```bash
# Health check
curl http://localhost:8000/health

# Get dashboard (requires auth token)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/dashboard/summary
```

---

## 🛠️ Troubleshooting

### Can't connect from Android device
- Check firewall settings on your computer
- Verify you're using the correct IP address
- Ensure the FastAPI server is bound to `0.0.0.0:8000` (not just `127.0.0.1`)

### Authentication errors
- Verify the Supabase JWT token is valid and not expired
- Check the `Authorization` header format: `Bearer <token>`
- For SMS ingestion use `POST /api/v1/sms/ingest` with JSON body `{ sms_text, sender, timestamp? }`
- Ensure `get_current_user` dependency is working in the backend

### CORS issues (if using web frontend)
- CORS is already configured in `main.py` with `allow_origins=["*"]`
- Adjust in production to only allow your frontend domain

---

## 📚 Additional Resources

- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)
- [Retrofit Documentation](https://square.github.io/retrofit/)
- [Ktor Client](https://ktor.io/docs/client.html)
- [Supabase Auth](https://supabase.com/docs/guides/auth)

---

**Need help?** Check the interactive API documentation at `http://localhost:8000/docs`
