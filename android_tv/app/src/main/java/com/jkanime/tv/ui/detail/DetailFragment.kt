package com.jkanime.tv.ui.detail

import android.content.Intent
import android.content.ActivityNotFoundException
import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.leanback.widget.ArrayObjectAdapter
import androidx.leanback.widget.ItemBridgeAdapter
import androidx.leanback.widget.Presenter
import androidx.leanback.widget.VerticalGridView
import com.bumptech.glide.Glide
import com.bumptech.glide.load.engine.DiskCacheStrategy
import com.jkanime.tv.JKanimeApp
import com.jkanime.tv.R
import com.jkanime.tv.data.SmbConfig
import com.jkanime.tv.data.api.RetrofitClient
import com.jkanime.tv.data.model.Capitulo
import com.jkanime.tv.data.model.Serie
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class DetailFragment : Fragment() {
    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private var serieId: Int = 0

    private lateinit var serieName: TextView
    private lateinit var serieCover: ImageView
    private lateinit var serieStatus: TextView
    private lateinit var serieNextEpisode: TextView
    private lateinit var chaptersGrid: VerticalGridView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        serieId = arguments?.getInt(ARG_SERIE_ID) ?: return
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        return inflater.inflate(R.layout.fragment_detail, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        serieName = view.findViewById(R.id.serie_name)
        serieCover = view.findViewById(R.id.serie_cover)
        serieStatus = view.findViewById(R.id.serie_status)
        serieNextEpisode = view.findViewById(R.id.serie_next_episode)
        chaptersGrid = view.findViewById(R.id.chapters_grid)

        loadDetail()
    }

    private fun loadDetail() {
        scope.launch {
            try {
                val app = requireContext().applicationContext as JKanimeApp
                RetrofitClient.init(app.prefs.serverUrl)
                val serie = withContext(Dispatchers.IO) {
                    RetrofitClient.getApi().getSerieDetail(serieId)
                }
                val capitulos = serie.capitulos.filter { it.rutaSmb != null }

                bindSerieInfo(serie)
                bindChapters(capitulos)
            } catch (e: Exception) {
                Log.e("DetailFragment", "loadDetail failed: ${e.message}", e)
                Toast.makeText(requireContext(), "Error: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun bindSerieInfo(serie: Serie) {
        serieName.text = serie.nombre

        Glide.with(this)
            .load(serie.portadaUrl)
            .diskCacheStrategy(DiskCacheStrategy.ALL)
            .centerCrop()
            .placeholder(android.R.color.darker_gray)
            .error(android.R.color.darker_gray)
            .into(serieCover)

        val estado = serie.estado.replace("_", " ").replaceFirstChar { it.uppercase() }
        serieStatus.text = "Estado: $estado"

        if (serie.estado != "concluido" && serie.diaEmision.isNotEmpty()) {
            serieNextEpisode.text = "Próximo: día ${serie.diaEmision.replaceFirstChar { it.uppercase() }}"
            serieNextEpisode.visibility = View.VISIBLE
        } else {
            serieNextEpisode.visibility = View.GONE
        }
    }

    private fun bindChapters(capitulos: List<Capitulo>) {
        val adapter = ArrayObjectAdapter(ChapterCardPresenter { openWithVlc(it) })
        adapter.addAll(0, capitulos)
        chaptersGrid.adapter = ItemBridgeAdapter(adapter)
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

private class ChapterCardPresenter(
    private val onChapterClick: (Capitulo) -> Unit,
) : Presenter() {
    override fun onCreateViewHolder(parent: ViewGroup): ViewHolder {
        val root = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_chapter, parent, false)
        return ViewHolder(root)
    }

    override fun onBindViewHolder(viewHolder: ViewHolder, item: Any) {
        val cap = item as Capitulo
        val root = viewHolder.view
        root.findViewById<TextView>(R.id.chapter_title).text = "Episodio ${cap.numero}"
        root.findViewById<TextView>(R.id.chapter_subtitle).text = cap.nombreArchivo
        root.setOnClickListener { onChapterClick(cap) }
    }

    override fun onUnbindViewHolder(viewHolder: ViewHolder) {}
}

private fun buildSmbUri(config: SmbConfig, capitulo: Capitulo): String? {
    val ruta = capitulo.rutaSmb ?: return null
    val userPart = if (config.username.isNotEmpty()) {
        "${config.username}:${config.password}@"
    } else ""
    return "smb://$userPart${config.serverIp}/${config.shareName}/$ruta"
}
