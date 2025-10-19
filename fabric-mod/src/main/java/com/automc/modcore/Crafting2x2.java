/**
 * AutoMinecraft 2x2 crafting helpers (v0 stubs).
 *
 * Purpose: Handle a minimal set of 2x2 recipes without requiring a crafting
 * table (planks, sticks, crafting_table). Currently acknowledges with
 * informative 'skipped' notes until UI interactions are implemented.
 *
 * Engineering notes: Use correct vanilla item ids (e.g., minecraft:oak_log
 * or tags) when implementing. Keep inventory checks cheap.
 */
package com.automc.modcore;

import net.minecraft.client.MinecraftClient;
import net.minecraft.entity.player.PlayerInventory;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.util.Identifier;

final class Crafting2x2 {
    private Crafting2x2() {}

    static boolean tryCraft(String actionId, String recipeId, int count) {
        if (recipeId == null || recipeId.isEmpty()) return false;
        switch (recipeId) {
            case "minecraft:planks":
                return requireInputs(actionId, new String[]{"minecraft:oak_log"}, new String[]{"log"}, "planks");
            case "minecraft:stick":
                return requireInputs(actionId, new String[]{"minecraft:planks"}, new String[]{"planks"}, "stick");
            case "minecraft:crafting_table":
                return requireInputs(actionId, new String[]{"minecraft:planks"}, new String[]{"planks"}, "crafting_table");
            default:
                ActionExecutor.sendProgress(actionId, "skipped", "unknown 2x2 recipe: " + recipeId);
                return true;
        }
    }

    private static boolean requireInputs(String actionId, String[] candidateIds, String[] missingNames, String recipeName) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null) return false;
        PlayerInventory inv = mc.player.getInventory();
        for (int i = 0; i < candidateIds.length; i++) {
            Item item = resolve(candidateIds[i]);
            if (item == null) continue;
            if (findFirst(inv, item) >= 0) {
                ActionExecutor.sendProgress(actionId, "skipped", "2x2 craft not implemented yet: " + recipeName);
                return true;
            }
        }
        String missing = missingNames.length > 0 ? missingNames[0] : "input";
        ActionExecutor.sendProgress(actionId, "fail", "missing input: " + missing);
        return true;
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
}
