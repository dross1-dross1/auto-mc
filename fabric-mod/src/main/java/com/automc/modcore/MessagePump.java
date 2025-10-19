/**
 * AutoMinecraft inbound message pump.
 *
 * Purpose: Transfer WebSocket IO-thread messages onto the Minecraft client
 * thread by queuing and draining a bounded batch each tick.
 *
 * How: Registers an END_CLIENT_TICK callback, polls a concurrent queue up to
 * a fixed limit, and routes each message through the MessageRouter.
 *
 * Engineering notes: Apply backpressure via per-tick and queue-size caps to
 * avoid stalls and runaway memory.
 */
package com.automc.modcore;

import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedQueue;

final class MessagePump {
    private static final Logger LOGGER = LogManager.getLogger("AutoMinecraft.Pump");
    private static final ConcurrentLinkedQueue<String> QUEUE = new ConcurrentLinkedQueue<>();
    private static volatile boolean registered = false;

    private MessagePump() {}

    static void register() {
        if (registered) return;
        registered = true;
        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            // Drain up to a sane number per tick to avoid stalls
            List<String> batch = new ArrayList<>(32);
            for (int i = 0; i < 64; i++) {
                String msg = QUEUE.poll();
                if (msg == null) break;
                batch.add(msg);
            }
            for (String raw : batch) {
                try {
                    MessageRouter.onMessage(raw);
                } catch (Throwable t) {
                    LOGGER.warn("message handling error: {}", t.toString());
                }
            }
        });
    }

    static void enqueue(String raw) {
        // Drop if queue is too large to avoid runaway memory usage
        if (QUEUE.size() > 2048) {
            return;
        }
        QUEUE.offer(raw);
    }
}
