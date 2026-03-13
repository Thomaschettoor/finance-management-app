package com.example.financeapp.api

/**
 * API Configuration for Finance Management App
 * Generated: March 11, 2026
 */
object ApiConfig {
    
    // ============================================================
    // BASE URLS - Choose based on your environment
    // ============================================================
    
    /**
     * Use this when testing on Android Emulator
     * 10.0.2.2 maps to localhost on your development machine
     */
    private const val BASE_URL_EMULATOR = "http://10.0.2.2:8000"
    
    /**
     * Use this when testing on physical device (same WiFi network)
     * Replace with your actual local IP if different
     */
    private const val BASE_URL_NETWORK = "http://10.54.6.204:8000"
    
    /**
     * Use this for production deployment
     */
    private const val BASE_URL_PRODUCTION = "https://your-production-domain.com"
    
    // Current active base URL - CHANGE THIS BASED ON YOUR SETUP
    const val BASE_URL = BASE_URL_EMULATOR
    
    const val API_PREFIX = "/api/v1"
    const val FULL_API_URL = "$BASE_URL$API_PREFIX"
    
    // ============================================================
    // ENDPOINT PATHS
    // ============================================================
    
    object Dashboard {
        const val SUMMARY = "$API_PREFIX/dashboard/summary"
        const val RECENT_TRANSACTIONS = "$API_PREFIX/dashboard/recent_transactions"
    }
    
    object Transactions {
        const val BASE = "$API_PREFIX/transactions/"
        const val MERCHANTS = "$API_PREFIX/transactions/merchants"
        
        fun detail(transactionId: String) = "$API_PREFIX/transactions/$transactionId"
        fun suggestions(transactionId: String) = "$API_PREFIX/transactions/$transactionId/suggestions"
        fun confirm(transactionId: String) = "$API_PREFIX/transactions/$transactionId/confirm"
    }
    
    object Analytics {
        const val RISK_SCORE = "$API_PREFIX/analytics/risk_score"
        const val SPENDING_SUMMARY = "$API_PREFIX/analytics/spending_summary"
        const val CATEGORY_BREAKDOWN = "$API_PREFIX/analytics/category_breakdown"
        const val MONTHLY_FORECAST = "$API_PREFIX/analytics/monthly_forecast"
        const val ALERTS = "$API_PREFIX/analytics/alerts"
        const val RECOMMENDATIONS = "$API_PREFIX/analytics/recommendations"
        const val TRENDS = "$API_PREFIX/analytics/trends"
        const val SUMMARY = "$API_PREFIX/analytics/summary"
    }
    
    object Chat {
        const val QUERY = "$API_PREFIX/chat/query"
        const val CONTEXT = "$API_PREFIX/chat/context"
        const val SUGGESTIONS = "$API_PREFIX/chat/suggestions"
        const val HISTORY = "$API_PREFIX/chat/history"
    }
    
    object Categories {
        const val LIST = "$API_PREFIX/categories"
    }
    
    object User {
        const val PROFILE = "$API_PREFIX/user/profile"
    }
    
    object Health {
        const val CHECK = "/health"
    }
    
    // ============================================================
    // AUTHENTICATION
    // ============================================================
    
    const val AUTH_HEADER = "Authorization"
    const val AUTH_TYPE = "Bearer"
    
    fun getAuthHeader(token: String): Pair<String, String> {
        return AUTH_HEADER to "$AUTH_TYPE $token"
    }
    
    // ============================================================
    // QUERY PARAMETERS
    // ============================================================
    
    object QueryParams {
        // Pagination
        const val PAGE = "page"
        const val LIMIT = "limit"
        
        // Filters
        const val CATEGORY = "category"
        const val SEARCH = "search"
        const val SORT = "sort"
        const val MIN_AMOUNT = "min_amount"
        const val MAX_AMOUNT = "max_amount"
        const val START_DATE = "start_date"
        const val END_DATE = "end_date"
        const val TYPE = "type"
        
        // Merchant search
        const val QUERY = "q"
    }
    
    object SortOptions {
        const val RECENT = "recent"
        const val HIGHEST = "highest"
    }
    
    object TransactionType {
        const val CREDIT = "credit"
        const val DEBIT = "debit"
    }
}

// ============================================================
// USAGE EXAMPLES
// ============================================================

/*
// 1. GET Dashboard Summary
val response = apiService.get(ApiConfig.Dashboard.SUMMARY)

// 2. GET Transactions with filters
val url = "${ApiConfig.Transactions.BASE}?" +
    "${ApiConfig.QueryParams.PAGE}=1&" +
    "${ApiConfig.QueryParams.LIMIT}=20&" +
    "${ApiConfig.QueryParams.SORT}=${ApiConfig.SortOptions.RECENT}"
val transactions = apiService.get(url)

// 3. POST Create Transaction
val createUrl = ApiConfig.Transactions.BASE
val body = CreateTransactionRequest(
    merchant = "Starbucks",
    amount = -5.50,
    category_id = "food-category-id"
)
val result = apiService.post(createUrl, body)

// 4. GET Transaction Detail
val detailUrl = ApiConfig.Transactions.detail("transaction-uuid")
val transaction = apiService.get(detailUrl)

// 5. GET Merchant Suggestions
val merchantUrl = "${ApiConfig.Transactions.MERCHANTS}?${ApiConfig.QueryParams.QUERY}=star"
val merchants = apiService.get(merchantUrl)

// 6. POST Chat Query
val chatUrl = ApiConfig.Chat.QUERY
val chatBody = ChatQueryRequest(query = "How much did I spend on food?")
val chatResponse = apiService.post(chatUrl, chatBody)

// 7. GET Risk Score
val riskUrl = ApiConfig.Analytics.RISK_SCORE
val risk = apiService.get(riskUrl)

// 8. GET Categories
val categoriesUrl = ApiConfig.Categories.LIST
val categories = apiService.get(categoriesUrl)

// 9. GET User Profile
val profileUrl = ApiConfig.User.PROFILE
val profile = apiService.get(profileUrl)

// 10. Health Check (no auth required)
val healthUrl = ApiConfig.Health.CHECK
val health = apiService.get(healthUrl)
*/
