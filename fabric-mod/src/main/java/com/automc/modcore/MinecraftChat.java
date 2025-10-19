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
        mc.execute(() -> mc.player.networkHandler.sendChatMessage(text));
    }
}
