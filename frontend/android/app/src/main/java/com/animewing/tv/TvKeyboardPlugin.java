package com.animewing.tv;

import android.content.Context;
import android.content.DialogInterface;
import android.view.inputmethod.InputMethodManager;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

import androidx.appcompat.app.AlertDialog;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.JSObject;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "TvKeyboard")
public class TvKeyboardPlugin extends Plugin {
    @PluginMethod
    public void edit(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            EditText editor = new EditText(getActivity());
            String value = call.getString("value", "");
            String kind = call.getString("kind", "text");
            editor.setSingleLine(true);
            editor.setText(value);
            editor.setSelection(value.length());
            editor.setFocusable(false);
            editor.setCursorVisible(false);

            LinearLayout keypad = new LinearLayout(getActivity());
            keypad.setOrientation(LinearLayout.VERTICAL);
            int padding = Math.round(24 * getActivity().getResources().getDisplayMetrics().density);
            keypad.setPadding(padding, 0, padding, padding);
            keypad.addView(editor, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

            Button[] firstKey = { null };
            String[][] rows = {
                { "1", "2", "3" },
                { "4", "5", "6" },
                { "7", "8", "9" },
                { "number".equals(kind) ? "Limpiar" : ".", "0", "⌫" }
            };
            for (String[] keys : rows) {
                LinearLayout row = new LinearLayout(getActivity());
                row.setOrientation(LinearLayout.HORIZONTAL);
                for (String key : keys) {
                    Button button = new Button(getActivity());
                    button.setText(key);
                    button.setTextSize(20);
                    button.setOnClickListener(view -> {
                        String current = editor.getText().toString();
                        if ("⌫".equals(key)) {
                            if (!current.isEmpty()) editor.setText(current.substring(0, current.length() - 1));
                        } else if ("Limpiar".equals(key)) {
                            editor.setText("");
                        } else if (!".".equals(key) || !current.contains(".")) {
                            editor.setText(current + key);
                        }
                    });
                    if (firstKey[0] == null) firstKey[0] = button;
                    row.addView(button, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
                }
                keypad.addView(row, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            }

            AlertDialog dialog = new AlertDialog.Builder(getActivity())
                .setTitle(call.getString("title", "Editar"))
                .setView(keypad)
                .setPositiveButton("Aceptar", null)
                .setNegativeButton("Cancelar", (target, which) -> {
                    JSObject result = new JSObject();
                    result.put("cancelled", true);
                    call.resolve(result);
                })
                .create();

            final boolean[] resolved = { false };
            Runnable accept = () -> {
                if (resolved[0]) return;
                resolved[0] = true;
                JSObject result = new JSObject();
                result.put("value", editor.getText().toString());
                result.put("cancelled", false);
                call.resolve(result);
                dialog.dismiss();
            };

            dialog.setOnShowListener(ignored -> {
                dialog.getButton(DialogInterface.BUTTON_POSITIVE).setOnClickListener(view -> accept.run());
                firstKey[0].requestFocus();
            });
            dialog.setOnCancelListener(ignored -> {
                if (resolved[0]) return;
                resolved[0] = true;
                JSObject result = new JSObject();
                result.put("cancelled", true);
                call.resolve(result);
            });
            dialog.show();
        });
    }

    @PluginMethod
    public void show(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            final android.webkit.WebView webView = getBridge().getWebView();
            webView.requestFocus();
            webView.postDelayed(() -> {
                InputMethodManager keyboard = (InputMethodManager) getActivity()
                    .getSystemService(Context.INPUT_METHOD_SERVICE);
                keyboard.showSoftInput(webView, InputMethodManager.SHOW_FORCED);
                call.resolve();
            }, 120);
        });
    }
}
