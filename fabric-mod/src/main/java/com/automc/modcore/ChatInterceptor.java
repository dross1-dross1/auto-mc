/**
 * AutoMinecraft chat interceptor.
 *
 * Purpose: Capture client chat messages starting with '!' and forward them to the backend
 * as structured command JSON, while preventing them from broadcasting to public chat.
 *
 * How: Registers a Fabric ALLOW_CHAT listener; on '!'-prefixed input, constructs a JSON
 * payload and sends it via the shared WebSocket manager, returning false to swallow.
 *
 * Engineering notes: Avoid disk IO on hot paths; reuse player id from the active
 * WebSocket manager instead of reloading config for each message.
 */
package com.automc.modcore;

import com.google.gson.JsonObject;
import net.fabricmc.fabric.api.client.message.v1.ClientSendMessageEvents;

public final class ChatInterceptor {
    private ChatInterceptor() {}

    public static void register() {
        ClientSendMessageEvents.ALLOW_CHAT.register((message) -> {
            String prefix = WebSocketClientManager.getInstance().getConfigOrDefaultCommandPrefix("!");
            if (message != null && prefix != null && !prefix.isEmpty() && message.startsWith(prefix)) {
                // swallow and forward to backend as command
                JsonObject obj = new JsonObject();
                obj.addProperty("type", Protocol.TYPE_COMMAND);
                obj.addProperty("request_id", java.util.UUID.randomUUID().toString());
                obj.addProperty("text", message);
                obj.addProperty("player_id", WebSocketClientManager.getInstance().getPlayerId());
                WebSocketClientManager.getInstance().sendJson(obj);
                return false;
            }
            return true;
        });
    }
}
