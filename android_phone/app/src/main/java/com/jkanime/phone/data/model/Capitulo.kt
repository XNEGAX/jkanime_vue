package com.jkanime.phone.data.model

import com.google.gson.annotations.SerializedName
import java.io.Serializable

data class Capitulo(
    val id: Int,
    val numero: Int,
    @SerializedName("nombre_archivo") val nombreArchivo: String = "",
    @SerializedName("ruta_smb") val rutaSmb: String? = null,
    @SerializedName("archivo_existe") val archivoExiste: Boolean = false,
    @SerializedName("url_jkanime") val urlJkanime: String = "",
    @SerializedName("fecha_publicacion") val fechaPublicacion: String? = null,
    @SerializedName("serie_id") val serieId: Int? = null,
    @SerializedName("serie_nombre") val serieNombre: String? = null,
    @SerializedName("serie_slug") val serieSlug: String? = null,
    @SerializedName("anterior_id") val anteriorId: Int? = null,
    @SerializedName("siguiente_id") val siguienteId: Int? = null,
) : Serializable
