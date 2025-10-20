package com.automc.modcore;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientPlayerInteractionManager;
import net.minecraft.screen.slot.SlotActionType;

final class UiSlots {
    private UiSlots() {}

    static int toHandlerSlotIndex(int playerInvIndex) {
        // PlayerInventory: 0..8 hotbar, 9..35 main; PlayerScreenHandler: 32..40 hotbar, 5..31 main
        if (playerInvIndex >= 0 && playerInvIndex <= 8) return 32 + playerInvIndex;
        return 5 + (playerInvIndex - 9);
    }

    static void click(int slot, int button, SlotActionType type) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return;
        ClientPlayerInteractionManager im = mc.interactionManager;
        int syncId = mc.player.currentScreenHandler.syncId;
        im.clickSlot(syncId, slot, button, type, mc.player);
    }
}


