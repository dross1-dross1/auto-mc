package com.automc.modcore;

/**
 * Protocol constants shared across client components.
 */
final class Protocol {
    private Protocol() {}

    // Message types
    static final String TYPE_HANDSHAKE = "handshake";
    static final String TYPE_COMMAND = "command";
    static final String TYPE_CHAT_SEND = "chat_send";
    static final String TYPE_CHAT_EVENT = "chat_event";
    static final String TYPE_ACTION_REQUEST = "action_request";
    static final String TYPE_PROGRESS_UPDATE = "progress_update";
    static final String TYPE_TELEMETRY_UPDATE = "telemetry_update";
    static final String TYPE_STATE_REQUEST = "state_request";
    static final String TYPE_STATE_RESPONSE = "state_response";
    static final String TYPE_INVENTORY_SNAPSHOT = "inventory_snapshot";
    static final String TYPE_INVENTORY_DIFF = "inventory_diff";
    static final String TYPE_PLAN = "plan";
    static final String TYPE_SETTINGS_UPDATE = "settings_update";
    static final String TYPE_SETTINGS_BROADCAST = "settings_broadcast";

    // Modes
    static final String MODE_CHAT_BRIDGE = "chat_bridge";
    static final String MODE_MOD_NATIVE = "mod_native";

    // Limits moved to runtime settings via WebSocketClientManager
}


