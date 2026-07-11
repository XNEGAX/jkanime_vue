package com.jkanime.tv.ui.playback

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.ViewGroup
import androidx.activity.ComponentActivity
import androidx.media3.common.MediaItem
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.PlayerView
import com.jkanime.tv.JKanimeApp
import com.jkanime.tv.data.SmbConfig
import com.jkanime.tv.data.model.Capitulo
import com.jkanime.tv.smb.SmbDataSourceFactory

class PlaybackActivity : ComponentActivity() {
    private var player: ExoPlayer? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val capitulo = intent.getSerializableExtra(EXTRA_CAPITULO) as? Capitulo ?: run {
            finish(); return
        }

        val app = application as JKanimeApp
        val smbUri = buildSmbUri(app.prefs.getSmbConfig(), capitulo) ?: run {
            finish(); return
        }

        val playerView = PlayerView(this).apply {
            useController = true
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
            )
        }
        setContentView(playerView)

        val smbFactory = SmbDataSourceFactory(this, app.prefs.getSmbConfig())
        val dataSourceFactory = DefaultDataSource.Factory(this, smbFactory)

        player = ExoPlayer.Builder(this)
            .setMediaSourceFactory(DefaultMediaSourceFactory(dataSourceFactory))
            .build()
            .also {
                playerView.player = it
                it.setMediaItem(MediaItem.fromUri(Uri.parse(smbUri)))
                it.prepare()
                it.playWhenReady = true
            }
    }

    override fun onStop() {
        super.onStop()
        player?.pause()
    }

    override fun onDestroy() {
        player?.release()
        player = null
        super.onDestroy()
    }

    companion object {
        private const val EXTRA_CAPITULO = "capitulo"

        fun intent(context: Context, capitulo: Capitulo): Intent {
            return Intent(context, PlaybackActivity::class.java).apply {
                putExtra(EXTRA_CAPITULO, capitulo)
            }
        }
    }
}

private fun buildSmbUri(config: SmbConfig, capitulo: Capitulo): String? {
    val ruta = capitulo.rutaSmb ?: return null
    val userPart = if (config.username.isNotEmpty()) {
        "${config.username}:${config.password}@"
    } else ""
    return "smb://$userPart${config.serverIp}/${config.shareName}/$ruta"
}
