package com.jkanime.tv.smb

import android.content.Context
import android.net.Uri
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DataSpec
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.TransferListener
import com.jkanime.tv.data.SmbConfig
import jcifs.SmbRandomAccess
import jcifs.context.BaseContext
import jcifs.context.SingletonContext
import jcifs.smb.NtlmPasswordAuthenticator
import jcifs.smb.SmbFile

@UnstableApi
class SmbDataSourceFactory(
    private val context: Context,
    private val config: SmbConfig,
) : DataSource.Factory {
    override fun createDataSource(): DataSource =
        SmbAwareDataSource(context, config)
}

private class SmbAwareDataSource(
    private val context: Context,
    private val config: SmbConfig,
) : DataSource {
    private val http = DefaultDataSource.Factory(context).createDataSource()
    private val smb = SmbDataSource(config)
    private var delegate: DataSource? = null

    override fun open(dataSpec: DataSpec): Long {
        delegate = if (dataSpec.uri.scheme == "smb") smb else http
        return delegate!!.open(dataSpec)
    }

    override fun read(buffer: ByteArray, offset: Int, length: Int): Int =
        delegate!!.read(buffer, offset, length)

    override fun getUri(): Uri = delegate?.uri ?: Uri.EMPTY
    override fun close() { delegate?.close() }

    override fun addTransferListener(listener: TransferListener) {
        http.addTransferListener(listener)
    }
}

private class SmbDataSource(
    private val config: SmbConfig,
) : DataSource {
    private var ra: SmbRandomAccess? = null
    private var currentUri: Uri? = null

    override fun open(dataSpec: DataSpec): Long {
        currentUri = dataSpec.uri
        val auth = NtlmPasswordAuthenticator(config.username, config.password)
        val ctx = BaseContext(SingletonContext.getInstance().config).withCredentials(auth)
        val file = SmbFile(dataSpec.uri.toString(), ctx)
        ra = file.openRandomAccess("r")
        if (dataSpec.position != 0L) ra?.seek(dataSpec.position)
        return file.length()
    }

    override fun read(buffer: ByteArray, offset: Int, length: Int): Int =
        ra?.read(buffer, offset, length) ?: C.RESULT_END_OF_INPUT

    override fun getUri(): Uri = currentUri ?: Uri.EMPTY

    override fun close() {
        try { ra?.close() } catch (_: Exception) {}
        ra = null; currentUri = null
    }

    override fun addTransferListener(listener: TransferListener) {}

    private object C {
        const val RESULT_END_OF_INPUT = -1
    }
}
