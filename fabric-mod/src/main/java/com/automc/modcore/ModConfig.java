/**
 * AutoMinecraft mod configuration (removed local defaults).
 *
 * Runtime settings are applied exclusively via backend settings_update after !connect.
 */
package com.automc.modcore;

public final class ModConfig {

    private ModConfig() {}

    public static ModConfig load() { throw new IllegalStateException("ModConfig defaults removed; use settings_update"); }
}
