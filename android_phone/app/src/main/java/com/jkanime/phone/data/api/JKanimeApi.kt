package com.jkanime.phone.data.api

import com.google.gson.annotations.SerializedName
import com.jkanime.phone.data.model.Capitulo
import com.jkanime.phone.data.model.Serie
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface JKanimeApi {
    @GET("api/series/")
    suspend fun getSeries(): List<Serie>

    @GET("api/series/favoritos/")
    suspend fun getFavoritos(): List<Serie>

    @GET("api/series/{id}/")
    suspend fun getSerieDetail(@Path("id") id: Int): Serie

    @GET("api/series/{id}/capitulos/")
    suspend fun getCapitulos(@Path("id") serieId: Int): CapitulosResponse

    @GET("api/capitulos/{id}/")
    suspend fun getCapituloDetail(@Path("id") id: Int): Capitulo

    @POST("api/series/{id}/favorito/")
    suspend fun toggleFavorito(@Path("id") id: Int): ToggleResponse
}

data class CapitulosResponse(
    val capitulos: List<Capitulo> = emptyList(),
    @SerializedName("nuevos_encontrados") val nuevosEncontrados: Int = 0,
    @SerializedName("total_jk") val totalJk: Int = 0,
)

data class ToggleResponse(val favorito: Boolean)
