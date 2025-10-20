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
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class AutoMinecraftClient implements ClientModInitializer {
    public static final Logger LOGGER = LogManager.getLogger("AutoMinecraft");

    @Override
    public void onInitializeClient() {
        LOGGER.info("AutoMinecraft client initializing");
        ModConfig config = ModConfig.load();
        MessagePump.register();
        WebSocketClientManager.getInstance().start(config);
        ChatInterceptor.register();
        ChatEventForwarder.register();
        InventoryWatcher.register();
    }
}
