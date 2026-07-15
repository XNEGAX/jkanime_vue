package com.jkanime.phone

import android.app.Application
import com.jkanime.phone.data.PreferencesManager
import com.jkanime.phone.data.api.RetrofitClient

class JKanimeApp : Application() {
    lateinit var prefs: PreferencesManager
        private set

    override fun onCreate() {
        super.onCreate()
        prefs = PreferencesManager(this)
        RetrofitClient.init(prefs.serverUrl)
    }
}
