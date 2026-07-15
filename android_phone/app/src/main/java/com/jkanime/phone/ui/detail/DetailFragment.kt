package com.jkanime.phone.ui.detail

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.bumptech.glide.load.engine.DiskCacheStrategy
import com.google.android.material.card.MaterialCardView
import com.jkanime.phone.JKanimeApp
import com.jkanime.phone.R
import com.jkanime.phone.data.SmbConfig
import com.jkanime.phone.data.api.RetrofitClient
import com.jkanime.phone.data.model.Capitulo
import com.jkanime.phone.data.model.Serie
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class DetailFragment : Fragment() {
    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private var serieId: Int = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        serieId = arguments?.getInt(ARG_SERIE_ID) ?: return
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        return inflater.inflate(R.layout.fragment_detail, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        loadDetail(view)
    }

    private fun loadDetail(root: View) {
        scope.launch {
            try {
                val app = requireContext().applicationContext as JKanimeApp
                RetrofitClient.init(app.prefs.serverUrl)
                val serie = withContext(Dispatchers.IO) {
                    RetrofitClient.getApi().getSerieDetail(serieId)
                }
                bindSerieInfo(root, serie)
                bindChapters(root, serie.capitulos.filter { it.rutaSmb != null })
            } catch (e: Exception) {
                Toast.makeText(requireContext(), "Error: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun bindSerieInfo(root: View, serie: Serie) {
        root.findViewById<TextView>(R.id.serie_name).text = serie.nombre

        Glide.with(this)
            .load(serie.portadaUrl)
            .diskCacheStrategy(DiskCacheStrategy.ALL)
            .centerCrop()
            .placeholder(android.R.color.darker_gray)
            .error(android.R.color.darker_gray)
            .into(root.findViewById<ImageView>(R.id.serie_cover))

        val estado = serie.estado.replace("_", " ").replaceFirstChar { it.uppercase() }
        root.findViewById<TextView>(R.id.serie_status).text = "Estado: $estado"

        val nextEp = root.findViewById<TextView>(R.id.serie_next_episode)
        if (serie.estado != "concluido" && serie.diaEmision.isNotEmpty()) {
            nextEp.text = "Próximo: día ${serie.diaEmision.replaceFirstChar { it.uppercase() }}"
            nextEp.visibility = View.VISIBLE
        } else {
            nextEp.visibility = View.GONE
        }
    }

    private fun bindChapters(root: View, capitulos: List<Capitulo>) {
        val rv = root.findViewById<RecyclerView>(R.id.chapters_list)
        rv.layoutManager = LinearLayoutManager(requireContext())
        rv.adapter = ChapterAdapter(capitulos) { openWithVlc(it) }
    }

    private fun openWithVlc(capitulo: Capitulo) {
        val app = requireContext().applicationContext as JKanimeApp
        val config = app.prefs.getSmbConfig()
        val smbUrl = buildSmbUri(config, capitulo) ?: run {
            Toast.makeText(requireContext(), "Ruta SMB no disponible", Toast.LENGTH_SHORT).show()
            return
        }

        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(Uri.parse(smbUrl), "video/*")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        try {
            startActivity(Intent.createChooser(intent, "Abrir con..."))
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(requireContext(), "No hay reproductor disponible", Toast.LENGTH_LONG).show()
        }
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val ARG_SERIE_ID = "serie_id"
        fun newInstance(serieId: Int) = DetailFragment().apply {
            arguments = Bundle().apply { putInt(ARG_SERIE_ID, serieId) }
        }
    }
}

private class ChapterAdapter(
    private val capitulos: List<Capitulo>,
    private val onClick: (Capitulo) -> Unit,
) : RecyclerView.Adapter<ChapterAdapter.ViewHolder>() {

    override fun getItemCount() = capitulos.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_chapter, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val cap = capitulos[position]
        holder.title.text = "Episodio ${cap.numero}"
        holder.subtitle.text = cap.nombreArchivo
        holder.itemView.setOnClickListener { onClick(cap) }
    }

    class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val title: TextView = view.findViewById(R.id.chapter_title)
        val subtitle: TextView = view.findViewById(R.id.chapter_subtitle)
    }
}

private fun buildSmbUri(config: SmbConfig, capitulo: Capitulo): String? {
    val ruta = capitulo.rutaSmb ?: return null
    val userPart = if (config.username.isNotEmpty()) {
        "${config.username}:${config.password}@"
    } else ""
    return "smb://$userPart${config.serverIp}/${config.shareName}/$ruta"
}
