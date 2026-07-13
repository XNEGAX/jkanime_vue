package com.jkanime.tv.data.model

import com.google.gson.annotations.SerializedName

data class Serie(
    val id: Int,
    val nombre: String,
    val anio: Int = 2024,
    @SerializedName("portada_url") val portadaUrl: String? = null,
    val slug: String = "",
    val favorito: Boolean = false,
    val estado: String = "desconocido",
    @SerializedName("dia_emision") val diaEmision: String = "",
    @SerializedName("latest_fecha") val latestFecha: String? = null,
    @SerializedName("capitulos_count") val capitulosCount: Int = 0,
    @SerializedName("descargados_count") val descargadosCount: Int = 0,
    val capitulos: List<Capitulo> = emptyList(),
)
