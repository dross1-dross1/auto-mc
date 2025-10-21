/**
 * AutoMinecraft mod configuration.
 *
 * Purpose: Centralize client config (backend URL, player id, telemetry interval,
 * chat bridge settings) and provide sane defaults. Writes a default file if none
 * exists to aid first-run.
 */
package com.automc.modcore;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.annotations.SerializedName;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

public final class ModConfig {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.Config");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

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
        Path configDir = Path.of("config");
        Path path = configDir.resolve("autominecraft.json");
        try {
            if (Files.notExists(path)) {
                Files.createDirectories(configDir);
                ModConfig def = new ModConfig("ws://127.0.0.1:8765", 500, true, 2, null, "!", false, true);
                try (BufferedWriter w = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
                    GSON.toJson(def, w);
                }
                LOGGER.info("wrote default config at {}", path.toAbsolutePath());
                return def;
            }
            try (BufferedReader r = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
                ModConfig cfg = GSON.fromJson(r, ModConfig.class);
                // If ack_on_command is absent in existing config, default it to true in-memory
                if (cfg == null) return new ModConfig("ws://127.0.0.1:8765", 500, true, 2, null, "!", false, true);
                return new ModConfig(
                    cfg.backendUrl,
                    cfg.telemetryIntervalMs,
                    cfg.chatBridgeEnabled,
                    cfg.chatBridgeRateLimitPerSec,
                    cfg.authToken,
                    cfg.commandPrefix,
                    cfg.echoPublicDefault,
                    (cfg.ackOnCommand)
                );
            }
        } catch (IOException e) {
            LOGGER.warn("failed to load config, using defaults: {}", e.toString());
            return new ModConfig("ws://127.0.0.1:8765", 500, true, 2, null, "!", false, true);
        }
    }
}
