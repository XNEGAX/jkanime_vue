package com.animewing.tv;

import com.getcapacitor.BridgeActivity;
import android.os.Bundle;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(TvKeyboardPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
