package com.jkanime.tv.ui.browse

import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import androidx.leanback.app.BrowseSupportFragment
import androidx.leanback.widget.ArrayObjectAdapter
import androidx.leanback.widget.HeaderItem
import androidx.leanback.widget.ImageCardView
import androidx.leanback.widget.ListRow
import androidx.leanback.widget.ListRowPresenter
import androidx.leanback.widget.Presenter
import com.bumptech.glide.Glide
import com.bumptech.glide.load.engine.DiskCacheStrategy
import com.jkanime.tv.JKanimeApp
import com.jkanime.tv.MainActivity
import com.jkanime.tv.R
import com.jkanime.tv.data.api.RetrofitClient
import com.jkanime.tv.data.model.Serie
import com.jkanime.tv.ui.settings.SettingsActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class BrowseFragment : BrowseSupportFragment() {
    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private lateinit var rowsAdapter: ArrayObjectAdapter

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        title = getString(R.string.app_name)
        headersState = HEADERS_ENABLED
        isHeadersTransitionOnBackEnabled = true
        brandColor = resources.getColor(R.color.primary)

        rowsAdapter = ArrayObjectAdapter(ListRowPresenter())
        adapter = rowsAdapter

        setOnItemViewClickedListener { _, item, _, _ ->
            when (item) {
                is Serie -> (activity as? MainActivity)?.navigateToDetail(item.id)
                is SettingsLaunch -> startActivity(Intent(requireContext(), SettingsActivity::class.java))
            }
        }

        loadSeries()
    }

    private fun loadSeries() {
        scope.launch {
            try {
                val app = requireContext().applicationContext as JKanimeApp
                RetrofitClient.init(app.prefs.serverUrl)
                val series = withContext(Dispatchers.IO) {
                    RetrofitClient.getApi().getSeries()
                }
                val favoritos = withContext(Dispatchers.IO) {
                    RetrofitClient.getApi().getFavoritos()
                }

                rowsAdapter.clear()

                if (favoritos.isNotEmpty()) {
                    rowsAdapter.add(createRow(getString(R.string.favoritos), favoritos))
                }
                rowsAdapter.add(createRow(getString(R.string.todas), series))

                val settingsAdapter = ArrayObjectAdapter(LabelCardPresenter())
                settingsAdapter.add(SettingsLaunch())
                rowsAdapter.add(ListRow(HeaderItem(getString(R.string.settings)), settingsAdapter))

            } catch (e: Exception) {
                Log.e("BrowseFragment", "loadSeries failed: ${e.message}", e)
                rowsAdapter.clear()
                val settingsAdapter = ArrayObjectAdapter(LabelCardPresenter())
                settingsAdapter.add(SettingsLaunch())
                rowsAdapter.add(ListRow(HeaderItem(getString(R.string.settings)), settingsAdapter))
                rowsAdapter.add(createRow(getString(R.string.error_no_series), emptyList()))
            }
        }
    }

    private fun createRow(title: String, series: List<Serie>): ListRow {
        val adapter = ArrayObjectAdapter(SerieCardPresenter())
        adapter.addAll(0, series)
        return ListRow(HeaderItem(title), adapter)
    }
}

private class SettingsLaunch

class SerieCardPresenter : Presenter() {
    override fun onCreateViewHolder(parent: ViewGroup): ViewHolder {
        val card = ImageCardView(parent.context).apply {
            isFocusable = true
            isFocusableInTouchMode = true
            setMainImageDimensions(200, 280)
        }
        return ViewHolder(card)
    }

    override fun onBindViewHolder(viewHolder: ViewHolder, item: Any) {
        val serie = item as Serie
        val card = viewHolder.view as ImageCardView
        card.titleText = serie.nombre
        card.contentText = "${serie.estado.replace("_", " ")} \u2022 ${serie.capitulosCount} ep."

        Glide.with(card.context)
            .load(serie.portadaUrl)
            .diskCacheStrategy(DiskCacheStrategy.ALL)
            .placeholder(android.R.color.darker_gray)
            .error(android.R.color.darker_gray)
            .centerCrop()
            .into(card.mainImageView)
    }

    override fun onUnbindViewHolder(viewHolder: ViewHolder) {
        val card = viewHolder.view as ImageCardView
        card.mainImageView.setImageDrawable(null)
    }
}

class LabelCardPresenter : Presenter() {
    override fun onCreateViewHolder(parent: ViewGroup): ViewHolder {
        val card = ImageCardView(parent.context).apply {
            isFocusable = true
            isFocusableInTouchMode = true
            setMainImageDimensions(200, 80)
        }
        return ViewHolder(card)
    }

    override fun onBindViewHolder(viewHolder: ViewHolder, item: Any) {
        val card = viewHolder.view as ImageCardView
        card.titleText = "⚙ ${card.context.getString(R.string.settings)}"
        card.contentText = card.context.getString(R.string.server_url_summary)
        card.setMainImageScaleType(ImageView.ScaleType.CENTER_INSIDE)
        card.setMainImage(
            card.context.resources?.getDrawable(android.R.drawable.ic_menu_manage, card.context.theme)
        )
    }

    override fun onUnbindViewHolder(viewHolder: ViewHolder) {
        val card = viewHolder.view as ImageCardView
        card.setMainImage(null)
    }
}
