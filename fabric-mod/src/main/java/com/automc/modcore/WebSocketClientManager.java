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
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class WebSocketClientManager {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.WS");
    private static final Gson GSON = new Gson();
    private static final WebSocketClientManager INSTANCE = new WebSocketClientManager();

    private WebSocketClient client;
    private volatile boolean connected = false;
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
    // Runtime overrides applied via settings_update
    private volatile Boolean chatBridgeEnabledOverride = null;
    private volatile Integer chatRateLimitPerSecOverride = null;
    private volatile Boolean echoPublicDefaultOverride = null;
    private volatile String commandPrefixOverride = null;
    private volatile Boolean ackOnCommandOverride = null;
    private volatile Integer telemetryIntervalMsOverride = null;
    private volatile Integer messagePumpMaxPerTickOverride = null;
    private volatile Integer messagePumpQueueCapOverride = null;
    private volatile Integer inventoryDiffDebounceMsOverride = null;
    private volatile Integer chatMaxLengthOverride = null;
    private volatile String feedbackPrefixOverride = null;
    private volatile String feedbackBracketColorOverride = null;
    private volatile String feedbackInnerColorOverride = null;

    private WebSocketClientManager() {}

    public static WebSocketClientManager getInstance() { return INSTANCE; }

    public String getPlayerId() {
        net.minecraft.client.MinecraftClient mc = net.minecraft.client.MinecraftClient.getInstance();
        if (mc == null || mc.player == null) {
            throw new IllegalStateException("player uuid unavailable before world join");
        }
        return mc.player.getUuidAsString();
    }

    public String getCommandPrefixOrNull() { return this.commandPrefixOverride; }

    public boolean getEchoPublicDefault() { return this.echoPublicDefaultOverride != null && this.echoPublicDefaultOverride.booleanValue(); }

    public int getChatRateLimitPerSecEffective() { return (this.chatRateLimitPerSecOverride != null) ? this.chatRateLimitPerSecOverride.intValue() : 0; }

    public boolean getAckOnCommandEnabled() { return this.ackOnCommandOverride != null && this.ackOnCommandOverride.booleanValue(); }

    public int getTelemetryIntervalMsEffective() { if (this.telemetryIntervalMsOverride == null) throw new IllegalStateException("telemetry_interval_ms not set"); return this.telemetryIntervalMsOverride.intValue(); }

    public int getMessagePumpMaxPerTick() { if (this.messagePumpMaxPerTickOverride == null) throw new IllegalStateException("message_pump_max_per_tick not set"); return this.messagePumpMaxPerTickOverride.intValue(); }

    public int getMessagePumpQueueCap() { if (this.messagePumpQueueCapOverride == null) throw new IllegalStateException("message_pump_queue_cap not set"); return this.messagePumpQueueCapOverride.intValue(); }

    public int getInventoryDiffDebounceMs() { if (this.inventoryDiffDebounceMsOverride == null) throw new IllegalStateException("inventory_diff_debounce_ms not set"); return this.inventoryDiffDebounceMsOverride.intValue(); }

    public int getChatMaxLengthOrZero() { return (this.chatMaxLengthOverride != null) ? this.chatMaxLengthOverride.intValue() : 0; }

    public String getFeedbackPrefixOrEmpty() { return this.feedbackPrefixOverride != null ? this.feedbackPrefixOverride : ""; }
    public String getFeedbackBracketColorOrNull() { return this.feedbackBracketColorOverride; }
    public String getFeedbackInnerColorOrNull() { return this.feedbackInnerColorOverride; }

    public boolean areSettingsApplied() {
        return this.telemetryIntervalMsOverride != null
            && this.messagePumpMaxPerTickOverride != null
            && this.messagePumpQueueCapOverride != null
            && this.chatBridgeEnabledOverride != null
            && this.chatRateLimitPerSecOverride != null
            && this.commandPrefixOverride != null
            && this.ackOnCommandOverride != null
            && this.inventoryDiffDebounceMsOverride != null;
    }

    public synchronized void connect(String backendUrl, String password) {
        if (this.client != null && this.client.isOpen()) return;
        try {
            URI uri = new URI(backendUrl);
            this.client = new WebSocketClient(uri) {
                @Override public void onOpen(ServerHandshake handshakeData) {
                    LOGGER.info("WS connected {}", uri);
                    JsonObject handshake = new JsonObject();
                    handshake.addProperty("type", Protocol.TYPE_HANDSHAKE);
                    handshake.addProperty("seq", 1);
                    handshake.addProperty("player_uuid", getPlayerId());
                    handshake.addProperty("password", password);
                    handshake.addProperty("client_version", "mod/0.1.0");
                    try {
                        net.minecraft.client.MinecraftClient mcClient = net.minecraft.client.MinecraftClient.getInstance();
                        if (mcClient != null && mcClient.player != null) {
                            handshake.addProperty("player_name", mcClient.player.getName().getString());
                        }
                    } catch (Throwable ignored) {}
                    JsonObject caps = new JsonObject();
                    caps.addProperty("chat_bridge", true);
                    caps.addProperty("mod_native_ensure", true);
                    handshake.add("capabilities", caps);
                    enqueueSend(GSON.toJson(handshake));
                    // Send one immediate telemetry snapshot for early username adoption
                    try {
                        sendTelemetryOnce();
                    } catch (Throwable ignored) {}
                    connected = true;
                }
                @Override public void onMessage(String message) {
                    try {
                        com.google.gson.JsonObject obj = GSON.fromJson(message, com.google.gson.JsonObject.class);
                        if (obj != null && obj.has("type")) {
                            String t = obj.get("type").getAsString();
                            if (Protocol.TYPE_SETTINGS_UPDATE.equals(t) || Protocol.TYPE_SETTINGS_BROADCAST.equals(t)) {
                                if (obj.has("settings") && obj.get("settings").isJsonObject()) {
                                    applySettings(obj.getAsJsonObject("settings"));
                                }
                                // Confirmation is provided by backend via chat_send; avoid duplicate local HUD
                                return; // settings applied; no need to enqueue this
                            }
                        }
                    } catch (Throwable ignored) {}
                    // Pump non-settings messages into a queue to be processed on the client tick
                    MessagePump.enqueue(message);
                }
                @Override public void onClose(int code, String reason, boolean remote) {
                    LOGGER.info("WS closed: {} {} remote={} ", code, reason, remote);
                    connected = false;
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

    public synchronized void disconnect() {
        try {
            telemetryRunning = false;
            if (client != null) {
                client.close();
            }
        } catch (Exception ignored) {}
        connected = false;
    }

    public boolean isConnected() { return connected && client != null && client.isOpen(); }

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

    // Settings application happens via backend-driven messages or explicit chat commands
    private void sendBaritoneSetting(String key, String value) { trySendChatRateLimited("#set " + key + " " + value); }

    private void startTelemetryHeartbeat() {
        if (telemetryRunning) return;
        telemetryRunning = true;
        auxExec.submit(() -> {
            while (telemetryRunning) {
                try {
                    Thread.sleep(getTelemetryIntervalMsEffective());
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
        JsonObject st = buildStateSnapshot();

                    JsonObject msg = new JsonObject();
                    msg.addProperty("type", Protocol.TYPE_TELEMETRY_UPDATE);
        msg.addProperty("player_uuid", getPlayerId());
        msg.addProperty("ts", java.time.Instant.now().toString());
        msg.add("state", st);
        sendJson(msg);
    }

    public JsonObject buildStateSnapshot() {
        net.minecraft.client.MinecraftClient mc = net.minecraft.client.MinecraftClient.getInstance();
        JsonObject st = new JsonObject();
        if (mc == null || mc.player == null || mc.world == null) return st;
        // Identity hints for backend to adopt UUID and username when config uses player_id=auto
        st.addProperty("uuid", mc.player.getUuidAsString());
        st.addProperty("username", mc.player.getName().getString());
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
        return st;
    }

    private static com.google.gson.JsonArray array3(double x, double y, double z) {
        com.google.gson.JsonArray a = new com.google.gson.JsonArray(3);
        a.add(x);
        a.add(y);
        a.add(z);
        return a;
    }

    public boolean trySendChatRateLimited(String text) {
        long now = System.currentTimeMillis();
        if (this.chatBridgeEnabledOverride == null || !this.chatBridgeEnabledOverride.booleanValue()) return false;
        int rate = getChatRateLimitPerSecEffective();
        long minIntervalMs = (rate <= 0) ? 0 : (1000L / rate);
        if (minIntervalMs > 0 && (now - lastChatSendMillis) < minIntervalMs) {
            return false;
        }
        lastChatSendMillis = now;
        MinecraftChat.send(text);
        return true;
    }

    public void applySettings(com.google.gson.JsonObject settings) {
        if (settings == null) return;
        try {
            if (settings.has("telemetry_interval_ms")) this.telemetryIntervalMsOverride = settings.get("telemetry_interval_ms").getAsInt();
            if (settings.has("chat_bridge_enabled")) this.chatBridgeEnabledOverride = settings.get("chat_bridge_enabled").getAsBoolean();
            if (settings.has("chat_bridge_rate_limit_per_sec")) this.chatRateLimitPerSecOverride = settings.get("chat_bridge_rate_limit_per_sec").getAsInt();
            if (settings.has("echo_public_default")) this.echoPublicDefaultOverride = settings.get("echo_public_default").getAsBoolean();
            if (settings.has("command_prefix")) this.commandPrefixOverride = settings.get("command_prefix").getAsString();
            if (settings.has("ack_on_command")) this.ackOnCommandOverride = settings.get("ack_on_command").getAsBoolean();
            if (settings.has("message_pump_max_per_tick")) this.messagePumpMaxPerTickOverride = settings.get("message_pump_max_per_tick").getAsInt();
            if (settings.has("message_pump_queue_cap")) this.messagePumpQueueCapOverride = settings.get("message_pump_queue_cap").getAsInt();
            if (settings.has("inventory_diff_debounce_ms")) this.inventoryDiffDebounceMsOverride = settings.get("inventory_diff_debounce_ms").getAsInt();
            if (settings.has("chat_max_length")) this.chatMaxLengthOverride = settings.get("chat_max_length").getAsInt();
            if (settings.has("crafting_click_delay_ms")) { /* reserved */ }
            if (settings.has("feedback_prefix")) this.feedbackPrefixOverride = settings.get("feedback_prefix").getAsString();
            if (settings.has("feedback_prefix_bracket_color")) this.feedbackBracketColorOverride = settings.get("feedback_prefix_bracket_color").getAsString();
            if (settings.has("feedback_prefix_inner_color")) this.feedbackInnerColorOverride = settings.get("feedback_prefix_inner_color").getAsString();
            if (settings.has("baritone") && settings.get("baritone").isJsonObject()) {
                com.google.gson.JsonObject baritone = settings.getAsJsonObject("baritone");
                for (java.util.Map.Entry<String, com.google.gson.JsonElement> e : baritone.entrySet()) {
                    String key = e.getKey();
                    String value = e.getValue().isJsonPrimitive() ? e.getValue().getAsString() : e.getValue().toString();
                    sendBaritoneSetting(key, value);
                }
            }
            // Start telemetry heartbeat only after interval is known
            if (!telemetryRunning && this.telemetryIntervalMsOverride != null && this.telemetryIntervalMsOverride.intValue() > 0) {
                startTelemetryHeartbeat();
            }
            // Wurst settings can be handled here in the future
        } catch (Throwable t) {
            LOGGER.debug("applySettings error: {}", t.toString());
        }
    }
}
