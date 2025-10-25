/**
 * AutoMinecraft client entrypoint.
 *
 * Purpose: Initialize the mod on client startup: load config, register the
 * message pump, start the WebSocket connection, and wire chat interception.
 *
 * How: Implements Fabric's ClientModInitializer and performs minimal, ordered
 * setup. Defers IO to dedicated managers to keep the entrypoint small.
 *
 * Engineering notes: Keep initialization concise; prefer centralized config;
 * avoid heavy work here.
 */
package com.automc.modcore;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class AutoMinecraftClient implements ClientModInitializer {
    public static final Logger LOGGER = LogManager.getLogger("AutoMinecraft");

    @Override
    public void onInitializeClient() {
        LOGGER.info("AutoMinecraft client initializing");
        MessagePump.register();
        ChatInterceptor.register();
        ChatEventForwarder.register();
        com.automc.modcore.inventory.InventoryWatcher.register();
        // Auto-disconnect when leaving world/server
        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            try {
                if (client == null) return;
                boolean inWorld = client.world != null && client.player != null;
                if (!inWorld && WebSocketClientManager.getInstance().isConnected()) {
                    WebSocketClientManager.getInstance().disconnect();
                }
            } catch (Throwable ignored) {}
        });
    }
}
