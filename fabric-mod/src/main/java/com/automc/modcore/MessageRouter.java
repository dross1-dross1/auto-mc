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
            if ("chat_send".equals(type)) {
                String text = obj.get("text").getAsString();
                boolean sent = WebSocketClientManager.getInstance().trySendChatRateLimited(text);
                LOGGER.info("chat_send -> {} (sent={})", text, sent);
                return;
            }
            if ("action_request".equals(type)) {
                String mode = obj.has("mode") ? obj.get("mode").getAsString() : "";
                if ("chat_bridge".equals(mode)) {
                    String chatText = obj.has("chat_text") ? obj.get("chat_text").getAsString() : "";
                    if (!chatText.isEmpty()) {
                        boolean sent = WebSocketClientManager.getInstance().trySendChatRateLimited(chatText);
                        LOGGER.info("chat_bridge exec -> {} (sent={})", chatText, sent);
                        // send progress_update ok
                        com.google.gson.JsonObject progress = new com.google.gson.JsonObject();
                        progress.addProperty("type", "progress_update");
                        progress.addProperty("action_id", obj.get("action_id").getAsString());
                        progress.addProperty("status", sent ? "ok" : "skipped");
                        WebSocketClientManager.getInstance().sendJson(progress);
                    }
                    return;
                }
                String actionId = obj.has("action_id") ? obj.get("action_id").getAsString() : "";
                String op = obj.has("op") ? obj.get("op").getAsString() : "";
                String chatText = obj.has("chat_text") ? obj.get("chat_text").getAsString() : "";
                LOGGER.info("action_request: id={} mode={} op={} chat_text={}", actionId, mode, op, chatText);
                // Route to mod-native action executor (v0 implements 2x2 crafting stubs)
                ActionExecutor.handle(obj);
                return;
            }
            if ("plan".equals(type)) {
                int count = obj.has("steps") && obj.get("steps").isJsonArray() ? obj.get("steps").getAsJsonArray().size() : -1;
                String req = obj.has("request_id") ? obj.get("request_id").getAsString() : "";
                LOGGER.info("plan received: request_id={} steps={}", req, count);
                return;
            }
        } catch (Exception e) {
            LOGGER.warn("message parse failed", e);
        }
    }
}
