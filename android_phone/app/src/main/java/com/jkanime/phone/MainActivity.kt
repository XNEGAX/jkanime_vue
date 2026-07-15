package com.jkanime.phone

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.jkanime.phone.data.PreferencesManager
import com.jkanime.phone.ui.browse.BrowseFragment
import com.jkanime.phone.ui.detail.DetailFragment
import com.jkanime.phone.ui.settings.SettingsActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (!PreferencesManager(this).isConfigured) {
            startActivity(Intent(this, SettingsActivity::class.java))
            finish()
            return
        }

        setContentView(R.layout.activity_main)

        val nav = findViewById<BottomNavigationView>(R.id.bottom_nav)
        nav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_series -> showBrowse(false)
                R.id.nav_favorites -> showBrowse(true)
                R.id.nav_settings -> startActivity(Intent(this, SettingsActivity::class.java))
            }
            true
        }

        if (savedInstanceState == null) {
            showBrowse(false)
        }
    }

    fun navigateToDetail(serieId: Int) {
        supportFragmentManager.beginTransaction()
            .replace(R.id.content_frame, DetailFragment.newInstance(serieId))
            .addToBackStack("detail")
            .commit()
    }

    private fun showBrowse(favoritesOnly: Boolean) {
        supportFragmentManager.beginTransaction()
            .replace(R.id.content_frame, BrowseFragment.newInstance(favoritesOnly))
            .commit()
    }
}
