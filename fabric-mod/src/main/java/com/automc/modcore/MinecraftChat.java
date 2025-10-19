/**
 * AutoMinecraft MC chat helper.
 *
 * Purpose: Safely send chat messages on the Minecraft client thread.
 *
 * How: Wraps networkHandler.sendChatMessage in a mc.execute runnable after
 * verifying the client and player are present.
 */
package com.automc.modcore;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.ChatScreen;

final class MinecraftChat {
    private MinecraftChat() {}

    static void send(String text) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null) return;
        mc.execute(() -> {
            try {
                if (text != null && text.startsWith(".")) {
                    // Route dot-commands through ChatScreen to allow client-side mods (e.g., Wurst) to intercept
                    ChatScreen screen = new ChatScreen("");
                    mc.setScreen(screen);
                    // Best-effort: use ChatScreen API to submit the message as if typed by the user
                    screen.sendMessage(text, true);
                    mc.setScreen(null);
                } else {
                    mc.player.networkHandler.sendChatMessage(text);
                }
            } catch (Throwable t) {
                // Fallback to direct send if UI path fails
                mc.player.networkHandler.sendChatMessage(text);
            }
        });
    }
}
