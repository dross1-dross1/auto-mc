/**
 * AutoMinecraft 2x2 crafting helpers.
 *
 * Purpose: Handle a minimal set of 2x2 recipes without requiring a crafting
 * table (planks, sticks, crafting_table) by simulating inventory slot clicks
 * on the client thread.
 *
 * Engineering notes: Avoid heavy logic; prefer single-item right-click placement
 * into 2x2 inputs and shift-click result to inventory. Works with generic ids by
 * matching actual items (e.g., *_log, *_planks). Keep operations on the MC thread.
 */
package com.automc.modcore;

import net.minecraft.client.MinecraftClient;
import net.minecraft.entity.player.PlayerInventory;
import net.minecraft.client.gui.screen.ingame.InventoryScreen;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.screen.slot.SlotActionType;
import net.minecraft.util.Identifier;

final class Crafting2x2 {
    private Crafting2x2() {}

    static boolean tryCraft(String actionId, String recipeId, int count) {
        if (recipeId == null || recipeId.isEmpty()) return false;
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return false;
        final int crafts = Math.max(1, count);

        switch (recipeId) {
            case "minecraft:oak_planks":
                mc.execute(() -> craftPlanks(actionId, crafts));
                return true;
            case "minecraft:stick":
                mc.execute(() -> craftSticks(actionId, crafts));
                return true;
            case "minecraft:crafting_table":
                mc.execute(() -> craftTable(actionId, crafts));
                return true;
            default:
                ActionExecutor.sendProgress(actionId, "skipped", "unknown 2x2 recipe: " + recipeId);
                return true;
        }
    }

    private static Item resolve(String id) {
        try {
            Identifier ident = Identifier.tryParse(id);
            if (ident == null) return null;
            return Registries.ITEM.get(ident);
        } catch (Exception ignore) {
            return null;
        }
    }

    private static int findFirst(PlayerInventory inv, Item item) {
        for (int i = 0; i < inv.size(); i++) {
            ItemStack s = inv.getStack(i);
            if (!s.isEmpty() && s.getItem() == item) return i;
        }
        return -1;
    }

    private static int findFirstMatching(PlayerInventory inv, java.util.function.Predicate<String> idPredicate) {
        for (int i = 0; i < inv.size(); i++) {
            ItemStack s = inv.getStack(i);
            if (s == null || s.isEmpty()) continue;
            String iid = Registries.ITEM.getId(s.getItem()).toString();
            if (idPredicate.test(iid)) return i;
        }
        return -1;
    }

    private static int toHandlerSlotIndex(int playerInvIndex) { return UiSlots.toHandlerSlotIndex(playerInvIndex); }
    private static void click(int slot, int button, SlotActionType type) { UiSlots.click(slot, button, type); }

    private static void craftPlanks(String actionId, int crafts) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return;
        ensureInventoryScreenOpen(mc);
        PlayerInventory inv = mc.player.getInventory();
        int made = 0;
        for (int i = 0; i < crafts; i++) {
            int src = findFirstMatching(inv, iid -> iid.endsWith("_log") || iid.endsWith("_stem"));
            if (src < 0) break;
            int srcSlot = toHandlerSlotIndex(src);
            // Pick up source stack (left click)
            click(srcSlot, 0, SlotActionType.PICKUP);
            // Place one into craft input slot 1 via right-click
            click(1, 1, SlotActionType.PICKUP);
            // Return remainder to source slot (left click) so cursor is empty
            click(srcSlot, 0, SlotActionType.PICKUP);
            // Shift-click result to inventory (cursor empty)
            click(0, 0, SlotActionType.QUICK_MOVE);
            made++;
        }
        if (made > 0) {
            ActionExecutor.sendProgress(actionId, "ok", "crafted oak_planks x" + made);
        } else {
            ActionExecutor.sendProgress(actionId, "fail", "missing input: log");
        }
    }

    private static void craftSticks(String actionId, int crafts) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return;
        ensureInventoryScreenOpen(mc);
        PlayerInventory inv = mc.player.getInventory();
        int made = 0;
        for (int i = 0; i < crafts; i++) {
            int src = findFirstMatching(inv, iid -> iid.endsWith("_planks"));
            if (src < 0) break;
            int srcSlot = toHandlerSlotIndex(src);
            // Pick up planks stack
            click(srcSlot, 0, SlotActionType.PICKUP);
            // Place one plank into slot 1 (top-left) and one into slot 3 (bottom-left)
            click(1, 1, SlotActionType.PICKUP);
            click(3, 1, SlotActionType.PICKUP);
            // Return remainder to source slot
            click(srcSlot, 0, SlotActionType.PICKUP);
            // Shift-click result (sticks)
            click(0, 0, SlotActionType.QUICK_MOVE);
            made++;
        }
        if (made > 0) {
            ActionExecutor.sendProgress(actionId, "ok", "crafted stick x" + made);
        } else {
            ActionExecutor.sendProgress(actionId, "fail", "missing input: planks");
        }
    }

    private static void craftTable(String actionId, int crafts) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.interactionManager == null) return;
        ensureInventoryScreenOpen(mc);
        PlayerInventory inv = mc.player.getInventory();
        int made = 0;
        for (int i = 0; i < crafts; i++) {
            int src = findFirstMatching(inv, iid -> iid.endsWith("_planks"));
            if (src < 0) break;
            int srcSlot = toHandlerSlotIndex(src);
            // Pick up planks stack
            click(srcSlot, 0, SlotActionType.PICKUP);
            // Place one plank into each of 4 craft input slots: 1,2,3,4
            click(1, 1, SlotActionType.PICKUP);
            click(2, 1, SlotActionType.PICKUP);
            click(3, 1, SlotActionType.PICKUP);
            click(4, 1, SlotActionType.PICKUP);
            // Return remainder to source slot
            click(srcSlot, 0, SlotActionType.PICKUP);
            // Shift-click result (crafting table)
            click(0, 0, SlotActionType.QUICK_MOVE);
            made++;
        }
        if (made > 0) {
            ActionExecutor.sendProgress(actionId, "ok", "crafted crafting_table x" + made);
        } else {
            ActionExecutor.sendProgress(actionId, "fail", "missing input: planks");
        }
    }

    private static void ensureInventoryScreenOpen(MinecraftClient mc) {
        try {
            if (!(mc.currentScreen instanceof net.minecraft.client.gui.screen.ingame.InventoryScreen)) {
                mc.setScreen(new InventoryScreen(mc.player));
            }
        } catch (Throwable ignored) {}
    }
}
