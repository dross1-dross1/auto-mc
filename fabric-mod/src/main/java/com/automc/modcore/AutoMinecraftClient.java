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
    }
}
