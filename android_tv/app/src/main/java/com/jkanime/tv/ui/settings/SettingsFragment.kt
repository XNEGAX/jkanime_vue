package com.jkanime.tv.ui.settings

import android.app.Fragment
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import com.jkanime.tv.data.PreferencesManager

class SettingsFragment : Fragment() {
    private var serverUrlField: EditText? = null
    private var smbServerField: EditText? = null
    private var smbShareField: EditText? = null
    private var smbUserField: EditText? = null
    private var smbPassField: EditText? = null

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        val ctx = activity ?: return LinearLayout(activity)
        val pm = PreferencesManager(ctx)

        return LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(64, 48, 64, 48)

            addView(TextView(ctx).apply {
                text = "Server URL"
                textSize = 18f
            })
            addView(EditText(ctx).apply {
                id = View.generateViewId()
                setText(pm.serverUrl)
                hint = "http://192.168.100.50:8000"
                serverUrlField = this
            })

            addView(TextView(ctx).apply {
                text = "SMB Server"
                textSize = 18f
                setPadding(0, 32, 0, 0)
            })
            addView(EditText(ctx).apply {
                id = View.generateViewId()
                setText(pm.smbServerIp)
                hint = "192.168.100.50"
                smbServerField = this
            })

            addView(TextView(ctx).apply {
                text = "SMB Share"
                textSize = 18f
                setPadding(0, 32, 0, 0)
            })
            addView(EditText(ctx).apply {
                id = View.generateViewId()
                setText(pm.smbShareName)
                hint = "jkanime"
                smbShareField = this
            })

            addView(TextView(ctx).apply {
                text = "SMB Username"
                textSize = 18f
                setPadding(0, 32, 0, 0)
            })
            addView(EditText(ctx).apply {
                id = View.generateViewId()
                setText(pm.smbUsername)
                hint = "guest"
                smbUserField = this
            })

            addView(TextView(ctx).apply {
                text = "SMB Password"
                textSize = 18f
                setPadding(0, 32, 0, 0)
            })
            addView(EditText(ctx).apply {
                id = View.generateViewId()
                setText(pm.smbPassword)
                hint = "contraseña"
                smbPassField = this
            })

            addView(Button(ctx).apply {
                text = "Guardar"
                textSize = 20f
                setPadding(0, 48, 0, 0)
                setOnClickListener {
                    pm.serverUrl = serverUrlField?.text?.toString() ?: ""
                    pm.smbServerIp = smbServerField?.text?.toString() ?: ""
                    pm.smbShareName = smbShareField?.text?.toString() ?: ""
                    pm.smbUsername = smbUserField?.text?.toString() ?: ""
                    pm.smbPassword = smbPassField?.text?.toString() ?: ""
                    pm.markConfigured()
                    activity?.finish()
                }
            })
        }
    }
}
