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

final class MinecraftChat {
    private MinecraftChat() {}

    static void send(String text) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null) return;
        String safe = sanitize(text);
        mc.execute(() -> {
            try {
                mc.player.networkHandler.sendChatMessage(safe);
            } catch (Throwable t) {
                // No UI toggles; ensure message is sent if possible
                try { mc.player.networkHandler.sendChatMessage(safe); } catch (Throwable ignored) {}
            }
        });
    }

    private static String sanitize(String text) {
        if (text == null) return "";
        String trimmed = text.replaceAll("\r|\n", " ").trim();
        int maxLen = WebSocketClientManager.getInstance().getChatMaxLengthOrZero();
        if (maxLen > 0 && trimmed.length() > maxLen) {
            trimmed = trimmed.substring(0, maxLen);
        }
        // Prevent accidental @everyone or formatting abuse; basic neutralization
        trimmed = trimmed.replaceAll("@everyone", "@everyοne");
        return trimmed;
    }
}
