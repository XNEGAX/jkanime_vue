package com.jkanime.tv.data

import android.content.Context
import androidx.preference.PreferenceManager

data class SmbConfig(
    val serverIp: String = "",
    val shareName: String = "",
    val username: String = "",
    val password: String = "",
)

class PreferencesManager(context: Context) {
    private val prefs = PreferenceManager.getDefaultSharedPreferences(context)

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER_URL, "http://192.168.100.50:8000") ?: ""
        set(v) = prefs.edit().putString(KEY_SERVER_URL, v).apply()

    var smbServerIp: String
        get() = prefs.getString(KEY_SMB_SERVER, "192.168.100.50") ?: ""
        set(v) = prefs.edit().putString(KEY_SMB_SERVER, v).apply()

    var smbShareName: String
        get() = prefs.getString(KEY_SMB_SHARE, "descargas") ?: ""
        set(v) = prefs.edit().putString(KEY_SMB_SHARE, v).apply()

    var smbUsername: String
        get() = prefs.getString(KEY_SMB_USER, "") ?: ""
        set(v) = prefs.edit().putString(KEY_SMB_USER, v).apply()

    var smbPassword: String
        get() = prefs.getString(KEY_SMB_PASS, "") ?: ""
        set(v) = prefs.edit().putString(KEY_SMB_PASS, v).apply()

    val isConfigured: Boolean
        get() = prefs.getBoolean(KEY_SETUP_DONE, false)

    fun markConfigured() {
        prefs.edit().putBoolean(KEY_SETUP_DONE, true).apply()
    }

    fun getSmbConfig() = SmbConfig(smbServerIp, smbShareName, smbUsername, smbPassword)

    companion object {
        private const val KEY_SETUP_DONE = "setup_done"
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_SMB_SERVER = "smb_server"
        private const val KEY_SMB_SHARE = "smb_share"
        private const val KEY_SMB_USER = "smb_user"
        private const val KEY_SMB_PASS = "smb_pass"
    }
}
