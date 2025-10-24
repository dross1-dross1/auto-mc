/**
 * AutoMinecraft message router.
 *
 * Purpose: Parse inbound JSON from the backend and dispatch to either the chat
 * bridge (rate-limited) or the mod-native action executor. Logs plans for
 * observability.
 *
 * How: Decodes with Gson on the client thread, switches by 'type' and 'mode',
 * and emits progress updates for chat-bridge actions immediately.
 *
 * Engineering notes: Keep parsing tolerant; prefer structured logging with ids;
 * non-blocking and minimal work per tick.
 */
package com.automc.modcore;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public final class MessageRouter {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.Router");
    private static final Gson GSON = new Gson();

    private MessageRouter() {}

    public static void onMessage(String raw) {
        try {
            JsonObject obj = GSON.fromJson(raw, JsonObject.class);
            if (obj == null || !obj.has("type")) return;
            String type = obj.get("type").getAsString();
            if (Protocol.TYPE_CHAT_SEND.equals(type)) {
                String text = obj.get("text").getAsString();
                boolean echoPublic = WebSocketClientManager.getInstance().getEchoPublicDefault();
                boolean isCommand = text.startsWith("#") || text.startsWith(".");
                boolean sent = false;
                if (isCommand) {
                    sent = WebSocketClientManager.getInstance().trySendChatRateLimited(text);
                } else if (echoPublic) {
                    sent = WebSocketClientManager.getInstance().trySendChatRateLimited(text);
                } else {
                    // Always show non-command chat_send locally in HUD
                    net.minecraft.client.MinecraftClient mc = net.minecraft.client.MinecraftClient.getInstance();
                    if (mc != null) {
                        mc.execute(() -> {
                            if (mc.inGameHud != null) {
                                mc.inGameHud.getChatHud().addMessage(net.minecraft.text.Text.of(text));
                            }
                        });
                    }
                }
                LOGGER.info("chat_send -> {} (sent={})", text, sent);
                return;
            }
            if (Protocol.TYPE_ACTION_REQUEST.equals(type)) {
                String mode = obj.has("mode") ? obj.get("mode").getAsString() : "";
                if (Protocol.MODE_CHAT_BRIDGE.equals(mode)) {
                    String chatText = obj.has("chat_text") ? obj.get("chat_text").getAsString() : "";
                    if (!chatText.isEmpty()) {
                        boolean sent = WebSocketClientManager.getInstance().trySendChatRateLimited(chatText);
                        LOGGER.info("chat_bridge exec -> {} (sent={})", chatText, sent);
                        WebSocketClientManager.getInstance().sendJson(ClientMessages.progress(obj.get("action_id").getAsString(), sent ? "ok" : "skipped", null));
                    }
                    return;
                }
                String actionId = obj.has("action_id") ? obj.get("action_id").getAsString() : "";
                String op = obj.has("op") ? obj.get("op").getAsString() : "";
                String chatText = obj.has("chat_text") ? obj.get("chat_text").getAsString() : "";
                LOGGER.info("action_request: id={} mode={} op={} chat_text={}", actionId, mode, op, chatText);
                // Route to mod-native action executor
                ActionExecutor.handle(obj);
                return;
            }
            if (Protocol.TYPE_PLAN.equals(type)) {
                int count = obj.has("steps") && obj.get("steps").isJsonArray() ? obj.get("steps").getAsJsonArray().size() : -1;
                String req = obj.has("request_id") ? obj.get("request_id").getAsString() : "";
                LOGGER.info("plan received: request_id={} steps={}", req, count);
                return;
            }
            if (Protocol.TYPE_STATE_REQUEST.equals(type)) {
                String reqId = obj.has("request_id") ? obj.get("request_id").getAsString() : java.util.UUID.randomUUID().toString();
                com.google.gson.JsonArray selector = obj.has("selector") && obj.get("selector").isJsonArray() ? obj.getAsJsonArray("selector") : null;
                com.google.gson.JsonObject full = WebSocketClientManager.getInstance().buildStateSnapshot();
                com.google.gson.JsonObject selected = new com.google.gson.JsonObject();
                if (selector != null && selector.size() > 0) {
                    for (com.google.gson.JsonElement el : selector) {
                        if (el != null && el.isJsonPrimitive()) {
                            String key = el.getAsString();
                            if (full.has(key)) {
                                selected.add(key, full.get(key));
                            }
                        }
                    }
                }
                com.google.gson.JsonObject state = (selector == null || selector.size() == 0) ? full : selected;
                WebSocketClientManager.getInstance().sendJson(ClientMessages.stateResponse(reqId, WebSocketClientManager.getInstance().getPlayerId(), state));
                return;
            }
            if (Protocol.TYPE_SETTINGS_UPDATE.equals(type) || Protocol.TYPE_SETTINGS_BROADCAST.equals(type)) {
                if (obj.has("settings") && obj.get("settings").isJsonObject()) {
                    WebSocketClientManager.getInstance().applySettings(obj.getAsJsonObject("settings"));
                    LOGGER.info("settings applied");
                }
                return;
            }
        } catch (Exception e) {
            LOGGER.warn("message parse failed", e);
        }
    }
}
