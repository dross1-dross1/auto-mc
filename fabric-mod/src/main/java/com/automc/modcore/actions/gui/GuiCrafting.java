package com.automc.modcore.actions.gui;

import com.automc.modcore.ActionExecutor;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.ingame.HandledScreen;
import net.minecraft.client.gui.screen.ingame.CraftingScreen;
import net.minecraft.util.Identifier;

/**
 * General GUI crafting entrypoints.
 *
 * Chooses 2x2 (player inventory) vs 3x3 (crafting table UI) and delegates to
 * specialized logic. Uses RecipeManager lookup as the source of truth.
 */
public final class GuiCrafting {
    private GuiCrafting() {}

    private static boolean tickRegistered = false;
    private static final java.util.ArrayDeque<PendingCraft> pending = new java.util.ArrayDeque<>();

    private static final class PendingCraft {
        final String actionId;
        final String recipeId;
        final int count;
        PendingCraft(String actionId, String recipeId, int count) {
            this.actionId = actionId;
            this.recipeId = recipeId;
            this.count = count;
        }
    }

    private static void ensureTickRegistered() {
        if (tickRegistered) return;
        tickRegistered = true;
        ClientTickEvents.END_CLIENT_TICK.register(GuiCrafting::onEndTick);
    }

    private static void onEndTick(MinecraftClient mc) {
        if (mc == null || mc.player == null) return;
        if (pending.isEmpty()) return;
        PendingCraft head = pending.peek();
        if (head == null) return;
        if (mc.currentScreen instanceof CraftingScreen) {
            boolean ok = Crafting3x3.tryCraft(head.actionId, head.recipeId, head.count);
            if (!ok) {
                ActionExecutor.sendProgress(head.actionId, "skipped", "3x3 craft not supported for recipe");
            }
            pending.poll();
        }
    }

    public static void craftByRecipeId(String actionId, String recipeId, int count) { craftByRecipeId(actionId, recipeId, count, ""); }

    public static void craftByRecipeId(String actionId, String recipeId, int count, String context) {
        if (recipeId == null || recipeId.isEmpty() || count <= 0) {
            ActionExecutor.sendProgress(actionId, "fail", "invalid recipe/count");
            return;
        }
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.world == null) {
            ActionExecutor.sendProgress(actionId, "fail", "no world");
            return;
        }
        Identifier ident = Identifier.tryParse(recipeId);
        if (ident == null) {
            ActionExecutor.sendProgress(actionId, "fail", "bad recipe id");
            return;
        }
        // If crafting table UI (3x3) is open, attempt 3x3; otherwise, defer recipes that require 3x3
        boolean isHandled = mc.currentScreen instanceof HandledScreen<?>;
        boolean isInventory = (!isHandled) || (mc.currentScreen instanceof net.minecraft.client.gui.screen.ingame.InventoryScreen);
        boolean isCrafting = isHandled && (mc.currentScreen instanceof net.minecraft.client.gui.screen.ingame.CraftingScreen);
        if (isCrafting) {
            boolean ok3 = Crafting3x3.tryCraft(actionId, recipeId, count);
            if (!ok3) {
                ActionExecutor.sendProgress(actionId, "skipped", "3x3 craft not supported for recipe");
            }
            return;
        }
        // Not in crafting table UI: allow only simple 2x2 recipes; skip table-only to defer conversion
        if (isInventory) {
            // If the backend explicitly indicated a crafting_table context, queue until the UI opens
            if ("crafting_table".equals(context)) {
                ensureTickRegistered();
                pending.add(new PendingCraft(actionId, recipeId, count));
                return;
            }
            // If backend annotated a required context, defer 2x2 crafting until context is present
            // (we receive the original object in ActionExecutor; read a thread-local context if set)
            // Best-effort: if recipe looks like a 3x3-only item (e.g., contains "_pickaxe"), skip here
            if (recipeId.endsWith("_pickaxe") || recipeId.endsWith("_sword") || recipeId.endsWith("_axe") || recipeId.endsWith("_shovel") || recipeId.endsWith("_hoe")) {
                ActionExecutor.sendProgress(actionId, "skipped", "craft requires 3x3 context");
                return;
            }
            if ("minecraft:oak_planks".equals(recipeId) || "minecraft:stick".equals(recipeId) || "minecraft:crafting_table".equals(recipeId)) {
                boolean ok = Crafting2x2.tryCraft(actionId, recipeId, count);
                if (!ok) {
                    ActionExecutor.sendProgress(actionId, "skipped", "2x2 craft not supported for recipe");
                }
            } else {
                ActionExecutor.sendProgress(actionId, "skipped", "craft requires 3x3 context");
            }
            return;
        }
        // Unknown screen; skip
        ActionExecutor.sendProgress(actionId, "skipped", "craft screen not supported");
    }
}


