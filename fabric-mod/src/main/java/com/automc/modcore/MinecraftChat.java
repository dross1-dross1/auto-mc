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
