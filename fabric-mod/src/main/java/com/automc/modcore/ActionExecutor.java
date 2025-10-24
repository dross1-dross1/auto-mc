/**
 * AutoMinecraft mod-native action executor.
 *
 * Purpose: Execute non-chat-bridge actions requested by the backend (e.g., craft,
 * ensure contexts), and report progress updates.
 *
 * How: Dispatches by 'op' and delegates to specific helpers like Crafting2x2.
 * Emits structured progress_update messages via the WebSocket manager.
 */
package com.automc.modcore;

import com.google.gson.JsonObject;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public final class ActionExecutor {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.Actions");

    private ActionExecutor() {}

    static void handle(JsonObject obj) {
        String actionId = obj.has("action_id") ? obj.get("action_id").getAsString() : "";
        String op = obj.has("op") ? obj.get("op").getAsString() : "";
        if ("craft".equals(op)) {
            String recipe = obj.has("recipe") ? obj.get("recipe").getAsString() : "";
            int count = obj.has("count") ? obj.get("count").getAsInt() : 1;
            String context = obj.has("context") && obj.get("context").isJsonPrimitive() ? obj.get("context").getAsString() : "";
            com.automc.modcore.actions.gui.GuiCrafting.craftByRecipeId(actionId, recipe, count, context);
            return;
        }
        if ("ensure".equals(op)) {
            // fail loudly: ensure-context is handled via Baritone (#set + #find + #goto) from backend
            sendProgress(actionId, "fail", "ensure handled via Baritone; no client fallback");
            return;
        }
        // Unknown or unimplemented op
        sendProgress(actionId, "skipped", "mod_native not implemented: " + op);
    }

    // 2x2 crafting is now delegated via GuiCrafting

    // no ensure handler

    public static void sendProgress(String actionId, String status, String note) {
        WebSocketClientManager.getInstance().sendJson(ClientMessages.progress(actionId, status, note));
        LOGGER.info("progress_update: id={} status={} note={}", actionId, status, note);
    }
}
