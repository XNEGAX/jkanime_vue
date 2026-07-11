package com.jkanime.tv.ui.detail

import android.graphics.drawable.Drawable
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.Toast
import androidx.leanback.app.DetailsSupportFragment
import androidx.leanback.widget.AbstractDetailsDescriptionPresenter
import androidx.leanback.widget.ArrayObjectAdapter
import androidx.leanback.widget.ClassPresenterSelector
import androidx.leanback.widget.DetailsOverviewRow
import androidx.leanback.widget.FullWidthDetailsOverviewRowPresenter
import androidx.leanback.widget.HeaderItem
import androidx.leanback.widget.ImageCardView
import androidx.leanback.widget.ListRow
import androidx.leanback.widget.ListRowPresenter
import androidx.leanback.widget.Presenter
import com.bumptech.glide.Glide
import com.bumptech.glide.load.engine.DiskCacheStrategy
import com.bumptech.glide.request.target.CustomTarget
import com.bumptech.glide.request.transition.Transition
import com.jkanime.tv.JKanimeApp
import com.jkanime.tv.R
import com.jkanime.tv.data.api.RetrofitClient
import com.jkanime.tv.data.model.Capitulo
import com.jkanime.tv.data.model.Serie
import com.jkanime.tv.ui.playback.PlaybackActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class DetailFragment : DetailsSupportFragment() {
    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private var serieId: Int = 0
    private lateinit var detailsAdapter: ArrayObjectAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        serieId = arguments?.getInt(ARG_SERIE_ID) ?: return
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val detailPresenter = FullWidthDetailsOverviewRowPresenter(DetailDescriptionPresenter()).apply {
            backgroundColor = resources.getColor(R.color.primary)
        }

        val selector = ClassPresenterSelector().apply {
            addClassPresenter(DetailsOverviewRow::class.java, detailPresenter)
            addClassPresenter(ListRow::class.java, ListRowPresenter())
        }

        detailsAdapter = ArrayObjectAdapter(selector)
        adapter = detailsAdapter

        setOnItemViewClickedListener { _, item, _, _ ->
            if (item is Capitulo && item.rutaSmb != null) {
                startActivity(PlaybackActivity.intent(requireContext(), item))
            }
        }

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
                val capitulos = withContext(Dispatchers.IO) {
                    RetrofitClient.getApi().getCapitulos(serieId)
                        .capitulos.filter { it.archivoExiste }
                }

                val row = DetailsOverviewRow(serie)
                detailsAdapter.add(row)

                Glide.with(requireContext())
                    .load(serie.portadaUrl)
                    .diskCacheStrategy(DiskCacheStrategy.ALL)
                    .centerCrop()
                    .into(object : CustomTarget<Drawable>() {
                        override fun onResourceReady(r: Drawable, t: Transition<in Drawable>?) {
                            row.imageDrawable = r
                        }
                        override fun onLoadCleared(p: Drawable?) {
                            row.imageDrawable = null
                        }
                    })

                if (capitulos.isNotEmpty()) {
                    val epAdapter = ArrayObjectAdapter(CapituloCardPresenter())
                    epAdapter.addAll(0, capitulos)
                    detailsAdapter.add(ListRow(HeaderItem(getString(R.string.capitulos)), epAdapter))
                }
            } catch (e: Exception) {
                Log.e("DetailFragment", "loadDetail failed: ${e.message}", e)
                Toast.makeText(requireContext(), "Error: ${e.message}", Toast.LENGTH_LONG).show()
            }
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

private class DetailDescriptionPresenter : AbstractDetailsDescriptionPresenter() {
    override fun onBindDescription(vh: ViewHolder, item: Any) {
        val serie = item as Serie
        vh.title.text = serie.nombre
        vh.subtitle.text = serie.estado.replace("_", " ")
        vh.body.text = "Episodios: ${serie.capitulosCount} | Descargados: ${serie.descargadosCount} | Emisión: ${serie.diaEmision}"
    }
}

class CapituloCardPresenter : Presenter() {
    override fun onCreateViewHolder(parent: ViewGroup): ViewHolder {
        val card = ImageCardView(parent.context).apply {
            isFocusable = true
            isFocusableInTouchMode = true
            setMainImageDimensions(160, 90)
        }
        return ViewHolder(card)
    }

    override fun onBindViewHolder(viewHolder: ViewHolder, item: Any) {
        val cap = item as Capitulo
        val card = viewHolder.view as ImageCardView
        card.titleText = "Episodio ${cap.numero}"
        card.contentText = cap.nombreArchivo
        card.setMainImageScaleType(ImageView.ScaleType.CENTER_INSIDE)
        card.setMainImage(
            card.context.resources?.getDrawable(android.R.drawable.ic_media_play, card.context.theme)
        )
    }

    override fun onUnbindViewHolder(viewHolder: ViewHolder) {
        val card = viewHolder.view as ImageCardView
        card.setMainImage(null)
    }
}
