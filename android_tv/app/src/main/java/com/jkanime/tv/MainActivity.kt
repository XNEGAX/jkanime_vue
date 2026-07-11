package com.jkanime.tv

import android.content.Intent
import android.os.Bundle
import androidx.activity.OnBackPressedCallback
import androidx.fragment.app.FragmentActivity
import com.jkanime.tv.data.PreferencesManager
import com.jkanime.tv.ui.browse.BrowseFragment
import com.jkanime.tv.ui.detail.DetailFragment
import com.jkanime.tv.ui.settings.SettingsActivity

class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (!PreferencesManager(this).isConfigured) {
            startActivity(Intent(this, SettingsActivity::class.java))
            finish()
            return
        }

        setContentView(R.layout.activity_main)

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (supportFragmentManager.backStackEntryCount > 0) {
                    supportFragmentManager.popBackStack()
                } else {
                    finish()
                }
            }
        })

        if (savedInstanceState == null) {
            supportFragmentManager.beginTransaction()
                .replace(R.id.content_frame, BrowseFragment())
                .commit()
        }
    }

    fun navigateToDetail(serieId: Int) {
        supportFragmentManager.beginTransaction()
            .replace(R.id.content_frame, DetailFragment.newInstance(serieId))
            .addToBackStack("detail")
            .commit()
    }
}
