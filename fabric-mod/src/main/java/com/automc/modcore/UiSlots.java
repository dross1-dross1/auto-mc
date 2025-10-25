/**
 * UI slot utilities for translating player inventory indices to handler slots
 * and issuing click actions on the current screen handler.
 */
package com.automc.modcore;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientPlayerInteractionManager;
import net.minecraft.screen.slot.SlotActionType;

public final class UiSlots {
    private UiSlots() {}

    public static int toHandlerSlotIndex(int playerInvIndex) {
        // PlayerInventory indices: 0..8 hotbar, 9..35 main
        // InventoryScreen (2x2): PlayerScreenHandler slot indices: 36..44 hotbar, 9..35 main (0..4 are craft/result)
        // CraftingScreen (3x3): 0 result, 1..9 grid, then 10..36 main, 37..45 hotbar
        net.minecraft.client.MinecraftClient mc = net.minecraft.client.MinecraftClient.getInstance();
        boolean isCrafting = (mc != null && mc.currentScreen instanceof net.minecraft.client.gui.screen.ingame.CraftingScreen);
        if (isCrafting) {
            if (playerInvIndex >= 0 && playerInvIndex <= 8) return 37 + playerInvIndex; // hotbar
            if (playerInvIndex >= 9 && playerInvIndex <= 35) return 1 + playerInvIndex; // main inv
            return playerInvIndex;
        }
        // Default to InventoryScreen mapping
        if (playerInvIndex >= 0 && playerInvIndex <= 8) return 36 + playerInvIndex;
        return playerInvIndex;
    }

    public static void click(int slot, int button, SlotActionType type) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return;
        ClientPlayerInteractionManager im = mc.interactionManager;
        int syncId = mc.player.currentScreenHandler.syncId;
        im.clickSlot(syncId, slot, button, type, mc.player);
    }
}
