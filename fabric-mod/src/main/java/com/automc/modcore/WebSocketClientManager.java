package com.automc.modcore;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Objects;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class WebSocketClientManager {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.WS");
    private static final Gson GSON = new Gson();
    private static final WebSocketClientManager INSTANCE = new WebSocketClientManager();

    private WebSocketClient client;
    private ModConfig config;
    private long lastChatSendMillis = 0L;
    private final ExecutorService sendExec = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "AutoMC-WS-Send");
        t.setDaemon(true);
        return t;
    });

    private WebSocketClientManager() {}

    public static WebSocketClientManager getInstance() { return INSTANCE; }

    public synchronized void start(ModConfig config) {
        this.config = config;
        if (this.client != null && this.client.isOpen()) return;
        try {
            URI uri = new URI(Objects.requireNonNullElse(config.backendUrl, "ws://127.0.0.1:8765"));
            this.client = new WebSocketClient(uri) {
                @Override public void onOpen(ServerHandshake handshakeData) {
                    LOGGER.info("WS connected {}", uri);
                    JsonObject handshake = new JsonObject();
                    handshake.addProperty("type", "handshake");
                    handshake.addProperty("seq", 1);
                    handshake.addProperty("player_id", config.playerId);
                    handshake.addProperty("client_version", "mod/0.1.0");
                    enqueueSend(GSON.toJson(handshake));
                }
                @Override public void onMessage(String message) {
                    // Pump into a queue to be processed on client tick, not IO thread
                    MessagePump.enqueue(message);
                }
                @Override public void onClose(int code, String reason, boolean remote) {
                    LOGGER.info("WS closed: {} {} remote={} ", code, reason, remote);
                }
                @Override public void onError(Exception ex) {
                    LOGGER.warn("WS error: {}", ex.toString());
                }
            };
            this.client.connect();
        } catch (Exception e) {
            LOGGER.warn("failed to start WS: {}", e.toString());
        }
    }

    public void sendJson(JsonObject obj) { enqueueSend(GSON.toJson(obj)); }

    private void enqueueSend(String text) {
        if (client == null) return;
        sendExec.submit(() -> {
            try {
                if (client.isOpen()) {
                    client.send(text);
                }
            } catch (Exception e) {
                LOGGER.warn("WS send failed: {}", e.toString());
            }
        });
    }

    public boolean trySendChatRateLimited(String text) {
        if (!config.chatBridgeEnabled) return false;
        long now = System.currentTimeMillis();
        long minIntervalMs = (config.chatBridgeRateLimitPerSec <= 0) ? 0 : (1000L / config.chatBridgeRateLimitPerSec);
        if (minIntervalMs > 0 && (now - lastChatSendMillis) < minIntervalMs) {
            return false;
        }
        lastChatSendMillis = now;
        MinecraftChat.send(text);
        return true;
    }
}
