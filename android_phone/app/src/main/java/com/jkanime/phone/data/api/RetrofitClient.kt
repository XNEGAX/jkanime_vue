package com.jkanime.phone.data.api

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object RetrofitClient {
    private var api: JKanimeApi? = null
    private var currentUrl: String? = null

    fun init(baseUrl: String) {
        if (baseUrl == currentUrl && api != null) return
        currentUrl = baseUrl
        val url = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        val retrofit = Retrofit.Builder()
            .baseUrl(url)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        api = retrofit.create(JKanimeApi::class.java)
    }

    fun getApi(): JKanimeApi = api ?: throw IllegalStateException("RetrofitClient not initialized")
}
