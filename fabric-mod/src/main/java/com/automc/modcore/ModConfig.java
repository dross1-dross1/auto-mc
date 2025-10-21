/**
 * AutoMinecraft mod configuration (stateless defaults).
 *
 * Purpose: Provide in-memory defaults only. The mod does not read or write any
 * files. Runtime settings are applied via backend-driven settings_update.
 */
package com.automc.modcore;

import com.google.gson.annotations.SerializedName;

public final class ModConfig {

    @SerializedName("backend_url")
    public final String backendUrl;
    @SerializedName("telemetry_interval_ms")
    public final int telemetryIntervalMs;
    @SerializedName("chat_bridge_enabled")
    public final boolean chatBridgeEnabled;
    @SerializedName("chat_bridge_rate_limit_per_sec")
    public final int chatBridgeRateLimitPerSec;
    @SerializedName("auth_token")
    public final String authToken;
    @SerializedName("command_prefix")
    public final String commandPrefix;
    @SerializedName("echo_public_default")
    public final boolean echoPublicDefault;
    @SerializedName("ack_on_command")
    public final boolean ackOnCommand;

    private ModConfig(String backendUrl, int telemetryIntervalMs, boolean chatBridgeEnabled, int chatBridgeRateLimitPerSec, String authToken, String commandPrefix, boolean echoPublicDefault, boolean ackOnCommand) {
        this.backendUrl = backendUrl;
        this.telemetryIntervalMs = telemetryIntervalMs;
        this.chatBridgeEnabled = chatBridgeEnabled;
        this.chatBridgeRateLimitPerSec = chatBridgeRateLimitPerSec;
        this.authToken = authToken;
        this.commandPrefix = commandPrefix;
        this.echoPublicDefault = echoPublicDefault;
        this.ackOnCommand = ackOnCommand;
    }

    public static ModConfig load() {
        // Stateless defaults; no disk I/O
        return new ModConfig("ws://127.0.0.1:8765", 500, true, 2, null, "!", false, true);
    }
}
