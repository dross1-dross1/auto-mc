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


