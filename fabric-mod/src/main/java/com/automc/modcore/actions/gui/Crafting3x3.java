package com.automc.modcore.actions.gui;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.ingame.HandledScreen;
import net.minecraft.entity.player.PlayerInventory;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.screen.slot.SlotActionType;

final class Crafting3x3 {
    private Crafting3x3() {}

    static boolean tryCraft(String actionId, String recipeId, int count) {
        if (recipeId == null || recipeId.isEmpty() || count <= 0) return false;
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return false;
        if (!(mc.currentScreen instanceof HandledScreen<?>)) return false;

        final int crafts = Math.max(1, count);
        switch (recipeId) {
            case "minecraft:wooden_pickaxe":
                mc.execute(() -> craftWoodenPickaxe(actionId, crafts));
                return true;
            case "minecraft:oak_planks":
                mc.execute(() -> craftPlanks3x3(actionId, crafts));
                return true;
            case "minecraft:stick":
                mc.execute(() -> craftSticks3x3(actionId, crafts));
                return true;
            default:
                // Unknown 3x3 recipe here; let caller report "not supported"
                return false;
        }
    }

    private static int toHandlerSlotIndex(int playerInvIndex) { return com.automc.modcore.UiSlots.toHandlerSlotIndex(playerInvIndex); }
    private static void click(int slot, int button, SlotActionType type) { com.automc.modcore.UiSlots.click(slot, button, type); }

    private static int findFirstMatching(PlayerInventory inv, java.util.function.Predicate<String> idPredicate) {
        for (int i = 0; i < inv.size(); i++) {
            ItemStack s = inv.getStack(i);
            if (s == null || s.isEmpty()) continue;
            String iid = Registries.ITEM.getId(s.getItem()).toString();
            if (idPredicate.test(iid)) return i;
        }
        return -1;
    }

    private static void craftWoodenPickaxe(String actionId, int crafts) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return;
        PlayerInventory inv = mc.player.getInventory();
        int made = 0;
        for (int i = 0; i < crafts; i++) {
            // Need 3 planks and 2 sticks
            int srcPlanks = findFirstMatching(inv, iid -> iid.endsWith("_planks"));
            int srcSticks = findFirstMatching(inv, iid -> iid.equals("minecraft:stick"));
            if (srcPlanks < 0 || srcSticks < 0) break;
            int planksSlot = toHandlerSlotIndex(srcPlanks);
            int sticksSlot = toHandlerSlotIndex(srcSticks);

            // Place planks into 3x3 slots: 1,2,3 (top row)
            click(planksSlot, 0, SlotActionType.PICKUP);
            click(1, 1, SlotActionType.PICKUP);
            click(2, 1, SlotActionType.PICKUP);
            click(3, 1, SlotActionType.PICKUP);
            click(planksSlot, 0, SlotActionType.PICKUP);

            // Place sticks into 3x3 slots: 5 (middle center), 8 (bottom center)
            click(sticksSlot, 0, SlotActionType.PICKUP);
            click(5, 1, SlotActionType.PICKUP);
            click(8, 1, SlotActionType.PICKUP);
            click(sticksSlot, 0, SlotActionType.PICKUP);

            // Shift-click result from slot 0
            click(0, 0, SlotActionType.QUICK_MOVE);
            made++;
        }
        if (made > 0) {
            com.automc.modcore.ActionExecutor.sendProgress(actionId, "ok", "crafted wooden_pickaxe x" + made);
        } else {
            com.automc.modcore.ActionExecutor.sendProgress(actionId, "fail", "missing inputs: planks or sticks");
        }
    }

    private static void craftPlanks3x3(String actionId, int crafts) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return;
        PlayerInventory inv = mc.player.getInventory();
        int made = 0;
        for (int i = 0; i < crafts; i++) {
            int srcLog = findFirstMatching(inv, iid -> iid.endsWith("_log") || iid.endsWith("_stem"));
            if (srcLog < 0) break;
            int srcSlot = toHandlerSlotIndex(srcLog);
            // Place one log into slot 1 (top-left)
            click(srcSlot, 0, SlotActionType.PICKUP);
            click(1, 1, SlotActionType.PICKUP);
            click(srcSlot, 0, SlotActionType.PICKUP);
            // Shift-click result (planks)
            click(0, 0, SlotActionType.QUICK_MOVE);
            made++;
        }
        if (made > 0) {
            com.automc.modcore.ActionExecutor.sendProgress(actionId, "ok", "crafted oak_planks x" + made);
        } else {
            com.automc.modcore.ActionExecutor.sendProgress(actionId, "fail", "missing input: log");
        }
    }

    private static void craftSticks3x3(String actionId, int crafts) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return;
        PlayerInventory inv = mc.player.getInventory();
        int made = 0;
        for (int i = 0; i < crafts; i++) {
            int srcPlanks = findFirstMatching(inv, iid -> iid.endsWith("_planks"));
            if (srcPlanks < 0) break;
            int srcSlot = toHandlerSlotIndex(srcPlanks);
            // Place planks into center column (slots 5 and 8)
            click(srcSlot, 0, SlotActionType.PICKUP);
            click(5, 1, SlotActionType.PICKUP);
            click(8, 1, SlotActionType.PICKUP);
            click(srcSlot, 0, SlotActionType.PICKUP);
            // Shift-click result (sticks)
            click(0, 0, SlotActionType.QUICK_MOVE);
            made++;
        }
        if (made > 0) {
            com.automc.modcore.ActionExecutor.sendProgress(actionId, "ok", "crafted stick x" + made);
        } else {
            com.automc.modcore.ActionExecutor.sendProgress(actionId, "fail", "missing input: planks");
        }
    }
}


