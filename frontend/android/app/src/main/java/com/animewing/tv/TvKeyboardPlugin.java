package com.animewing.tv;

import android.content.Context;
import android.content.DialogInterface;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
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
            editor.setTextColor(Color.WHITE);
            editor.setTextSize(22);
            editor.setBackgroundColor(Color.parseColor("#0B1928"));
            editor.setPadding(padding(18), padding(14), padding(18), padding(14));

            LinearLayout keypad = new LinearLayout(getActivity());
            keypad.setOrientation(LinearLayout.VERTICAL);
            int padding = Math.round(24 * getActivity().getResources().getDisplayMetrics().density);
            keypad.setPadding(padding, 0, padding, padding);
            keypad.addView(editor, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

            Button[] firstKey = { null };
            LinearLayout keyArea = new LinearLayout(getActivity());
            keyArea.setOrientation(LinearLayout.VERTICAL);
            keypad.addView(keyArea, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            String[] mode = { "number".equals(kind) ? "numbers" : "letters" };
            boolean[] uppercase = { false };
            renderKeyboard(keyArea, editor, mode, uppercase, firstKey);

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

    private void renderKeyboard(LinearLayout area, EditText editor, String[] mode, boolean[] uppercase, Button[] firstKey) {
        area.removeAllViews();
        firstKey[0] = null;
        String[][] rows;
        if ("numbers".equals(mode[0])) {
            rows = new String[][] {
                { "1", "2", "3" }, { "4", "5", "6" }, { "7", "8", "9" },
                { "ABC", "0", "#+=" }, { ".", "Limpiar", "⌫" }
            };
        } else if ("symbols".equals(mode[0])) {
            rows = new String[][] {
                { "_", ":", "/", "@", "#", "%", "&", "?", "=", "+" },
                { "!", "$", "(", ")", "[", "]", "{", "}", ",", ";" },
                { "-", "*", "\"", "'", "\\", "|", "~", "^", "<", ">" },
                { "ABC", "123", ".", "Espacio", "Limpiar", "⌫" }
            };
        } else {
            rows = new String[][] {
                { "q", "w", "e", "r", "t", "y", "u", "i", "o", "p" },
                { "a", "s", "d", "f", "g", "h", "j", "k", "l" },
                { "⇧", "z", "x", "c", "v", "b", "n", "m", "⌫" },
                { "123", "#+=", ".", "Espacio", "Limpiar" }
            };
        }

        for (String[] keys : rows) addKeyRow(area, editor, keys, mode, uppercase, firstKey);
        if (firstKey[0] != null) firstKey[0].requestFocus();
    }

    private void addKeyRow(LinearLayout area, EditText editor, String[] keys, String[] mode, boolean[] uppercase, Button[] firstKey) {
        LinearLayout row = new LinearLayout(getActivity());
        row.setOrientation(LinearLayout.HORIZONTAL);
        for (String rawKey : keys) {
            String key = "letters".equals(mode[0]) && uppercase[0] && rawKey.length() == 1
                ? rawKey.toUpperCase() : rawKey;
            Button button = new Button(getActivity());
            button.setText(key);
            button.setTextSize(keys.length <= 5 ? 18 : 15);
            button.setMinHeight(padding(52));
            button.setAllCaps(false);
            button.setBackground(keyBackground());
            button.setTextColor(keyTextColors());
            button.setOnClickListener(view -> {
                if ("ABC".equals(key)) { mode[0] = "letters"; renderKeyboard(area, editor, mode, uppercase, firstKey); return; }
                if ("123".equals(key)) { mode[0] = "numbers"; renderKeyboard(area, editor, mode, uppercase, firstKey); return; }
                if ("#+=".equals(key)) { mode[0] = "symbols"; renderKeyboard(area, editor, mode, uppercase, firstKey); return; }
                if ("⇧".equals(key)) { uppercase[0] = !uppercase[0]; renderKeyboard(area, editor, mode, uppercase, firstKey); return; }
                String current = editor.getText().toString();
                if ("⌫".equals(key)) {
                    if (!current.isEmpty()) editor.setText(current.substring(0, current.length() - 1));
                } else if ("Limpiar".equals(key)) editor.setText("");
                else if ("Espacio".equals(key)) editor.setText(current + " ");
                else editor.setText(current + key);
            });
            if (firstKey[0] == null) firstKey[0] = button;
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT,
                "Espacio".equals(key) ? 2.4f : ("Limpiar".equals(key) ? 1.7f : 1f));
            params.setMargins(padding(3), padding(3), padding(3), padding(3));
            row.addView(button, params);
        }
        area.addView(row, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    private int padding(int dp) {
        return Math.round(dp * getActivity().getResources().getDisplayMetrics().density);
    }

    private StateListDrawable keyBackground() {
        GradientDrawable focused = new GradientDrawable();
        focused.setColor(Color.parseColor("#F4C430"));
        focused.setCornerRadius(padding(8));
        GradientDrawable normal = new GradientDrawable();
        normal.setColor(Color.parseColor("#293B4F"));
        normal.setCornerRadius(padding(8));
        StateListDrawable states = new StateListDrawable();
        states.addState(new int[] { android.R.attr.state_focused }, focused);
        states.addState(new int[] { android.R.attr.state_pressed }, focused);
        states.addState(new int[] {}, normal);
        return states;
    }

    private ColorStateList keyTextColors() {
        return new ColorStateList(
            new int[][] { new int[] { android.R.attr.state_focused }, new int[] { android.R.attr.state_pressed }, new int[] {} },
            new int[] { Color.parseColor("#07111F"), Color.parseColor("#07111F"), Color.WHITE });
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
