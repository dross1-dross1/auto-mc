/**
 * AutoMinecraft chat interceptor.
 *
 * Purpose: Capture client chat messages starting with '!' and forward them to the backend
 * as structured command JSON, while preventing them from broadcasting to public chat.
 *
 * How: Registers a Fabric ALLOW_CHAT listener; on '!'-prefixed input, constructs a JSON
 * payload and sends it via the shared WebSocket manager, returning false to swallow.
 *
 * Engineering notes: Avoid disk IO on hot paths; reuse player id from the active
 * WebSocket manager instead of reloading config for each message.
 */
package com.automc.modcore;

import com.google.gson.JsonObject;
import net.fabricmc.fabric.api.client.message.v1.ClientSendMessageEvents;

public final class ChatInterceptor {
    private ChatInterceptor() {}

    public static void register() {
        ClientSendMessageEvents.ALLOW_CHAT.register((message) -> {
            String prefix = WebSocketClientManager.getInstance().getCommandPrefixOrNull();
            if (message == null) return true;
            // Bootstrap: allow only !connect when disconnected
            if (!WebSocketClientManager.getInstance().isConnected()) {
                if (message.startsWith("!connect ")) {
                    String[] parts = message.substring("!connect ".length()).trim().split("\\s+", 2);
                    if (parts.length == 2) {
                        String addr = parts[0];
                        String password = parts[1];
                        WebSocketClientManager.getInstance().connect("ws://" + addr, password);
                        hud("Connecting to " + addr + "...");
                    } else {
                        hud("Usage: !connect <ip:port> <password>");
                    }
                    return false;
                } else if (message.startsWith("!")) {
                    hud("A backend connection is required. Use !connect <ip:port> <password>.");
                    return false;
                }
                return true;
            }
            // Connected: block !connect and forward other commands with configured prefix
            if (message.startsWith("!connect")) {
                hud("Already connected; use !disconnect first.");
                return false;
            }
            if (message.startsWith("!disconnect")) {
                WebSocketClientManager.getInstance().disconnect();
                hud("Disconnected.");
                return false;
            }
            boolean isCommand = (message.startsWith("!")) || (prefix != null && !prefix.isEmpty() && message.startsWith(prefix));
            if (isCommand) {
                // Always swallow and forward commands; never send to public chat
                JsonObject obj = new JsonObject();
                obj.addProperty("type", Protocol.TYPE_COMMAND);
                obj.addProperty("request_id", java.util.UUID.randomUUID().toString());
                // Normalize nested echo payloads client-side for UX parity with backend
                String textOut = message;
                if (textOut.startsWith("!echo ")) {
                    String payload = textOut.substring("!echo ".length()).trim();
                    while (payload.startsWith("!echo ")) payload = payload.substring("!echo ".length()).trim();
                    textOut = "!echo " + payload;
                }
                obj.addProperty("text", textOut);
                obj.addProperty("player_uuid", WebSocketClientManager.getInstance().getPlayerId());
                WebSocketClientManager.getInstance().sendJson(obj);
                if (WebSocketClientManager.getInstance().getAckOnCommandEnabled()) {
                    hud(textOut);
                }
                return false;
            }
            return true;
        });
    }

    public static void hud(String text) {
        net.minecraft.client.MinecraftClient mc = net.minecraft.client.MinecraftClient.getInstance();
        if (mc == null) return;
        mc.execute(() -> {
            if (mc.inGameHud != null) {
                String pfx = WebSocketClientManager.getInstance().getFeedbackPrefixOrEmpty();
                String src = text == null ? "" : text;
                boolean hasPrefix = pfx != null && !pfx.isEmpty() && src.startsWith(pfx);
                boolean needsPrefix = pfx != null && !pfx.isEmpty() && !hasPrefix;

                net.minecraft.text.MutableText msg = net.minecraft.text.Text.empty();
                if (hasPrefix) {
                    String rest = src.substring(pfx.length());
                    appendColoredPrefix(msg, pfx);
                    msg.append(net.minecraft.text.Text.literal(rest));
                } else if (needsPrefix) {
                    appendColoredPrefix(msg, pfx);
                    msg.append(net.minecraft.text.Text.literal(src));
                } else {
                    msg.append(net.minecraft.text.Text.literal(src));
                }
                mc.inGameHud.getChatHud().addMessage(msg);
            }
        });
    }

    private static void appendColoredPrefix(net.minecraft.text.MutableText dst, String pfx) {
        String base = pfx == null ? "" : pfx;
        boolean trailingSpace = base.endsWith(" ");
        if (trailingSpace) base = base.substring(0, base.length() - 1);
        if (base.startsWith("[") && base.endsWith("]") && base.length() >= 2) {
            String inner = base.substring(1, base.length() - 1);
            net.minecraft.util.Formatting bracketFmt = resolveFormatting(WebSocketClientManager.getInstance().getFeedbackBracketColorOrNull(), net.minecraft.util.Formatting.GRAY);
            net.minecraft.util.Formatting innerFmt = resolveFormatting(WebSocketClientManager.getInstance().getFeedbackInnerColorOrNull(), net.minecraft.util.Formatting.DARK_GREEN);
            dst.append(net.minecraft.text.Text.literal("[").formatted(bracketFmt));
            if (!inner.isEmpty()) dst.append(net.minecraft.text.Text.literal(inner).formatted(innerFmt));
            dst.append(net.minecraft.text.Text.literal("]").formatted(bracketFmt));
            if (trailingSpace) dst.append(net.minecraft.text.Text.literal(" "));
        } else {
            net.minecraft.util.Formatting bracketFmt = resolveFormatting(WebSocketClientManager.getInstance().getFeedbackBracketColorOrNull(), net.minecraft.util.Formatting.GRAY);
            dst.append(net.minecraft.text.Text.literal(base).formatted(bracketFmt));
            if (trailingSpace) dst.append(net.minecraft.text.Text.literal(" "));
        }
    }

    private static net.minecraft.util.Formatting resolveFormatting(String nameOrNull, net.minecraft.util.Formatting fallback) {
        if (nameOrNull == null || nameOrNull.isEmpty()) return fallback;
        try {
            return net.minecraft.util.Formatting.valueOf(nameOrNull.trim().toUpperCase());
        } catch (IllegalArgumentException ex) {
            return fallback;
        }
    }
}
