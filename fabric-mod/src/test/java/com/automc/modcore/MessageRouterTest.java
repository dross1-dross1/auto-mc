package com.automc.modcore;

import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.MockedStatic;
import org.mockito.Mockito;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

final class MessageRouterTest {

    @Test
    void chatSend_withCommandPrefix_isRateLimitedSent() {
        try (MockedStatic<WebSocketClientManager> staticMock = Mockito.mockStatic(WebSocketClientManager.class)) {
            WebSocketClientManager mgr = mock(WebSocketClientManager.class);
            staticMock.when(WebSocketClientManager::getInstance).thenReturn(mgr);
            when(mgr.trySendChatRateLimited("#mine iron_ore")).thenReturn(true);

            String raw = "{\"type\":\"chat_send\",\"text\":\"#mine iron_ore\"}";
            MessageRouter.onMessage(raw);

            verify(mgr, times(1)).trySendChatRateLimited("#mine iron_ore");
        }
    }

    @Test
    void chatSend_withoutCommandPrefix_isNotSent() {
        try (MockedStatic<WebSocketClientManager> staticMock = Mockito.mockStatic(WebSocketClientManager.class)) {
            WebSocketClientManager mgr = mock(WebSocketClientManager.class);
            staticMock.when(WebSocketClientManager::getInstance).thenReturn(mgr);

            String raw = "{\"type\":\"chat_send\",\"text\":\"hello world\"}";
            MessageRouter.onMessage(raw);

            verify(mgr, never()).trySendChatRateLimited(anyString());
        }
    }

    @Test
    void actionRequest_chatBridge_sendsProgressOkOnSent() {
        try (MockedStatic<WebSocketClientManager> staticMock = Mockito.mockStatic(WebSocketClientManager.class)) {
            WebSocketClientManager mgr = mock(WebSocketClientManager.class);
            staticMock.when(WebSocketClientManager::getInstance).thenReturn(mgr);
            when(mgr.trySendChatRateLimited("#goto 1 2 3")).thenReturn(true);

            String raw = "{\"type\":\"action_request\",\"action_id\":\"a1\",\"mode\":\"chat_bridge\",\"chat_text\":\"#goto 1 2 3\"}";
            MessageRouter.onMessage(raw);

            ArgumentCaptor<JsonObject> cap = ArgumentCaptor.forClass(JsonObject.class);
            verify(mgr, times(1)).sendJson(cap.capture());
            JsonObject sent = cap.getValue();
            assertEquals("progress_update", sent.get("type").getAsString());
            assertEquals("a1", sent.get("action_id").getAsString());
            assertEquals("ok", sent.get("status").getAsString());
        }
    }

    @Test
    void actionRequest_chatBridge_sendsProgressSkippedWhenRateLimited() {
        try (MockedStatic<WebSocketClientManager> staticMock = Mockito.mockStatic(WebSocketClientManager.class)) {
            WebSocketClientManager mgr = mock(WebSocketClientManager.class);
            staticMock.when(WebSocketClientManager::getInstance).thenReturn(mgr);
            when(mgr.trySendChatRateLimited("#goto 1 2 3")).thenReturn(false);

            String raw = "{\"type\":\"action_request\",\"action_id\":\"a2\",\"mode\":\"chat_bridge\",\"chat_text\":\"#goto 1 2 3\"}";
            MessageRouter.onMessage(raw);

            ArgumentCaptor<JsonObject> cap = ArgumentCaptor.forClass(JsonObject.class);
            verify(mgr, times(1)).sendJson(cap.capture());
            JsonObject sent = cap.getValue();
            assertEquals("progress_update", sent.get("type").getAsString());
            assertEquals("a2", sent.get("action_id").getAsString());
            assertEquals("skipped", sent.get("status").getAsString());
        }
    }

    @Test
    void actionRequest_modNative_routesToActionExecutor() {
        try (MockedStatic<ActionExecutor> actionMock = Mockito.mockStatic(ActionExecutor.class)) {
            String raw = "{\"type\":\"action_request\",\"action_id\":\"a3\",\"mode\":\"mod_native\",\"op\":\"craft\",\"recipe\":\"minecraft:stick\"}";
            MessageRouter.onMessage(raw);
            actionMock.verify(() -> ActionExecutor.handle(Mockito.any(JsonObject.class)), times(1));
        }
    }

    @Test
    void stateRequest_sendsStateResponse_withSelectedKeys() {
        try (MockedStatic<WebSocketClientManager> staticMock = Mockito.mockStatic(WebSocketClientManager.class)) {
            WebSocketClientManager mgr = mock(WebSocketClientManager.class);
            staticMock.when(WebSocketClientManager::getInstance).thenReturn(mgr);
            when(mgr.getPlayerId()).thenReturn("p1");
            JsonObject snapshot = new JsonObject();
            snapshot.addProperty("foo", "bar");
            snapshot.addProperty("other", "x");
            when(mgr.buildStateSnapshot()).thenReturn(snapshot);

            String raw = "{\"type\":\"state_request\",\"request_id\":\"r1\",\"selector\":[\"foo\"]}";
            MessageRouter.onMessage(raw);

            ArgumentCaptor<JsonObject> cap = ArgumentCaptor.forClass(JsonObject.class);
            verify(mgr, times(1)).sendJson(cap.capture());
            JsonObject sent = cap.getValue();
            assertEquals("state_response", sent.get("type").getAsString());
            assertEquals("r1", sent.get("request_id").getAsString());
            JsonObject state = sent.getAsJsonObject("state");
            assertEquals("bar", state.get("foo").getAsString());
            assertFalse(state.has("other"));
        }
    }

    @Test
    void settingsUpdate_appliesSettingsOnClient() {
        try (MockedStatic<WebSocketClientManager> staticMock = Mockito.mockStatic(WebSocketClientManager.class)) {
            WebSocketClientManager mgr = mock(WebSocketClientManager.class);
            staticMock.when(WebSocketClientManager::getInstance).thenReturn(mgr);

            String raw = "{\"type\":\"settings_update\",\"settings\":{\"telemetry_interval_ms\":1500,\"rate_limit_chat\":1,\"baritone\":{\"autoTool\":\"true\"}}}";
            MessageRouter.onMessage(raw);

            ArgumentCaptor<JsonObject> cap = ArgumentCaptor.forClass(JsonObject.class);
            verify(mgr, times(1)).applySettings(Mockito.any(JsonObject.class));
        }
    }

    @Test
    void invalidJson_isTolerated() {
        assertDoesNotThrow(() -> MessageRouter.onMessage("{ not json }"));
    }
}
