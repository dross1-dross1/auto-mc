package com.automc.modcore.inventory;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.automc.modcore.Protocol;
import com.automc.modcore.WebSocketClientManager;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.screen.v1.ScreenEvents;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.ingame.HandledScreen;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.screen.ScreenHandler;
import net.minecraft.screen.slot.Slot;
import net.minecraft.util.math.BlockPos;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.HashMap;
import java.util.Map;

public final class InventoryWatcher {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.InvWatch");
    private static boolean registered = false;
    private static Map<Integer, Snapshot> lastSnapshot = new HashMap<>();

    private InventoryWatcher() {}

    public static void register() {
        if (registered) return;
        registered = true;

        ScreenEvents.AFTER_INIT.register((client, screen, scaledWidth, scaledHeight) -> {
            tryEmitSnapshot(client);
            lastDiffSendMs = 0L;
        });

        ClientTickEvents.END_CLIENT_TICK.register(InventoryWatcher::tryEmitDiff);
    }

    private static void tryEmitSnapshot(MinecraftClient mc) {
        if (mc == null || mc.player == null) return;
        if (!(mc.currentScreen instanceof HandledScreen<?> hs)) return;
        ScreenHandler h = hs.getScreenHandler();
        Snapshot snap = buildSnapshot(mc.player, h);
        if (snap == null) return;
        lastSnapshot.put(h.syncId, snap);
        JsonObject msg = new JsonObject();
        msg.addProperty("type", Protocol.TYPE_INVENTORY_SNAPSHOT);
        msg.addProperty("player_uuid", WebSocketClientManager.getInstance().getPlayerId());
        msg.add("container", snap.toJson());
        WebSocketClientManager.getInstance().sendJson(msg);
    }

    private static long lastDiffSendMs = 0L;

    private static void tryEmitDiff(MinecraftClient mc) {
        if (mc == null || mc.player == null) return;
        // Skip until runtime settings are applied to avoid throwing on missing debounce value
        if (!WebSocketClientManager.getInstance().areSettingsApplied()) return;
        if (!(mc.currentScreen instanceof HandledScreen<?> hs)) return;
        long nowMs = System.currentTimeMillis();
        int debounce = WebSocketClientManager.getInstance().getInventoryDiffDebounceMs();
        if ((nowMs - lastDiffSendMs) < debounce) return;
        ScreenHandler h = hs.getScreenHandler();
        Snapshot prev = lastSnapshot.get(h.syncId);
        Snapshot snap = buildSnapshot(mc.player, h);
        if (snap == null) return;
        if (prev == null) { lastSnapshot.put(h.syncId, snap); return; }
        if (prev.version == snap.version && prev.hash.equals(snap.hash)) return;
        JsonObject diff = new JsonObject();
        diff.addProperty("type", Protocol.TYPE_INVENTORY_DIFF);
        diff.addProperty("player_uuid", WebSocketClientManager.getInstance().getPlayerId());
        JsonObject key = new JsonObject();
        key.addProperty("dim", snap.dim);
        JsonArray pos = new JsonArray();
        pos.add(snap.pos[0]); pos.add(snap.pos[1]); pos.add(snap.pos[2]);
        key.add("pos", pos);
        diff.add("container_key", key);
        diff.addProperty("from_version", prev.version);
        diff.addProperty("to_version", snap.version);
        JsonArray adds = new JsonArray();
        JsonArray removes = new JsonArray();
        for (Map.Entry<Integer, SlotEntry> e : snap.slots.entrySet()) {
            int idx = e.getKey();
            SlotEntry cur = e.getValue();
            SlotEntry old = prev.slots.get(idx);
            if (old == null) {
                JsonObject add = new JsonObject();
                add.addProperty("slot", idx);
                add.addProperty("id", cur.id);
                add.addProperty("count", cur.count);
                adds.add(add);
            } else if (!old.id.equals(cur.id) || old.count != cur.count) {
                int delta = cur.count - old.count;
                JsonObject obj = new JsonObject();
                obj.addProperty("slot", idx);
                obj.addProperty("id", delta >= 0 ? cur.id : old.id);
                obj.addProperty("count", Math.abs(delta));
                if (delta >= 0) adds.add(obj); else removes.add(obj);
            }
        }
        for (Map.Entry<Integer, SlotEntry> e : prev.slots.entrySet()) {
            if (!snap.slots.containsKey(e.getKey())) {
                JsonObject r = new JsonObject();
                r.addProperty("slot", e.getKey());
                r.addProperty("id", e.getValue().id);
                r.addProperty("count", e.getValue().count);
                removes.add(r);
            }
        }
        diff.add("adds", adds);
        diff.add("removes", removes);
        diff.add("moves", new JsonArray());
        WebSocketClientManager.getInstance().sendJson(diff);
        lastDiffSendMs = nowMs;
        lastSnapshot.put(h.syncId, snap);
    }

    private static Snapshot buildSnapshot(ClientPlayerEntity player, ScreenHandler handler) {
        try {
            MinecraftClient mc = MinecraftClient.getInstance();
            if (mc == null || mc.world == null) return null;
            BlockPos pos = null;
            try {
                if (mc.crosshairTarget instanceof net.minecraft.util.hit.BlockHitResult bhr) {
                    pos = bhr.getBlockPos();
                }
            } catch (Throwable ignored) {}
            if (pos == null) return null;
            int[] p = new int[]{pos.getX(), pos.getY(), pos.getZ()};
            String dim = mc.world.getRegistryKey().getValue().toString();
            Map<Integer, SlotEntry> slots = new HashMap<>();
            int version = (int)(System.currentTimeMillis() / 1000);
            for (int i = 0; i < handler.slots.size(); i++) {
                Slot s = handler.slots.get(i);
                ItemStack st = s.getStack();
                if (st == null || st.isEmpty()) continue;
                String id = Registries.ITEM.getId(st.getItem()).toString();
                int cnt = st.getCount();
                slots.put(i, new SlotEntry(id, cnt));
            }
            String hash = Integer.toHexString(slots.hashCode() ^ version ^ dim.hashCode());
            String containerType = handler.getClass().getSimpleName();
            if (!isContainerType(containerType)) return null;
            return new Snapshot(dim, p, containerType, version, hash, slots);
        } catch (Throwable t) {
            LOGGER.debug("snapshot error: {}", t.toString());
            return null;
        }
    }

    private static boolean isContainerType(String name) {
        if (name == null) return false;
        String n = name.toLowerCase();
        return n.contains("chest") || n.contains("furnace") || n.contains("smoker") || n.contains("blastfurnace") || n.contains("ender") || n.contains("barrel") || n.contains("shulker");
    }

    private static final class SlotEntry {
        final String id; final int count;
        SlotEntry(String id, int count) { this.id = id; this.count = count; }
    }

    private static final class Snapshot {
        final String dim;
        final int[] pos;
        final String containerType;
        final int version;
        final String hash;
        final Map<Integer, SlotEntry> slots;

        Snapshot(String dim, int[] pos, String containerType, int version, String hash, Map<Integer, SlotEntry> slots) {
            this.dim = dim; this.pos = pos; this.containerType = containerType; this.version = version; this.hash = hash; this.slots = slots;
        }

        JsonObject toJson() {
            JsonObject c = new JsonObject();
            c.addProperty("dim", dim);
            JsonArray p = new JsonArray(); p.add(pos[0]); p.add(pos[1]); p.add(pos[2]);
            c.add("pos", p);
            c.addProperty("container_type", containerType);
            c.addProperty("version", version);
            c.addProperty("hash", hash);
            c.addProperty("ts_iso", java.time.Instant.now().toString());
            JsonArray arr = new JsonArray();
            for (Map.Entry<Integer, SlotEntry> e : slots.entrySet()) {
                JsonObject s = new JsonObject();
                s.addProperty("slot", e.getKey());
                s.addProperty("id", e.getValue().id);
                s.addProperty("count", e.getValue().count);
                arr.add(s);
            }
            c.add("slots", arr);
            return c;
        }
    }
}


