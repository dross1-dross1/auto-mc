/**
 * AutoMinecraft ensure-context helpers.
 *
 * Purpose: Satisfy context requirements like `crafting_table_nearby` and
 * `furnace_nearby` by locating and interacting with nearby blocks. For v0,
 * this scans within a small radius and opens the block if found; placement and
 * navigation fallbacks are planned next.
 */
package com.automc.modcore;

import net.minecraft.block.Block;
import net.minecraft.block.Blocks;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientPlayerInteractionManager;
import net.minecraft.entity.player.PlayerInventory;
import net.minecraft.item.ItemStack;
import net.minecraft.item.Items;
import net.minecraft.util.Hand;
import net.minecraft.util.hit.BlockHitResult;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.Direction;
import net.minecraft.util.math.Vec3d;

final class EnsureContext {
    private static final int NEAR_RADIUS = 8; // blocks
    private EnsureContext() {}

    static void ensureCraftingTableNearby(String actionId) {
        if (interactWithNearbyBlock(actionId, Blocks.CRAFTING_TABLE)) return;
        // Try to place from hotbar
        BlockPos placed = placeBlockFromHotbar(Items.CRAFTING_TABLE);
        if (placed != null) {
            interactSpecific(actionId, placed);
            return;
        }
        ActionExecutor.sendProgress(actionId, "fail", "crafting_table not found nearby");
    }

    static void ensureFurnaceNearby(String actionId) {
        if (interactWithNearbyBlock(actionId, Blocks.FURNACE)) return;
        BlockPos placed = placeBlockFromHotbar(Items.FURNACE);
        if (placed != null) {
            interactSpecific(actionId, placed);
            return;
        }
        ActionExecutor.sendProgress(actionId, "fail", "furnace not found nearby");
    }

    private static boolean interactWithNearbyBlock(String actionId, Block target) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.world == null) return false;
        BlockPos playerPos = mc.player.getBlockPos();
        BlockPos best = null;
        double bestDist = Double.MAX_VALUE;
        for (int dx = -NEAR_RADIUS; dx <= NEAR_RADIUS; dx++) {
            for (int dy = -1; dy <= 2; dy++) {
                for (int dz = -NEAR_RADIUS; dz <= NEAR_RADIUS; dz++) {
                    BlockPos pos = playerPos.add(dx, dy, dz);
                    if (mc.world.getBlockState(pos).isOf(target)) {
                        double d = pos.getSquaredDistance(playerPos);
                        if (d < bestDist) {
                            bestDist = d;
                            best = pos;
                        }
                    }
                }
            }
        }
        if (best == null) return false;

        final BlockPos usePos = best;
        // Interact on client thread
        mc.execute(() -> {
            try {
                ClientPlayerInteractionManager im = mc.interactionManager;
                if (im == null) return;
                Vec3d hit = Vec3d.ofCenter(usePos);
                BlockHitResult bhr = new BlockHitResult(hit, Direction.UP, usePos, false);
                im.interactBlock(mc.player, Hand.MAIN_HAND, bhr);
                ActionExecutor.sendProgress(actionId, "ok", null);
            } catch (Throwable t) {
                ActionExecutor.sendProgress(actionId, "fail", "interact error: " + t.getClass().getSimpleName());
            }
        });
        return true;
    }

    private static void interactSpecific(String actionId, BlockPos usePos) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null) return;
        mc.execute(() -> {
            try {
                ClientPlayerInteractionManager im = mc.interactionManager;
                if (im == null) return;
                Vec3d hit = Vec3d.ofCenter(usePos);
                BlockHitResult bhr = new BlockHitResult(hit, Direction.UP, usePos, false);
                im.interactBlock(mc.player, Hand.MAIN_HAND, bhr);
                ActionExecutor.sendProgress(actionId, "ok", null);
            } catch (Throwable t) {
                ActionExecutor.sendProgress(actionId, "fail", "interact error: " + t.getClass().getSimpleName());
            }
        });
    }

    private static BlockPos placeBlockFromHotbar(net.minecraft.item.Item targetItem) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.player == null || mc.world == null) return null;
        PlayerInventory inv = mc.player.getInventory();
        int hotbarSlot = -1;
        for (int i = 0; i < 9; i++) {
            ItemStack s = inv.getStack(i);
            if (!s.isEmpty() && s.getItem() == targetItem) {
                hotbarSlot = i;
                break;
            }
        }
        if (hotbarSlot < 0) return null; // not in hotbar

        // Choose a placement spot in front of the player
        BlockPos playerPos = mc.player.getBlockPos();
        Direction facing = mc.player.getHorizontalFacing();
        BlockPos below = playerPos.offset(facing);
        BlockPos placePos = below.up();
        // Adjust if obstructed
        if (!mc.world.getBlockState(placePos).isAir()) {
            placePos = playerPos.up();
            below = playerPos;
        }
        if (!mc.world.getBlockState(placePos).isAir()) return null;

        final int sel = hotbarSlot;
        final BlockPos clickPos = below;
        final BlockPos expected = placePos;
        mc.execute(() -> {
            try {
                inv.setSelectedSlot(sel);
                ClientPlayerInteractionManager im = mc.interactionManager;
                if (im == null) return;
                Vec3d hit = Vec3d.ofCenter(clickPos);
                BlockHitResult bhr = new BlockHitResult(hit, Direction.UP, clickPos, false);
                im.interactBlock(mc.player, Hand.MAIN_HAND, bhr);
            } catch (Throwable ignored) {}
        });
        return expected;
    }
}
