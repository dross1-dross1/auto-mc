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

final class ActionExecutor {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.Actions");

    private ActionExecutor() {}

    static void handle(JsonObject obj) {
        String actionId = obj.has("action_id") ? obj.get("action_id").getAsString() : "";
        String op = obj.has("op") ? obj.get("op").getAsString() : "";
        if ("craft".equals(op)) {
            String recipe = obj.has("recipe") ? obj.get("recipe").getAsString() : "";
            int count = obj.has("count") ? obj.get("count").getAsInt() : 1;
            tryCraft2x2(actionId, recipe, count);
            return;
        }
        if ("ensure".equals(op)) {
            String ensure = obj.has("ensure") ? obj.get("ensure").getAsString() : "";
            handleEnsure(actionId, ensure);
            return;
        }
        // Unknown or unimplemented op
        sendProgress(actionId, "skipped", "mod_native not implemented: " + op);
    }

    private static void tryCraft2x2(String actionId, String recipe, int count) {
        boolean attempted = Crafting2x2.tryCraft(actionId, recipe, count);
        if (!attempted) {
            sendProgress(actionId, "fail", "craft attempt failed: " + recipe);
        }
    }

    private static void handleEnsure(String actionId, String ensure) {
        if ("crafting_table_nearby".equals(ensure)) {
            EnsureContext.ensureCraftingTableNearby(actionId);
            return;
        }
        if ("furnace_nearby".equals(ensure)) {
            EnsureContext.ensureFurnaceNearby(actionId);
            return;
        }
        sendProgress(actionId, "skipped", "unknown ensure: " + ensure);
    }

    static void sendProgress(String actionId, String status, String note) {
        JsonObject progress = new JsonObject();
        progress.addProperty("type", "progress_update");
        progress.addProperty("action_id", actionId);
        progress.addProperty("status", status);
        if (note != null) progress.addProperty("note", note);
        WebSocketClientManager.getInstance().sendJson(progress);
        LOGGER.info("progress_update: id={} status={} note={}", actionId, status, note);
    }
}
