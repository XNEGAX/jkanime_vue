package com.jkanime.phone.ui.browse

import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.bumptech.glide.Glide
import com.bumptech.glide.load.engine.DiskCacheStrategy
import com.jkanime.phone.JKanimeApp
import com.jkanime.phone.MainActivity
import com.jkanime.phone.R
import com.jkanime.phone.data.api.RetrofitClient
import com.jkanime.phone.data.model.Serie
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class BrowseFragment : Fragment() {
    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private var favoritesOnly: Boolean = false
    private lateinit var seriesAdapter: SeriesAdapter
    private lateinit var recyclerView: RecyclerView
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var searchInput: EditText
    private lateinit var emptyView: TextView
    private var allSeries: List<Serie> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        favoritesOnly = arguments?.getBoolean(ARG_FAVORITES, false) ?: false
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        return inflater.inflate(R.layout.fragment_browse, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        recyclerView = view.findViewById(R.id.series_grid)
        swipeRefresh = view.findViewById(R.id.swipe_refresh)
        searchInput = view.findViewById(R.id.search_input)
        emptyView = view.findViewById(R.id.empty_view)

        seriesAdapter = SeriesAdapter { serie -> (activity as? MainActivity)?.navigateToDetail(serie.id) }
        recyclerView.layoutManager = GridLayoutManager(requireContext(), 2)
        recyclerView.adapter = seriesAdapter

        searchInput.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                filter(s?.toString() ?: "")
            }
            override fun afterTextChanged(s: Editable?) {}
        })

        swipeRefresh.setOnRefreshListener { loadSeries() }
        loadSeries()
    }

    private fun loadSeries() {
        swipeRefresh.isRefreshing = true
        scope.launch {
            try {
                val app = requireContext().applicationContext as JKanimeApp
                RetrofitClient.init(app.prefs.serverUrl)
                allSeries = withContext(Dispatchers.IO) {
                    if (favoritesOnly) RetrofitClient.getApi().getFavoritos()
                    else RetrofitClient.getApi().getSeries()
                }
                filter(searchInput.text.toString())
            } catch (_: Exception) {
                allSeries = emptyList()
                filter("")
            } finally {
                swipeRefresh.isRefreshing = false
            }
        }
    }

    private fun filter(query: String) {
        val filtered = if (query.isBlank()) allSeries
        else allSeries.filter { it.nombre.contains(query, ignoreCase = true) }
        seriesAdapter.submitList(filtered)
        emptyView.visibility = if (filtered.isEmpty()) View.VISIBLE else View.GONE
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val ARG_FAVORITES = "favorites_only"
        fun newInstance(favoritesOnly: Boolean) = BrowseFragment().apply {
            arguments = Bundle().apply { putBoolean(ARG_FAVORITES, favoritesOnly) }
        }
    }
}

class SeriesAdapter(
    private val onClick: (Serie) -> Unit,
) : RecyclerView.Adapter<SeriesAdapter.ViewHolder>() {
    private var items: List<Serie> = emptyList()

    fun submitList(list: List<Serie>) {
        items = list
        notifyDataSetChanged()
    }

    override fun getItemCount() = items.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_series_card, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val serie = items[position]
        holder.title.text = serie.nombre
        holder.subtitle.text = "${serie.capitulosCount} eps \u2022 ${serie.estado.replace("_", " ")}"
        holder.itemView.setOnClickListener { onClick(serie) }

        Glide.with(holder.cover)
            .load(serie.portadaUrl)
            .diskCacheStrategy(DiskCacheStrategy.ALL)
            .placeholder(android.R.color.darker_gray)
            .error(android.R.color.darker_gray)
            .centerCrop()
            .into(holder.cover)
    }

    class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val cover: ImageView = view.findViewById(R.id.series_cover)
        val title: TextView = view.findViewById(R.id.series_title)
        val subtitle: TextView = view.findViewById(R.id.series_subtitle)
    }
}
