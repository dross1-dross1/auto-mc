package com.automc.modcore;

import com.google.gson.JsonObject;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.message.v1.ClientReceiveMessageEvents;
import net.fabricmc.fabric.api.client.message.v1.ClientSendMessageEvents;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public final class ChatInterceptor {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.Chat");

    private ChatInterceptor() {}

    public static void register() {
        ClientSendMessageEvents.ALLOW_CHAT.register((message) -> {
            if (message != null && message.startsWith("!")) {
                // swallow and forward to backend as command
                JsonObject obj = new JsonObject();
                obj.addProperty("type", "command");
                obj.addProperty("request_id", java.util.UUID.randomUUID().toString());
                obj.addProperty("text", message);
                obj.addProperty("player_id", ModConfig.load().playerId);
                WebSocketClientManager.getInstance().sendJson(obj);
                return false;
            }
            return true;
        });
    }
}


