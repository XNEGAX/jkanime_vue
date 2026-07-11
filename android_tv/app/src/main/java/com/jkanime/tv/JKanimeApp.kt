package com.jkanime.tv

import android.app.Application
import com.jkanime.tv.data.PreferencesManager
import com.jkanime.tv.data.api.RetrofitClient

class JKanimeApp : Application() {
    lateinit var prefs: PreferencesManager
        private set

    override fun onCreate() {
        super.onCreate()
        prefs = PreferencesManager(this)
        RetrofitClient.init(prefs.serverUrl)
    }
}
