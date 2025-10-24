package com.automc.modcore;

/**
 * Protocol constants shared across client components.
 */
public final class Protocol {
	private Protocol() {}

	// Message types
	public static final String TYPE_HANDSHAKE = "handshake";
	public static final String TYPE_COMMAND = "command";
	public static final String TYPE_CHAT_SEND = "chat_send";
	public static final String TYPE_CHAT_EVENT = "chat_event";
	public static final String TYPE_ACTION_REQUEST = "action_request";
	public static final String TYPE_PROGRESS_UPDATE = "progress_update";
	public static final String TYPE_TELEMETRY_UPDATE = "telemetry_update";
	public static final String TYPE_STATE_REQUEST = "state_request";
	public static final String TYPE_STATE_RESPONSE = "state_response";
	public static final String TYPE_INVENTORY_SNAPSHOT = "inventory_snapshot";
	public static final String TYPE_INVENTORY_DIFF = "inventory_diff";
	public static final String TYPE_PLAN = "plan";
	public static final String TYPE_SETTINGS_UPDATE = "settings_update";
	public static final String TYPE_SETTINGS_BROADCAST = "settings_broadcast";

	// Modes
	public static final String MODE_CHAT_BRIDGE = "chat_bridge";
	public static final String MODE_MOD_NATIVE = "mod_native";
}


