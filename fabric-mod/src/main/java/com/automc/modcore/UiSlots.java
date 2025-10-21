package com.automc.modcore;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientPlayerInteractionManager;
import net.minecraft.screen.slot.SlotActionType;

final class UiSlots {
    private UiSlots() {}

    static int toHandlerSlotIndex(int playerInvIndex) {
        // PlayerInventory indices: 0..8 hotbar, 9..35 main
        // PlayerScreenHandler slot indices: 36..44 hotbar, 9..35 main (0..4 are 2x2/result, 5..8 armor/offhand)
        if (playerInvIndex >= 0 && playerInvIndex <= 8) return 36 + playerInvIndex;
        return playerInvIndex;
    }

    static void click(int slot, int button, SlotActionType type) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return;
        ClientPlayerInteractionManager im = mc.interactionManager;
        int syncId = mc.player.currentScreenHandler.syncId;
        im.clickSlot(syncId, slot, button, type, mc.player);
    }
}


