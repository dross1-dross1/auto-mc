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

    public final String backendUrl;
    public final String playerId;
    public final int telemetryIntervalMs;
    public final boolean chatBridgeEnabled;
    public final int chatBridgeRateLimitPerSec;

    private ModConfig(String backendUrl, String playerId, int telemetryIntervalMs, boolean chatBridgeEnabled, int chatBridgeRateLimitPerSec) {
        this.backendUrl = backendUrl;
        this.playerId = playerId;
        this.telemetryIntervalMs = telemetryIntervalMs;
        this.chatBridgeEnabled = chatBridgeEnabled;
        this.chatBridgeRateLimitPerSec = chatBridgeRateLimitPerSec;
    }

    public static ModConfig load() {
        Path configDir = Path.of("config");
        Path path = configDir.resolve("autominecraft.json");
        try {
            if (Files.notExists(path)) {
                Files.createDirectories(configDir);
                ModConfig def = new ModConfig("ws://127.0.0.1:8765", "player-1", 1000, true, 2);
                try (BufferedWriter w = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
                    GSON.toJson(def, w);
                }
                LOGGER.info("wrote default config at {}", path.toAbsolutePath());
                return def;
            }
            try (BufferedReader r = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
                return GSON.fromJson(r, ModConfig.class);
            }
        } catch (IOException e) {
            LOGGER.warn("failed to load config, using defaults: {}", e.toString());
            return new ModConfig("ws://127.0.0.1:8765", "player-1", 1000, true, 2);
        }
    }
}
