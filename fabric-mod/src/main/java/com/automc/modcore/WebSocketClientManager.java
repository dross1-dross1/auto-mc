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

public final class WebSocketClientManager {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.WS");
    private static final Gson GSON = new Gson();
    private static final WebSocketClientManager INSTANCE = new WebSocketClientManager();

    private WebSocketClient client;
    private ModConfig config;

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
                    send(GSON.toJson(handshake).getBytes(StandardCharsets.UTF_8));
                }
                @Override public void onMessage(String message) {
                    MessageRouter.onMessage(message);
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

    public void sendJson(JsonObject obj) {
        if (client != null && client.isOpen()) {
            client.send(GSON.toJson(obj));
        }
    }
}


