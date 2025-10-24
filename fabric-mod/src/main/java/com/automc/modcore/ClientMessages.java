package com.automc.modcore;

import com.google.gson.JsonObject;

final class ClientMessages {
    private ClientMessages() {}

    static JsonObject progress(String actionId, String status, String note) {
        JsonObject obj = new JsonObject();
        obj.addProperty("type", Protocol.TYPE_PROGRESS_UPDATE);
        obj.addProperty("action_id", actionId);
        obj.addProperty("status", status);
        if (note != null) obj.addProperty("note", note);
        return obj;
    }

    static JsonObject stateResponse(String requestId, String playerId, com.google.gson.JsonObject state) {
        JsonObject obj = new JsonObject();
        obj.addProperty("type", Protocol.TYPE_STATE_RESPONSE);
        obj.addProperty("request_id", requestId);
        obj.addProperty("player_uuid", playerId);
        obj.add("state", state);
        return obj;
    }
}


