/**
 * AutoMinecraft chat event forwarder.
 *
 * Purpose: Listen for incoming chat/game messages and forward filtered lines
 * (e.g., Baritone/Wurst outputs) to the backend as `chat_event` messages.
 */
package com.automc.modcore;

import com.google.gson.JsonObject;
import net.fabricmc.fabric.api.client.message.v1.ClientReceiveMessageEvents;
import net.minecraft.text.Text;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

final class ChatEventForwarder {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.ChatEvents");

    private ChatEventForwarder() {}

    static void register() {
        // Forward game chat messages after they are shown to the HUD
        ClientReceiveMessageEvents.GAME.register((Text message, boolean overlay) -> {
            try {
                String text = message.getString();
                if (!shouldForward(text)) return;
                JsonObject evt = new JsonObject();
                evt.addProperty("type", Protocol.TYPE_CHAT_EVENT);
                evt.addProperty("player_uuid", WebSocketClientManager.getInstance().getPlayerId());
                evt.addProperty("text", text);
                evt.addProperty("ts", java.time.Instant.now().toString());
                WebSocketClientManager.getInstance().sendJson(evt);
            } catch (Throwable t) {
                LOGGER.debug("chat_event forward failed: {}", t.toString());
            }
        });
    }

    private static boolean shouldForward(String text) {
        if (text == null || text.isEmpty()) return false;
        String lower = text.toLowerCase();
        // Basic filter for common automation sources; expand as needed
        return lower.contains("baritone") || lower.contains("wurst");
    }
}


