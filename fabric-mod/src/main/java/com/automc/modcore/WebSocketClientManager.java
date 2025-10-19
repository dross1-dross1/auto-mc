/**
 * AutoMinecraft WebSocket client manager.
 *
 * Purpose: Owns the single client-side WebSocket connection to the backend and provides
 * a thread-safe JSON send path plus a rate-limited chat-bridge helper.
 *
 * How: Creates dedicated single-thread executors for sending and auxiliary tasks, wires
 * WebSocket callbacks to enqueue inbound messages into the game-thread MessagePump, and
 * applies safe Baritone defaults after connect. Exposes an accessor for the active
 * player id and a rate-limited chat send that executes on the MC thread.
 *
 * Engineering notes: Keep IO off the MC thread; centralize rate-limiting and settings;
 * prefer explicit reconnection/backoff in future; avoid hardcoded secrets; structured logs.
 */
package com.automc.modcore;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;

import java.net.URI;
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
    private final ExecutorService auxExec = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "AutoMC-WS-Aux");
        t.setDaemon(true);
        return t;
    });
    private volatile boolean telemetryRunning = false;

    private WebSocketClientManager() {}

    public static WebSocketClientManager getInstance() { return INSTANCE; }

    public String getPlayerId() {
        return this.config != null ? this.config.playerId : "";
    }

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
                    // Apply conservative Baritone defaults shortly after connect
                    applyBaritoneDefaultsAsync();
                    // Start telemetry heartbeat
                    startTelemetryHeartbeat();
                }
                @Override public void onMessage(String message) {
                    // Pump into a queue to be processed on client tick, not IO thread
                    MessagePump.enqueue(message);
                }
                @Override public void onClose(int code, String reason, boolean remote) {
                    LOGGER.info("WS closed: {} {} remote={} ", code, reason, remote);
                }
                @Override public void onError(Exception ex) {
                    LOGGER.warn("WS error", ex);
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

    private void applyBaritoneDefaultsAsync() {
        // Space out a few safe defaults; backend may override later via settings_update
        auxExec.submit(() -> {
            try {
                Thread.sleep(250L);
                sendBaritoneSetting("allowParkour", "false");
                sendBaritoneSetting("allowDiagonalAscend", "false");
                sendBaritoneSetting("assumeWalkOnWater", "false");
                sendBaritoneSetting("freeLook", "false");
                sendBaritoneSetting("primaryTimeoutMS", "4000");
            } catch (InterruptedException ignored) {
            }
        });
    }

    private void sendBaritoneSetting(String key, String value) {
        JsonObject msg = new JsonObject();
        msg.addProperty("type", "chat_send");
        msg.addProperty("request_id", java.util.UUID.randomUUID().toString());
        msg.addProperty("player_id", config.playerId);
        msg.addProperty("text", "#set " + key + " " + value);
        sendJson(msg);
    }

    private void startTelemetryHeartbeat() {
        if (telemetryRunning) return;
        telemetryRunning = true;
        auxExec.submit(() -> {
            while (telemetryRunning) {
                try {
                    Thread.sleep(Math.max(250, config.telemetryIntervalMs));
                    sendTelemetryOnce();
                } catch (InterruptedException ignored) {
                } catch (Throwable t) {
                    LOGGER.warn("telemetry heartbeat error", t);
                }
            }
        });
    }

    private void sendTelemetryOnce() {
        net.minecraft.client.MinecraftClient mc = net.minecraft.client.MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.world == null) return;
        JsonObject st = new JsonObject();
        st.add("pos", array3(mc.player.getX(), mc.player.getY(), mc.player.getZ()));
        st.addProperty("dim", mc.world.getRegistryKey().getValue().toString());
        st.addProperty("yaw", mc.player.getYaw());
        st.addProperty("pitch", mc.player.getPitch());
        st.addProperty("health", (int) Math.ceil(mc.player.getHealth()));
        st.addProperty("hunger", mc.player.getHungerManager().getFoodLevel());
        st.addProperty("saturation", (double) mc.player.getHungerManager().getSaturationLevel());
        st.addProperty("air", mc.player.getAir());
        st.addProperty("xp_level", mc.player.experienceLevel);
        st.addProperty("time", (int) (mc.world.getTimeOfDay() % Integer.MAX_VALUE));
        // Inventory snapshot (non-empty slots)
        com.google.gson.JsonArray inv = new com.google.gson.JsonArray();
        net.minecraft.entity.player.PlayerInventory pinv = mc.player.getInventory();
        for (int i = 0; i < pinv.size(); i++) {
            net.minecraft.item.ItemStack stack = pinv.getStack(i);
            if (stack == null || stack.isEmpty()) continue;
            JsonObject slot = new JsonObject();
            slot.addProperty("slot", i);
            slot.addProperty("id", net.minecraft.registry.Registries.ITEM.getId(stack.getItem()).toString());
            slot.addProperty("count", stack.getCount());
            inv.add(slot);
        }
        st.add("inventory", inv);

        JsonObject msg = new JsonObject();
        msg.addProperty("type", "telemetry_update");
        msg.addProperty("player_id", config.playerId);
        msg.addProperty("ts", java.time.Instant.now().toString());
        msg.add("state", st);
        sendJson(msg);
    }

    private static com.google.gson.JsonArray array3(double x, double y, double z) {
        com.google.gson.JsonArray a = new com.google.gson.JsonArray(3);
        a.add(x);
        a.add(y);
        a.add(z);
        return a;
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
