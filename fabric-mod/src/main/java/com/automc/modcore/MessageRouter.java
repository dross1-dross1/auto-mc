package com.automc.modcore;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import net.minecraft.client.MinecraftClient;
import net.minecraft.text.Text;
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
                sendChat(text);
                LOGGER.info("chat_send -> {}", text);
                return;
            }
            if ("plan".equals(type)) {
                int count = obj.has("steps") && obj.get("steps").isJsonArray() ? obj.get("steps").getAsJsonArray().size() : -1;
                String req = obj.has("request_id") ? obj.get("request_id").getAsString() : "";
                LOGGER.info("plan received: request_id={} steps={}", req, count);
                return;
            }
            if ("action_request".equals(type)) {
                String actionId = obj.has("action_id") ? obj.get("action_id").getAsString() : "";
                String mode = obj.has("mode") ? obj.get("mode").getAsString() : "";
                String op = obj.has("op") ? obj.get("op").getAsString() : "";
                String chatText = obj.has("chat_text") ? obj.get("chat_text").getAsString() : "";
                LOGGER.info("action_request: id={} mode={} op={} chat_text={}", actionId, mode, op, chatText);
                return;
            }
        } catch (Exception e) {
            LOGGER.warn("message parse failed: {}", e.toString());
        }
    }

    private static void sendChat(String text) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc.player == null) return;
        mc.execute(() -> mc.player.networkHandler.sendChatMessage(text));
    }
}


