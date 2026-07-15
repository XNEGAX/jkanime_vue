package com.jkanime.phone.ui.settings

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import androidx.fragment.app.Fragment
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import com.jkanime.phone.R
import com.jkanime.phone.data.PreferencesManager

class SettingsFragment : Fragment() {
    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        val ctx = requireContext()
        val pm = PreferencesManager(ctx)
        val view = inflater.inflate(R.layout.fragment_settings, container, false)

        view.findViewById<EditText>(R.id.server_url).setText(pm.serverUrl)
        view.findViewById<EditText>(R.id.smb_server).setText(pm.smbServerIp)
        view.findViewById<EditText>(R.id.smb_share).setText(pm.smbShareName)
        view.findViewById<EditText>(R.id.smb_user).setText(pm.smbUsername)
        view.findViewById<EditText>(R.id.smb_pass).setText(pm.smbPassword)

        view.findViewById<Button>(R.id.btn_save).setOnClickListener {
            pm.serverUrl = view.findViewById<EditText>(R.id.server_url).text.toString()
            pm.smbServerIp = view.findViewById<EditText>(R.id.smb_server).text.toString()
            pm.smbShareName = view.findViewById<EditText>(R.id.smb_share).text.toString()
            pm.smbUsername = view.findViewById<EditText>(R.id.smb_user).text.toString()
            pm.smbPassword = view.findViewById<EditText>(R.id.smb_pass).text.toString()
            pm.markConfigured()
            activity?.finish()
        }

        return view
    }
}
